"""2026 EV/LA analysis: explicit complete cases, two held-out dates, no raw mutation.

Run with data/mlb/2026/.venv/Scripts/python.exe (packages captured in analysis/).
Stages: clean, fit, render, verify, all. No network access is used by this script.
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import os
import pickle
import platform
import re
import subprocess
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

# Keep native math thread counts bounded on a shared Windows workstation.
os.environ.setdefault('OMP_NUM_THREADS', '2')
os.environ.setdefault('OPENBLAS_NUM_THREADS', '2')
os.environ.setdefault('MKL_NUM_THREADS', '2')
os.environ.setdefault('MPLCONFIGDIR', str(Path(__file__).resolve().parents[1] / 'data' / 'mlb' / '2026' / '.matplotlib'))

import numpy as np
import pandas as pd
from scipy import sparse
from sklearn.exceptions import ConvergenceWarning
from sklearn.linear_model import LogisticRegression, Ridge
from sklearn.metrics import log_loss, mean_absolute_error, r2_score, roc_auc_score
from sklearn.preprocessing import SplineTransformer
from threadpoolctl import threadpool_limits
import warnings

ROOT = Path(__file__).resolve().parents[1] / 'data' / 'mlb' / '2026'
PROCESSED = ROOT / 'processed'
OUT = ROOT / 'analysis'
FIGURES = OUT / 'figures'
FEATURES = ['launch_speed', 'launch_angle']
CLASSES = ['non_hit', 'single', 'double', 'triple', 'home_run']
AIRBORNE = ['line_drive', 'fly_ball', 'popup']
FEET_TO_M = .3048
SEED = 20261011


def write_json(path: Path, obj):
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')


def read_json(path: Path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def filehash(path: Path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def clean():
    PROCESSED.mkdir(parents=True, exist_ok=True)
    OUT.mkdir(parents=True, exist_ok=True)
    inventory = ROOT / 'audit' / 'batted_ball_inventory.csv.gz'
    df = pd.read_csv(inventory, dtype={'game_date': str, 'game_pk': str,
                                     'at_bat_number': str, 'pitch_number': str},
                     keep_default_na=False)
    numeric = {}
    for column in (*FEATURES, 'hit_distance_sc'):
        numeric[column] = pd.to_numeric(df[column], errors='coerce')
    bunt = df['is_bunt_candidate'].astype(str).str.lower().eq('true')
    schedule = read_json(ROOT / 'raw' / 'schedule.json')
    completed = {str(g['gamePk']): g for day in schedule['dates'] for g in day['games']
                 if g['status']['detailedState'] in {'Final', 'Completed Early'}}
    games_by_date = {}
    for key, game in completed.items():
        games_by_date.setdefault(game['officialDate'], set()).add(key)
    dates = sorted(games_by_date)
    # User requested a date with many games around opening, rather than the 1-game opener.
    first = next(day for day in dates if len(games_by_date[day]) >= 10)
    last = dates[-1]
    assert first != last
    split = np.where(df['game_date'].eq(first), 'early_holdout',
                     np.where(df['game_date'].eq(last), 'final_holdout', 'development'))
    df['split'] = split
    outcome = df['events'].where(df['events'].isin(CLASSES[1:]), 'non_hit')
    result_present = df['events'].str.strip().ne('')
    probability_ok = (~bunt) & result_present & np.isfinite(numeric[FEATURES[0]]) & np.isfinite(numeric[FEATURES[1]])
    distance_ok = probability_ok & np.isfinite(numeric['hit_distance_sc'])
    df['outcome'] = outcome
    df['eligible_probability'] = probability_ok
    df['eligible_distance'] = distance_ok
    for column, values in numeric.items():
        df[column] = values
    # Original values remain in raw/inventory; derived files use numeric interpretation only.
    df.to_csv(PROCESSED / 'eligibility-inventory.csv.gz', index=False, compression='gzip')
    df.loc[probability_ok].to_csv(PROCESSED / 'probability.csv.gz', index=False, compression='gzip')
    df.loc[distance_ok].to_csv(PROCESSED / 'distance.csv.gz', index=False, compression='gzip')
    rejected = df.loc[~probability_ok | ~distance_ok].copy()
    reasons = []
    for row in rejected.itertuples():
        rs = []
        if str(row.is_bunt_candidate).lower() == 'true':
            rs.append('bunt_candidate')
        for column in (*FEATURES, 'hit_distance_sc'):
            if not np.isfinite(getattr(row, column)):
                rs.append(column + '_missing_or_invalid')
        if not row.events.strip():
            rs.append('outcome_missing')
        reasons.append('|'.join(rs))
    rejected['rejection_reasons'] = reasons
    rejected.to_csv(PROCESSED / 'rejected-inventory.csv.gz', index=False, compression='gzip')
    split_counts = []
    for label in ('development', 'early_holdout', 'final_holdout'):
        mask = df['split'].eq(label)
        split_counts.append({'split': label, 'date': first if label == 'early_holdout' else last if label == 'final_holdout' else 'all other regular-season dates',
                             'non_bunt': int((mask & ~bunt).sum()),
                             'probability': int((mask & probability_ok).sum()),
                             'distance': int((mask & distance_ok).sum()),
                             'airborne_distance': int((mask & distance_ok & df['bb_type'].isin(AIRBORNE)).sum()),
                             'games': int(df.loc[mask, 'game_pk'].nunique()),
                             'home_runs_eligible': int((mask & probability_ok & df['events'].eq('home_run')).sum())})
    policy = {'season': 2026, 'scope': 'regular-season type=X batted balls; exclude recorded bunt candidates',
              'source_inventory': str(inventory.relative_to(ROOT)), 'source_inventory_sha256': filehash(inventory),
              'source_manifest_sha256': filehash(ROOT / 'manifest.json'),
              'probability_required': FEATURES + ['events'], 'distance_required': FEATURES + ['events', 'hit_distance_sc'],
              'missing_treatment': 'exclude only from outputs requiring the missing value; no imputation',
              'zero_distance': 'retain', 'negative_launch_angles': 'retain',
              'outliers': 'no extra deletions; prior audit range flags were zero',
              'bunts': 'exclude original description-derived candidate flag; raw retained',
              'features_binned_for_fitting': False, 'holdout_selection': 'earliest completed regular-season date with at least 10 games; final official date',
              'reserved_dates': [first, last], 'prior_audit_reserved_dates': ['2026-03-25', '2026-09-27'],
              'raw_rows': len(df), 'bunt_candidates': int(bunt.sum()), 'non_bunt': int((~bunt).sum()),
              'probability_kept': int(probability_ok.sum()), 'distance_kept': int(distance_ok.sum()),
              'probability_missing_removed_non_bunt': int((~bunt & ~probability_ok).sum()),
              'distance_missing_removed_non_bunt': int((~bunt & ~distance_ok).sum()),
              'distance_only_missing_kept_for_probability': int((probability_ok & ~distance_ok).sum()),
              'splits': split_counts, 'created_at_utc': datetime.now(timezone.utc).isoformat()}
    write_json(PROCESSED / 'cleaning-policy.json', policy)
    write_json(PROCESSED / 'reserved-dates.json', {'game_date': [first, last],
               'overrides': 'original audit opening-day selection',
               'exclude_from': ['training', 'model selection', 'preprocessing fitting', 'calibration']})
    pd.DataFrame(split_counts).to_csv(PROCESSED / 'split-counts.csv', index=False, encoding='utf-8-sig')
    print('CLEANING', json.dumps(policy, ensure_ascii=False), flush=True)


class TensorSplines:
    """Continuous tensor-product cubic B-splines; no observation aggregation/binning."""
    def __init__(self, n_knots):
        self.n_knots = n_knots
        self.axes = [SplineTransformer(n_knots=n_knots, degree=3, knots='uniform',
                                      include_bias=True, extrapolation='constant') for _ in range(2)]

    def fit(self, x):
        for j, axis in enumerate(self.axes):
            axis.fit(x[:, j:j + 1])
        return self

    def transform(self, x):
        chunks = []
        for start in range(0, len(x), 8000):
            xx = x[start:start + 8000]
            a, b = [axis.transform(xx[:, j:j + 1]) for j, axis in enumerate(self.axes)]
            chunks.append(sparse.csr_matrix((a[:, :, None] * b[:, None, :]).reshape(len(xx), -1)))
        return sparse.vstack(chunks, format='csr')


def class_codes(df):
    return df['outcome'].map({name: j for j, name in enumerate(CLASSES)}).to_numpy(dtype=int)


def probabilities(model, basis, x):
    p = model.predict_proba(basis.transform(x))
    assert np.array_equal(model.classes_, np.arange(5))
    return p


def binary_metrics(y, p):
    eps = 1e-12
    clipped = np.clip(p, eps, 1 - eps)
    return {'brier': float(np.mean((p - y) ** 2)),
            'log_loss': float(-np.mean(y * np.log(clipped) + (1 - y) * np.log(1 - clipped))),
            'roc_auc': float(roc_auc_score(y, p)) if len(np.unique(y)) == 2 else None,
            'actual_rate': float(np.mean(y)), 'predicted_rate': float(np.mean(p))}


def probability_metrics(y, p, baseline):
    hit_y, hr_y = (y != 0).astype(int), (y == 4).astype(int)
    hit_p, hr_p = 1 - p[:, 0], p[:, 4]
    result = {'n': len(y), 'multiclass_log_loss': float(log_loss(y, p, labels=np.arange(5))),
              'hit': binary_metrics(hit_y, hit_p), 'home_run': binary_metrics(hr_y, hr_p),
              'baseline_multiclass_log_loss': float(log_loss(y, np.tile(baseline, (len(y), 1)), labels=np.arange(5)))}
    for key, yy, bp in [('hit', hit_y, 1 - baseline[0]), ('home_run', hr_y, baseline[4])]:
        result[key]['baseline_brier'] = float(np.mean((bp - yy) ** 2))
        result[key]['brier_skill'] = 1 - result[key]['brier'] / result[key]['baseline_brier']
    return result


def distance_metrics(y, pred, baseline):
    return {'n': len(y), 'mae_m': float(mean_absolute_error(y, pred) * FEET_TO_M),
            'rmse_m': float(np.sqrt(np.mean((y - pred) ** 2)) * FEET_TO_M),
            'r2': float(r2_score(y, pred)), 'mean_error_m': float(np.mean(pred - y) * FEET_TO_M),
            'baseline_mae_m': float(np.mean(np.abs(y - baseline)) * FEET_TO_M)}


def fit():
    OUT.mkdir(exist_ok=True)
    policy = read_json(PROCESSED / 'cleaning-policy.json')
    prob = pd.read_csv(PROCESSED / 'probability.csv.gz', dtype={'game_date': str, 'game_pk': str})
    dist = pd.read_csv(PROCESSED / 'distance.csv.gz', dtype={'game_date': str, 'game_pk': str})
    dev = prob.loc[prob['split'].eq('development')].copy()
    dev_dist = dist.loc[dist['split'].eq('development')].copy()
    days = sorted(dev['game_date'].unique())
    cutoff = days[int(len(days) * .8)]
    train, valid = dev.loc[dev['game_date'].lt(cutoff)], dev.loc[dev['game_date'].ge(cutoff)]
    dtrain, dvalid = dev_dist.loc[dev_dist['game_date'].lt(cutoff)], dev_dist.loc[dev_dist['game_date'].ge(cutoff)]
    held_dates = set(policy['reserved_dates'])
    assert not set(dev['game_date']) & held_dates
    assert not set(dev_dist['game_date']) & held_dates
    assert not set(train['game_pk']) & set(valid['game_pk'])
    xtrain, xvalid = train[FEATURES].to_numpy(), valid[FEATURES].to_numpy()
    ytrain, yvalid = class_codes(train), class_codes(valid)
    candidates_p, candidates_d = [], []
    best_p, best_d = None, {}
    feature_cache = {}
    print(f'MODEL SELECTION: training {len(train):,}, validation {len(valid):,}, cutoff {cutoff}; held dates excluded', flush=True)
    with threadpool_limits(limits=2):
        for knots in (9, 13):
            basis = TensorSplines(knots).fit(xtrain)
            ftrain, fvalid = basis.transform(xtrain), basis.transform(xvalid)
            feature_cache[knots] = basis
            for c in (1., 10.):
                model = LogisticRegression(C=c, solver='lbfgs', max_iter=1000, tol=1e-6, random_state=SEED)
                with warnings.catch_warnings():
                    warnings.simplefilter('error', ConvergenceWarning)
                    model.fit(ftrain, ytrain)
                score = float(log_loss(yvalid, model.predict_proba(fvalid), labels=np.arange(5)))
                candidates_p.append({'n_knots': knots, 'C': c, 'validation_log_loss': score, 'iterations': int(model.n_iter_[0])})
                if best_p is None or score < best_p['validation_log_loss']:
                    best_p = candidates_p[-1]
                print('PROBABILITY CANDIDATE', candidates_p[-1], flush=True)
            for population in ('all_batted', 'airborne'):
                tr = dtrain if population == 'all_batted' else dtrain.loc[dtrain['bb_type'].isin(AIRBORNE)]
                va = dvalid if population == 'all_batted' else dvalid.loc[dvalid['bb_type'].isin(AIRBORNE)]
                fdtr, fdva = basis.transform(tr[FEATURES].to_numpy()), basis.transform(va[FEATURES].to_numpy())
                for alpha in (.1, 1.):
                    model = Ridge(alpha=alpha, fit_intercept=False, solver='lsqr', tol=1e-7, max_iter=1500)
                    model.fit(fdtr, tr['hit_distance_sc'].to_numpy())
                    pred = np.maximum(model.predict(fdva), 0)
                    score = float(mean_absolute_error(va['hit_distance_sc'], pred) * FEET_TO_M)
                    record = {'population': population, 'n_knots': knots, 'alpha': alpha, 'validation_mae_m': score}
                    candidates_d.append(record)
                    if population not in best_d or score < best_d[population]['validation_mae_m']:
                        best_d[population] = record
                    print('DISTANCE CANDIDATE', record, flush=True)
        # Refit selected models on ALL development dates after selecting settings.
        # Held-out observations never enter basis fitting, optimization or selection.
        bases = {}
        for knots in {best_p['n_knots'], *(r['n_knots'] for r in best_d.values())}:
            bases[knots] = TensorSplines(knots).fit(dev[FEATURES].to_numpy())
        p_basis = bases[best_p['n_knots']]
        p_model = LogisticRegression(C=best_p['C'], solver='lbfgs', max_iter=1200, tol=1e-6, random_state=SEED)
        with warnings.catch_warnings():
            warnings.simplefilter('error', ConvergenceWarning)
            p_model.fit(p_basis.transform(dev[FEATURES].to_numpy()), class_codes(dev))
        distance_models = {}
        for population, spec in best_d.items():
            dd = dev_dist if population == 'all_batted' else dev_dist.loc[dev_dist['bb_type'].isin(AIRBORNE)]
            basis = bases[spec['n_knots']]
            model = Ridge(alpha=spec['alpha'], fit_intercept=False, solver='lsqr', tol=1e-7, max_iter=1500)
            model.fit(basis.transform(dd[FEATURES].to_numpy()), dd['hit_distance_sc'].to_numpy())
            distance_models[population] = {'basis': basis, 'model': model, 'baseline_mean_ft': float(dd['hit_distance_sc'].mean())}
    bundle = {'probability': {'basis': p_basis, 'model': p_model}, 'distance': distance_models,
              'classes': CLASSES, 'features': FEATURES, 'reserved_dates': policy['reserved_dates']}
    with (OUT / 'models.pkl').open('wb') as f:
        pickle.dump(bundle, f)
    baseline = np.bincount(class_codes(dev), minlength=5) / len(dev)
    metrics = {}
    predictions = []
    for label in ('early_holdout', 'final_holdout', 'combined_holdout'):
        subset = prob.loc[prob['split'].ne('development') if label == 'combined_holdout' else prob['split'].eq(label)].copy()
        p = probabilities(p_model, p_basis, subset[FEATURES].to_numpy())
        metric = {'probability': probability_metrics(class_codes(subset), p, baseline), 'distance': {}}
        subset['pred_home_run'] = p[:, 4]
        subset['pred_hit'] = 1 - p[:, 0]
        for j, cls in enumerate(CLASSES):
            subset['pred_' + cls] = p[:, j]
        dsub = dist.loc[dist['split'].ne('development') if label == 'combined_holdout' else dist['split'].eq(label)]
        for population, model_info in distance_models.items():
            dd = dsub if population == 'all_batted' else dsub.loc[dsub['bb_type'].isin(AIRBORNE)]
            pred = np.maximum(model_info['model'].predict(model_info['basis'].transform(dd[FEATURES].to_numpy())), 0)
            metric['distance'][population] = distance_metrics(dd['hit_distance_sc'].to_numpy(), pred, model_info['baseline_mean_ft'])
        subset['pred_distance_m'] = np.maximum(distance_models['all_batted']['model'].predict(distance_models['all_batted']['basis'].transform(subset[FEATURES].to_numpy())), 0) * FEET_TO_M
        if label != 'combined_holdout':
            predictions.append(subset)
        metrics[label] = metric
    held = pd.concat(predictions, ignore_index=True)
    held.to_csv(OUT / 'holdout-predictions.csv', index=False, encoding='utf-8-sig')
    # Game-cluster bootstrap intervals for evaluation metrics, not refitting/tuning.
    rng = np.random.default_rng(SEED)
    grouped_games = [g.index.to_numpy() for _, g in held.groupby('game_pk')]
    vals = {'hr_brier': [], 'hit_brier': [], 'distance_mae_m': []}
    hit_true = held['events'].isin(CLASSES[1:]).to_numpy(dtype=float)
    hr_true = held['events'].eq('home_run').to_numpy(dtype=float)
    for _ in range(500):
        idx = np.concatenate([grouped_games[j] for j in rng.integers(0, len(grouped_games), len(grouped_games))])
        hh = held.iloc[idx]
        vals['hr_brier'].append(float(np.mean((hh['pred_home_run'].to_numpy() - hr_true[idx]) ** 2)))
        vals['hit_brier'].append(float(np.mean((hh['pred_hit'].to_numpy() - hit_true[idx]) ** 2)))
        measured = hh['hit_distance_sc'].notna()
        vals['distance_mae_m'].append(float(np.mean(np.abs(hh.loc[measured, 'pred_distance_m'] - hh.loc[measured, 'hit_distance_sc'] * FEET_TO_M))))
    uncertainty = {name: {'lo': float(np.quantile(v, .025)), 'hi': float(np.quantile(v, .975))} for name, v in vals.items()}
    # Observations in neighboring cells measure support; never aggregate fit inputs.
    ev_edges = np.arange(0, 132, 2.)
    la_edges = np.arange(-90, 95, 5.)
    hist, _, _ = np.histogram2d(dev['launch_speed'], dev['launch_angle'], bins=[ev_edges, la_edges])
    ev = np.arange(20., 121., 1.)
    la = np.arange(-90., 91., 1.)
    evmesh, lamesh = np.meshgrid(ev, la)
    xgrid = np.column_stack([evmesh.ravel(), lamesh.ravel()])
    pg = probabilities(p_model, p_basis, xgrid)
    grid = pd.DataFrame({'launch_speed': xgrid[:, 0], 'launch_angle': xgrid[:, 1],
                         'p_home_run': pg[:, 4], 'p_hit': 1 - pg[:, 0],
                         'p_non_hr_hit': pg[:, 1:4].sum(axis=1)})
    for population, model_info in distance_models.items():
        pred = np.maximum(model_info['model'].predict(model_info['basis'].transform(xgrid)), 0)
        grid['distance_' + population + '_m'] = pred * FEET_TO_M
    ix = np.clip(np.searchsorted(ev_edges, xgrid[:, 0], side='right') - 1, 0, len(ev_edges) - 2)
    iy = np.clip(np.searchsorted(la_edges, xgrid[:, 1], side='right') - 1, 0, len(la_edges) - 2)
    grid['cell_n'] = hist[ix, iy].astype(int)
    # 3x3 adjacent cells = a ~6 mph by 15-degree local neighborhood.
    from scipy.ndimage import uniform_filter
    neighborhood = np.rint(uniform_filter(hist, size=3, mode='constant') * 9)
    grid['local_support_n'] = neighborhood[ix, iy].astype(int)
    grid['supported'] = grid['local_support_n'].ge(50)
    grid.to_csv(OUT / 'prediction-grid.csv.gz', index=False, compression='gzip')
    # Angle maxima and sample profiles use development support, never test outcomes.
    optima = []
    examples = []
    for speed in (80., 90., 95., 100., 105., 110.):
        line = grid.loc[grid['launch_speed'].eq(speed) & grid['supported']].copy()
        air_line = line.loc[line['launch_angle'].between(5, 60)]
        result = {'ev_mph': speed, 'ev_kmh': speed * 1.609344}
        for target in ('distance_all_batted_m', 'p_home_run', 'p_hit'):
            candidate = air_line if target == 'distance_all_batted_m' else line
            peak = candidate.loc[candidate[target].idxmax()]
            result[target + '_optimal_angle'] = float(peak['launch_angle'])
            result[target + '_peak'] = float(peak[target])
        optima.append(result)
        for angle in (0., 10., 20., 25., 30., 35., 45., 60.):
            point = grid.loc[grid['launch_speed'].eq(speed) & grid['launch_angle'].eq(angle)].iloc[0].to_dict()
            local = dev.loc[dev['launch_speed'].between(speed - 2.5, speed + 2.5) & dev['launch_angle'].between(angle - 2.5, angle + 2.5)]
            point['observed_local_n'] = len(local)
            point['observed_local_hr'] = float(local['events'].eq('home_run').mean()) if len(local) else None
            point['observed_local_hit'] = float(local['events'].isin(CLASSES[1:]).mean()) if len(local) else None
            examples.append(point)
    pd.DataFrame(optima).to_csv(OUT / 'optimal-angles.csv', index=False, encoding='utf-8-sig')
    pd.DataFrame(examples).to_csv(OUT / 'example-combinations.csv', index=False, encoding='utf-8-sig')
    calibration = []
    for target, truth, prediction in [('home_run', hr_true, held['pred_home_run'].to_numpy()),
                                      ('hit', hit_true, held['pred_hit'].to_numpy())]:
        bins = np.minimum((prediction * 10).astype(int), 9)
        for j in range(10):
            mask = bins == j
            if mask.sum():
                successes, n = int(truth[mask].sum()), int(mask.sum())
                lo, hi = wilson(successes, n)
                calibration.append({'target': target, 'bin': j, 'n': n,
                                    'predicted_mean': float(prediction[mask].mean()),
                                    'observed_rate': successes / n, 'lo95': lo, 'hi95': hi})
    pd.DataFrame(calibration).to_csv(OUT / 'calibration.csv', index=False, encoding='utf-8-sig')
    run = {'features': FEATURES, 'classes': CLASSES, 'seed': SEED,
           'model': 'tensor-product cubic B-splines + penalized multinomial logistic; distance ridge',
           'training_unit': 'individual raw-precision batted ball; no bin aggregation',
           'internal_validation': {'cutoff': cutoff, 'train_first': min(train['game_date']), 'train_last': max(train['game_date']),
                                   'validation_first': min(valid['game_date']), 'validation_last': max(valid['game_date']),
                                   'training_n_probability': len(train), 'validation_n_probability': len(valid)},
           'probability_candidates': candidates_p, 'distance_candidates': candidates_d,
           'selected_probability': best_p, 'selected_distance': best_d,
           'final_fitted_n_probability': len(dev), 'final_fitted_n_distance': len(dev_dist),
           'reserved_dates': policy['reserved_dates'], 'baseline_class_probabilities': baseline.tolist(),
           'grid_support': 'count of development observations in 3x3 neighboring 2mph x 5deg cells, minimum 50',
           'coverage': '20..120mph, -90..90deg grid; estimates outside support suppressed in charts/dashboard',
           'metrics': metrics, 'combined_game_bootstrap_95': uncertainty,
           'optima': optima, 'source_cleaning_policy_sha256': filehash(PROCESSED / 'cleaning-policy.json'),
           'fit_held_out_dates_used': False, 'holdout_based_model_selection': False,
           'probability_features_exclude_distance': True,
           'environment': {'python': platform.python_version(), 'numpy': np.__version__, 'pandas': pd.__version__},
           'generated_at_utc': datetime.now(timezone.utc).isoformat()}
    import sklearn, scipy, matplotlib, importlib.metadata
    run['environment'].update({'scikit-learn': sklearn.__version__, 'scipy': scipy.__version__, 'matplotlib': matplotlib.__version__})
    for name in ('numpy', 'pandas', 'scipy', 'scikit-learn', 'matplotlib', 'joblib', 'threadpoolctl'):
        run['environment'][name] = importlib.metadata.version(name)
    (OUT / 'requirements-lock.txt').write_text('\n'.join(f'{name}=={run["environment"][name]}' for name in ('numpy', 'pandas', 'scipy', 'scikit-learn', 'matplotlib', 'joblib', 'threadpoolctl')) + '\n', encoding='utf-8')
    write_json(OUT / 'results.json', run)
    print('FINAL HOLDOUT METRICS', json.dumps(metrics, ensure_ascii=False), flush=True)
    print('OPTIMAL ANGLES', json.dumps(optima, ensure_ascii=False), flush=True)


def wilson(successes, n):
    z = 1.95996398454
    p = successes / n
    center = (p + z*z/(2*n)) / (1 + z*z/n)
    radius = z * np.sqrt(p*(1-p)/n + z*z/(4*n*n)) / (1 + z*z/n)
    return max(0, float(center - radius)), min(1, float(center + radius))


def render():
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.colors import LogNorm
    from matplotlib import font_manager
    FIGURES.mkdir(parents=True, exist_ok=True)
    font_manager.fontManager.addfont(r'C:\Windows\Fonts\malgun.ttf')
    plt.rcParams.update({'font.family': 'Malgun Gothic', 'axes.unicode_minus': False,
                         'font.size': 10, 'axes.titlesize': 13,
                         'axes.labelsize': 11, 'figure.facecolor': '#f4f7f8',
                         'axes.facecolor': '#e7ecee', 'axes.edgecolor': '#83939b',
                         'text.color': '#162b36', 'axes.labelcolor': '#162b36',
                         'xtick.color': '#52656f', 'ytick.color': '#52656f',
                         'savefig.facecolor': '#f4f7f8'})
    run = read_json(OUT / 'results.json')
    policy = read_json(PROCESSED / 'cleaning-policy.json')
    grid = pd.read_csv(OUT / 'prediction-grid.csv.gz')
    ev, la = np.sort(grid['launch_speed'].unique()), np.sort(grid['launch_angle'].unique())
    shape = (len(la), len(ev))
    support = grid['supported'].to_numpy().reshape(shape)
    xx, yy = np.meshgrid(ev, la)

    def finish(fig, name, title, subtitle):
        fig.suptitle(title, x=.07, y=.965, ha='left', fontsize=20, fontweight='bold')
        fig.text(.07, .90, subtitle, fontsize=10, color='#64747d', ha='left')
        fig.text(.07, .025, '2026 MLB 정규시즌 · Baseball Savant / Statcast · 번트·필수 변수 결측 제외 · 검증일 3/26, 9/27 학습 제외', fontsize=8, color='#64747d')
        fig.subplots_adjust(left=.07, right=.98, bottom=.15, top=.80, wspace=.33)
        fig.savefig(FIGURES / name, dpi=180)
        plt.close(fig)

    def map_axes(ax, data, cmap, vmin, vmax, label, norm=None):
        if norm is None:
            mesh = ax.pcolormesh(xx, yy, data, shading='nearest', cmap=cmap, vmin=vmin, vmax=vmax, rasterized=True)
        else:
            mesh = ax.pcolormesh(xx, yy, data, shading='nearest', cmap=cmap, norm=norm, rasterized=True)
        ax.set(xlim=(40, 120), ylim=(-30, 80), xlabel='타구 속도 (mph)', ylabel='발사각 (°)')
        ax.set_xticks([40, 60, 80, 100, 120])
        ax.set_yticks([-30, 0, 30, 60])
        cb = ax.figure.colorbar(mesh, ax=ax, shrink=.90, pad=.02)
        cb.set_label(label)
        return mesh

    fig, axes = plt.subplots(1, 3, figsize=(16, 6.1))
    for ax, field, title, cmap, top, label in zip(axes,
              ['distance_all_batted_m', 'p_home_run', 'p_hit'],
              ['예상 비거리', '기대 홈런 확률', '기대 안타 확률 · 홈런 포함'],
              ['viridis', 'magma', 'YlGnBu'], [150, 100, 100], ['m', '%', '%']):
        values = grid[field].to_numpy().reshape(shape) * (100 if field.startswith('p_') else 1)
        values = np.where(support, values, np.nan)
        map_axes(ax, values, cmap, 0, top, label)
        ax.set_title(title, loc='left', pad=12)
    finish(fig, '01-response-maps.png', '타구 속도와 발사각에 따른 세 가지 결과',
           '개별 타구로 학습한 모델 · 회색: 주변 학습 표본 50개 미만 · 비거리: 전체 타구의 Statcast 추정 비거리')

    fig, axes = plt.subplots(1, 3, figsize=(16, 6.1))
    colors = {90: '#5698a2', 100: '#0d718e', 110: '#dc795b'}
    for ax, field, title in zip(axes, ['distance_all_batted_m', 'p_home_run', 'p_hit'],
                               ['예상 비거리', '기대 홈런 확률', '기대 안타 확률 · 홈런 포함']):
        for speed, color in colors.items():
            line = grid.loc[grid['launch_speed'].eq(speed)].copy()
            values = line[field].where(line['supported']) * (100 if field.startswith('p_') else 1)
            ax.plot(line['launch_angle'], values, label=f'{speed} mph', color=color, lw=2.5)
        ax.set(xlim=(-20, 70), xlabel='발사각 (°)', ylabel='확률 (%)' if field.startswith('p_') else '추정 비거리 (m)')
        ax.set_ylim(0, 105 if field.startswith('p_') else 150)
        ax.set_title(title, loc='left', pad=12)
        ax.set_facecolor('#fff')
        ax.grid(alpha=.20)
        ax.legend(frameon=False, loc='upper left')
    finish(fig, '02-angle-profiles.png', '속도가 같아도 목표에 따라 유리한 각도가 달라집니다',
           '90 / 100 / 110 mph 비교 · 표본이 충분한 영역만 표시 · 안타 확률은 홈런을 포함')

    held = pd.read_csv(OUT / 'holdout-predictions.csv')
    display_calibration = []
    for target, prediction, outcome in [('home_run', 'pred_home_run', held['events'].eq('home_run')),
                                         ('hit', 'pred_hit', held['events'].isin(CLASSES[1:]))]:
        width = .2 if target == 'home_run' else .1
        bin_index = np.minimum((held[prediction] / width).astype(int), round(1 / width) - 1)
        for j in range(round(1 / width)):
            mask = bin_index.eq(j)
            if not mask.any():
                continue
            n, successes = int(mask.sum()), int(outcome[mask].sum())
            lo, hi = wilson(successes, n)
            display_calibration.append({'target': target, 'bin_width': width, 'bin': j, 'n': n,
                                        'predicted_mean': float(held.loc[mask, prediction].mean()),
                                        'observed_rate': successes / n, 'lo95': lo, 'hi95': hi})
    calibration = pd.DataFrame(display_calibration)
    calibration.to_csv(OUT / 'calibration-display.csv', index=False, encoding='utf-8-sig')
    fig, axes = plt.subplots(1, 3, figsize=(16, 6.1))
    for label, color, title in [('early_holdout', '#0d718e', '3월 26일'), ('final_holdout', '#dc795b', '9월 27일')]:
        points = held.loc[held['split'].eq(label)].dropna(subset=['hit_distance_sc'])
        axes[0].scatter(points['hit_distance_sc'] * FEET_TO_M, points['pred_distance_m'],
                        s=10, alpha=.45, color=color, label=title, edgecolors='none')
    axes[0].plot([0, 150], [0, 150], color='#64747d', lw=1, ls='--')
    axes[0].set(xlim=(0, 150), ylim=(0, 150), xlabel='Statcast 추정 비거리 (m)', ylabel='모델 예측 비거리 (m)')
    axes[0].set_title('비거리 예측과 기록', loc='left', pad=12)
    axes[0].legend(frameon=False)
    for ax, target, title in [(axes[1], 'home_run', '홈런 확률의 일치 정도'), (axes[2], 'hit', '안타 확률의 일치 정도')]:
        points = calibration.loc[calibration['target'].eq(target) & calibration['n'].ge(20)]
        ax.plot([0, 100], [0, 100], color='#64747d', lw=1, ls='--')
        ax.errorbar(points['predicted_mean'] * 100, points['observed_rate'] * 100,
                    yerr=np.maximum(np.vstack([(points['observed_rate'] - points['lo95']) * 100,
                                                (points['hi95'] - points['observed_rate']) * 100]), 0),
                    fmt='o', color='#0d718e', capsize=3)
        ax.set(xlim=(0, 100), ylim=(0, 100), xlabel='평균 예측 확률 (%)', ylabel='실제 발생 비율 (%)')
        ax.set_title(title, loc='left', pad=12)
    for ax in axes:
        ax.set_facecolor('white')
        ax.grid(alpha=.15)
    combined = run['metrics']['combined_holdout']
    finish(fig, '03-validation.png', '학습에서 제외한 25경기 · 1,246타구 검증',
           f"비거리 MAE {combined['distance']['all_batted']['mae_m']:.2f} m · Wilson 95% 구간 · 홈런 20%p / 안타 10%p 구간, 각 20개 이상")

    dev = pd.read_csv(PROCESSED / 'probability.csv.gz')
    dev = dev.loc[dev['split'].eq('development')].copy()
    ev_edges, la_edges = np.arange(0, 132, 2.), np.arange(-90, 95, 5.)
    dev['ev_bin'] = np.clip(np.searchsorted(ev_edges, dev['launch_speed'], side='right') - 1, 0, len(ev_edges) - 2)
    dev['la_bin'] = np.clip(np.searchsorted(la_edges, dev['launch_angle'], side='right') - 1, 0, len(la_edges) - 2)
    grouped = dev.groupby(['ev_bin', 'la_bin'])
    stats = grouped.agg(n=('events', 'size'), distance_n=('hit_distance_sc', 'count'),
                        median_distance_ft=('hit_distance_sc', 'median'),
                        hr=('events', lambda v: int(v.eq('home_run').sum())),
                        hits=('events', lambda v: int(v.isin(CLASSES[1:]).sum()))).reset_index()
    stats['observed_home_run'] = stats['hr'] / stats['n']
    stats['observed_hit'] = stats['hits'] / stats['n']
    for target, successes in [('home_run', 'hr'), ('hit', 'hits')]:
        intervals = [wilson(int(s), int(n)) for s, n in zip(stats[successes], stats['n'])]
        stats[target + '_lo95'], stats[target + '_hi95'] = [r[0] for r in intervals], [r[1] for r in intervals]
    stats['ev_mph_center'] = ev_edges[stats['ev_bin'].to_numpy()] + 1
    stats['angle_center'] = la_edges[stats['la_bin'].to_numpy()] + 2.5
    stats['median_distance_m'] = stats['median_distance_ft'] * FEET_TO_M
    stats.to_csv(OUT / 'observed-cells.csv', index=False, encoding='utf-8-sig')
    fig, axes = plt.subplots(1, 3, figsize=(16, 6.1))
    observed_matrices = {}
    for ax, field, title, cmap, vmax in zip(axes,
                 ['median_distance_m', 'observed_home_run', 'observed_hit'],
                 ['비거리 중앙값', '관측 홈런 비율', '관측 안타 비율 · 홈런 포함'],
                 ['viridis', 'magma', 'YlGnBu'], [150, 100, 100]):
        matrix = np.full((len(la_edges) - 1, len(ev_edges) - 1), np.nan)
        selected = stats.loc[stats['distance_n' if field == 'median_distance_m' else 'n'].ge(30)]
        matrix[selected['la_bin'], selected['ev_bin']] = selected[field] * (100 if field.startswith('observed') else 1)
        mesh = ax.pcolormesh(ev_edges, la_edges, matrix, cmap=cmap, vmin=0, vmax=vmax, shading='flat')
        ax.set(xlim=(40, 120), ylim=(-30, 80), xlabel='타구 속도 (mph)', ylabel='발사각 (°)')
        ax.set_title(title, loc='left', pad=12)
        fig.colorbar(mesh, ax=ax, shrink=.90, pad=.02).set_label('%' if field.startswith('observed') else 'm')
        observed_matrices[field] = matrix
    finish(fig, '04-observed-maps.png', '2026년 타구에서 직접 관측한 결과',
           '검증일을 제외한 관측값 · 각 구간 2 mph × 5° · 표본 30개 이상만 표시 · 모델 예측 지도와 비교 가능')

    counts = np.zeros((len(la_edges) - 1, len(ev_edges) - 1))
    counts[stats['la_bin'], stats['ev_bin']] = stats['n']
    fig, ax = plt.subplots(figsize=(10, 6.6))
    mesh = ax.pcolormesh(ev_edges, la_edges, np.ma.masked_less(counts, 1), cmap='YlGnBu',
                         norm=LogNorm(vmin=1, vmax=float(counts.max())), shading='flat')
    ax.set(xlim=(40, 120), ylim=(-30, 80), xlabel='타구 속도 (mph)', ylabel='발사각 (°)')
    fig.colorbar(mesh, ax=ax, pad=.03).set_label('타구 수 · 로그 눈금')
    finish(fig, '05-sample-counts.png', '속도·각도 조합별 표본 수',
           '검증일을 제외한 학습 후보 · 각 구간 2 mph × 5° · 관측이 드문 영역의 예측은 제한')
    write_dashboard(run, grid)
    write_analysis_report(run, policy)
    print('RENDERED', [p.name for p in FIGURES.glob('*.png')], flush=True)


def write_dashboard(run, grid):
    validation = []
    for label, day in zip(('early_holdout', 'final_holdout'), run['reserved_dates']):
        m = run['metrics'][label]
        validation.append({'date': day, 'n': m['probability']['n'],
                           'hrActual': m['probability']['home_run']['actual_rate'],
                           'hrPred': m['probability']['home_run']['predicted_rate'],
                           'hitActual': m['probability']['hit']['actual_rate'],
                           'hitPred': m['probability']['hit']['predicted_rate'],
                           'mae': m['distance']['all_batted']['mae_m']})
    payload = {'training': run['final_fitted_n_probability'], 'optima': run['optima'],
               'validation': validation, 'support': grid['local_support_n'].astype(int).tolist(),
               'distance': grid['distance_all_batted_m'].round(3).tolist(),
               'hr': grid['p_home_run'].round(6).tolist(), 'hit': grid['p_hit'].round(6).tolist()}
    template = Path(__file__).with_name('mlb_statcast_dashboard.html').read_text(encoding='utf-8')
    document = template.replace('__PAYLOAD__', json.dumps(payload, ensure_ascii=False, separators=(',', ':'), allow_nan=False))
    (OUT / 'dashboard.html').write_text(document, encoding='utf-8')


def write_analysis_report(run, policy):
    def table(headers, rows):
        return '\n'.join(['| ' + ' | '.join(headers) + ' |', '| ' + ' | '.join(['---'] * len(headers)) + ' |'] +
                         ['| ' + ' | '.join(str(v) for v in row) + ' |' for row in rows])
    def pct(value):
        return f'{100 * value:.1f}%'
    examples = pd.read_csv(OUT / 'example-combinations.csv')
    focus = examples.loc[examples['launch_speed'].eq(100) & examples['launch_angle'].isin([0, 10, 20, 25, 30, 35, 45, 60])]
    speed_focus = examples.loc[examples['launch_angle'].eq(30) & examples['launch_speed'].isin([90, 95, 100, 105, 110])]
    inv = pd.read_csv(PROCESSED / 'eligibility-inventory.csv.gz')
    zeros = inv.loc[~inv['is_bunt_candidate'] & inv['hit_distance_sc'].eq(0)]
    zero_kept = int(zeros['eligible_distance'].sum())
    combined = run['metrics']['combined_holdout']
    ci = run['combined_game_bootstrap_95']
    opt = run['optima']
    onehundred = next(r for r in opt if r['ev_mph'] == 100)
    lines = ['# 2026 MLB 타구 속도·발사각 분석', '',
             '타구 속도와 발사각에 따라 공이 얼마나 멀리 가는지, 홈런과 안타가 될 가능성은 어떻게 달라지는지 알아보고 싶었다. 2026년 MLB 정규시즌의 Statcast 데이터를 이용해 두 조건과 타구 결과의 관계를 살펴봤다.', '',
             '타구 속도와 발사각을 입력으로 비거리, 홈런 확률, 안타 확률을 추정했다. 같은 속도에서 각도를 바꾸는 경우와, 같은 각도에서 속도를 바꾸는 경우를 나누어 비교했다. 안타 확률에는 홈런이 포함된다.', '',
             '분석 기준일: 2026-10-11 KST.', '',
             '[조건을 바꾸며 보는 인터랙티브 결과](dashboard.html)', '',
             '## 핵심 결과', '',
             '타구 속도 90~110 mph에서 모델이 추정한 비거리 최대 각도는 약 30~31°였다. 이 범위를 넘어 더 높이 띄우면 비거리가 줄어드는 관계가 관측되었다.', '',
             f"100 mph(160.9 km/h)를 예로 보면 비거리 최대 지점은 약 {onehundred['distance_all_batted_m_optimal_angle']:.0f}°에서 {onehundred['distance_all_batted_m_peak']:.1f} m였다. 홈런 확률도 비슷한 각도인 약 {onehundred['p_home_run_optimal_angle']:.0f}°에서 {pct(onehundred['p_home_run_peak'])}로 가장 높았다. 반면 안타 확률은 약 {onehundred['p_hit_optimal_angle']:.0f}°에서 {pct(onehundred['p_hit_peak'])}로 가장 높았다. 같은 속도라도 홈런과 안타에 유리한 각도가 달랐다.", '',
             '다만 속도가 더 높아지면 관계가 달라졌다. 105~110 mph에서는 안타 확률도 약 30°에서 최대가 되었다. 안타 확률에 홈런이 포함되기 때문에, 홈런 확률이 높은 강한 타구에서는 두 목표의 유리한 각도가 가까워졌다.', '',
             f"검증에는 학습에서 제외한 두 날짜의 25경기·{combined['probability']['n']:,}타구를 사용했다. 비거리 평균 절대 오차는 {combined['distance']['all_batted']['mae_m']:.2f} m였다. 홈런 확률 Brier 오차는 {combined['probability']['home_run']['brier']:.4f}, 안타 확률은 {combined['probability']['hit']['brier']:.4f}였다.", '',
             '수치는 모델 추정값이며, 개별 타구의 확정 결과나 각도를 바꾸었을 때의 인과 효과가 아니다. 최대 지점은 표본이 충분한 1° 격자에서 비교한 값으로 해석한다.', '',
             '## 1. 데이터와 결측치 처리', '',
             table(['항목', '타구 수'], [['원본 타구', f"{policy['raw_rows']:,}"],
                     ['번트 후보 제외', f"{policy['bunt_candidates']:,}"], ['비번트 타구', f"{policy['non_bunt']:,}"],
                     ['속도·각도 결측으로 확률 분석에서 제외', f"{policy['probability_missing_removed_non_bunt']:,}"],
                     ['속도·각도·비거리 결측으로 비거리 분석에서 제외', f"{policy['distance_missing_removed_non_bunt']:,}"],
                     ['확률 분석 전체 표본 (검증 포함)', f"{policy['probability_kept']:,}"],
                     ['비거리 분석 전체 표본 (검증 포함)', f"{policy['distance_kept']:,}"],
                     ['비거리만 없지만 확률 분석에 유지', f"{policy['distance_only_missing_kept_for_probability']:,}"]]), '',
             '원본은 보존했다. 필요한 변수에만 완전 사례 기준을 적용했으며, 제공자의 xBA나 사용하지 않는 열의 결측으로 타구를 제거하지 않았다. 비거리 0인 땅볼과 음수 발사각도 유지했다. 번트는 기존 설명 기반 후보 플래그를 사용했다.', '',
             f"비거리 0인 비번트 타구 {len(zeros):,}개 중 필수 입력이 완전한 {zero_kept:,}개를 비거리 분석에 유지했다. 나머지 {len(zeros) - zero_kept:,}개는 속도 결측으로 제외되었다. 비거리 0 자체를 삭제 이유로 삼지는 않았다.", '',
             '## 2. 검증 날짜와 학습 방법', '',
             '첫 검증일은 실제 개막 다음 날인 **2026-03-26 (11경기)**로 변경했다. 최소 10경기가 열린 가장 이른 날짜를 선택한 것이다. 최종일 **2026-09-27 (14경기)**과 함께 학습·모델 선택·전처리 적합에서 완전히 제외했다. 3월 25일은 변경된 정책에 따라 학습 후보에 포함된다.', '',
             table(['구분', '경기 수', '확률 표본', '비거리 표본', '공중 타구 비거리 표본', '홈런'],
                   [[r['date'] if r['split'] != 'development' else '학습 후보 · 나머지 날짜', r['games'], f"{r['probability']:,}", f"{r['distance']:,}", f"{r['airborne_distance']:,}", r['home_runs_eligible']] for r in policy['splits']]), '',
             f"모델 선택은 학습 후보 안에서 시간순으로 분리했다. {run['internal_validation']['train_first']}~{run['internal_validation']['train_last']}의 {run['internal_validation']['training_n_probability']:,}타구로 학습하고, {run['internal_validation']['validation_first']}~{run['internal_validation']['validation_last']}의 {run['internal_validation']['validation_n_probability']:,}타구로 설정을 선택했다. 설정을 확정한 뒤 검증일을 제외한 전체 후보로 다시 학습했다.", '',
             '- 입력: 타구 속도 `launch_speed`와 발사각 `launch_angle` 두 가지. 비거리·선수·구장·날짜·공식 xBA를 확률 모델의 입력으로 사용하지 않았다.',
             '- 확률: 두 입력의 상호작용을 반영하는 연속적인 2차원 3차 B-spline + 규제 다항 로지스틱 회귀. 아웃·단타·2루타·3루타·홈런의 확률을 함께 예측한다.',
             '- 홈런 확률은 홈런 클래스 확률이다. 안타 확률은 단타·2루타·3루타·홈런 확률의 합이다. 홈런 확률이 안타 확률을 초과하지 않도록 일관되게 구성했다.',
             '- 비거리: 동일한 두 입력의 spline 상호작용 + ridge 회귀. 전체 타구 모델과 공중 타구(직선타·뜬공·팝업) 모델을 따로 학습했다. 음수 예측 비거리는 0으로 제한했다.',
             '- 원본 정밀도의 타구별 값으로 학습했다. 2 mph × 5° 구간은 관측 결과와 표본 수를 확인할 때만 사용했다.', '',
             f"선택된 확률 설정: n_knots={run['selected_probability']['n_knots']}, C={run['selected_probability']['C']}. 전체 비거리 설정: n_knots={run['selected_distance']['all_batted']['n_knots']}, alpha={run['selected_distance']['all_batted']['alpha']}. 공중 타구 설정은 results.json에 기록했다.", '',
             '## 3. 같은 속도에서 각도 변화', '',
             '먼저 타구 속도를 100 mph(약 160.9 km/h)로 고정하고 발사각에 따른 차이를 비교했다. 아래 값은 전체 타구 비거리 모델과 공동 확률 모델의 예측이다.', '',
             table(['발사각', '예상 비거리', '기대 홈런 확률', '기대 안타 확률', '홈런 제외 안타 확률', '근처 관측 타구 수'],
                   [[f"{r.launch_angle:.0f}°", f"{r.distance_all_batted_m:.1f} m", pct(r.p_home_run), pct(r.p_hit), pct(r.p_non_hr_hit), r.observed_local_n] for r in focus.itertuples()]), '',
             '발사각 10°에서는 안타 확률이 76.8%였지만 홈런 확률은 반올림하면 0.0%였다. 30°에서는 예상 비거리가 117.1 m로 길어지고 홈런 확률이 41.7%로 높아졌지만, 안타 확률은 51.6%였다. 45°까지 높였을 때는 비거리와 두 확률이 모두 줄었다. 같은 속도에서도 각도를 계속 높이는 것이 유리하지는 않았다.', '',
             '근처 관측 수는 속도 ±2.5 mph, 각도 ±2.5°의 학습 후보에서 센 값이다. 모델 학습과 별개의 설명용 집계이며, 예측 확률과 실제 관측 비율은 구분해야 한다. 모든 예시 조합의 근처 실제 비율은 example-combinations.csv에 함께 보관했다.', '',
             '## 4. 같은 각도에서 속도 변화', '',
             '이번에는 발사각을 30°로 고정하고 타구 속도를 바꾸어 비교했다.', '',
             table(['타구 속도', '예상 비거리', '기대 홈런 확률', '기대 안타 확률'],
                   [[f"{r.launch_speed:.0f} mph / {r.launch_speed * 1.609344:.1f} km/h", f"{r.distance_all_batted_m:.1f} m", pct(r.p_home_run), pct(r.p_hit)] for r in speed_focus.itertuples()]), '',
             '90 mph에서 예상 비거리는 100.5 m, 홈런 확률은 0.5%였다. 110 mph에서는 각각 131.8 m와 98.5%였다. 속도가 높아질수록 비거리가 길어졌고, 100~105 mph 구간에서는 홈런 확률도 크게 높아졌다. 다만 구장마다 담장 위치와 높이가 다르므로 특정 비거리를 넘으면 반드시 홈런이라는 단일 경계는 사용하지 않았다.', '',
             '## 5. 속도별 최대 지점', '',
             table(['속도', '비거리 최대 각도 / 거리', '홈런 확률 최대 각도 / 확률', '안타 확률 최대 각도 / 확률'],
                   [[f"{r['ev_mph']:.0f} mph", f"{r['distance_all_batted_m_optimal_angle']:.0f}° / {r['distance_all_batted_m_peak']:.1f} m",
                     f"{r['p_home_run_optimal_angle']:.0f}° / {pct(r['p_home_run_peak'])}", f"{r['p_hit_optimal_angle']:.0f}° / {pct(r['p_hit_peak'])}"] for r in opt]), '',
             '비거리 최대 지점은 공중 타구 비교에 적합한 5~60° 범위에서, 확률 최대 지점은 지원되는 전체 각도에서 찾았다. 80~90 mph의 매우 낮은 홈런 확률에서 최대 각도는 특히 불확실하므로 타격 권장값으로 해석하지 않는다.', '',
             '## 6. 최종 검증 성능', '',
             table(['검증 구분', '확률 타구 수', '비거리 MAE', '공중 타구 비거리 MAE', '홈런 Brier', '안타 Brier', '홈런 AUC', '안타 AUC'],
                   [[label, m['probability']['n'], f"{m['distance']['all_batted']['mae_m']:.2f} m", f"{m['distance']['airborne']['mae_m']:.2f} m",
                     f"{m['probability']['home_run']['brier']:.4f}", f"{m['probability']['hit']['brier']:.4f}",
                     f"{m['probability']['home_run']['roc_auc']:.3f}", f"{m['probability']['hit']['roc_auc']:.3f}"]
                    for label, m in [(run['reserved_dates'][0], run['metrics']['early_holdout']), (run['reserved_dates'][1], run['metrics']['final_holdout']), ('두 날짜 합산', combined)]]), '',
             'MAE는 평균 절대 오차(m), Brier는 예측 확률과 실제 0/1 결과의 평균 제곱 오차다. 둘 다 작을수록 좋다. AUC는 발생 타구를 더 높은 확률로 정렬하는 능력이며, 확률이 정확하다는 뜻은 아니다.', '',
             f"합산 홈런 Brier는 학습 후보의 일정한 홈런율만 예측하는 기준 모델({combined['probability']['home_run']['baseline_brier']:.4f}) 대비 약 {100 * combined['probability']['home_run']['brier_skill']:.1f}% 개선했다. 안타는 기준 모델({combined['probability']['hit']['baseline_brier']:.4f}) 대비 약 {100 * combined['probability']['hit']['brier_skill']:.1f}% 개선했다.", '',
             table(['합산 불확실성 · 경기 단위 bootstrap 500회', '95% 범위'],
                   [['전체 비거리 MAE', f"{ci['distance_mae_m']['lo']:.2f}~{ci['distance_mae_m']['hi']:.2f} m"],
                    ['홈런 Brier', f"{ci['hr_brier']['lo']:.4f}~{ci['hr_brier']['hi']:.4f}"],
                    ['안타 Brier', f"{ci['hit_brier']['lo']:.4f}~{ci['hit_brier']['hi']:.4f}"]]), '',
             '같은 경기의 타구를 함께 재표집했다. 이는 두 검증일의 경기 변동을 반영한 성능 범위이며, 개별 타구 예측의 신뢰구간이나 시즌 전체 일반화에 대한 보장이 아니다. 확률 검증 그림의 오차막대는 관측 비율의 Wilson 구간이다.', '',
             '## 7. 해석상의 제한', '',
             '- 비거리 목표는 Statcast의 추정 비거리다. 입력도 같은 추적 시스템에서 나온 속도·각도여서 높은 재현 성능을 실제 착지 거리 예측이나 완전히 독립된 물리 실험의 정확도로 해석하지 않는다.',
             '- 전체 비거리 성능에는 땅볼과 공중 타구의 큰 거리 차이가 포함되므로, 공중 타구 성능도 별도로 보고했다.',
             '- 타구 방향·구장·고도·날씨·회전·수비·주력은 입력에 포함되지 않았다. 결과는 2026년 관측 환경을 평균한 관계다.',
             '- 결측은 땅볼과 일부 구장에 집중되어 있었다. 사용자가 선택한 완전 사례 제외로 인한 표본 구성 변화 가능성은 남아 있다.',
             '- 모델 지도는 인접 3×3개의 2 mph × 5° 구간에 학습 타구 50개 이상이 있는 영역만 표시한다. 관측 지도는 각 구간 표본 30개 이상만 표시한다. 관측이 희박한 조합의 극단적인 예측을 최대 지점으로 사용하지 않았다.',
             '- 현재 snapshot에서 관측된 최댓값 등과 모델 grid의 범위를 구분한다. 표본 밖의 속도·각도로 외삽하지 않는다.',
             '- 검증은 요청한 시즌 양 끝의 두 날짜를 기준으로 했다. 첫 검증일은 이후 경기로 학습한 모델의 과거 날짜 재현 평가이며, 시즌 시작 이전의 미래 예측 성능을 뜻하지 않는다.', '',
             '## 그래프', '',
             '![모델 예측 지도](figures/01-response-maps.png)', '',
             '![속도별 발사각 곡선](figures/02-angle-profiles.png)', '',
             '![독립 날짜 검증](figures/03-validation.png)', '',
             '![직접 관측 지도](figures/04-observed-maps.png)', '',
             '![표본 수](figures/05-sample-counts.png)', '',
             '## 파일과 재실행', '',
             '- `processed/cleaning-policy.json`, `processed/reserved-dates.json`: 확정된 처리 및 변경된 검증 날짜. 이전 사전 감사 보고서의 3월 25일 설정을 대체한다.',
             '- `processed/probability.csv.gz`, `processed/distance.csv.gz`: 분석별 정제 데이터. 검증 구분 열 포함.',
             '- `processed/rejected-inventory.csv.gz`: 제외 타구와 겹칠 수 있는 이유.',
             '- `analysis/results.json`: 설정 선택, 최종 성능, 불확실성, 실행 환경.',
             '- `analysis/holdout-predictions.csv`: 검증 타구별 예측과 실제 결과.',
             '- `analysis/prediction-grid.csv.gz`, `optimal-angles.csv`, `example-combinations.csv`: 예측 지도와 조합별 결과.',
             '- `analysis/observed-cells.csv`, `calibration.csv`, `calibration-display.csv`: 관측 비율과 불확실성 집계. 확률 검증 그림은 홈런 20%p, 안타 10%p 구간을 사용한다.',
             '- `analysis/models.pkl`: 이 프로젝트 스크립트에서 재사용할 수 있는 로컬 모델 객체.',
             '- `analysis/requirements-lock.txt`: 주요 라이브러리의 설치 버전.', '',
             '프로젝트 루트에서 전용 Python으로 실행:', '',
             '```powershell',
             "& 'data\\mlb\\2026\\.venv\\Scripts\\python.exe' -X utf8 scripts/mlb_statcast_analysis.py all",
             '```', '',
             '원본 다운로드를 다시 하지 않고 정제·학습·검증·시각화를 재현한다. 단계별 clean / fit / render / verify 실행도 지원한다.', '',
             '정의와 방법 출처: [Baseball Savant CSV](https://baseballsavant.mlb.com/csv-docs), [scikit-learn spline](https://scikit-learn.org/stable/modules/generated/sklearn.preprocessing.SplineTransformer.html), [다항 로지스틱 회귀](https://scikit-learn.org/stable/modules/generated/sklearn.linear_model.LogisticRegression.html), [확률 검증](https://scikit-learn.org/stable/modules/calibration.html).', '']
    (OUT / 'analysis-report.md').write_text('\n'.join(lines), encoding='utf-8')


def verify():
    policy = read_json(PROCESSED / 'cleaning-policy.json')
    run = read_json(OUT / 'results.json')
    assert policy['source_inventory_sha256'] == filehash(ROOT / policy['source_inventory'])
    assert policy['source_manifest_sha256'] == filehash(ROOT / 'manifest.json')
    assert not run['fit_held_out_dates_used'] and not run['holdout_based_model_selection']
    assert run['features'] == FEATURES and run['probability_features_exclude_distance']
    inv = pd.read_csv(PROCESSED / 'eligibility-inventory.csv.gz', dtype={'game_date': str})
    prob = pd.read_csv(PROCESSED / 'probability.csv.gz', dtype={'game_date': str})
    dist = pd.read_csv(PROCESSED / 'distance.csv.gz', dtype={'game_date': str})
    assert len(inv) == policy['raw_rows']
    assert len(prob) == policy['probability_kept'] and len(dist) == policy['distance_kept']
    assert len(prob) - len(dist) == policy['distance_only_missing_kept_for_probability']
    assert np.isfinite(prob[FEATURES].to_numpy()).all()
    assert np.isfinite(dist[FEATURES + ['hit_distance_sc']].to_numpy()).all()
    assert not prob['is_bunt_candidate'].astype(str).str.lower().eq('true').any()
    key = ['game_pk', 'at_bat_number', 'pitch_number']
    expected_zeros = inv.loc[inv['eligible_distance'] & inv['hit_distance_sc'].eq(0)]
    assert set(map(tuple, dist.loc[dist['hit_distance_sc'].eq(0), key].to_numpy())) == set(map(tuple, expected_zeros[key].to_numpy()))
    assert set(prob.loc[prob['split'].ne('development'), 'game_date']) == set(policy['reserved_dates'])
    assert not set(prob.loc[prob['split'].eq('development'), 'game_date']) & set(policy['reserved_dates'])
    assert not prob.duplicated(key).any() and not dist.duplicated(key).any()
    assert len(prob.loc[prob['split'].eq('development')]) == run['final_fitted_n_probability']
    grid = pd.read_csv(OUT / 'prediction-grid.csv.gz')
    assert np.isfinite(grid.select_dtypes(include='number').to_numpy()).all()
    assert grid['p_home_run'].between(0, 1).all() and grid['p_hit'].between(0, 1).all()
    assert (grid['p_home_run'] <= grid['p_hit'] + 1e-12).all()
    assert np.allclose(grid['p_home_run'] + grid['p_non_hr_hit'], grid['p_hit'])
    assert grid['distance_all_batted_m'].ge(0).all()
    held = pd.read_csv(OUT / 'holdout-predictions.csv', dtype={'game_date': str})
    assert set(held['game_date']) == set(policy['reserved_dates'])
    assert len(held) == run['metrics']['combined_holdout']['probability']['n']
    assert np.allclose(held[[f'pred_{c}' for c in CLASSES]].sum(axis=1), 1)
    for name in ('01-response-maps.png', '02-angle-profiles.png', '03-validation.png',
                 '04-observed-maps.png', '05-sample-counts.png'):
        assert (FIGURES / name).stat().st_size > 10000
    html_doc = (OUT / 'dashboard.html').read_text(encoding='utf-8')
    assert '__PAYLOAD__' not in html_doc and 'const data=' in html_doc
    assert 'fetch(' not in html_doc and '<script src=' not in html_doc
    from PIL import Image
    image_sizes = {}
    for p in FIGURES.glob('*.png'):
        with Image.open(p) as image:
            image.verify()
        with Image.open(p) as image:
            image_sizes[p.name] = list(image.size)
    result = {'status': 'pass', 'checks': ['raw snapshot hashes unchanged', 'population and exclusion counts',
              'required inputs/targets complete', 'zero distances preserved', 'distinct source observation keys',
              'held-out dates excluded from development', 'training features limited to EV/LA',
              'probabilities valid and coherent', 'held-out prediction totals', 'offline dashboard payload', 'readable figure files'],
              'figures': image_sizes, 'reserved_dates': policy['reserved_dates']}
    write_json(OUT / 'verification.json', result)
    print('VERIFICATION', json.dumps(result, ensure_ascii=False), flush=True)


def browser_check():
    edge = Path(r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe')
    if not edge.exists():
        raise RuntimeError('Microsoft Edge is not available for the optional browser check')
    checks = OUT / '_browser-check'
    checks.mkdir(exist_ok=True)
    probe = '''<script>
const checks=[];function snap(){return {distance:el('distance').textContent,hr:el('hr').textContent,hit:el('hit').textContent,support:el('support').textContent};}
checks.push({kind:'initial',...snap()});
el('speed').value='110';el('angle').value='30';el('speed').dispatchEvent(new Event('input'));
checks.push({kind:'slider',...snap()});
document.querySelector('[data-field="hit"]').click();checks.push({kind:'tab',value:field});
el('speed').value='118';el('angle').value='80';el('angle').dispatchEvent(new Event('input'));
checks.push({kind:'low_support',...snap()});
el('speed').value='100';el('angle').value='25';el('speed').dispatchEvent(new Event('input'));
document.querySelector('[data-field="distance"]').click();
checks.push({kind:'canvas',nonblank:ctx.getImageData(200,200,1,1).data[3]===255});
const probeResult=document.createElement('pre');probeResult.id='browser-check';probeResult.textContent=JSON.stringify(checks);document.body.appendChild(probeResult);
</script>'''
    doc = (OUT / 'dashboard.html').read_text(encoding='utf-8')
    page = checks / 'test.html'
    page.write_text(doc.replace('</body>', probe + '</body>'), encoding='utf-8')
    cmd = [str(edge), '--headless=new', '--disable-gpu', '--no-first-run', '--disable-background-networking',
           '--no-default-browser-check', '--allow-file-access-from-files',
           '--user-data-dir=' + str(checks / 'profile'), '--window-size=1400,1200',
           '--screenshot=' + str(OUT / 'dashboard-preview.png'), '--dump-dom', page.as_uri()]
    response = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=45,
                              creationflags=subprocess.CREATE_NO_WINDOW)
    dom = response.stdout.decode('utf-8', errors='replace')
    match = re.search(r'<pre id="browser-check">(.*?)</pre>', dom, flags=re.S)
    if not match:
        (checks / 'browser-errors.txt').write_text(response.stderr.decode('utf-8', errors='replace'), encoding='utf-8')
        raise RuntimeError('Browser did not execute the dashboard probe; see local browser-errors.txt')
    observed = json.loads(html.unescape(match.group(1)))
    grid = pd.read_csv(OUT / 'prediction-grid.csv.gz')
    def expected(speed, angle):
        r = grid.loc[grid['launch_speed'].eq(speed) & grid['launch_angle'].eq(angle)].iloc[0]
        return {'distance': f"{r.distance_all_batted_m:.1f} m", 'hr': f"{r.p_home_run*100:.1f}%", 'hit': f"{r.p_hit*100:.1f}%"}
    for index, point in [(0, expected(100, 25)), (1, expected(110, 30))]:
        assert all(observed[index][k] == v for k, v in point.items()), (observed[index], point)
    assert observed[2]['value'] == 'hit'
    assert observed[3]['distance'] == '표본 부족' and observed[3]['hr'] == '표본 부족'
    assert observed[4]['nonblank']
    result = {'status': 'pass', 'checks': observed, 'browser': 'Microsoft Edge headless',
              'external_network_used_by_dashboard': False}
    write_json(OUT / 'browser-verification.json', result)
    print('BROWSER', json.dumps(result, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['clean', 'fit', 'render', 'verify', 'browser-check', 'all'])
    args = parser.parse_args()
    if args.action in ('clean', 'all'):
        clean()
    if args.action in ('fit', 'all'):
        fit()
    if args.action in ('render', 'all'):
        render()
    if args.action in ('verify', 'all'):
        verify()
    if args.action == 'browser-check':
        browser_check()

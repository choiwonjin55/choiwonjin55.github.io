"""Compare similar 2026 ground balls by base state, using saved sources only.

audit preserves all candidate rows and missingness; analyze uses complete cases.
Outcome is hits per ground ball, not H/AB. No fielding-position causal claim.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATCAST = ROOT / 'data/mlb/2026'
CLUTCH = ROOT / 'data/mlb/clutch-2026'
OUT = CLUTCH / 'groundball-context'
ASSETS = ROOT / 'assets/mlb-clutch-2026'
os.environ.setdefault('MPLCONFIGDIR', str(CLUTCH / '.matplotlib'))
os.environ.setdefault('OPENBLAS_NUM_THREADS', '2')
os.environ.setdefault('OMP_NUM_THREADS', '2')

import numpy as np
import pandas as pd
from scipy import stats

from mlb_pitcher_context_analysis import absorb

LABELS = ['주자 없음', '1루만', '득점권']
SOURCES = [STATCAST / 'manifest.json',
           CLUTCH / 'processed/player-season-inventory.csv',
           CLUTCH / 'pitcher-context/plate-appearances.csv.gz']


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def dump(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n',
                    encoding='utf-8')


def direction(x, y):
    """Coordinate-based direction proxy, not a tracked launch azimuth."""
    return np.degrees(np.arctan2(x - 125.42, 198.27 - y))


def audit():
    manifest = json.loads(SOURCES[0].read_text(encoding='utf-8'))
    columns = ['game_pk', 'at_bat_number', 'pitch_number', 'game_date', 'game_type',
               'type', 'batter', 'pitcher', 'events', 'bb_type', 'des',
               'launch_speed', 'launch_angle', 'hc_x', 'hc_y', 'stand',
               'home_team', 'away_team', 'inning_topbot']
    chunks = []
    for item in manifest['chunks']:
        raw = gzip.decompress((STATCAST / item['path']).read_bytes())
        assert hashlib.sha256(raw).hexdigest() == item['sha256_csv']
        chunks.append(pd.read_csv(io.BytesIO(raw), usecols=columns))
    all_rows = pd.concat(chunks, ignore_index=True)
    assert len(all_rows) == manifest['rows_downloaded']
    inplay = all_rows[(all_rows['type'] == 'X') & (all_rows.game_type == 'R')].copy()
    keys = ['game_pk', 'at_bat_number', 'pitch_number']
    duplicates = inplay.duplicated(keys)
    if duplicates.any():
        for _, group in inplay[inplay.duplicated(keys, keep=False)].groupby(keys):
            assert len(group.drop_duplicates()) == 1, 'Conflicting source rows'
    inplay = inplay.drop_duplicates(keys)
    ground = inplay[inplay.bb_type == 'ground_ball'].copy()
    ground['bunt'] = (ground.des.str.contains(r'\bbunt(?:s|ed|ing)?\b', case=False, na=False)
                      | ground.events.isin(['sac_bunt', 'sac_bunt_double_play']))
    official = pd.read_csv(SOURCES[2])
    official['at_bat_number'] = official.at_bat_index + 1
    keep = ['game_pk', 'at_bat_number', 'batter', 'pitcher', 'event', 'hit',
            'inning', 'outs', 'on_1b', 'on_2b', 'on_3b', 'context_valid',
            'mid_pa_change', 'mid_pa_batter_change']
    ground = ground.merge(official[keep], on=['game_pk', 'at_bat_number'], how='left',
                          suffixes=('', '_pbp'), validate='one_to_one', indicator=True)
    inventory = pd.read_csv(SOURCES[1])
    eligible = inventory[(inventory.season == 2026) & (inventory.ab >= 300)
                         & (inventory.risp_ab >= 75)].player_id
    assert len(eligible) == 237
    ground['eligible_batter'] = ground.batter.isin(eligible)
    ground['batter_match'] = ground.batter == ground.batter_pbp
    ground['pitcher_match'] = ground.pitcher == ground.pitcher_pbp
    ground['state'] = np.where((ground.on_2b == 1) | (ground.on_3b == 1), 2,
                                np.where(ground.on_1b == 1, 1, 0))
    ground['spray_direction'] = direction(ground.hc_x, ground.hc_y)
    ground['fielding_team'] = np.where(ground.inning_topbot == 'Top',
                                        ground.home_team, ground.away_team)
    scope = (ground.eligible_batter & ~ground.bunt & ground.inning.le(9)
             & ground.context_valid.eq(1) & ground.batter_match & ground.pitcher_match
             & ground.mid_pa_change.eq(0) & ground.mid_pa_batter_change.eq(0))
    required = ['launch_speed', 'launch_angle', 'hc_x', 'hc_y', 'stand',
                'outs', 'fielding_team', 'hit', 'event']
    complete = ground[required].notna().all(axis=1)
    # Locations at/behind home do not identify the outgoing ground-ball direction.
    # Retain them in candidates, but do not match on an unreliable direction proxy.
    forward_coordinate = ground.hc_y < 198.27
    ground['analysis_scope'] = scope
    ground['complete_case'] = complete & forward_coordinate
    missing = []
    for state, label in enumerate(LABELS):
        selected = ground[scope & (ground.state == state)]
        missing.append({'state': state, 'label': label, 'n': len(selected),
                        'missing_any_required': int(selected[required].isna().any(axis=1).sum()),
                        'nonforward_coordinate': int((selected[required].notna().all(axis=1)
                                                       & selected.hc_y.ge(198.27)).sum()),
                        'by_field': {key: int(selected[key].isna().sum()) for key in required}})
    result = {
        'source_hashes': {str(p.relative_to(ROOT)): digest(p) for p in SOURCES},
        'source_rows': len(all_rows), 'unique_inplay': len(inplay),
        'duplicate_rows': int(duplicates.sum()), 'ground_balls': len(ground),
        'bunt_candidates': int(ground.bunt.sum()),
        'unmatched_pbp': int((ground['_merge'] != 'both').sum()),
        'batter_mismatch': int((~ground.batter_match).sum()),
        'pitcher_mismatch': int((~ground.pitcher_match).sum()),
        'ground_ball_event_counts': {str(k): int(v) for k, v in ground.event.value_counts().items()},
        'scope_n': int(scope.sum()), 'complete_n': int((scope & ground.complete_case).sum()),
        'missing_required_n': int((scope & ~complete).sum()),
        'nonforward_coordinate_n': int((scope & complete & ~forward_coordinate).sum()),
        'missingness': missing,
        'direction_range': [float(ground.loc[scope & ground.complete_case, 'spray_direction'].min()),
                            float(ground.loc[scope & ground.complete_case, 'spray_direction'].max())],
        'date_range': [str(ground.game_date.min()), str(ground.game_date.max())],
        'policy': 'Original eligible 237 hitters; innings 1-9; exclude bunt candidates, mid-PA changes, unmatched PBP, missing required values, and coordinates at/behind home plate. No imputation.',
        'direction_definition': 'degrees(atan2(hc_x-125.42,198.27-hc_y)); coordinate direction proxy',
        'direction_reference': 'https://beanumber.github.io/abdwr3e/C_statcast.html',
        'field_reference': 'https://baseballsavant.mlb.com/csv-docs',
    }
    OUT.mkdir(parents=True, exist_ok=True)
    ground.to_csv(OUT / 'candidate-ground-balls.csv.gz', index=False, compression='gzip')
    dump(OUT / 'audit.json', result)
    print(json.dumps(result, ensure_ascii=False, indent=2))


def matched_sample(data, widths=(5, 5, 10), min_per_state=2):
    selected = data[data.analysis_scope & data.complete_case].copy()
    columns = []
    for name, width in zip(['launch_speed', 'launch_angle', 'spray_direction'], widths):
        key = name + '_bin'
        selected[key] = np.floor(selected[name] / width).astype(int)
        columns.append(key)
    columns += ['stand', 'outs']
    selected['stratum'] = pd.factorize(pd.MultiIndex.from_frame(selected[columns]))[0]
    counts = selected.groupby(['stratum', 'state']).size().unstack(fill_value=0)
    common = counts.index[(counts.reindex(columns=[0, 1, 2], fill_value=0) >= min_per_state).all(axis=1)]
    matched = selected[selected.stratum.isin(common)].copy().reset_index(drop=True)
    return matched, {'widths': list(widths), 'bin_origin': 0,
                     'intervals': 'left-closed, right-open',
                     'min_per_state_in_stratum': min_per_state,
                     'eligible_complete_n': len(selected), 'matched_n': len(matched),
                     'coverage': len(matched) / len(selected), 'common_strata': len(common)}


def fit(data):
    data = data.reset_index(drop=True)
    groups = [pd.factorize(data[key])[0] for key in ['stratum', 'batter', 'fielding_team']]
    # Keep original precision within matching bins; allow smooth local variation.
    raw = data[['launch_speed', 'launch_angle', 'spray_direction']].to_numpy() / 10
    controls = np.column_stack([raw, raw ** 2, raw[:, 0] * raw[:, 1],
                                 raw[:, 0] * raw[:, 2], raw[:, 1] * raw[:, 2]])
    values = np.column_stack([data.hit, (data.state == 1).astype(float),
                              (data.state == 2).astype(float), controls])
    transformed, iterations = absorb(values, groups, tolerance=1e-10, max_iterations=1000)
    y, x = transformed[:, 0], transformed[:, 1:]
    beta, _, rank, _ = np.linalg.lstsq(x, y, rcond=None)
    assert rank == x.shape[1]
    residual = y - x @ beta
    codes, games = pd.factorize(data.game_pk)
    scores = np.column_stack([np.bincount(codes, weights=x[:, j] * residual)
                               for j in range(x.shape[1])])
    bread = np.linalg.inv(x.T @ x)
    fe_df = sum(len(np.unique(group)) for group in groups) - 2
    correction = len(games) / (len(games) - 1) * (len(data) - 1) / (len(data) - x.shape[1] - fe_df)
    covariance = bread @ (scores.T @ scores) @ bread * correction
    critical = stats.t.ppf(.975, len(games) - 1)
    output = {'n': len(data), 'games': len(games), 'iterations': iterations,
              'method': 'Linear probability model with stratum, batter, and fielding-team fixed effects, continuous speed/angle/direction and quadratic interactions; game-cluster robust CI',
              'comparisons': []}
    for label, vector in [('first_only_minus_empty', [1, 0]),
                           ('risp_minus_empty', [0, 1]),
                           ('risp_minus_first_only', [-1, 1])]:
        vector = np.r_[vector, np.zeros(x.shape[1] - 2)]
        estimate = float(vector @ beta)
        se = float(np.sqrt(vector @ covariance @ vector))
        output['comparisons'].append({'name': label, 'estimate': estimate, 'se': se,
                                      'ci95': [estimate - critical * se, estimate + critical * se],
                                      'p': float(2 * stats.t.sf(abs(estimate / se), len(games) - 1))})
    return output


def analyze():
    audit_result = json.loads((OUT / 'audit.json').read_text(encoding='utf-8'))
    for path, expected in audit_result['source_hashes'].items():
        assert digest(ROOT / path) == expected
    data = pd.read_csv(OUT / 'candidate-ground-balls.csv.gz')
    matched, matching = matched_sample(data)
    cells = []
    for state, label in enumerate(LABELS):
        subset = matched[matched.state == state]
        cells.append({'state': state, 'label': label, 'n': len(subset),
                      'hits': int(subset.hit.sum()), 'rate': float(subset.hit.mean())})
    result = {'scope': audit_result['policy'], 'outcome': 'hits / ground balls; fielding errors and choices remain non-hits',
              'matching': matching, 'cells': cells, 'adjusted': fit(matched),
              'event_counts': {str(k): int(v) for k, v in matched.event.value_counts().items()},
              'sensitivity': [],
              'interpretation': 'Association for comparable ground balls. Starting fielder positions unobserved; no causal attribution to defense.',
              'source_hashes': {str(p.relative_to(ROOT)): digest(p) for p in
                               [OUT / 'audit.json', OUT / 'candidate-ground-balls.csv.gz',
                                Path(__file__), ROOT / 'scripts/mlb_pitcher_context_analysis.py']}}
    for widths in [(5, 10, 10), (3, 5, 10)]:
        selected, match = matched_sample(data, widths)
        result['sensitivity'].append({'matching': match, 'adjusted': fit(selected)})
    dump(OUT / 'results.json', result)
    dump(ASSETS / 'groundball-context-results.json', result)
    matched.to_csv(OUT / 'matched-ground-balls.csv.gz', index=False, compression='gzip')
    figure(result)
    print(json.dumps({key: result[key] for key in ['matching', 'cells', 'adjusted', 'sensitivity']},
                     ensure_ascii=False, indent=2))


def figure(result):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.ticker import FormatStrFormatter
    plt.rcParams.update({'font.family': ['Malgun Gothic', 'DejaVu Sans'],
                         'axes.unicode_minus': False, 'font.size': 12,
                         'axes.spines.top': False, 'axes.spines.right': False,
                         'figure.facecolor': '#fbfaf7', 'axes.facecolor': '#fbfaf7',
                         'savefig.facecolor': '#fbfaf7'})
    fig, ax = plt.subplots(figsize=(10, 4.5), layout='constrained')
    for y, comparison, color in zip([1, 0], result['adjusted']['comparisons'][:2],
                                    ['#df744d', '#157b8c']):
        estimate = comparison['estimate']
        low, high = np.asarray(comparison['ci95'])
        ax.errorbar(estimate, y, xerr=[[estimate - low], [high - estimate]],
                    fmt='o', markersize=9, color=color, capsize=5, linewidth=2)
        ax.text(estimate, y + .20,
                f'{estimate:+.3f}  (95% 신뢰구간 {low:+.3f}~{high:+.3f})',
                ha='center', va='bottom', color=color, fontsize=11, fontweight='bold')
    ax.axvline(0, color='#84959e', lw=1)
    ax.set(yticks=[1, 0], yticklabels=['1루만', '득점권'], ylim=(-.5, 1.6),
           xlim=(-.01, .1), xlabel='주자 없음 대비 땅볼 안타 비율 차이',
           title='비슷한 땅볼의 주자 상황별 안타 비율 차이')
    ax.tick_params(axis='y', length=0, pad=10)
    ax.xaxis.set_major_formatter(FormatStrFormatter('%.3f'))
    ax.spines['left'].set_visible(False)
    fig.savefig(ASSETS / 'groundball-context.png', dpi=180)
    plt.close(fig)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('stage', choices=['audit', 'analyze'])
    stage = parser.parse_args().stage
    audit() if stage == 'audit' else analyze()

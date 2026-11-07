"""Plot every observed WAR/win gap against sorted independent-binomial draws.

Run with scripts/requirements-mlb-war-wins.txt installed. Uses saved inputs only.
The rank intervals are pointwise simulation intervals, not team-specific bounds.
"""
from __future__ import annotations

import argparse
import json
import math
import os
from pathlib import Path
from statistics import mean, pstdev

import numpy as np

from mlb_war_wins_collect import DATA, ROOT, TEAM_IDS, YEARS, digest, save_json
from mlb_war_wins_probability import binomial_pmf

ASSETS = ROOT/'assets/mlb-war-wins'


def validate_rows(base):
    rows = base['rows']
    keys = {(r['season'], r['team_id']) for r in rows}
    required = {(year, team) for year in YEARS for team in TEAM_IDS.values()}
    if base['status'] != 'complete' or len(rows) != 150 or keys != required:
        raise ValueError('Exactly 150 unique, complete team-seasons required')
    for r in rows:
        n, wins, mu = r['games'], r['wins'], r['fwar_expected']
        if not isinstance(n, int) or not isinstance(wins, int) or not 0 <= wins <= n:
            raise ValueError('Invalid games or wins')
        if not math.isfinite(mu) or not 0 < mu < n:
            raise ValueError('Invalid binomial mean')
        if not math.isclose(mu, 48*n/162+r['fwar'], abs_tol=1e-9):
            raise ValueError('WAR-based mean does not reconcile')
        if not math.isclose(wins-mu, r['fwar_error'], abs_tol=1e-9):
            raise ValueError('Gap sign or value does not reconcile')
    return sorted(rows, key=lambda r: (r['season'], r['team_id']))


def exact_reference(rows):
    """Moments of the equal-weight theoretical residual mixture; no normal fit."""
    gaps = [r['wins']-r['fwar_expected'] for r in rows]
    maximum = max(map(abs, gaps))
    variances, absolute_means, max_cdfs = [], [], []
    for r in rows:
        n, mu = r['games'], r['fwar_expected']
        p = mu/n
        masses = binomial_pmf(n, p)
        variances.append(n*p*(1-p))
        absolute_means.append(math.fsum(abs(k-mu)*v for k, v in enumerate(masses)))
        max_cdfs.append(math.fsum(v for k, v in enumerate(masses)
                                  if abs(k-mu) <= maximum+1e-12))
    return dict(
        observed=dict(mean=mean(gaps), sd=pstdev(gaps),
                      mae=mean(map(abs, gaps)), rmse=math.sqrt(mean(x*x for x in gaps)),
                      maximum_absolute=maximum),
        model=dict(mean=0., sd=math.sqrt(mean(variances)),
                   mae=mean(absolute_means), rmse=math.sqrt(mean(variances)),
                   probability_maximum_at_most_observed=math.prod(max_cdfs)))


def simulate(rows, repetitions=100000, seed=20261107):
    if repetitions < 1000:
        raise ValueError('At least 1000 simulations required for rank intervals')
    n = np.array([r['games'] for r in rows])
    mu = np.array([r['fwar_expected'] for r in rows])
    actual = np.array([r['wins'] for r in rows])-mu
    rng = np.random.Generator(np.random.PCG64(seed))
    ordered = np.empty((repetitions, len(rows)))
    statistics = {name: np.empty(repetitions) for name in ('sd', 'rmse', 'mae', 'maximum')}
    for start in range(0, repetitions, 1000):
        stop = min(repetitions, start+1000)
        gaps = rng.binomial(n, mu/n, size=(stop-start, len(rows)))-mu
        statistics['sd'][start:stop] = gaps.std(axis=1, ddof=0)
        statistics['rmse'][start:stop] = np.sqrt(np.mean(gaps*gaps, axis=1))
        statistics['mae'][start:stop] = np.abs(gaps).mean(axis=1)
        statistics['maximum'][start:stop] = np.abs(gaps).max(axis=1)
        gaps.sort(axis=1)
        ordered[start:stop] = gaps
    lower, center, upper = np.quantile(ordered, [.025, .5, .975], axis=0,
                                       method='inverted_cdf')
    ranks = [dict(rank=i+1, lower=float(lo), median=float(mid), upper=float(hi))
             for i, (lo, mid, hi) in enumerate(zip(lower, center, upper))]
    actual_values = dict(sd=float(actual.std(ddof=0)),
                         rmse=float(np.sqrt(np.mean(actual*actual))),
                         mae=float(np.abs(actual).mean()), maximum=float(np.abs(actual).max()))
    checks = {}
    for name, samples in statistics.items():
        count = int(np.count_nonzero(samples <= actual_values[name]+1e-12))
        checks[name] = dict(observed=actual_values[name],
                            model_median=float(np.median(samples)),
                            model_interval_95=np.quantile(samples, [.025, .975]).tolist(),
                            at_most_observed=count,
                            lower_tail_mc_p=(count+1)/(repetitions+1))
    return dict(repetitions=repetitions, seed=seed, generator='NumPy PCG64',
                numpy_version=np.__version__, ranks=ranks, checks=checks)


def analyze(base, repetitions=100000, seed=20261107):
    rows = validate_rows(base)
    codes = {tid: code for code, tid in TEAM_IDS.items()}
    actual = [dict(r, rank=i+1, code=codes[r['team_id']]) for i, r in enumerate(
        sorted(rows, key=lambda r: (r['fwar_error'], r['season'], r['team_id'])))]
    return dict(n=len(actual), rows=actual, **exact_reference(rows),
                simulation=simulate(rows, repetitions, seed),
                methods=dict(
                    gap='Actual wins minus (48*games/162 + fWAR); original precision retained.',
                    display='One bar per team-season, sorted by observed gap; no grouping or histogram bins.',
                    model='Independent Binomial(games, WAR-based wins/games) for each of the same 150 records. No refitting or rescaling.',
                    rank_curve='Sort all 150 simulated residuals separately in every repetition. Plot their pointwise 2.5%, 50% and 97.5% quantiles at the same rank as the observed bars; these are not predictions for the team occupying that rank.',
                    checks='Lower-tail simulation comparisons of descriptive population SD, RMSE, MAE and cohort maximum. Monte Carlo p uses (count+1)/(repetitions+1). No test is applied to 150 correlated order statistics.',
                    limitations='Conditional same-season model; WAR and actual outcomes share performance inputs. Schedule constraints, dependence and WAR uncertainty are not modeled. Compatibility of one extreme is not a goodness-of-fit result for the full distribution.'),
                references=[
                    'https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.binom.html',
                    'https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.monte_carlo_test.html'])


def render(result):
    os.environ.setdefault('MPLCONFIGDIR', str(DATA/'.matplotlib'))
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt

    plt.rcParams.update({'font.family': ['Malgun Gothic', 'DejaVu Sans'], 'font.size': 12,
                         'axes.unicode_minus': False, 'axes.spines.top': False,
                         'axes.spines.right': False, 'figure.facecolor': '#fbfaf7',
                         'axes.facecolor': '#fbfaf7', 'savefig.facecolor': '#fbfaf7',
                         'svg.hashsalt': 'mlb-war-wins-gaps'})
    x = [r['rank'] for r in result['rows']]
    ranks = result['simulation']['ranks']
    fig, ax = plt.subplots(figsize=(12, 6.5), layout='constrained')
    ax.fill_between(x, [r['lower'] for r in ranks], [r['upper'] for r in ranks],
                    color='#b6bfc1', alpha=.35, linewidth=0, label='이항모형 순위별 95% 구간')
    ax.bar(x, [r['fwar_error'] for r in result['rows']], color='#157b8c', width=.78,
           label='실제 차이', zorder=3)
    ax.plot(x, [r['median'] for r in ranks], color='#df744d', lw=2,
            label='이항모형 순위별 중앙값', zorder=4)
    ax.axhline(0, color='#839397', lw=.8)
    ax.set(xlim=(0, 151), xticks=[1, 25, 50, 75, 100, 125, 150],
           xlabel='승수 차이 순위 (작은 순)', ylabel='실제 − WAR 기반 승수 (승)',
           title='2022~2026 MLB · 150개 팀·시즌의 승수 차이')
    ax.grid(axis='y', alpha=.13)
    ax.legend(frameon=False, loc='upper left', fontsize=10)
    fig.savefig(ASSETS/'win-gap-bars.png', dpi=180)
    fig.savefig(ASSETS/'win-gap-bars.svg', metadata={'Date': None})
    plt.close(fig)

    template = (ROOT/'scripts/mlb_war_wins_gap_bars.html').read_text(encoding='utf-8')
    if template.count('__GAP_PAYLOAD__') != 1:
        raise ValueError('Exactly one graph payload required')
    encoded = json.dumps(result, ensure_ascii=False, allow_nan=False,
                         separators=(',', ':')).replace('<', '\\u003c')
    (ROOT/'scripts/mlb-war-wins-gap-bars.html').write_text(
        template.replace('__GAP_PAYLOAD__', encoded), encoding='utf-8')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repetitions', type=int, default=100000)
    parser.add_argument('--seed', type=int, default=20261107)
    args = parser.parse_args()
    source = ASSETS/'results.json'
    result = analyze(json.loads(source.read_text(encoding='utf-8')), args.repetitions, args.seed)
    result.update(base_result_sha256=digest(source.read_bytes()),
                  code_sha256=digest(Path(__file__).read_bytes()),
                  template_sha256=digest((ROOT/'scripts/mlb_war_wins_gap_bars.html').read_bytes()))
    save_json(ASSETS/'win-gap-model.json', result)
    save_json(DATA/'analysis/win-gap-model.json', result)
    render(result)
    print(json.dumps({k: result[k] for k in ('n', 'observed', 'model')}, ensure_ascii=False))
    print(json.dumps(result['simulation']['checks'], ensure_ascii=False))


if __name__ == '__main__':
    main()

"""Compare all observed WAR/win gaps with fitted-normal quantiles, without bins.

Install scripts/requirements-mlb-war-wins.txt and run this file from the repo.
This estimates a descriptive distribution, not new WAR-to-win coefficients.
"""
from __future__ import annotations

import json
import math
import os
from pathlib import Path
from statistics import NormalDist

import numpy as np
from scipy import stats
from scipy import __version__ as scipy_version

from mlb_war_wins_collect import DATA, ROOT, digest, save_json
from mlb_war_wins_gaps import validate_rows

ASSETS = ROOT/'assets/mlb-war-wins'


def normal_qq(rows):
    if len(rows) < 3:
        raise ValueError('At least three observations required')
    ordered = sorted(rows, key=lambda r: (r['fwar_error'], r['season'], r['team_id']))
    errors = np.array([r['fwar_error'] for r in ordered], dtype=float)
    if not np.isfinite(errors).all():
        raise ValueError('Finite gaps required; no observations are dropped')
    mu, sigma = float(errors.mean()), float(errors.std(ddof=0))
    if sigma == 0:
        raise ValueError('Nonzero scale required for a normal Q-Q comparison')
    normal = NormalDist(mu, sigma)
    points = []
    for rank, row in enumerate(ordered, start=1):
        probability = (rank-.5)/len(ordered)
        points.append(dict(row, rank=rank, probability=probability,
                           normal_quantile=normal.inv_cdf(probability)))
    test = stats.shapiro(errors)
    return dict(n=len(points), mean=mu, sd=sigma, sd_ddof=0, points=points,
                skewness=float(stats.skew(errors, bias=False)),
                excess_kurtosis=float(stats.kurtosis(errors, bias=False)),
                shapiro=dict(statistic=float(test.statistic), p_value=float(test.pvalue),
                             status='Exploratory; assumes independent identically distributed observations, not established for this pooled cohort.'),
                qq_correlation=float(np.corrcoef(
                    [p['normal_quantile'] for p in points], errors)[0, 1]))


def analyze(base):
    rows = validate_rows(base)
    return dict(**normal_qq(rows),
                seasons={str(year): normal_qq([r for r in rows if r['season'] == year])
                         for year in sorted({r['season'] for r in rows})},
                methods=dict(
                    gap='Actual wins minus (48*games/162 + fWAR). Keep original values, all 150 team-seasons and negative gaps.',
                    ordering='Sort original gaps, breaking ties by season and MLB team ID; one point per team-season, without bins.',
                    positions='Hazen plotting positions p_i=(i-0.5)/n, i=1,...,n.',
                    reference='Normal quantiles mu+sigma*Phi^-1(p_i); mu and sigma (population SD, ddof=0) estimated from these gaps. Reference line y=x; no regression refit.',
                    interpretation='Descriptive distribution shape only; fitted location and scale do not validate WAR, causality, random luck or future predictions. Shapiro results are exploratory because independence and a common distribution are not established.',
                    distinction='The plotted normal is fitted to the actual gaps; this is not the previous independent-game binomial model.'),
                references=[
                    'https://www.itl.nist.gov/div898/handbook/eda/section3/normprpl.htm',
                    'https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.shapiro.html'])


def render(result):
    os.environ.setdefault('MPLCONFIGDIR', str(DATA/'.matplotlib'))
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt

    plt.rcParams.update({'font.family': ['Malgun Gothic', 'DejaVu Sans'],
                         'font.size': 12, 'axes.unicode_minus': False,
                         'axes.spines.top': False, 'axes.spines.right': False,
                         'figure.facecolor': '#fbfaf7', 'axes.facecolor': '#fbfaf7',
                         'savefig.facecolor': '#fbfaf7', 'svg.hashsalt': 'mlb-war-wins-qq'})
    x = [p['normal_quantile'] for p in result['points']]
    y = [p['fwar_error'] for p in result['points']]
    low = math.floor(min(x+y)/5)*5
    high = math.ceil(max(x+y)/5)*5
    fig, ax = plt.subplots(figsize=(8, 7), layout='constrained')
    ax.plot([low, high], [low, high], color='#df744d', lw=1.7,
            label='정규분포 기준선', zorder=2)
    ax.scatter(x, y, color='#157b8c', edgecolor='#fbfaf7', linewidth=.5,
               s=30, alpha=.85, label='실제 차이', zorder=3)
    ax.set(xlim=(low-.5, high+.5), ylim=(low-.5, high+.5),
           xlabel='정규분포 분위수 (승)', ylabel='실제 − WAR 기반 승수 (승)',
           title='2022~2026 MLB · 승수 차이의 Q-Q 플롯', aspect='equal')
    ax.set_xticks(range(low, high+1, 5))
    ax.set_yticks(range(low, high+1, 5))
    ax.grid(alpha=.13)
    ax.legend(frameon=False, loc='upper left', fontsize=11)
    fig.savefig(ASSETS/'win-gap-qq.png', dpi=180)
    svg_path = ASSETS/'win-gap-qq.svg'
    fig.savefig(svg_path, metadata={'Date': None})
    svg_path.write_text('\n'.join(line.rstrip() for line in
                        svg_path.read_text(encoding='utf-8').splitlines())+'\n', encoding='utf-8', newline='\n')
    plt.close(fig)


def main():
    source = ASSETS/'results.json'
    result = analyze(json.loads(source.read_text(encoding='utf-8')))
    result.update(base_result_sha256=digest(source.read_bytes()),
                  code_sha256=digest(Path(__file__).read_bytes()),
                  numpy_version=np.__version__, scipy_version=scipy_version)
    save_json(ASSETS/'qq.json', result)
    save_json(DATA/'analysis/qq.json', result)
    render(result)
    print(json.dumps({k: result[k] for k in ('n', 'mean', 'sd', 'qq_correlation', 'shapiro')},
                     ensure_ascii=False))


if __name__ == '__main__':
    main()

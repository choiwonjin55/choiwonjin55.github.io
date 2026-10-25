"""Count official RISP-AVG advantages and their 2025-to-2026 transitions.

Offline: reuse saved official integer H/AB, original eligibility and cohorts.
"""
from pathlib import Path
import hashlib
import json
import os

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'data/mlb/clutch-2026'
ASSETS = ROOT / 'assets/mlb-clutch-2026'
os.environ.setdefault('MPLCONFIGDIR', str(DATA / '.matplotlib'))

import numpy as np
import pandas as pd
from scipy import stats


def signs(frame, suffix=''):
    """Compare exact fractions, retaining distinctions hidden by rounded AVG."""
    counts = {key: frame[key + suffix].to_numpy(dtype=np.int64)
              for key in ('ab', 'h', 'risp_ab', 'risp_h')}
    assert (counts['ab'] > 0).all() and (counts['risp_ab'] > 0).all()
    return np.sign(counts['risp_h'] * counts['ab'] - counts['h'] * counts['risp_ab'])


def transition_summary(pair):
    first, second = signs(pair, '_2025'), signs(pair, '_2026')
    matrix = np.array([[int(((first == a) & (second == b)).sum()) for b in (-1, 0, 1)]
                       for a in (-1, 0, 1)])
    positive_2025 = int((first > 0).sum())
    positive_2026 = int((second > 0).sum())
    retained = int(((first > 0) & (second > 0)).sum())
    negative_2025 = int((first < 0).sum())
    became_positive = int(((first < 0) & (second > 0)).sum())
    binary = [[retained, positive_2025 - retained],
              [int(((first <= 0) & (second > 0)).sum()),
               int(((first <= 0) & (second <= 0)).sum())]]
    return {'n': len(pair), 'matrix_sign_order': [-1, 0, 1], 'matrix': matrix.tolist(),
            'positive_2025': positive_2025, 'positive_2026': positive_2026,
            'retained_positive': retained, 'positive_retention': retained / positive_2025,
            'negative_2025': negative_2025, 'negative_to_positive': became_positive,
            'negative_to_positive_rate': became_positive / negative_2025,
            'random_expected_retention': positive_2026 / len(pair),
            'positive_retention_upper_p': float(stats.hypergeom.sf(retained - 1, len(pair),
                                                                 positive_2026, positive_2025)),
            'binary_association_fisher_two_sided_p': float(stats.fisher_exact(binary).pvalue)}


def figure(frame):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.ticker import FormatStrFormatter
    plt.rcParams.update({'font.family': ['Malgun Gothic', 'DejaVu Sans'],
                         'axes.unicode_minus': False, 'font.size': 11,
                         'axes.spines.top': False, 'axes.spines.right': False,
                         'figure.facecolor': '#fbfaf7', 'axes.facecolor': '#fbfaf7',
                         'savefig.facecolor': '#fbfaf7'})
    sign = signs(frame)
    x = frame.h / frame.ab
    y = frame.risp_h / frame.risp_ab
    delta = y - x
    colors = {1: '#157b8c', -1: '#84959e', 0: '#df744d'}
    fig, axes = plt.subplots(1, 2, figsize=(13, 5.5), layout='constrained')
    for value, text in [(1, '득타율 > 타율'), (-1, '득타율 < 타율'), (0, '같음')]:
        mask = sign == value
        if mask.any():
            count = int(mask.sum())
            axes[0].scatter(x[mask], y[mask], s=28, color=colors[value], alpha=.75,
                            label=f'{text} · {count}명 ({count / len(frame):.1%})')
    lo = min(x.min(), y.min()) - .01
    hi = max(x.max(), y.max()) + .05
    axes[0].plot([lo, hi], [lo, hi], color='#768897', ls='--', lw=1, zorder=0)
    axes[0].set(xlim=(lo, hi), ylim=(lo, hi), xlabel='전체 타율', ylabel='득점권 타율',
                title='2026년 선수별 타율과 득타율')
    axes[0].set_aspect('equal', adjustable='box')
    axes[0].xaxis.set_major_formatter(FormatStrFormatter('%.3f'))
    axes[0].yaxis.set_major_formatter(FormatStrFormatter('%.3f'))
    axes[0].legend(loc='upper left', fontsize=9, frameon=False)

    edges = np.linspace(-.18, .18, 25)
    counts, _ = np.histogram(delta, bins=edges)
    assert int(counts.sum()) == len(frame)
    mid = (edges[1:] + edges[:-1]) / 2
    axes[1].bar(mid, counts, width=np.diff(edges),
                color=np.where(mid >= 0, colors[1], colors[-1]), alpha=.85)
    axes[1].axvline(0, color='#768897', lw=1)
    axes[1].xaxis.set_major_formatter(FormatStrFormatter('%.3f'))
    axes[1].set(xlabel='득타율 − 전체 타율', ylabel='선수 수',
                title='2026년 선수별 차이의 분포')
    fig.savefig(ASSETS / 'positive-gap-overview.png', dpi=180)
    plt.close(fig)


def main():
    frames, hashes, yearly = {}, {}, {}
    for year in (2025, 2026):
        sources = {}
        for kind in ('season', 'risp'):
            path = DATA / f'raw/{year}-players-{kind}.json'
            raw = path.read_bytes()
            hashes[str(path.relative_to(ROOT))] = hashlib.sha256(raw).hexdigest()
            splits = json.loads(raw)['stats'][0]['splits']
            sources[kind] = {s['player']['id']: s for s in splits}
            assert len(sources[kind]) == len(splits)
        rows = []
        for pid, split in sources['season'].items():
            total = split['stat']
            risp = sources['risp'].get(pid)
            if risp is None or total['atBats'] < 300 or risp['stat']['atBats'] < 75:
                continue
            risp = risp['stat']
            rows.append({'player_id': pid, 'name': split['player']['fullName'],
                         'ab': total['atBats'], 'h': total['hits'],
                         'risp_ab': risp['atBats'], 'risp_h': risp['hits']})
        frame = pd.DataFrame(rows).sort_values('player_id').reset_index(drop=True)
        frames[year] = frame
        sign = signs(frame)
        yearly[str(year)] = {'n': len(frame), 'positive': int((sign > 0).sum()),
                              'equal': int((sign == 0).sum()), 'negative': int((sign < 0).sum()),
                              'positive_share': float((sign > 0).mean())}
    pair = frames[2025].merge(frames[2026], on='player_id', suffixes=('_2025', '_2026'),
                              validate='one_to_one')
    saved_pair = pd.read_csv(DATA / 'analysis/paired-players.csv')
    assert set(pair.player_id) == set(saved_pair.player_id)
    transition = transition_summary(pair)
    hashes[str(Path(__file__).relative_to(ROOT))] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    result = {'definition': 'Official H/AB in RISP minus overall; strict positive via integer cross-products',
              'eligibility': 'Overall AB >=300 and RISP AB >=75, separately in each season',
              'yearly': yearly, 'paired': transition, 'source_hashes': hashes}
    encoded = json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + '\n'
    (DATA / 'analysis/positive-gap.json').write_text(encoded, encoding='utf-8')
    (ASSETS / 'positive-gap-results.json').write_text(encoded, encoding='utf-8')
    figure(frames[2026])
    print(json.dumps({'yearly': yearly, 'paired': transition}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()

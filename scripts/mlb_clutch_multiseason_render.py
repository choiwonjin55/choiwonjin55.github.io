"""Render four-season article figures and interactive charts from saved results."""
from pathlib import Path
import json
import os

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / 'assets/mlb-clutch-2026'
os.environ.setdefault('MPLCONFIGDIR', str(ROOT / 'data/mlb/clutch-2026/.matplotlib'))

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.ticker import FormatStrFormatter
import numpy as np


def main():
    result = json.loads((ASSETS / 'four-season-results.json').read_text(encoding='utf-8'))
    pairs, years = result['pairs'], result['yearly']
    latest = pairs['2025-2026']
    payload = {'default_pair': '2025-2026', 'pairs': pairs,
               'players': latest['players'], 'persistence': latest['persistence']}
    template = (ROOT / 'scripts/mlb_clutch_dashboard.html').read_text(encoding='utf-8')
    encoded = json.dumps(payload, ensure_ascii=False, allow_nan=False).replace('<', '\\u003c')
    assert template.count('__CLUTCH_PAYLOAD__') == 1
    (ROOT / 'scripts/mlb-clutch-dashboard.html').write_text(template.replace('__CLUTCH_PAYLOAD__', encoded), encoding='utf-8')
    template = (ROOT / 'scripts/mlb_clutch_season_overview.html').read_text(encoding='utf-8')
    encoded = json.dumps({'years': years}, ensure_ascii=False, allow_nan=False).replace('<', '\\u003c')
    assert template.count('__FOUR_SEASON_OVERVIEW__') == 1
    (ROOT / 'scripts/mlb-clutch-season-overview.html').write_text(template.replace('__FOUR_SEASON_OVERVIEW__', encoded), encoding='utf-8')

    plt.rcParams.update({'font.family': ['Malgun Gothic', 'DejaVu Sans'],
                         'axes.unicode_minus': False, 'font.size': 11,
                         'axes.spines.top': False, 'axes.spines.right': False,
                         'figure.facecolor': '#fbfaf7', 'axes.facecolor': '#fbfaf7',
                         'savefig.facecolor': '#fbfaf7'})
    teal, orange, gray = '#157b8c', '#df744d', '#768897'
    fig, axes = plt.subplots(2, 2, figsize=(12, 11), layout='constrained')
    all_rates = [p[value] for year in years.values() for p in year['players'] for value in ('avg', 'risp_avg')]
    low, high = min(all_rates) - .01, max(all_rates) + .03
    for ax, (year, data) in zip(axes.flat, years.items()):
        for positive, color in [(False, gray), (True, teal)]:
            selected = [p for p in data['players'] if (p['risp_h'] * p['ab'] > p['h'] * p['risp_ab']) == positive]
            ax.scatter([p['avg'] for p in selected], [p['risp_avg'] for p in selected], s=20, color=color, alpha=.7)
        ax.plot([low, high], [low, high], color=gray, ls='--', lw=1)
        ax.set(xlim=(low, high), ylim=(low, high), xlabel='전체 타율', ylabel='득타율',
               title=f"{year}년 · 높은 선수 {data['positive']}/{data['n']}명")
        ax.xaxis.set_major_formatter(FormatStrFormatter('%.3f'))
        ax.yaxis.set_major_formatter(FormatStrFormatter('%.3f'))
    fig.savefig(ASSETS / 'four-season-overview.png', dpi=180)
    plt.close(fig)

    fig, axes = plt.subplots(1, 3, figsize=(15, 5), layout='constrained')
    for ax, pair in zip(axes, pairs.values()):
        before, after = pair['before'], pair['after']
        x = np.array([p[f'delta_{before}'] for p in pair['players']])
        y = np.array([p[f'delta_{after}'] for p in pair['players']])
        ax.scatter(x, y, color=teal, alpha=.7, s=22)
        slope, intercept = np.polyfit(x, y, 1)
        limits = [min(x.min(), y.min()) - .01, max(x.max(), y.max()) + .01]
        ax.plot(limits, intercept + slope * np.asarray(limits), color=orange)
        ax.axhline(0, color=gray, lw=.7)
        ax.axvline(0, color=gray, lw=.7)
        ax.set(xlim=limits, ylim=limits, xlabel=f'{before}년 차이', ylabel=f'{after}년 차이',
               title=f"{before}→{after} · r={pair['persistence']['delta']['pearson']:.3f}")
        ax.xaxis.set_major_formatter(FormatStrFormatter('%.3f'))
        ax.yaxis.set_major_formatter(FormatStrFormatter('%.3f'))
    fig.savefig(ASSETS / 'four-season-persistence.png', dpi=180)
    plt.close(fig)

    fig, axes = plt.subplots(2, 3, figsize=(15, 9), layout='constrained')
    for column, pair in enumerate(pairs.values()):
        ax, counts = axes[0, column], axes[1, column]
        before, after = pair['before'], pair['after']
        for group, color, label in zip(pair['tails']['groups'], [teal, orange], ['하위권', '상위권']):
            values = [group['mean_before'], group['mean_after']]
            ax.plot([0, 1], values, marker='o', color=color, label=label)
            low, high = group['mean_after_95']
            ax.errorbar(1, values[1], yerr=[[values[1] - low], [high - values[1]]], color=color, capsize=4)
        ax.plot([0, 1], [pair['mean_before'], pair['mean_after']], marker='o', color=gray, ls='--', label='공통 선수 평균')
        ax.axhline(0, color=gray, lw=.7)
        ax.set(xticks=[0, 1], xticklabels=[str(before), str(after)], xlim=(-.15, 1.25),
               title=f'{before}→{after}', ylabel='평균 득타율 − 전체 타율')
        ax.yaxis.set_major_formatter(FormatStrFormatter('%.3f'))
        ax.legend(fontsize=9)
        groups = pair['tails']['groups']
        for index, group in enumerate(groups):
            counts.bar(index, group['retained'], color=[teal, orange][index], width=.5)
            counts.text(index, group['retained'] + .2, f"{group['retained']}명", ha='center')
        expected = groups[0]['expected_retained']
        counts.axhline(expected, color=gray, ls='--', label=f'기대 인원 약 {expected:.1f}명')
        counts.set(xticks=[0, 1], xticklabels=['하위권 유지', '상위권 유지'], ylim=(0, 12), ylabel='다음 해 같은 집단에 남은 선수 수')
        counts.legend(fontsize=9)
    fig.savefig(ASSETS / 'four-season-groups.png', dpi=180)
    plt.close(fig)
    print('Rendered four-season overview, three comparison pairs, and tail-group figures.')


if __name__ == '__main__':
    main()

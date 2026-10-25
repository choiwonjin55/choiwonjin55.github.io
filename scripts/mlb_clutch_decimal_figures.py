"""Render saved persistence/group results with decimal baseball rate labels."""
from pathlib import Path
import json
import os

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'data/mlb/clutch-2026'
ASSETS = ROOT / 'assets/mlb-clutch-2026'
os.environ.setdefault('MPLCONFIGDIR', str(DATA / '.matplotlib'))

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.ticker import FormatStrFormatter
import numpy as np
import pandas as pd


def main():
    result = json.loads((ASSETS / 'results.json').read_text(encoding='utf-8'))['primary']
    paired = pd.read_csv(DATA / 'analysis/paired-players.csv')
    plt.rcParams.update({'font.family': ['Malgun Gothic', 'DejaVu Sans'],
                         'axes.unicode_minus': False, 'font.size': 11,
                         'axes.spines.top': False, 'axes.spines.right': False,
                         'figure.facecolor': '#fbfaf7', 'axes.facecolor': '#fbfaf7',
                         'savefig.facecolor': '#fbfaf7'})
    teal, orange, gray = '#157b8c', '#df744d', '#768897'
    fig, axes = plt.subplots(1, 2, figsize=(13, 5.5), layout='constrained')
    for ax, metric, label in zip(axes, ['delta', 'avg'], ['득타율 − 전체 타율', '전체 타율']):
        x, y = paired[f'{metric}_2025'], paired[f'{metric}_2026']
        for group, text, color in [('middle', '중간 60%', gray),
                                    ('top', '2025년 상위 20%', orange),
                                    ('bottom', '2025년 하위 20%', teal)]:
            mask = paired.group_2025 == group
            ax.scatter(x[mask], y[mask], s=25, color=color, label=text, alpha=.8)
        if metric == 'delta':
            ax.axhline(0, color=gray, lw=.7)
            ax.axvline(0, color=gray, lw=.7)
        slope, intercept = np.polyfit(x, y, 1)
        limits = [min(x.min(), y.min()) - .01, max(x.max(), y.max()) + .01]
        ax.plot(limits, np.asarray(limits) * slope + intercept, color=orange, lw=1.5)
        ax.set(xlim=limits, ylim=limits, xlabel=f'2025년 {label}', ylabel=f'2026년 {label}',
                title=f"{label} · r={result['persistence'][metric]['pearson']:.3f}")
        ax.xaxis.set_major_formatter(FormatStrFormatter('%.3f'))
        ax.yaxis.set_major_formatter(FormatStrFormatter('%.3f'))
        ax.set_aspect('equal', adjustable='box')
    axes[0].legend(fontsize=9)
    fig.suptitle(f'같은 선수 {len(paired)}명의 연도 간 비교', fontsize=17)
    fig.savefig(ASSETS / 'persistence.png', dpi=180)
    plt.close(fig)

    fig, axes = plt.subplots(1, 2, figsize=(13, 5), layout='constrained')
    groups = result['groups_delta']['groups']
    means = [paired[f'delta_{year}'].mean() for year in (2025, 2026)]
    for group, color, label in zip(groups, [teal, orange], ['2025년 하위 20%', '2025년 상위 20%']):
        values = np.asarray([group['mean_2025'], group['mean_2026']])
        axes[0].plot([0, 1], values, marker='o', color=color, lw=2, label=label)
        low, high = group['mean_2026_95']
        axes[0].errorbar(1, values[1], yerr=[[values[1] - low], [high - values[1]]],
                          color=color, capsize=5)
    axes[0].plot([0, 1], means, marker='o', color=gray, ls='--', lw=1.5,
                  label='공통 선수 전체 평균')
    axes[0].axhline(0, color=gray, lw=.8)
    axes[0].set(xticks=[0, 1], xticklabels=['2025', '2026'], xlim=(-.2, 1.25),
                 ylabel='평균 득타율 − 전체 타율', title='상·하위권의 다음 해 평균과 95% 신뢰구간')
    axes[0].yaxis.set_major_formatter(FormatStrFormatter('%.3f'))
    axes[0].legend(fontsize=9)
    for index, group in enumerate(groups):
        axes[1].bar(index, group['retained'], color=[teal, orange][index], width=.5)
        axes[1].text(index, group['retained'] + .3, f"{group['retained']}명", ha='center')
    expected = groups[0]['null_retention_expected'] * groups[0]['n']
    axes[1].axhline(expected, color=gray, ls='--',
                     label=f'무작위 기대 인원 · 약 {expected:.1f}명')
    axes[1].set(xticks=[0, 1], xticklabels=['하위권 유지', '상위권 유지'],
                 ylim=(0, max(12, max(group['retained'] for group in groups) + 3)),
                 ylabel='2026년 같은 집단에 남은 선수 수', title='같은 순위 집단에 남은 인원')
    axes[1].legend(fontsize=9)
    fig.savefig(ASSETS / 'groups.png', dpi=180)
    plt.close(fig)
    print('Rendered persistence.png and groups.png with decimal rate labels.')


if __name__ == '__main__':
    main()

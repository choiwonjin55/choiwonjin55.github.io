"""Plot the RISP average gap from saved results, without rerunning analysis."""
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
    result = json.loads((ASSETS / 'results.json').read_text(encoding='utf-8'))
    distribution = result['primary']['distribution_2026']
    saved = distribution['figure_data']
    observed = np.asarray(saved['qq_observed'])
    edges = np.asarray(saved['edges'])
    mean = distribution['mean_delta']
    low, high = np.asarray(distribution['null_mean_95'])
    assert len(observed) == distribution['n']
    assert np.isclose(observed.mean(), mean)
    assert len(observed) == np.histogram(observed, bins=edges)[0].sum()

    plt.rcParams.update({
        'font.family': ['Malgun Gothic', 'DejaVu Sans'],
        'axes.unicode_minus': False,
        'font.size': 12,
        'axes.spines.top': False,
        'axes.spines.right': False,
        'figure.facecolor': '#fbfaf7',
        'axes.facecolor': '#fbfaf7',
        'savefig.facecolor': '#fbfaf7',
    })
    teal, orange, gray = '#157b8c', '#df744d', '#768897'
    fig, axes = plt.subplots(2, 1, figsize=(10, 8.6),
                             gridspec_kw={'height_ratios': [2.4, 1]},
                             layout='constrained')
    ax = axes[0]
    ax.hist(observed, bins=edges, color=teal, alpha=.8,
            label=f"실제 선수 {distribution['n']}명")
    midpoint = (edges[:-1] + edges[1:]) / 2
    ax.plot(midpoint, saved['null_hist_mean'], color=orange, lw=2,
            label='무작위 배정 평균')
    ax.fill_between(midpoint, saved['null_hist_low'], saved['null_hist_high'],
                    color=orange, alpha=.15, label='구간별 모의 결과 95% 범위')
    ax.axvline(0, color=gray, lw=1)
    ax.set(title='2026년 선수별 득타율과 타율의 차이',
           xlabel='득타율 − 전체 타율', ylabel='선수 수')
    ax.xaxis.set_major_formatter(FormatStrFormatter('%.3f'))
    ax.legend(fontsize=11, loc='upper right', frameon=False)

    ax = axes[1]
    ax.hlines(0, low, high, color=orange, lw=8, alpha=.7)
    ax.vlines([low, high], -.08, .08, color=orange, lw=2)
    ax.scatter(mean, 1, color=teal, s=100, zorder=3)
    ax.text(mean, 1.20, f'{mean:+.3f}', color=teal,
            ha='center', va='bottom', fontweight='bold')
    ax.text((low + high) / 2, .20, f'{low:+.3f}~{high:+.3f}',
            color=orange, ha='center', va='bottom', fontweight='bold')
    ax.axvline(0, color=gray, lw=1)
    ax.set(yticks=[0, 1], yticklabels=['무작위 배정\n평균의 95% 범위', '실제 평균'],
           ylim=(-.35, 1.6), xlim=(-.008, .014),
           xlabel='득타율 − 전체 타율의 평균', title='평균 차이의 비교')
    ax.xaxis.set_major_formatter(FormatStrFormatter('%.3f'))
    ax.spines['left'].set_visible(False)
    ax.tick_params(axis='y', length=0, pad=10)
    output = ASSETS / 'average-gap.png'
    fig.savefig(output, dpi=180)
    plt.close(fig)
    print(output)


if __name__ == '__main__':
    main()

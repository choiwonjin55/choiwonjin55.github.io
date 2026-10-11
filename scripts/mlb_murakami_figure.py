"""Render the existing Murakami case alone for the unpublished MLB draft."""
from pathlib import Path
import os

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'data/mlb/2026'
os.environ.setdefault('MPLCONFIGDIR', str(DATA / '.matplotlib'))

import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

frame = pd.read_csv(DATA / 'processed/probability.csv.gz',
                    usecols=['batter', 'events', 'launch_speed', 'launch_angle'])
player = frame.loc[frame['batter'].eq(808959)]
assert len(player) == 257 and player['events'].eq('home_run').sum() == 35
plt.rcParams.update({'font.family': 'Malgun Gothic', 'axes.unicode_minus': False, 'font.size': 11})
fig, ax = plt.subplots(figsize=(9, 6.6), layout='constrained')
hits = ['single', 'double', 'triple', 'home_run']
groups = [(~player['events'].isin(hits), '아웃', '#a7afb5', 'o', 23),
          (player['events'].isin(hits[:-1]), '홈런 제외 안타', '#147c9c', 'o', 25),
          (player['events'].eq('home_run'), '홈런', '#d86240', 'D', 65)]
for mask, label, color, marker, size in groups:
    subset = player.loc[mask]
    ax.scatter(subset['launch_speed'], subset['launch_angle'], c=color, marker=marker,
               s=size, alpha=.6 if label=='아웃' else .85, label=label, edgecolors='white', linewidths=.5)
ax.set(xlim=(40, 120), ylim=(-40, 70), xlabel='타구 속도 (mph)', ylabel='발사각 (°)',
       title='무네타카 무라카미의 타구 분포 · 257타구')
ax.text(.03, .97, f"평균 타구 속도 {player['launch_speed'].mean():.1f} mph\n"
        f"95 mph 이상 {100 * player['launch_speed'].ge(95).mean():.1f}%",
        transform=ax.transAxes, va='top',
        bbox={'facecolor': 'white', 'edgecolor': 'none', 'alpha': .9})
ax.legend(loc='upper right')
output = DATA / 'analysis/player-cases/murakami-contact-map.png'
fig.savefig(output, dpi=180)
plt.close(fig)
print(output.relative_to(ROOT))

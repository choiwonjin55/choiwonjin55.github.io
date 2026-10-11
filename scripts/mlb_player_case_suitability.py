"""Audit existing player examples against 2026 EV/LA region definitions.

Uses saved complete cases only; no model fitting, cleaning changes or draft edits.
Regions are descriptive, including the previously selected player-comparison region.
"""
from pathlib import Path
import hashlib
import json

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'data/mlb/2026'
SOURCE = DATA / 'processed/probability.csv.gz'
REPORT = ROOT / 'posts/2026-10-11-mlb-hit-regions.md'
REGIONS = {
    'A': (65, 75, 20, 35), 'B': (90, 105, 5, 15),
    'C': (105, 115, 25, 35), 'D': (85, 100, 25, 35),
    'E': (75, 95, 10, 25),
}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def summarize(frame):
    hit = frame['events'].isin(['single', 'double', 'triple', 'home_run'])
    hr = frame['events'].eq('home_run')
    rows = {}
    for key, (lo, hi, alo, ahi) in REGIONS.items():
        mask = (frame['launch_speed'].ge(lo) & frame['launch_speed'].lt(hi)
                & frame['launch_angle'].ge(alo) & frame['launch_angle'].lt(ahi))
        rows[key] = {
            'n': int(mask.sum()), 'share': float(mask.mean()),
            'hits': int((mask & hit).sum()), 'home_runs': int((mask & hr).sum()),
            'share_of_all_hits': float((mask & hit).sum() / hit.sum()),
            'share_of_all_hr': float((mask & hr).sum() / hr.sum()) if hr.sum() else None,
        }
    angle_mask = frame['launch_angle'].ge(25) & frame['launch_angle'].lt(35)
    angle_frame = frame.loc[angle_mask]
    return {
        'batted_n': len(frame), 'mean_ev': float(frame['launch_speed'].mean()),
        'mean_la': float(frame['launch_angle'].mean()),
        'hard_hit_share': float(frame['launch_speed'].ge(95).mean()),
        'ev_under_80_share': float(frame['launch_speed'].lt(80).mean()),
        'hits': int(hit.sum()), 'home_runs': int(hr.sum()),
        'non_hr_hits': int((hit & ~hr).sum()),
        'angle_25_35_n': len(angle_frame),
        'angle_25_35_ev_mean': float(angle_frame['launch_speed'].mean()),
        'angle_25_35_ev_ge_105_share': float(angle_frame['launch_speed'].ge(105).mean()),
        'angle_25_35_hits': int(angle_frame['events'].isin(['single', 'double', 'triple', 'home_run']).sum()),
        'angle_25_35_home_runs': int(angle_frame['events'].eq('home_run').sum()),
        'regions': rows,
    }


def main():
    before = {str(p.relative_to(ROOT)): sha(p) for p in [SOURCE, REPORT]}
    frame = pd.read_csv(SOURCE, usecols=['batter', 'events', 'launch_speed', 'launch_angle', 'split'])
    assert len(frame) == 122540
    frame['hard'] = frame['launch_speed'].ge(95)
    grouped = frame.groupby('batter').agg(n=('events', 'size'), mean_ev=('launch_speed', 'mean'),
                                        hard_hit_share=('hard', 'mean'))
    eligible = grouped.loc[grouped['n'].ge(200)]
    summaries = {'mlb': summarize(frame)}
    for key, player_id in [('arraez', 650333), ('murakami', 808959)]:
        summary = summarize(frame.loc[frame['batter'].eq(player_id)])
        summary['rank_scope'] = 'all players with at least 200 cleaned batted balls; not official qualifying PA'
        summary['rank_population_n'] = len(eligible)
        summary['mean_ev_rank_descending'] = int(eligible['mean_ev'].rank(ascending=False, method='min').loc[player_id])
        summary['hard_hit_rank_descending'] = int(eligible['hard_hit_share'].rank(ascending=False, method='min').loc[player_id])
        summaries[key] = summary
    after = {str(p.relative_to(ROOT)): sha(p) for p in [SOURCE, REPORT]}
    assert before == after
    output = {'season': 2026, 'scope': 'full-season complete-case batted balls; descriptive player suitability',
              'new_model_fitted': False, 'draft_changed': False,
              'bounds': 'lower inclusive, upper exclusive', 'regions': REGIONS,
              'source_sha256': before, 'summaries': summaries}
    target = DATA / 'analysis/player-cases/suitability-audit.json'
    target.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(summaries, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()

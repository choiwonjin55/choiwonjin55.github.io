"""Summarize saved 2026 holdout predictions for the unpublished blog draft.

Offline; does not refit models, choose settings, or modify source data.
"""
from pathlib import Path
import hashlib
import json

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'data/mlb/2026'
OUT = DATA / 'analysis/blog-validation'
SOURCES = [DATA / 'analysis/holdout-predictions.csv',
           DATA / 'processed/probability.csv.gz',
           DATA / 'analysis/results.json', DATA / 'analysis/models.pkl']


def hashes():
    return {str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in SOURCES}


def summarize(frame, name):
    hit = frame['events'].isin(['single', 'double', 'triple', 'home_run'])
    hr = frame['events'].eq('home_run')
    distance = frame.loc[frame['hit_distance_sc'].notna() & frame['pred_distance_m'].notna()]
    airborne = distance.loc[distance['bb_type'].isin(['line_drive', 'fly_ball', 'popup'])]
    row = {
        'date': name, 'games': int(frame['game_pk'].nunique()), 'batted_n': len(frame),
        'observed_hits': int(hit.sum()), 'expected_hits': float(frame['pred_hit'].sum()),
        'observed_home_runs': int(hr.sum()),
        'expected_home_runs': float(frame['pred_home_run'].sum()),
        'mean_ev_mph': float(frame['launch_speed'].mean()),
        'mean_la_deg': float(frame['launch_angle'].mean()),
        'hard_hit_share': float(frame['launch_speed'].ge(95).mean()),
        'observed_hit_rate': float(hit.mean()), 'observed_hr_rate': float(hr.mean()),
        'expected_hit_rate': float(frame['pred_hit'].mean()),
        'expected_hr_rate': float(frame['pred_home_run'].mean()),
        'distance_n': len(distance), 'airborne_distance_n': len(airborne),
        'distance_mae_m': float(np.abs(distance['pred_distance_m'] - distance['hit_distance_sc'] * .3048).mean()),
        'all_batted_model_airborne_mae_m': float(np.abs(airborne['pred_distance_m'] - airborne['hit_distance_sc'] * .3048).mean()),
    }
    return row


def main():
    before = hashes()
    held = pd.read_csv(SOURCES[0])
    assert set(held['game_date']) == {'2026-03-26', '2026-09-27'}
    assert len(held) == 1246
    assert held[['pred_hit', 'pred_home_run']].notna().all().all()
    assert held['pred_home_run'].le(held['pred_hit'] + 1e-12).all()
    rows = [summarize(frame, date) for date, frame in held.groupby('game_date')]
    rows.append(summarize(held, 'combined'))
    full = pd.read_csv(SOURCES[1], usecols=['events', 'split'])
    assert not full.loc[full['split'].eq('development')].empty
    hit = full['events'].isin(['single', 'double', 'triple', 'home_run'])
    hr = full['events'].eq('home_run')
    total = {'batted_n': len(full), 'hits': int(hit.sum()), 'home_runs': int(hr.sum()),
             'non_hr_hits': int((hit & ~hr).sum()), 'non_hits': int((~hit).sum())}
    metrics = json.loads(SOURCES[2].read_text(encoding='utf-8'))['metrics']
    for row, split in zip(rows, ['early_holdout', 'final_holdout', 'combined_holdout']):
        recorded = metrics[split]
        assert np.isclose(row['distance_mae_m'], recorded['distance']['all_batted']['mae_m'])
        assert np.isclose(row['observed_hit_rate'], recorded['probability']['hit']['actual_rate'])
        assert np.isclose(row['expected_hit_rate'], recorded['probability']['hit']['predicted_rate'])
        assert np.isclose(row['observed_hr_rate'], recorded['probability']['home_run']['actual_rate'])
        assert np.isclose(row['expected_hr_rate'], recorded['probability']['home_run']['predicted_rate'])
        assert row['airborne_distance_n'] == recorded['distance']['airborne']['n']
        row['airborne_model_mae_m'] = recorded['distance']['airborne']['mae_m']
        assert row['distance_n'] == row['batted_n']
        assert 0 <= row['expected_hits'] <= row['batted_n']
        assert 0 <= row['expected_home_runs'] <= row['expected_hits']
    assert hashes() == before
    OUT.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(OUT / 'summary.csv', index=False, encoding='utf-8')
    details = {'scope': 'saved predictions on two reserved dates; full-season outcomes descriptive',
               'model_refitted': False, 'settings_selected_using_holdout': False,
               'expected_counts': 'sum of per-batted-ball probabilities, not hard classifications',
               'source_sha256': before, 'full_season_outcomes': total, 'holdout': rows}
    (OUT / 'details.json').write_text(json.dumps(details, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'full_season_outcomes': total, 'holdout': rows}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()

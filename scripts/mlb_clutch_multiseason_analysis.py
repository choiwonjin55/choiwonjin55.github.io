"""Adjacent-season persistence comparisons across 2023-2026, offline."""
from pathlib import Path
import copy
import hashlib
import json

import numpy as np
import pandas as pd

import mlb_clutch_analysis as legacy
from mlb_clutch_signs import signs, transition_summary

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'data/mlb/clutch-2023-2026'
ASSETS = ROOT / 'assets/mlb-clutch-2026'


def normalized_tails(tails):
    return {'group_size': tails['group_size'], 'cohort_n': tails['cohort_n'],
            'next_gap': tails['top_minus_bottom_2026'],
            'next_gap_95': tails['top_minus_bottom_2026_95'],
            'next_gap_permutation_p': tails['top_minus_bottom_permutation_p'],
            'groups': [{
                'group': row['group'], 'n': row['n'],
                'mean_before': row['mean_2025'], 'mean_after': row['mean_2026'],
                'mean_after_95': row['mean_2026_95'], 'retained': row['retained'],
                'expected_retained': row['n'] * row['null_retention_expected'],
                'retention_upper_p': row['retention_upper_p']}
                for row in tails['groups']]}


def run():
    manifest = json.loads((DATA / 'manifest.json').read_text(encoding='utf-8'))
    audit = json.loads((DATA / 'audit.json').read_text(encoding='utf-8'))
    for record in manifest['sources']:
        assert hashlib.sha256((ROOT / record['path']).read_bytes()).hexdigest() == record['sha256']
    assert set(audit['years']) == {'2023', '2024', '2025', '2026'}
    assert all(row['player_team_totals_match'] and row['missing_risp_with_300_ab'] == 0
               for row in audit['years'].values())
    inventory = pd.read_csv(DATA / 'processed/player-season-inventory.csv')
    frames = {year: legacy.eligible(inventory, year, 75) for year in range(2023, 2027)}
    result = {'spec': {'seasons': list(frames), 'overall_ab_min': 300, 'risp_ab_min': 75,
                       'outcome': 'Official H/AB; no SF denominator adjustment',
                       'pair_cohorts': 'Eligible in each adjacent pair, not required to qualify in all four seasons',
                       'bootstrap_repetitions': legacy.BOOT, 'permutation_repetitions': legacy.REPS,
                       'pooled_inference': 'No pooled independent-pair test: some players recur across pairs'},
              'yearly': {}, 'pairs': {}}
    for year, frame in frames.items():
        sign = signs(frame)
        result['yearly'][str(year)] = {
            'n': len(frame), 'positive': int((sign > 0).sum()),
            'negative': int((sign < 0).sum()), 'equal': int((sign == 0).sum()),
            'positive_share': float((sign > 0).mean()), 'mean_delta': float(frame.delta.mean()),
            'players': frame.to_dict(orient='records')}
    previous = json.loads((ASSETS / 'results.json').read_text(encoding='utf-8'))['primary']
    for before, after in zip(range(2023, 2026), range(2024, 2027)):
        # Reuse the tested two-season routines through temporary legacy suffixes.
        pair = frames[before].merge(frames[after], on='player_id',
                                     suffixes=('_2025', '_2026'), validate='one_to_one')
        pair = pair.sort_values('player_id').reset_index(drop=True)
        key = f'{before}-{after}'
        if before == 2025:
            correlations = copy.deepcopy(previous['persistence'])
            tails = copy.deepcopy(previous['groups_delta'])
            members = pd.read_csv(ROOT / 'data/mlb/clutch-2026/analysis/paired-players.csv')
            assert set(members.player_id) == set(pair.player_id)
        else:
            print('analyze', key, len(pair), flush=True)
            correlations = legacy.persistence(pair, 20261023 + before * 10)
            tails, members = legacy.tail_groups(pair, 20261024 + before * 10)
        transition = { {'positive_2025': 'positive_before', 'positive_2026': 'positive_after',
                         'negative_2025': 'negative_before'}.get(name, name): value
                       for name, value in transition_summary(pair).items() }
        mean_before, mean_after = float(pair.delta_2025.mean()), float(pair.delta_2026.mean())
        rename = {column: column[:-5] + f'_{before}' if column.endswith('_2025')
                    else column[:-5] + f'_{after}' for column in members
                    if column.endswith(('_2025', '_2026'))}
        members = members.rename(columns=rename)
        result['pairs'][key] = {
            'before': before, 'after': after, 'n': len(pair), 'signs': transition,
            'mean_before': mean_before, 'mean_after': mean_after,
            'persistence': correlations, 'tails': normalized_tails(tails),
            'players': members.to_dict(orient='records')}
    # Account for looking at both tails in all three adjacent pairs.
    family = [group for pair in result['pairs'].values() for group in pair['tails']['groups']]
    for group, adjusted in zip(family, legacy.holm([g['retention_upper_p'] for g in family])):
        group['retention_holm_p_6'] = adjusted
    result['source_hashes'] = {str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in [DATA / 'manifest.json', DATA / 'audit.json',
                     DATA / 'processed/player-season-inventory.csv',
                     ASSETS / 'results.json', Path(__file__),
                     ROOT / 'scripts/mlb_clutch_multiseason_collect.py',
                     ROOT / 'scripts/mlb_clutch_collect.py', ROOT / 'scripts/mlb_clutch_analysis.py',
                     ROOT / 'scripts/mlb_clutch_signs.py']}
    (DATA / 'analysis').mkdir(exist_ok=True)
    encoded = json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + '\n'
    (DATA / 'analysis/results.json').write_text(encoded, encoding='utf-8')
    (ASSETS / 'four-season-results.json').write_text(encoded, encoding='utf-8')
    summary = {'yearly': {year: {k: v for k, v in row.items() if k != 'players'}
                           for year, row in result['yearly'].items()},
               'pairs': {key: {k: v for k, v in row.items() if k not in ('players', 'persistence')}
                          | {'correlations': {k: row['persistence'][k] for k in ('delta', 'avg')}}
                          for key, row in result['pairs'].items()}}
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    run()

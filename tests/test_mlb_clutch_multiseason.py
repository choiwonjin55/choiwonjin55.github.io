"""Independent four-season source, cohort, sign, correlation, and tail checks."""
import hashlib
import json
import math
from pathlib import Path
import unittest

import numpy as np
from scipy import stats

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'data/mlb/clutch-2023-2026'


class FourSeasonChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.result = json.loads((DATA / 'analysis/results.json').read_text(encoding='utf-8'))

    def test_source_lineage_and_team_reconciliation(self):
        for path, expected in self.result['source_hashes'].items():
            self.assertEqual(hashlib.sha256((ROOT / path).read_bytes()).hexdigest(), expected)
        manifest = json.loads((DATA / 'manifest.json').read_text(encoding='utf-8'))
        for record in manifest['sources']:
            self.assertEqual(hashlib.sha256((ROOT / record['path']).read_bytes()).hexdigest(), record['sha256'])
        audit = json.loads((DATA / 'audit.json').read_text(encoding='utf-8'))
        self.assertEqual(set(audit['years']), {'2023', '2024', '2025', '2026'})
        for row in audit['years'].values():
            self.assertTrue(row['player_team_totals_match'])
            self.assertEqual(row['missing_risp_with_300_ab'], 0)
            self.assertEqual(row['missing_required_fields_in_present_records'], 0)

    def test_year_counts_and_official_integer_rates(self):
        expected = {'2023': (236, 137), '2024': (235, 144), '2025': (238, 146), '2026': (237, 136)}
        for year, data in self.result['yearly'].items():
            players = data['players']
            positive = sum(p['risp_h'] * p['ab'] > p['h'] * p['risp_ab'] for p in players)
            self.assertEqual((len(players), positive), expected[year])
            self.assertEqual(data['positive'], positive)
            self.assertEqual(data['positive'] + data['negative'] + data['equal'], data['n'])
            for player in players:
                self.assertGreaterEqual(player['ab'], 300)
                self.assertGreaterEqual(player['risp_ab'], 75)
                self.assertAlmostEqual(player['avg'], player['h'] / player['ab'])
                self.assertAlmostEqual(player['delta'], player['risp_h'] / player['risp_ab'] - player['h'] / player['ab'])

    def test_adjacent_pairs_use_correct_years_and_pairwise_intersection(self):
        for pair in self.result['pairs'].values():
            before, after = pair['before'], pair['after']
            a = {p['player_id']: p for p in self.result['yearly'][str(before)]['players']}
            b = {p['player_id']: p for p in self.result['yearly'][str(after)]['players']}
            self.assertEqual({p['player_id'] for p in pair['players']}, set(a) & set(b))
            for player in pair['players']:
                pid = player['player_id']
                for year, source in [(before, a[pid]), (after, b[pid])]:
                    self.assertEqual(int(player[f'season_{year}']), year)
                    for field in ('ab', 'h', 'risp_ab', 'risp_h'):
                        self.assertEqual(player[f'{field}_{year}'], source[field])

    def test_sign_transitions_expected_counts_and_correlations(self):
        for pair in self.result['pairs'].values():
            before, after = pair['before'], pair['after']
            rows = pair['players']
            positive = lambda row, year: row[f'risp_h_{year}'] * row[f'ab_{year}'] > row[f'h_{year}'] * row[f'risp_ab_{year}']
            n_before = sum(positive(row, before) for row in rows)
            n_after = sum(positive(row, after) for row in rows)
            repeated = sum(positive(row, before) and positive(row, after) for row in rows)
            self.assertEqual(pair['signs']['positive_before'], n_before)
            self.assertEqual(pair['signs']['positive_after'], n_after)
            self.assertEqual(pair['signs']['retained_positive'], repeated)
            self.assertAlmostEqual(pair['signs']['random_expected_retention'], n_after / len(rows))
            for metric in ('delta', 'avg'):
                x = [row[f'{metric}_{before}'] for row in rows]
                y = [row[f'{metric}_{after}'] for row in rows]
                self.assertAlmostEqual(pair['persistence'][metric]['pearson'], stats.pearsonr(x, y).statistic)
                self.assertAlmostEqual(pair['persistence'][metric]['spearman'], stats.spearmanr(x, y).statistic)

    def test_rank_groups_match_independent_ordering(self):
        for pair in self.result['pairs'].values():
            before, after = pair['before'], pair['after']
            n, k = pair['n'], math.floor(.2 * pair['n'])
            first = sorted(pair['players'], key=lambda p: (p[f'delta_{before}'], p['player_id']))
            second = sorted(pair['players'], key=lambda p: (p[f'delta_{after}'], p['player_id']))
            for name, selected, next_selected in [('bottom', first[:k], second[:k]), ('top', first[-k:], second[-k:])]:
                group = next(g for g in pair['tails']['groups'] if g['group'] == name)
                self.assertEqual(group['n'], k)
                self.assertEqual(group['retained'], len({p['player_id'] for p in selected} & {p['player_id'] for p in next_selected}))
                self.assertAlmostEqual(group['expected_retained'], k * k / n)
                self.assertAlmostEqual(group['mean_after'], np.mean([p[f'delta_{after}'] for p in selected]))
                self.assertGreaterEqual(group['retention_holm_p_6'], group['retention_upper_p'])

    def test_existing_latest_pair_results_are_preserved(self):
        original = json.loads((ROOT / 'assets/mlb-clutch-2026/results.json').read_text(encoding='utf-8'))['primary']
        latest = self.result['pairs']['2025-2026']
        self.assertEqual(latest['persistence'], original['persistence'])
        self.assertEqual(latest['n'], 163)
        self.assertEqual(latest['signs']['retained_positive'], 61)


if __name__ == '__main__':
    unittest.main()

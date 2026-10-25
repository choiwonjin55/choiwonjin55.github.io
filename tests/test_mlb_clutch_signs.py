"""Exact-rate classification, retention baseline, and saved-result checks."""
import csv
from decimal import Decimal
from fractions import Fraction
import hashlib
import itertools
import json
from pathlib import Path
import sys
import unittest

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import mlb_clutch_signs as analysis


class PositiveGapChecks(unittest.TestCase):
    def test_exact_rates_distinguish_rounded_ties(self):
        frame = pd.DataFrame({'ab': [2000] * 3, 'h': [600] * 3,
                              'risp_ab': [999, 1001, 1000], 'risp_h': [300] * 3})
        np.testing.assert_array_equal((frame.risp_h / frame.risp_ab).round(3), [.300] * 3)
        np.testing.assert_array_equal(analysis.signs(frame), [1, -1, 0])

    def test_retention_benchmark_matches_exhaustive_random_assignments(self):
        frame = pd.DataFrame({'ab_2025': [10] * 6, 'h_2025': [3] * 6,
                              'risp_ab_2025': [2] * 6, 'risp_h_2025': [1, 1, 1, 1, 0, 0],
                              'ab_2026': [10] * 6, 'h_2026': [3] * 6,
                              'risp_ab_2026': [2] * 6, 'risp_h_2026': [1, 1, 1, 0, 1, 0]})
        result = analysis.transition_summary(frame)
        overlaps = [len({0, 1, 2, 3} & set(chosen))
                    for chosen in itertools.combinations(range(6), 4)]
        self.assertEqual(result['retained_positive'], 3)
        self.assertAlmostEqual(result['random_expected_retention'], 4 / 6)
        self.assertAlmostEqual(result['positive_retention'], 3 / 4)
        self.assertAlmostEqual(result['positive_retention_upper_p'],
                               sum(value >= 3 for value in overlaps) / len(overlaps))
        self.assertAlmostEqual(np.mean(overlaps) / 4, result['random_expected_retention'])

    def test_saved_counts_against_independent_fraction_comparisons(self):
        result = json.loads((analysis.ASSETS / 'positive-gap-results.json').read_text(encoding='utf-8'))
        for path, expected in result['source_hashes'].items():
            self.assertEqual(hashlib.sha256((ROOT / path).read_bytes()).hexdigest(), expected)
        data = analysis.DATA / 'analysis'
        for year in (2025, 2026):
            with (data / f'eligible-{year}.csv').open(encoding='utf-8-sig', newline='') as stream:
                rows = list(csv.DictReader(stream))
            def fraction(row, hits, at_bats):
                return Fraction(int(Decimal(row[hits])), int(Decimal(row[at_bats])))
            positive = sum(fraction(row, 'risp_h', 'risp_ab') > fraction(row, 'h', 'ab') for row in rows)
            self.assertEqual(result['yearly'][str(year)]['n'], len(rows))
            self.assertEqual(result['yearly'][str(year)]['positive'], positive)
        self.assertEqual(result['paired']['matrix'], [[25, 0, 32], [0, 0, 0], [45, 0, 61]])
        self.assertEqual(result['paired']['n'], 163)
        self.assertEqual(result['paired']['positive_2026'], 93)


if __name__ == '__main__':
    unittest.main()

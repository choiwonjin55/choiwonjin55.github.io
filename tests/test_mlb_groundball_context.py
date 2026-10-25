"""Offline checks for ground-ball matching and independently fitted contrasts."""
import hashlib
import json
from pathlib import Path
import sys
import unittest

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import mlb_groundball_context as analysis


class GroundBallChecks(unittest.TestCase):
    def test_direction_geometry(self):
        np.testing.assert_allclose(analysis.direction(np.array([125.42, 135.42, 115.42]),
                                                      np.array([188.27] * 3)), [0, 45, -45])

    def test_matching_boundaries_and_common_support(self):
        rows = []
        for state in range(3):
            for speed in (90., 94.99):
                rows.append({'state': state, 'launch_speed': speed, 'launch_angle': -1.,
                             'spray_direction': 1., 'stand': 'L', 'outs': 0,
                             'analysis_scope': True, 'complete_case': True})
        # Adjacent speed bin lacks the other states and must be excluded.
        rows += [dict(rows[0], launch_speed=95.)] * 3
        # Wrong outs cannot be pooled with the matched cell.
        rows += [dict(rows[0], outs=1)] * 3
        matched, info = analysis.matched_sample(pd.DataFrame(rows))
        self.assertEqual(len(matched), 6)
        self.assertEqual(info['common_strata'], 1)
        self.assertTrue(matched.launch_speed.lt(95).all())
        self.assertTrue(matched.launch_angle_bin.eq(-1).all())
        self.assertTrue(matched.outs.eq(0).all())

    def test_absorbed_estimates_and_cluster_se_match_full_dummy_ols(self):
        rng = np.random.default_rng(20261025)
        n = 1200
        data = pd.DataFrame({'stratum': rng.integers(0, 15, n),
                             'batter': rng.integers(0, 10, n),
                             'fielding_team': rng.integers(0, 4, n),
                             'game_pk': rng.integers(0, 60, n),
                             'state': rng.integers(0, 3, n),
                             'launch_speed': rng.normal(90, 10, n),
                             'launch_angle': rng.normal(-12, 10, n),
                             'spray_direction': rng.uniform(-45, 45, n),
                             'hit': rng.binomial(1, .3, n)})
        fitted = analysis.fit(data)
        raw = data[['launch_speed', 'launch_angle', 'spray_direction']].to_numpy() / 10
        controls = np.column_stack([raw, raw ** 2, raw[:, 0] * raw[:, 1],
                                     raw[:, 0] * raw[:, 2], raw[:, 1] * raw[:, 2]])
        dummies = pd.get_dummies(data[['stratum', 'batter', 'fielding_team']].astype(str),
                                  drop_first=True, dtype=float).to_numpy()
        x = np.column_stack([data.state.eq(1), data.state.eq(2), controls,
                              np.ones(n), dummies])
        beta, _, rank, _ = np.linalg.lstsq(x, data.hit, rcond=None)
        self.assertEqual(rank, x.shape[1])
        residual = data.hit.to_numpy() - x @ beta
        scores = pd.DataFrame(x * residual[:, None]).groupby(data.game_pk.to_numpy()).sum().to_numpy()
        bread = np.linalg.inv(x.T @ x)
        ng = len(scores)
        covariance = bread @ scores.T @ scores @ bread * ng / (ng - 1) * (n - 1) / (n - rank)
        for index, comparison in enumerate(fitted['comparisons'][:2]):
            self.assertAlmostEqual(comparison['estimate'], beta[index], places=9)
            self.assertAlmostEqual(comparison['se'], np.sqrt(covariance[index, index]), places=9)

    def test_saved_sample_and_source_lineage(self):
        result = json.loads((analysis.OUT / 'results.json').read_text(encoding='utf-8'))
        audit = json.loads((analysis.OUT / 'audit.json').read_text(encoding='utf-8'))
        for saved in (result, audit):
            for path, expected in saved['source_hashes'].items():
                self.assertEqual(hashlib.sha256((ROOT / path).read_bytes()).hexdigest(), expected)
        data = pd.read_csv(analysis.OUT / 'matched-ground-balls.csv.gz')
        self.assertEqual(len(data), result['matching']['matched_n'])
        self.assertTrue(data.analysis_scope.all())
        self.assertTrue(data.complete_case.all())
        self.assertTrue(data.hc_y.lt(198.27).all())
        self.assertFalse(data.bunt.any())
        self.assertTrue(data.inning.le(9).all())
        self.assertFalse(data.duplicated(['game_pk', 'at_bat_number']).any())
        counts = data.groupby(['stratum', 'state']).size().unstack(fill_value=0)
        self.assertTrue((counts >= 2).all().all())
        for cell in result['cells']:
            subset = data[data.state == cell['state']]
            self.assertEqual(len(subset), cell['n'])
            self.assertEqual(int(subset.hit.sum()), cell['hits'])
            self.assertAlmostEqual(subset.hit.mean(), cell['rate'])
        self.assertEqual(audit['scope_n'] - audit['missing_required_n']
                         - audit['nonforward_coordinate_n'], audit['complete_n'])


if __name__ == '__main__':
    unittest.main()

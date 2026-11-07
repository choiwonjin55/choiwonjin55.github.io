"""Check quantile positions, location/scale behavior and source completeness."""
import json
from pathlib import Path
from statistics import NormalDist
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
from mlb_war_wins_qq import analyze, normal_qq


class NormalQQTests(unittest.TestCase):
    def test_three_known_ordered_gaps(self):
        rows = [dict(season=2022, team_id=i, fwar_error=value)
                for i, value in enumerate([1., -1., 0.])]
        result = normal_qq(rows)
        self.assertEqual([p['fwar_error'] for p in result['points']], [-1., 0., 1.])
        self.assertEqual(result['mean'], 0.)
        self.assertAlmostEqual(result['sd'], (2/3)**.5)
        for p, probability in zip(result['points'], [1/6, .5, 5/6]):
            self.assertEqual(p['probability'], probability)
            self.assertAlmostEqual(p['normal_quantile'],
                                   NormalDist().inv_cdf(probability)*(2/3)**.5)

    def test_affine_change_alters_error_size_not_distribution_shape(self):
        rows = [dict(season=2022, team_id=i, fwar_error=value)
                for i, value in enumerate([-3., -1., 0., 1., 2., 4.])]
        original = normal_qq(rows)
        shifted = normal_qq([dict(r, fwar_error=3+5*r['fwar_error']) for r in rows])
        self.assertAlmostEqual(shifted['mean'], 3+5*original['mean'])
        self.assertAlmostEqual(shifted['sd'], 5*original['sd'])
        self.assertAlmostEqual(shifted['shapiro']['p_value'], original['shapiro']['p_value'])
        for a, b in zip(original['points'], shifted['points']):
            self.assertAlmostEqual(b['normal_quantile'], 3+5*a['normal_quantile'])

    def test_nonfinite_values_are_not_silently_removed(self):
        rows = [dict(season=2022, team_id=i, fwar_error=x)
                for i, x in enumerate([0., 1., float('nan')])]
        with self.assertRaises(ValueError):
            normal_qq(rows)

    def test_actual_cohort_stays_complete(self):
        base = json.loads((ROOT/'assets/mlb-war-wins/results.json').read_text(encoding='utf-8'))
        result = analyze(base)
        self.assertEqual(result['n'], 150)
        self.assertEqual({(p['season'], p['team_id']) for p in result['points']},
                         {(r['season'], r['team_id']) for r in base['rows']})
        self.assertTrue(all(s['n'] == 30 for s in result['seasons'].values()))


if __name__ == '__main__':
    unittest.main()

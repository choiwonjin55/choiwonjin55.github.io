"""Check model moments and rank comparisons against tiny analytic examples."""
import copy
import json
import math
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
from mlb_war_wins_gaps import exact_reference, simulate, validate_rows


class GapTests(unittest.TestCase):
    def test_known_moments_and_inclusive_maximum(self):
        # Two fair, two-game seasons: residual -1/0/+1 has mass 1/4,1/2,1/4.
        rows = [dict(games=2, fwar_expected=1., wins=1)]*2
        result = exact_reference(rows)
        self.assertEqual(result['observed']['sd'], 0.)
        self.assertEqual(result['observed']['mae'], 0.)
        self.assertAlmostEqual(result['model']['sd'], math.sqrt(.5))
        self.assertEqual(result['model']['mae'], .5)
        self.assertEqual(result['model']['probability_maximum_at_most_observed'], .25)
        rows = [dict(games=2, fwar_expected=1., wins=w) for w in (0, 2)]
        result = exact_reference(rows)
        self.assertEqual(result['observed']['sd'], 1.)
        self.assertEqual(result['observed']['rmse'], 1.)
        self.assertEqual(result['model']['probability_maximum_at_most_observed'], 1.)

    def test_unbiased_mixture_uses_each_teams_own_probability(self):
        rows = [dict(games=2, fwar_expected=.5, wins=0),
                dict(games=4, fwar_expected=3., wins=4)]
        result = exact_reference(rows)
        self.assertAlmostEqual(result['model']['sd']**2, (.375+.75)/2)
        self.assertEqual(result['observed']['mean'], .25)
        self.assertEqual(result['observed']['sd'], .75)

    def test_rank_simulation_against_known_two_season_distribution(self):
        rows = [dict(games=2, fwar_expected=1., wins=1)]*2
        result = simulate(rows, repetitions=10000, seed=7)
        self.assertEqual(result, simulate(rows, repetitions=10000, seed=7))
        self.assertTrue(all(r['median'] == 0. for r in result['ranks']))
        self.assertTrue(all([r['lower'], r['upper']] == [-1., 1.] for r in result['ranks']))
        check = result['checks']['maximum']
        self.assertLess(abs(check['at_most_observed']/10000-.25), .02)
        self.assertEqual(check['lower_tail_mc_p'], (check['at_most_observed']+1)/10001)

    def test_real_cohort_and_gap_sign_validation(self):
        base = json.loads((ROOT/'assets/mlb-war-wins/results.json').read_text(encoding='utf-8'))
        self.assertEqual(len(validate_rows(base)), 150)
        changed = copy.deepcopy(base)
        changed['rows'][0]['fwar_error'] += 1
        with self.assertRaises(ValueError):
            validate_rows(changed)
        changed = copy.deepcopy(base)
        changed['rows'][-1] = changed['rows'][0]
        with self.assertRaises(ValueError):
            validate_rows(changed)


if __name__ == '__main__':
    unittest.main()

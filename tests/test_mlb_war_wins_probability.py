import itertools
import math
from pathlib import Path
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from mlb_war_wins_probability import (binomial_pmf,holm_adjust,maximum_cdf_less,
                                      quantile,simulate_maxima,two_sided)


class ProbabilityTests(unittest.TestCase):
    def test_known_binomial_and_boundaries(self):
        self.assertEqual(binomial_pmf(2,.5),[.25,.5,.25])
        self.assertEqual(binomial_pmf(3,0),[1,0,0,0])
        self.assertEqual(binomial_pmf(3,1),[0,0,0,1])
        self.assertEqual(binomial_pmf(0,.5),[1])
        self.assertAlmostEqual(sum(binomial_pmf(162,.42)),1)
        with self.assertRaises(ValueError):binomial_pmf(10,-.1)
        with self.assertRaises(ValueError):binomial_pmf(-1,.5)

    def test_exact_two_sided_and_interval(self):
        masses=binomial_pmf(10,.5)
        self.assertAlmostEqual(two_sided(masses,0),2/1024)
        self.assertAlmostEqual(two_sided(masses,5),1)
        self.assertEqual([quantile(masses,.025),quantile(masses,.975)],[2,8])
        # With asymmetric p, do not double one tail mechanically.
        masses=binomial_pmf(3,.2)
        self.assertAlmostEqual(two_sided(masses,1),.488)

    def test_maximum_cdf_matches_enumeration(self):
        distributions=[(.6,binomial_pmf(3,.2)),(1.8,binomial_pmf(3,.6))]
        for threshold in [.6,1,1.8,2.4,3]:
            enumerated=math.fsum(
                distributions[0][1][a]*distributions[1][1][b]
                for a,b in itertools.product(range(4),repeat=2)
                if max(abs(a-.6),abs(b-1.8))<threshold-1e-12)
            self.assertAlmostEqual(maximum_cdf_less(distributions,threshold),enumerated)

    def test_simulation_seed_and_cohort_selection(self):
        distributions=[(1,binomial_pmf(2,.5))]*2
        exact=1-maximum_cdf_less(distributions,1)
        self.assertAlmostEqual(exact,.75)
        first=simulate_maxima(distributions,1,10000,77)
        self.assertEqual(first,simulate_maxima(distributions,1,10000,77))
        self.assertLess(abs(first['tail_probability']-exact),.025)
        self.assertEqual(sum(b['count'] for b in first['histogram']),10000)

    def test_holm_adjustment_restores_original_order(self):
        adjusted=holm_adjust([.04,.01,.03])
        for actual,expected in zip(adjusted,[.06,.03,.06]):self.assertAlmostEqual(actual,expected)


if __name__=='__main__':unittest.main()

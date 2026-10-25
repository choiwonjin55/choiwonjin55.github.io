"""Mathematical and saved-source checks for the clutch analysis (offline)."""
import importlib.util
import itertools
import json
from pathlib import Path
import unittest

import numpy as np
import pandas as pd
from scipy import stats

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('clutch', ROOT/'scripts/mlb_clutch_analysis.py')
clutch = importlib.util.module_from_spec(spec)
spec.loader.exec_module(clutch)


class ClutchChecks(unittest.TestCase):
    def test_conditional_null_against_exhaustive_allocation(self):
        # Enumerate every choice of 3 RISP AB from 10 AB containing 4 hits.
        h = np.array([sum(i < 4 for i in subset) for subset in itertools.combinations(range(10),3)])
        self.assertAlmostEqual(float(h.mean()),1.2)
        self.assertAlmostEqual(float(h.var()),3*.4*.6*7/9)
        s = clutch.rates(pd.DataFrame([{'ab':10,'h':4,'risp_ab':3,'risp_h':2,
                                       'nonrisp_ab':7,'nonrisp_h':2}]))
        self.assertAlmostEqual(float(s.null_sd_delta.iloc[0]**2),float((h/3-.4).var()))
        self.assertAlmostEqual(float(s.contrast.iloc[0]),2/3-2/7)

    def test_retention_null_against_all_rank_groups(self):
        baseline={0,1}
        overlaps=[len(baseline & set(s)) for s in itertools.combinations(range(6),2)]
        self.assertAlmostEqual(sum(x>=1 for x in overlaps)/len(overlaps),stats.hypergeom.sf(0,6,2,2))
        self.assertAlmostEqual(np.mean(overlaps)/2,2/6)

    def test_correlations_match_scipy_with_ties(self):
        x=np.array([1,1,2,4,8,9]);y=np.array([7,3,5,1,1,2])
        self.assertAlmostEqual(float(clutch.correlation(x,y)),stats.pearsonr(x,y).statistic)
        self.assertAlmostEqual(float(clutch.correlation(stats.rankdata(x),stats.rankdata(y))),stats.spearmanr(x,y).statistic)

    def test_holm_controls_all_retention_tests(self):
        np.testing.assert_allclose(clutch.holm([.04,.001,.03]),[.06,.003,.06])
        result=json.loads((clutch.OUT/'results.json').read_text(encoding='utf-8'))
        groups=[g for s in result['sensitivity'] for m in ('delta','contrast') for g in s['groups_'+m]['groups']]
        self.assertEqual(len(groups),12)
        np.testing.assert_allclose([g['retention_holm_p_12_tests'] for g in groups],
                                   clutch.holm([g['retention_upper_p'] for g in groups]))

    def test_stored_counts_and_cohort(self):
        inv=pd.read_csv(clutch.DATA/'processed/player-season-inventory.csv')
        actual=pd.read_csv(clutch.OUT/'paired-players.csv')
        expected=set(clutch.eligible(inv,2025,75).player_id)&set(clutch.eligible(inv,2026,75).player_id)
        self.assertEqual(set(actual.player_id),expected)
        self.assertTrue(actual.player_id.is_unique)
        self.assertEqual(int((actual.group_2025=='top').sum()),len(actual)//5)
        self.assertEqual(int((actual.group_2025=='bottom').sum()),len(actual)//5)
        for y in (2025,2026):
            raw=json.loads((clutch.DATA/f'raw/{y}-players-risp.json').read_text(encoding='utf-8'))
            counts={s['player']['id']:s['stat'] for s in raw['stats'][0]['splits']}
            for row in actual.to_dict('records'):
                s=counts[row['player_id']]
                self.assertEqual(row[f'risp_ab_{y}'],s['atBats'])
                self.assertEqual(row[f'risp_h_{y}'],s['hits'])
                self.assertAlmostEqual(row[f'delta_{y}'],s['hits']/s['atBats']-row[f'h_{y}']/row[f'ab_{y}'])

    def test_source_hashes_and_intervals(self):
        import hashlib
        result=json.loads((clutch.OUT/'results.json').read_text(encoding='utf-8'))
        for name,digest in result['source_hashes'].items():
            self.assertEqual(hashlib.sha256((ROOT/name).read_bytes()).hexdigest(),digest,name)
        for s in result['sensitivity']:
            for m in s['persistence'].values():
                self.assertLessEqual(m['pearson_95'][0],m['pearson_95'][1])
                self.assertTrue(-1<=m['pearson']<=1)


if __name__=='__main__':
    unittest.main()

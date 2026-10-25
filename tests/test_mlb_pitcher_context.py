"""Independent reconstruction and estimation checks for pitcher-context analysis."""
import csv
import gzip
import io
import json
from pathlib import Path
import sys
import unittest

import numpy as np

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import mlb_pitcher_context_collect as collect
import mlb_pitcher_context_analysis as analysis


class PitcherContextChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.et={x['code']:x for x in json.loads((collect.DATA/'event-types.json').read_text(encoding='utf-8'))}
        cls.game=json.loads(gzip.decompress((collect.DATA/'raw/823244.json.gz').read_bytes()))
        cls.rows,cls.issues,_=collect.parse_game(823244,collect.schedule()[823244],cls.game,cls.et)

    def test_multi_base_advances_are_one_runner(self):
        p=next(p for p in self.game['allPlays'] if p['about']['atBatIndex']==5)
        movements=collect.collapse_movements(p['runners'])
        self.assertEqual(len(movements),2)
        before={'1B':656305}
        after=collect.move(before,movements)
        self.assertEqual(after,{'1B':646240,'3B':656305})
        self.assertEqual(collect.unmove(after,movements),before)

    def test_entry_group_has_first_reliever_only(self):
        by_index={r['at_bat_index']:r for r in self.rows}
        self.assertEqual(by_index[0]['starter_first_pa'],1)
        self.assertEqual(by_index[0]['fresh_reliever'],0)
        self.assertEqual(by_index[45]['fresh_reliever'],1)
        self.assertEqual(by_index[46]['fresh_reliever'],0)
        self.assertEqual(by_index[45]['mid_pa_change'],0)
        self.assertEqual(self.issues,[])

    def test_terminal_runner_state_matches_independent_statcast_snapshot(self):
        path=ROOT/'data/mlb/2026/raw/sample-2026-03-25-all.csv.gz'
        with gzip.open(path,'rt',encoding='utf-8-sig') as f:
            snapshot=[r for r in csv.DictReader(f) if r['events']]
        rows={r['at_bat_index']:r for r in self.rows}
        self.assertEqual(len(rows),len(snapshot))
        for r in snapshot:
            pa=rows[int(r['at_bat_number'])-1]
            self.assertEqual(pa['batter'],int(r['batter']))
            self.assertEqual(pa['pitcher'],int(r['pitcher']))
            self.assertEqual(pa['risp'],int(bool(r['on_2b'] or r['on_3b'])))

    def test_absorption_matches_full_dummy_regression(self):
        rng=np.random.default_rng(21);n=600
        g1=rng.integers(0,12,n);g2=rng.integers(0,15,n)
        x=rng.normal(size=n)
        y=.3*x+rng.normal(size=12)[g1]+rng.normal(size=15)[g2]+rng.normal(size=n)*.1
        v,_=analysis.absorb(np.column_stack([y,x]),[g1,g2])
        actual=np.linalg.lstsq(v[:,1:],v[:,0],rcond=None)[0][0]
        design=np.column_stack([x,np.ones(n),np.eye(12)[g1][:,1:],np.eye(15)[g2][:,1:]])
        expected=np.linalg.lstsq(design,y,rcond=None)[0][0]
        self.assertAlmostEqual(actual,expected,places=10)

    def test_all_season_counts_match_official_records(self):
        audit=json.loads((collect.DATA/'audit.json').read_text(encoding='utf-8'))
        self.assertTrue(audit['complete_schedule'])
        self.assertEqual(audit['games'],2429)
        self.assertFalse(any(audit['official_differences'].values()),audit['official_differences'])
        self.assertEqual(audit['missing_core_fields'],0)

    def test_post_outcome_conditioning_diagnostic_is_not_used(self):
        r=json.loads((collect.DATA/'results.json').read_text(encoding='utf-8'))
        self.assertNotIn('daily',r['models'])
        self.assertTrue(r['diagnostics']['pitcher_game_fe_not_used_for_inference'])
        null=r['diagnostics']['independent_null_previous_outcome_test']
        self.assertLess(abs(null['unadjusted_slope']),.01)
        self.assertLess(null['same_stint_fe_slope'],-.15)

    def test_result_lineage_and_main_sample(self):
        import hashlib
        r=json.loads((collect.DATA/'results.json').read_text(encoding='utf-8'))
        for name,digest in r['source_hashes'].items():
            self.assertEqual(hashlib.sha256((ROOT/name).read_bytes()).hexdigest(),digest,name)
        self.assertEqual(r['spec']['primary_batters'],237)
        cells=r['raw_primary']['cells']
        self.assertEqual(r['spec']['outcome'],'H/AB')
        self.assertEqual(sum(c['n'] for c in cells),r['audit']['primary_ab'])
        for c in cells:
            self.assertEqual(c['n'],c['official_ab'])
            self.assertEqual(c['sf'],0)
            self.assertAlmostEqual(c['official_avg'],c['hits']/c['official_ab'])

    def test_official_average_preserves_charged_at_bats(self):
        r=json.loads((collect.DATA/'results.json').read_text(encoding='utf-8'))
        expected=[(74097,18512),(24236,6326),(7567,1854),(1603,397)]
        for cell,(at_bats,hits) in zip(r['raw_primary']['cells'],expected):
            self.assertEqual(cell['official_ab'],at_bats)
            self.assertEqual(cell['hits'],hits)
            self.assertAlmostEqual(cell['official_avg'],hits/at_bats)
        self.assertEqual(r['audit']['primary_ab'],107503)


if __name__=='__main__':
    unittest.main()

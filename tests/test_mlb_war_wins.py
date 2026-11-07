"""Independent arithmetic and bad-input checks for the WAR/wins analysis."""
import json
import math
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from mlb_war_wins_analysis import enrich, ranks, regression, summarize, analyze
from mlb_war_wins_collect import (TEAM_IDS, YEARS, digest, load_snapshot, number,
                                  parse_fg, save_json, store_snapshot, team_id,
                                  audit, source_specs)


def observation(war=30,wins=80,games=162,season=2022,tid=109):
    return dict(season=season,team_id=tid,team='Test team',games=games,wins=wins,
                losses=games-wins,runs_scored=700,runs_allowed=700,
                fwar_bat=war-10 if war is not None else None,fwar_pit=10,fwar=war)


class Arithmetic(unittest.TestCase):
    def test_short_schedule_and_error_sign(self):
        r=enrich(observation(war=20,wins=65,games=108))
        self.assertEqual(r['fwar_expected'],52)
        self.assertEqual(r['fwar_error'],13)
        self.assertEqual(r['wins_162'],97.5)
        self.assertEqual(r['fwar_162'],30)
        self.assertEqual(r['pythagorean_wins'],54)

    def test_error_metrics_are_not_regression_residuals(self):
        # Expected wins are 58/68/78, observed wins 60/66/82: errors +2,-2,+4.
        rows=[enrich(observation(war=x,wins=y)) for x,y in [(10,60),(20,66),(30,82)]]
        s=summarize(rows,'fwar')
        self.assertAlmostEqual(s['bias'],4/3)
        self.assertAlmostEqual(s['mae'],8/3)
        self.assertAlmostEqual(s['rmse'],math.sqrt(8))
        self.assertEqual(s['within_5'],1)

    def test_closed_form_regression(self):
        r=regression([0,1,2],[2,4,6])
        self.assertEqual((r['slope'],r['intercept']),(2,2))
        self.assertAlmostEqual(r['pearson'],1)
        self.assertAlmostEqual(r['r_squared'],1)
        self.assertAlmostEqual(regression([0,1,2],[6,4,2])['spearman'],-1)

    def test_spearman_ties_and_degenerate_values(self):
        self.assertEqual(ranks([3,1,1,2]),[4,1.5,1.5,3])
        self.assertAlmostEqual(regression([1,2,3],[10,10,20])['spearman'],math.sqrt(3)/2)
        self.assertIsNone(regression([1,1],[2,3])['slope'])
        self.assertIsNone(regression([1,2],[3,3])['pearson'])

    def test_no_imputation_of_missing_fwar(self):
        rows=[observation(season=year,tid=tid) for year in YEARS for tid in TEAM_IDS.values()]
        rows[0]['fwar']=None
        result=analyze(rows)
        self.assertIsNone(result['summaries']['fwar']['all'])
        self.assertIsNone(result['rows'][0]['fwar_expected'])
        self.assertEqual(result['outliers']['fwar'],[])
        self.assertEqual(set(result['summaries']),{'fwar'})

    def test_complete_fwar_results_need_no_other_metric(self):
        rows=[observation(season=year,tid=tid) for year in YEARS for tid in TEAM_IDS.values()]
        result=analyze(rows)
        self.assertEqual(result['summaries']['fwar']['all']['n'],150)
        self.assertEqual(set(result['summaries']),{'fwar'})
        self.assertEqual(len(list(source_specs())),20)
        self.assertTrue(all(url.startswith(('https://statsapi.mlb.com/','https://www.fangraphs.com/')) for _,url in source_specs()))

    def test_negative_war_and_exact_five_boundary(self):
        rows=[enrich(observation(war=-1,wins=52)),enrich(observation(war=0,wins=42))]
        self.assertEqual(rows[0]['fwar_expected'],47)
        self.assertEqual(summarize(rows,'fwar')['within_5'],.5)


class Sources(unittest.TestCase):
    def test_team_identity_aliases(self):
        self.assertEqual(team_id('OAK'),team_id('ATH'))
        self.assertEqual(team_id('Oakland Athletics'),team_id('Athletics'))
        self.assertEqual(team_id('CWS'),145)

    def test_nonfinite_and_missing_rejected(self):
        for value in [None,'',True,'nan','inf']:
            with self.subTest(value=value),self.assertRaises(ValueError):number(value)

    def test_raw_hash_tampering_detected(self):
        with tempfile.TemporaryDirectory() as d:
            data=Path(d)
            store_snapshot(data,'sample','https://example.test',b'original','text/plain')
            self.assertEqual(load_snapshot(data,'sample')[0],b'original')
            (data/'raw/sample.raw').write_bytes(b'changed')
            with self.assertRaises(ValueError):load_snapshot(data,'sample')
            with self.assertRaises(ValueError):store_snapshot(data,'sample','https://example.test',b'changed','text/plain')

    def test_provider_team_rows_and_season(self):
        rows=[dict(Season=2022,TeamName=code,teamid=i,WAR=-1 if i==0 else i) for i,code in enumerate(TEAM_IDS)]
        raw=lambda r:json.dumps(dict(data=r,totalCount=len(r))).encode()
        self.assertEqual(len(parse_fg(raw(rows),2022)),30)
        self.assertEqual(parse_fg(raw(rows),2022)[109]['war'],-1)
        with self.assertRaises(ValueError):parse_fg(raw(rows),2023)
        with self.assertRaises(ValueError):parse_fg(raw(rows[:-1]),2022)
        with self.assertRaises(ValueError):parse_fg(raw(rows[:-1]+[rows[0]]),2022)


    def test_audit_rejects_fangraphs_mlb_win_mismatch(self):
        # A fully populated synthetic collection must still fail a W/L mismatch.
        with tempfile.TemporaryDirectory() as directory:
            data=Path(directory)
            for year in YEARS:
                official=[dict(team={'id':tid},season=str(year),gamesPlayed=162,wins=81,losses=81,runsScored=700,runsAllowed=700) for tid in TEAM_IDS.values()]
                snapshots={f'mlb-{year}':dict(records=[dict(teamRecords=official)]),
                           f'teams-{year}':dict(teams=[dict(id=tid,name=code) for code,tid in TEAM_IDS.items()])}
                for kind in ('bat','pit'):
                    rows=[dict(Season=year,TeamName=code,teamid=i,WAR=1,W=81,L=81) for i,code in enumerate(TEAM_IDS)]
                    if year==2022 and kind=='pit':rows[0]['W']=80
                    snapshots[f'fg-{year}-{kind}']=dict(data=rows,totalCount=30)
                for name,obj in snapshots.items():store_snapshot(data,name,'https://example.test/'+name,json.dumps(obj).encode(),'application/json')
            result=audit(data)
            self.assertEqual(result['status'],'incomplete')
            self.assertTrue(any('W/L differ' in i['error'] for i in result['issues']))


if __name__=='__main__':unittest.main()

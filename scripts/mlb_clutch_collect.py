"""Collect official MLB season/RISP batting counts; audit without imputing records.

Standard library only. Run `python scripts/mlb_clutch_collect.py collect` online,
then `python scripts/mlb_clutch_collect.py audit` offline. Raw bytes are immutable
unless --refresh is explicitly supplied. No Statcast contact filters are applied.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'data/mlb/clutch-2026'
BASE = 'https://statsapi.mlb.com/api/v1/'
YEARS = (2025, 2026)
FIELDS = ('atBats', 'hits', 'plateAppearances', 'strikeOuts', 'baseOnBalls',
          'hitByPitch', 'sacFlies', 'sacBunts', 'catchersInterference')


def save_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')


def query(endpoint, **params):
    return BASE + endpoint + '?' + urllib.parse.urlencode(params)


def fetch(name, url, refresh=False):
    path = DATA / 'raw' / (name + '.json')
    meta = path.with_suffix('.meta.json')
    if path.exists() and not refresh:
        record = json.loads(meta.read_text(encoding='utf-8'))
        assert record['url'] == url, (name, 'cache query differs')
        assert record['sha256'] == hashlib.sha256(path.read_bytes()).hexdigest()
        return record
    for attempt in range(3):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'MLB-clutch-research/1.0'})
            with urllib.request.urlopen(req, timeout=40) as response:
                raw = response.read()
            parsed = json.loads(raw)
            assert isinstance(parsed, (dict, list))
            if isinstance(parsed, dict):
                assert 'message' not in parsed, parsed
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(raw)
            record = {'url': url, 'path': str(path.relative_to(DATA)),
                      'retrieved_at_utc': datetime.now(timezone.utc).isoformat(),
                      'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}
            save_json(meta, record)
            print(name, len(raw), flush=True)
            return record
        except Exception:
            if attempt == 2:
                raise
            time.sleep(attempt + 1)
    raise RuntimeError('unreachable')


def load(name):
    return json.loads((DATA / 'raw' / (name + '.json')).read_text(encoding='utf-8'))


def collect(refresh=False):
    records = [fetch('situation-codes', BASE + 'situationCodes', refresh)]
    for year in YEARS:
        for kind, stat, sit in [('season', 'season', None), ('risp', 'statSplits', 'risp')]:
            params = dict(stats=stat, group='hitting', season=year, sportIds=1,
                          gameType='R', limit=10000)
            if sit:
                params['sitCodes'] = sit
            records.append(fetch(f'{year}-players-{kind}', query('stats', **params, playerPool='ALL'), refresh))
            records.append(fetch(f'{year}-teams-{kind}', query('teams/stats', **params), refresh))
        records.append(fetch(f'{year}-schedule', query('schedule', sportId=1, season=year, gameType='R'), refresh))
        # Check three traded players directly, independently of league leaderboards.
        splits = load(f'{year}-players-season')['stats'][0]['splits']
        traded = sorted((s for s in splits if s.get('numTeams', 1) > 1),
                        key=lambda s: (-s['stat']['atBats'], s['player']['id']))[:3]
        for s in traded:
            pid = s['player']['id']
            records.append(fetch(f'{year}-person-{pid}', query(f'people/{pid}/stats',
                stats='season,statSplits', group='hitting', season=year, gameType='R', sitCodes='risp'), refresh))
    save_json(DATA / 'manifest.json', {'seasons': YEARS, 'game_type': 'R',
        'unit': 'player-season official batting counts, all teams combined',
        'client_as_of_kst': '2026-10-23', 'sources': records})


def splits(name, year, kind, player):
    groups = load(name)['stats']
    assert len(groups) == 1
    g = groups[0]
    values = g['splits']
    assert len(values) == g['totalSplits'], (name, 'truncated response')
    keys = [s['player' if player else 'team']['id'] for s in values]
    assert len(keys) == len(set(keys)), (name, 'duplicate identifiers')
    for s in values:
        assert int(s['season']) == year
        assert s.get('gameType', 'R') == 'R'
        if player:
            assert s['sport']['id'] == 1
        if kind == 'risp':
            assert s['split']['code'] == 'risp'
        for field in FIELDS:
            assert isinstance(s['stat'][field], int) and s['stat'][field] >= 0
        assert s['stat']['hits'] <= s['stat']['atBats'] <= s['stat']['plateAppearances']
        n, h = s['stat']['atBats'], s['stat']['hits']
        if n:
            assert abs(float(s['stat']['avg']) - h / n) <= .000501
    return {k: s for k, s in zip(keys, values)}


def audit():
    audit_years, rows = {}, []
    for year in YEARS:
        players = {kind: splits(f'{year}-players-{kind}', year, kind, True) for kind in ('season', 'risp')}
        teams = {kind: splits(f'{year}-teams-{kind}', year, kind, False) for kind in ('season', 'risp')}
        assert set(players['risp']) <= set(players['season'])
        totals = {}
        for kind in ('season', 'risp'):
            assert len(teams[kind]) == 30
            ptotal = {f: sum(s['stat'][f] for s in players[kind].values()) for f in FIELDS}
            ttotal = {f: sum(s['stat'][f] for s in teams[kind].values()) for f in FIELDS}
            assert ptotal == ttotal, (year, kind, ptotal, ttotal)
            totals[kind] = ttotal
        missing_risp = []
        for pid, s in players['season'].items():
            a = s['stat']
            r = players['risp'].get(pid)
            row = {'season': year, 'player_id': pid, 'name': s['player']['fullName'],
                   'ab': a['atBats'], 'h': a['hits'], 'pa': a['plateAppearances'],
                   'teams': s.get('numTeams', 1), 'risp_record_present': r is not None}
            if r is None:
                missing_risp.append({'player_id': pid, 'name': row['name'], 'ab': row['ab']})
                # Do not impute an absent split as zero. These rows remain in inventory.
                row.update(risp_ab=None, risp_h=None, nonrisp_ab=None, nonrisp_h=None)
            else:
                b = r['stat']
                for f in FIELDS:
                    assert b[f] <= a[f], (year, pid, f)
                row.update(risp_ab=b['atBats'], risp_h=b['hits'],
                           nonrisp_ab=a['atBats']-b['atBats'], nonrisp_h=a['hits']-b['hits'])
                assert row['nonrisp_h'] <= row['nonrisp_ab']
            rows.append(row)
        schedule = load(f'{year}-schedule')
        entries = [(day['date'], g) for day in schedule['dates'] for g in day['games']]
        assert all(g['gameType'] == 'R' for _, g in entries)
        finals = [(d, g) for d, g in entries if g['status']['abstractGameState'] == 'Final']
        pending = [(d, g['gamePk'], g['status']['detailedState']) for d, g in entries
                   if g['status']['abstractGameState'] != 'Final' and g['status']['detailedState'] not in ('Cancelled', 'Postponed')]
        assert not pending, pending
        checks = []
        for path in sorted((DATA / 'raw').glob(f'{year}-person-*.json')):
            if path.name.endswith('.meta.json'):
                continue
            pid = int(path.stem.rsplit('-', 1)[1])
            gs = json.loads(path.read_text(encoding='utf-8'))['stats']
            for kind, typ in [('season', 'season'), ('risp', 'statSplits')]:
                group = next(x for x in gs if x['type']['displayName'] == typ)
                ss = [x for x in group['splits'] if int(x['season']) == year and
                      (kind == 'season' or x['split']['code'] == 'risp')]
                # The people endpoint includes team rows AND a no-team combined row.
                combined = [x for x in ss if 'team' not in x]
                assert len(combined) == 1, (pid, kind, 'missing combined row')
                assert all(combined[0]['stat'][f] == players[kind][pid]['stat'][f] for f in FIELDS)
                checks.append({'player_id': pid, 'kind': kind, 'matched': True})
        audit_years[str(year)] = {'players_total': len(players['season']),
            'players_with_risp_record': len(players['risp']), 'missing_risp_records': missing_risp,
            'missing_risp_with_300_ab': sum(x['ab'] >= 300 for x in missing_risp),
            'missing_required_fields_in_present_records': 0, 'duplicate_player_ids': 0,
            'player_team_totals_match': True, 'totals': totals, 'traded_player_checks': checks,
            'first_completed_date': min(d for d, _ in finals),
            'last_completed_date': max(d for d, _ in finals),
            'completed_schedule_entries': len(finals),
            'unique_completed_games': len({g['gamePk'] for _, g in finals}),
            'nonfinal_unresolved': pending}
    out = DATA / 'processed'
    out.mkdir(parents=True, exist_ok=True)
    with (out / 'player-season-inventory.csv').open('w', encoding='utf-8-sig', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    save_json(DATA / 'audit.json', {'years': audit_years,
        'selection': 'Analysis eligibility: >=300 total AB and >=50/75/100 RISP AB; no missing-value imputation.',
        'notes': ['Official AB include strikeouts and bunt hits; exclude walks, HBP, sacrifices, interference.',
                  'No EV/LA/distance completeness or contact-quality exclusions.',
                  'No leaderboard rows are added twice; league totals match sums of 30 team records.']})
    print(json.dumps({k: {f: v[f] for f in ('players_total', 'players_with_risp_record',
        'missing_risp_with_300_ab', 'totals', 'unique_completed_games')} for k,v in audit_years.items()}, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=('collect', 'audit'))
    parser.add_argument('--refresh', action='store_true')
    args = parser.parse_args()
    if args.mode == 'collect':
        collect(args.refresh)
    else:
        audit()

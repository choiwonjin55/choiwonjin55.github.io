"""Collect immutable official team WAR/standings snapshots and audit them offline.

Standard library only. A failed source remains missing; no WAR is imputed.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'data/mlb/war-wins-2022-2026'
YEARS = tuple(range(2022, 2027))
USER_AGENT = 'Mozilla/5.0 (compatible; WAR-wins-research/1.0)'
# Provider abbreviations are mapped explicitly, never by the current display name.
TEAM_IDS = dict(ARI=109, ATL=144, BAL=110, BOS=111, CHC=112, CHW=145,
                CIN=113, CLE=114, COL=115, DET=116, HOU=117, KCR=118,
                LAA=108, LAD=119, MIA=146, MIL=158, MIN=142, NYM=121,
                NYY=147, OAK=133, PHI=143, PIT=134, SDP=135, SEA=136,
                SFG=137, STL=138, TBR=139, TEX=140, TOR=141, WSN=120)
ALIASES = dict(CWS='CHW', KC='KCR', SD='SDP', SF='SFG', TB='TBR',
               WSH='WSN', WAS='WSN', ATH='OAK', ATHLETICS='OAK', ANA='LAA')
TEAM_NAMES = {
    'Arizona Diamondbacks':'ARI', 'Atlanta Braves':'ATL', 'Baltimore Orioles':'BAL',
    'Boston Red Sox':'BOS', 'Chicago Cubs':'CHC', 'Chicago White Sox':'CHW',
    'Cincinnati Reds':'CIN', 'Cleveland Guardians':'CLE', 'Colorado Rockies':'COL',
    'Detroit Tigers':'DET', 'Houston Astros':'HOU', 'Kansas City Royals':'KCR',
    'Los Angeles Angels':'LAA', 'Los Angeles Dodgers':'LAD', 'Miami Marlins':'MIA',
    'Milwaukee Brewers':'MIL', 'Minnesota Twins':'MIN', 'New York Mets':'NYM',
    'New York Yankees':'NYY', 'Oakland Athletics':'OAK', 'Athletics':'OAK',
    'Philadelphia Phillies':'PHI', 'Pittsburgh Pirates':'PIT', 'San Diego Padres':'SDP',
    'San Francisco Giants':'SFG', 'Seattle Mariners':'SEA', 'St. Louis Cardinals':'STL',
    'Tampa Bay Rays':'TBR', 'Texas Rangers':'TEX', 'Toronto Blue Jays':'TOR',
    'Washington Nationals':'WSN',
}


def save_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2,
                               allow_nan=False) + '\n', encoding='utf-8', newline='\n')


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def team_id(value):
    raw = str(value).strip()
    code = TEAM_NAMES.get(raw, raw).upper()
    return TEAM_IDS[ALIASES.get(code, code)]


def number(value):
    if value is None or isinstance(value, bool) or str(value).strip() == '':
        raise ValueError('Missing numeric value')
    result = float(str(value).replace(',', '').replace('\u2212', '-'))
    if not math.isfinite(result):
        raise ValueError('Nonfinite numeric value')
    return result


def integer(value):
    result = number(value)
    if not result.is_integer():
        raise ValueError(f'Noninteger count: {value}')
    return int(result)


def fg_url(year, kind, team='0,ts', players=None):
    params = dict(age=0, pos='all', stats=kind, lg='all', qual=0, type=8,
                  season=year, season1=year, ind=0, team=team,
                  pageitems=3000, pagenum=1)
    if players is not None:
        params['players'] = players
    return 'https://www.fangraphs.com/api/leaders/major-league/data?' + urllib.parse.urlencode(params)


def source_specs():
    for year in YEARS:
        yield f'mlb-{year}', ('https://statsapi.mlb.com/api/v1/standings?'
                              f'leagueId=103,104&season={year}&standingsTypes=regularSeason')
        yield f'teams-{year}', f'https://statsapi.mlb.com/api/v1/teams?sportId=1&season={year}'
        for kind in ('bat', 'pit'):
            yield f'fg-{year}-{kind}', fg_url(year, kind)


def load_snapshot(data, name):
    record = json.loads((data / 'raw' / f'{name}.meta.json').read_text(encoding='utf-8'))
    path = data / record['path']
    if path.resolve().parent != (data / 'raw').resolve():
        raise ValueError('Snapshot path escapes raw directory')
    raw = path.read_bytes()
    if digest(raw) != record['sha256']:
        raise ValueError(f'Raw snapshot hash mismatch: {name}')
    return raw, record


def fetch(data, name, url):
    if (data / 'raw' / f'{name}.meta.json').exists():
        _, record = load_snapshot(data, name)
        if record['url'] != url:
            raise ValueError(f'Cached URL differs: {name}')
        return record
    request = urllib.request.Request(url, headers={'User-Agent': USER_AGENT})
    with urllib.request.urlopen(request, timeout=35) as response:
        raw = response.read()
        content_type = response.headers.get('Content-Type', '')
    obj = json.loads(raw)
    if not isinstance(obj, dict):
        raise ValueError('Expected JSON object')
    if name.startswith('fg-') and not obj.get('data'):
        raise ValueError('Empty FanGraphs response')
    return store_snapshot(data, name, url, raw, content_type)


def store_snapshot(data, name, url, raw, content_type, retrieved_at=None):
    if (data / 'raw' / f'{name}.meta.json').exists():
        previous, meta = load_snapshot(data, name)
        if previous != raw or meta['url'] != url:
            raise ValueError('Refusing to replace an immutable snapshot')
        return meta
    record = dict(url=url, path=f'raw/{name}.raw', bytes=len(raw), sha256=digest(raw),
                  retrieved_at_utc=retrieved_at or datetime.now(timezone.utc).isoformat(),
                  content_type=content_type)
    raw_path = data / record['path']
    if raw_path.exists() and raw_path.read_bytes() != raw:
        raise ValueError('Refusing to replace an immutable snapshot')
    raw_path.parent.mkdir(parents=True, exist_ok=True)
    raw_path.write_bytes(raw)
    save_json(data / 'raw' / f'{name}.meta.json', record)
    return record


def collect(data):
    previous_path = data / 'manifest.json'
    previous = json.loads(previous_path.read_text(encoding='utf-8')) if previous_path.exists() else {}
    active = {name for name, _ in source_specs()}
    attempts = [a for a in previous.get('attempts', []) if a['name'] in active]
    sources, failures = [], []
    for name, url in source_specs():
        try:
            sources.append(dict(name=name, **fetch(data, name, url)))
            print(name, 'saved', flush=True)
        except Exception as error:
            failure = dict(name=name, url=url, error=f'{type(error).__name__}: {error}',
                           attempted_at_utc=datetime.now(timezone.utc).isoformat())
            failures.append(failure)
            attempts.append(failure)
            print(name, failure['error'], flush=True)
        time.sleep(.15)
    manifest = dict(seasons=list(YEARS), game_type='R', unit='team-season',
                    sources=sources, failures=failures, attempts=attempts,
                    collection_complete=not failures)
    save_json(previous_path, manifest)
    return manifest


def parse_fg(raw, year):
    obj = json.loads(raw)
    rows = obj['data']
    if len(rows) != 30 or integer(obj['totalCount']) != 30:
        raise ValueError('Expected complete 30-team FanGraphs response')
    result = {}
    for row in rows:
        if integer(row['Season']) != year:
            raise ValueError('FanGraphs season mismatch')
        tid = team_id(row['TeamName'])
        if tid in result:
            raise ValueError('Duplicate FanGraphs team')
        result[tid] = dict(war=number(row['WAR']), source_team_id=integer(row['teamid']),
                           wins=row.get('W'), losses=row.get('L'))
    return result


def audit(data):
    rows, issues, snapshots = [], [], []
    manifest_path = data / 'manifest.json'
    manifest = json.loads(manifest_path.read_text(encoding='utf-8')) if manifest_path.exists() else {}
    failed_sources = {f['name']: f['error'] for f in manifest.get('failures', [])}
    for year in YEARS:
        loaded = {}
        for name, _ in source_specs():
            if f'-{year}' not in name:
                continue
            try:
                raw, meta = load_snapshot(data, name)
                snapshots.append(dict(name=name, **meta))
                loaded[name] = (raw, meta)
            except FileNotFoundError:
                issue=dict(source=name,error='FileNotFoundError: raw snapshot not acquired')
                if name in failed_sources:
                    issue['collection_error']=failed_sources[name]
                issues.append(issue)
            except Exception as error:
                issues.append(dict(source=name, error=f'{type(error).__name__}: {error}'))
        try:
            standings = json.loads(loaded[f'mlb-{year}'][0])
            teams = {integer(t['id']): t['name'] for t in json.loads(loaded[f'teams-{year}'][0])['teams']}
            official = [t for group in standings['records'] for t in group['teamRecords']]
            if len(official) != 30 or len(teams) != 30:
                raise ValueError('MLB coverage must contain 30 teams')
        except Exception as error:
            issues.append(dict(source=f'mlb-{year}', error=str(error)))
            continue
        parsed = {}
        for provider in ('fg',):
            for kind in ('bat', 'pit'):
                name = f'{provider}-{year}-{kind}'
                if name not in loaded:
                    continue
                try:
                    raw, meta = loaded[name]
                    parsed[provider, kind] = parse_fg(raw, year)
                    if set(parsed[provider, kind]) != set(teams):
                        raise ValueError('Provider team IDs differ from MLB')
                except Exception as error:
                    parsed.pop((provider, kind), None)
                    issues.append(dict(source=name, error=str(error)))
        season_rows = []
        for t in official:
            try:
                tid = integer(t['team']['id'])
                if str(t['season']) != str(year):
                    raise ValueError('Standings season mismatch')
                g, w, l = (integer(t[k]) for k in ('gamesPlayed', 'wins', 'losses'))
                if g != w + l or not 0 < g <= 163 or min(w, l) < 0:
                    raise ValueError('Invalid games/wins/losses')
                rs, ra = integer(t['runsScored']), integer(t['runsAllowed'])
                if min(rs, ra) < 0 or rs + ra <= 0:
                    raise ValueError('Invalid runs')
                row = dict(season=year, team_id=tid, team=teams[tid], games=g,
                           wins=w, losses=l, runs_scored=rs, runs_allowed=ra)
                for provider, prefix in [('fg', 'fwar')]:
                    for kind in ('bat', 'pit'):
                        entry = parsed.get((provider, kind), {}).get(tid)
                        row[f'{prefix}_{kind}'] = entry['war'] if provider == 'fg' and entry is not None else entry
                        if provider == 'fg' and kind == 'pit' and entry is not None:
                            if (integer(entry['wins']), integer(entry['losses'])) != (w, l):
                                raise ValueError('FanGraphs pitching W/L differ from MLB')
                    bat, pit = row[f'{prefix}_bat'], row[f'{prefix}_pit']
                    row[prefix] = bat + pit if bat is not None and pit is not None else None
                season_rows.append(row)
            except Exception as error:
                issues.append(dict(source=f'{year}-{t["team"]["id"]}', error=str(error)))
        if len({r['team_id'] for r in season_rows}) != 30:
            issues.append(dict(source=f'{year}-coverage', error='Incomplete/duplicate season'))
        if sum(r['wins'] for r in season_rows) != sum(r['losses'] for r in season_rows):
            issues.append(dict(source=f'{year}-league', error='League wins and losses differ'))
        if sum(r['runs_scored'] for r in season_rows) != sum(r['runs_allowed'] for r in season_rows):
            issues.append(dict(source=f'{year}-league', error='League runs scored/allowed differ'))
        rows.extend(season_rows)
    rows.sort(key=lambda r: (r['season'], r['team_id']))
    keys = [(r['season'], r['team_id']) for r in rows]
    if len(keys) != len(set(keys)):
        raise ValueError('Duplicate team-season key')
    available = {p: sum(r[p] is not None for r in rows) for p in ('fwar',)}
    checks_path = data / 'case-audit.json'
    case_checks = json.loads(checks_path.read_text(encoding='utf-8')) if checks_path.exists() else {'status': 'pending'}
    complete = len(rows) == 150 and all(n == 150 for n in available.values()) and not issues and case_checks.get('status') == 'pass'
    result = dict(status='complete' if complete else 'incomplete', rows=len(rows),
                  available=available, missing={p:150-n for p,n in available.items()},
                  issues=issues, sources=snapshots, case_checks=case_checks)
    save_json(data / 'audit.json', result)
    save_json(data / 'processed/team-seasons.json', rows)
    if rows:
        path = data / 'processed/team-seasons.csv'
        with path.open('w', encoding='utf-8-sig', newline='') as stream:
            writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
    print(json.dumps({k: result[k] for k in ('status', 'rows', 'available', 'missing')}, ensure_ascii=False))
    return result


def collect_cases(data):
    specs = [
        ('fg-case-laa-2023-bat', fg_url(2023, 'bat', '1')),
        ('fg-case-laa-2023-pit', fg_url(2023, 'pit', '1')),
        ('fg-case-col-2023-bat', fg_url(2023, 'bat', '19')),
        ('fg-case-grichuk-2023-total', fg_url(2023, 'bat', '0', 10243)),
        ('fg-case-ohtani-2023-bat', fg_url(2023, 'bat', '0', 19755)),
        ('fg-case-ohtani-2023-pit', fg_url(2023, 'pit', '0', 19755)),
    ]
    for name, url in specs:
        fetch(data, name, url)
    return audit_cases(data)


def audit_cases(data):
    evidence, sources = [], []

    def records(name):
        raw, meta = load_snapshot(data, name)
        sources.append(dict(name=name, **meta))
        obj = json.loads(raw)
        if len(obj['data']) != integer(obj['totalCount']):
            raise ValueError('Incomplete case leaderboard')
        return obj['data']

    def player(rows, pid):
        found = [r for r in rows if integer(r['playerid']) == pid]
        if len(found) != 1:
            raise ValueError('Case player must occur exactly once in team records')
        return found[0]

    try:
        laa_bat = records('fg-case-laa-2023-bat')
        laa_pit = records('fg-case-laa-2023-pit')
        col_bat = records('fg-case-col-2023-bat')
        for code, kind, rows in [('LAA', 'bat', laa_bat), ('LAA', 'pit', laa_pit), ('COL', 'bat', col_bat)]:
            if len({r['playerid'] for r in rows}) != len(rows):
                raise ValueError('Duplicate player in case team')
            raw, meta = load_snapshot(data, f'fg-2023-{kind}')
            sources.append(dict(name=f'fg-2023-{kind}', **meta))
            expected = parse_fg(raw, 2023)[team_id(code)]['war']
            actual = sum(number(r['WAR']) for r in rows)
            if abs(expected - actual) > 1e-6:
                raise ValueError('Player/team WAR reconciliation failed')
            evidence.append(dict(check='player_team_sum', team=code, kind=kind,
                                 player_count=len(rows), negative_count=sum(number(r['WAR']) < 0 for r in rows),
                                 player_sum=actual, team_total=expected, difference=actual-expected, tolerance=1e-6))
        total = player(records('fg-case-grichuk-2023-total'), 10243)
        stints = [player(laa_bat, 10243), player(col_bat, 10243)]
        summed = sum(number(r['WAR']) for r in stints)
        # Context/rounding can cause small differences; preserve the observed delta.
        if abs(summed-number(total['WAR'])) > .1:
            raise ValueError('Traded player split/total WAR differ by more than 0.1')
        evidence.append(dict(check='traded_player', player='Randal Grichuk', season=2023,
                             stints=[dict(team=r['TeamName'], war=r['WAR']) for r in stints],
                             season_total=total['WAR'], difference=summed-number(total['WAR']), tolerance=.1))
        components = {}
        for kind, rows in [('bat', laa_bat), ('pit', laa_pit)]:
            row = player(rows, 19755)
            separate = player(records(f'fg-case-ohtani-2023-{kind}'), 19755)
            if abs(number(row['WAR'])-number(separate['WAR'])) > 1e-6:
                raise ValueError('Two-way player cross-check failed')
            components[kind] = row['WAR']
        evidence.append(dict(check='two_way_player', player='Shohei Ohtani', season=2023,
                             components=components, combined=sum(components.values())))
        result = dict(status='pass', fwar='pass', evidence=evidence,
                      sources=sources, reason='FanGraphs player/team cases reconciled')
    except Exception as error:
        result = dict(status='fail', fwar='fail', evidence=evidence,
                      sources=sources, reason=str(error))
    save_json(data / 'case-audit.json', result)
    print(json.dumps({k:result[k] for k in ('status','fwar','reason')}, ensure_ascii=False))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('stage', choices=['collect', 'audit', 'collect-cases', 'audit-cases'])
    parser.add_argument('--data', type=Path, default=DATA)
    args = parser.parse_args()
    if args.stage == 'collect':
        collect(args.data)
    elif args.stage in ('collect-cases', 'audit-cases'):
        (collect_cases if args.stage == 'collect-cases' else audit_cases)(args.data)
    audit(args.data)


if __name__ == '__main__':
    main()

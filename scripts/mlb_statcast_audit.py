"""Download/audit 2026 Statcast with Python's standard library only. No modeling."""
from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import io
import json
import math
import re
import time
import urllib.parse
import urllib.request
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

NUMERIC_FIELDS = ('launch_speed', 'launch_angle', 'hit_distance_sc')
MISSING_TOKENS = {'', 'null', 'nan', 'none', 'na', 'n/a'}
HITS = {'single', 'double', 'triple', 'home_run'}

ROOT = Path(__file__).resolve().parents[1] / 'data' / 'mlb' / '2026'
SAVANT = 'https://baseballsavant.mlb.com/statcast_search/csv'


def request(url: str) -> bytes:
    for attempt in range(4):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'MLB-2026-research-audit/1.0'})
            with urllib.request.urlopen(req, timeout=120) as response:
                return response.read()
        except Exception:
            if attempt == 3:
                raise
            time.sleep(3 * (attempt + 1))
    raise RuntimeError('unreachable')


def csv_url(start: str, end: str, inplay: bool = True) -> str:
    params = {'all': 'true', 'type': 'details', 'hfGT': 'R|',
              'hfSea': '2026|', 'game_date_gt': start, 'game_date_lt': end,
              'player_type': 'pitcher', 'min_pitches': '0', 'min_results': '0',
              'min_abs': '0', 'group_by': 'name', 'sort_col': 'pitches',
              'sort_order': 'desc'}
    if inplay:
        params['hfPR'] = 'hit_into_play|'
    return SAVANT + '?' + urllib.parse.urlencode(params)


def parse(data: bytes) -> tuple[list[str], list[dict[str, str]]]:
    reader = csv.DictReader(io.StringIO(data.decode('utf-8-sig')))
    fields = reader.fieldnames or []
    if 'game_pk' not in fields or 'launch_speed' not in fields:
        raise ValueError(f'Invalid Statcast CSV: {data[:160]!r}')
    rows = list(reader)
    if len(rows) >= 25000:
        raise ValueError(f'Possible server row truncation: {len(rows)}')
    return fields, rows


def sample() -> None:
    (ROOT / 'raw').mkdir(parents=True, exist_ok=True)
    initial = ROOT.parents[1] / 'mlb-2026-schedule-initial.json'
    existing = ROOT / 'raw' / 'schedule.json'
    if existing.exists():
        schedule = json.loads(existing.read_text(encoding='utf-8'))
    elif initial.exists():
        schedule = json.loads(initial.read_text(encoding='utf-8-sig'))
    else:
        schedule = json.loads(request('https://statsapi.mlb.com/api/v1/schedule?sportId=1&season=2026&gameType=R'))
    (ROOT / 'raw' / 'schedule.json').write_text(json.dumps(schedule, ensure_ascii=False, indent=2), encoding='utf-8')
    day = schedule['dates'][0]['date']
    results = {}
    for label, inplay in [('all', False), ('inplay', True)]:
        url = csv_url(day, day, inplay)
        data = request(url)
        fields, rows = parse(data)
        with gzip.open(ROOT / 'raw' / f'sample-{day}-{label}.csv.gz', 'wb') as f:
            f.write(data)
        results[label] = {'rows': len(rows), 'types': dict(Counter(r['type'] for r in rows)),
                          'descriptions': dict(Counter(r['description'] for r in rows)),
                          'events': dict(Counter(r['events'] for r in rows)), 'url': url,
                          'keys': sorted((r['game_pk'], r['at_bat_number'], r['pitch_number'])
                                         for r in rows if r['type'] == 'X')}
    results['filter_matches_type_X'] = results['all']['keys'] == results['inplay']['keys']
    for item in (results['all'], results['inplay']):
        del item['keys']
    (ROOT / 'sample-check.json').write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(results, ensure_ascii=False, indent=2), flush=True)


def download() -> None:
    check = json.loads((ROOT / 'sample-check.json').read_text(encoding='utf-8'))
    if not check['filter_matches_type_X']:
        raise ValueError('In-play filter has not passed the sample check')
    schedule = json.loads((ROOT / 'raw' / 'schedule.json').read_text(encoding='utf-8'))
    completed = [g for d in schedule['dates'] for g in d['games']
                 if g['status']['detailedState'] in {'Final', 'Completed Early'}]
    start = date.fromisoformat(min(g['officialDate'] for g in completed))
    end = date.fromisoformat(max(g['officialDate'] for g in completed))
    spans = []
    cursor = start
    while cursor <= end:
        stop = min(cursor + timedelta(days=6), end)
        spans.append((cursor.isoformat(), stop.isoformat()))
        cursor = stop + timedelta(days=1)
    out = ROOT / 'raw' / 'statcast'
    out.mkdir(parents=True, exist_ok=True)

    def fetch(span: tuple[str, str]) -> dict:
        first, last = span
        path = out / f'{first}_{last}.csv.gz'
        url = csv_url(first, last)
        cached = path.exists()
        data = gzip.decompress(path.read_bytes()) if cached else request(url)
        fields, rows = parse(data)
        invalid = [r for r in rows if r['description'] != 'hit_into_play' or r['game_type'] != 'R'
                   or not r['game_date'].startswith('2026-')]
        if invalid:
            raise ValueError(f'Unexpected row outside requested population: {first}')
        if not cached:
            with gzip.open(path, 'wb') as f:
                f.write(data)
        info = {'start': first, 'end': last, 'url': url, 'path': str(path.relative_to(ROOT)),
                'rows': len(rows), 'columns': len(fields), 'sha256_csv': hashlib.sha256(data).hexdigest(),
                'dates_outside_query': dict(Counter(r['game_date'] for r in rows if not first <= r['game_date'] <= last)),
                'pitch_type_counts': dict(Counter(r['type'] for r in rows)),
                'bytes_csv': len(data), 'bytes_gzip': path.stat().st_size,
                'retrieved_at_utc': datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat()}
        return info

    chunks = []
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = {pool.submit(fetch, span): span for span in spans}
        for future in as_completed(futures):
            info = future.result()
            chunks.append(info)
            print(f"[{len(chunks)}/{len(spans)}] {info['start']}..{info['end']}: {info['rows']} source rows", flush=True)
    manifest = {'season': 2026, 'game_type': 'R', 'source': SAVANT,
                'audit_as_of_kst': '2026-10-11', 'first_game_date': start.isoformat(),
                'last_game_date': end.isoformat(), 'completed_schedule_entries': len(completed),
                'completed_schedule_games': len({g['gamePk'] for g in completed}),
                'rows_downloaded': sum(c['rows'] for c in chunks),
                'chunks': sorted(chunks, key=lambda c: c['start']),
                'note': 'All hit_into_play rows; no EV/LA/distance/non-bunt filter, no imputation, no modeling.'}
    (ROOT / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({k: v for k, v in manifest.items() if k != 'chunks'}, ensure_ascii=False), flush=True)


def missing(value: str | None) -> bool:
    return value is None or value.strip().lower() in MISSING_TOKENS


def number(value: str | None) -> float | None:
    if missing(value):
        return None
    try:
        result = float(value)
        return result if math.isfinite(result) else None
    except (TypeError, ValueError):
        return None


def summarize(rows: list[dict]) -> dict:
    total = len(rows)
    result = {'n': total}
    for field in (*NUMERIC_FIELDS, 'events', 'bb_type', 'estimated_ba_using_speedangle'):
        absent = sum(missing(r.get(field)) for r in rows)
        invalid = sum(not missing(r.get(field)) and number(r.get(field)) is None for r in rows) if field not in {'events', 'bb_type'} else 0
        result[field + '_missing'] = absent
        result[field + '_missing_pct'] = round(100 * absent / total, 4) if total else None
        result[field + '_invalid'] = invalid
    result['missing_ev_or_la'] = sum(any(missing(r.get(k)) for k in NUMERIC_FIELDS[:2]) for r in rows)
    result['missing_any_ev_la_distance'] = sum(any(missing(r.get(k)) for k in NUMERIC_FIELDS) for r in rows)
    result['available_probability'] = sum(all(number(r.get(k)) is not None for k in NUMERIC_FIELDS[:2]) and not missing(r.get('events')) for r in rows)
    result['available_distance'] = sum(all(number(r.get(k)) is not None for k in NUMERIC_FIELDS) for r in rows)
    result['home_runs'] = sum(r.get('events') == 'home_run' for r in rows)
    result['hits'] = sum(r.get('events') in HITS for r in rows)
    result['games'] = len({r['game_pk'] for r in rows})
    return result


def write_csv(path: Path, records: list[dict]) -> None:
    if not records:
        path.write_text('', encoding='utf-8-sig')
        return
    with path.open('w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=list(records[0]))
        writer.writeheader()
        writer.writerows(records)


def quantile(values: list[float], q: float) -> float | None:
    if not values:
        return None
    pos = (len(values) - 1) * q
    lower = int(pos)
    upper = min(lower + 1, len(values) - 1)
    return values[lower] + (values[upper] - values[lower]) * (pos - lower)


def verify() -> None:
    manifest = json.loads((ROOT / 'manifest.json').read_text(encoding='utf-8'))
    checks = []
    for day in (manifest['first_game_date'], manifest['last_game_date']):
        path = ROOT / 'raw' / f'sample-{day}-all.csv.gz'
        if path.exists():
            data = gzip.decompress(path.read_bytes())
        else:
            data = request(csv_url(day, day, False))
            path.write_bytes(gzip.compress(data))
        _, full = parse(data)
        expected = {(r['game_pk'], r['at_bat_number'], r['pitch_number'])
                    for r in full if r['type'] == 'X'}
        actual = set()
        for chunk in manifest['chunks']:
            if not chunk['start'] <= day <= chunk['end']:
                continue
            _, filtered = parse(gzip.decompress((ROOT / chunk['path']).read_bytes()))
            actual.update((r['game_pk'], r['at_bat_number'], r['pitch_number'])
                          for r in filtered if r['game_date'] == day and r['type'] == 'X')
        check = {'game_date': day, 'full_pitch_rows': len(full), 'full_type_X_rows': len(expected),
                 'filtered_type_X_rows': len(actual), 'keys_match': expected == actual,
                 'missing_keys': sorted(expected - actual), 'extra_keys': sorted(actual - expected),
                 'full_query_url': csv_url(day, day, False)}
        checks.append(check)
    (ROOT / 'filter-check.json').write_text(json.dumps(checks, indent=2), encoding='utf-8')
    print(json.dumps(checks, indent=2), flush=True)
    if not all(c['keys_match'] for c in checks):
        raise ValueError('Full-pitch/filtered-pitch cross-check failed')


def audit() -> None:
    manifest = json.loads((ROOT / 'manifest.json').read_text(encoding='utf-8'))
    schedule = json.loads((ROOT / 'raw' / 'schedule.json').read_text(encoding='utf-8'))
    games = {str(g['gamePk']): g for day in schedule['dates'] for g in day['games']
             if g['status']['detailedState'] in {'Final', 'Completed Early'}}
    first, last = manifest['first_game_date'], manifest['last_game_date']
    kept = ['game_date', 'game_pk', 'at_bat_number', 'pitch_number', 'batter', 'pitcher',
            'player_name', 'events', 'description', 'type', 'game_type', 'des',
            'launch_speed', 'launch_angle', 'hit_distance_sc', 'bb_type',
            'estimated_ba_using_speedangle', 'home_team', 'away_team', 'hc_x', 'hc_y']
    rows, key_counts, row_hashes, duplicate_rows, conflicts = [], Counter(), {}, [], []
    non_batted_response_rows = []
    column_missing = {p: Counter() for p in ('all_batted_balls', 'non_bunt_candidates', 'bunt_candidates')}
    schemas, chunk_checks = [], []
    for chunk in manifest['chunks']:
        data = gzip.decompress((ROOT / chunk['path']).read_bytes())
        fields, chunk_rows = parse(data)
        if hashlib.sha256(data).hexdigest() != chunk['sha256_csv']:
            raise ValueError('Raw chunk hash mismatch')
        schemas.append(fields)
        chunk_checks.append({'start': chunk['start'], 'end': chunk['end'], 'actual_rows': len(chunk_rows),
                             'manifest_rows': chunk['rows'], 'sha256_matches': True})
        for raw in chunk_rows:
            if raw['type'] != 'X':
                non_batted_response_rows.append({k: raw.get(k, '') for k in kept})
                continue
            key = tuple(raw[k] for k in ('game_pk', 'at_bat_number', 'pitch_number'))
            key_counts[key] += 1
            digest = hashlib.sha256(json.dumps(raw, sort_keys=True).encode()).hexdigest()
            if key in row_hashes:
                duplicate_rows.append({k: raw[k] for k in kept})
                if digest != row_hashes[key]:
                    conflicts.append(key)
            else:
                row_hashes[key] = digest
            row = {k: raw.get(k, '') for k in kept}
            game = games.get(raw['game_pk'])
            row['venue_id'] = str(game['venue']['id']) if game else 'unknown'
            row['venue_name'] = game['venue']['name'] if game else 'unknown'
            row['schedule_official_date'] = game['officialDate'] if game else ''
            row['is_bunt_candidate'] = bool(re.search(r'\bbunt(?:s|ed|ing)?\b', raw.get('des', ''), re.I)
                                             or raw['events'] in {'sac_bunt', 'sac_bunt_double_play'})
            population = 'bunt_candidates' if row['is_bunt_candidate'] else 'non_bunt_candidates'
            for field in fields:
                if missing(raw.get(field)):
                    column_missing['all_batted_balls'][field] += 1
                    column_missing[population][field] += 1
            row['split'] = 'opening_day_holdout' if raw['game_date'] == first else 'final_day_holdout' if raw['game_date'] == last else 'middle_dates'
            row['outcome_group'] = 'home_run' if raw['events'] == 'home_run' else 'non_hr_hit' if raw['events'] in HITS else 'non_hit' if raw['events'] else 'unknown'
            for field in NUMERIC_FIELDS:
                row[field + '_missing'] = missing(raw.get(field))
            rows.append(row)
    out = ROOT / 'audit'
    out.mkdir(exist_ok=True)
    with gzip.open(out / 'batted_ball_inventory.csv.gz', 'wt', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    nonbunts = [r for r in rows if not r['is_bunt_candidate']]
    bunts = [r for r in rows if r['is_bunt_candidate']]
    sets = {'all_batted_balls': rows, 'non_bunt_candidates': nonbunts, 'bunt_candidates': bunts}
    overall = {label: summarize(subset) for label, subset in sets.items()}
    write_csv(out / 'all_column_missingness.csv',
              [{'population': p, 'field': field, 'n': len(sets[p]),
                'missing': column_missing[p][field],
                'missing_pct': round(100 * column_missing[p][field] / len(sets[p]), 4)}
               for p in sets for field in schemas[0]])
    grouped = {}
    for population, subset in sets.items():
        for dimension in ('game_date', 'month', 'venue_name', 'bb_type', 'events', 'outcome_group', 'split'):
            buckets = {}
            for r in subset:
                value = r['game_date'][:7] if dimension == 'month' else r[dimension] or '(missing)'
                buckets.setdefault(value, []).append(r)
            records = [{'population': population, 'group': key, **summarize(bucket)}
                       for key, bucket in sorted(buckets.items())]
            grouped[f'{population}_by_{dimension}'] = records
            write_csv(out / f'{population}_by_{dimension}.csv', records)
    patterns = []
    for population, subset in sets.items():
        counts = Counter(tuple(missing(r[k]) for k in NUMERIC_FIELDS) for r in subset)
        for pattern, count in sorted(counts.items()):
            patterns.append({'population': population, **dict(zip(NUMERIC_FIELDS, pattern)),
                             'n': count, 'pct': round(100 * count / len(subset), 4) if subset else 0})
    write_csv(out / 'missing_patterns.csv', patterns)
    numeric = []
    suspect = []
    for field in NUMERIC_FIELDS:
        values = sorted(v for r in nonbunts if (v := number(r[field])) is not None)
        numeric.append({'field': field, 'n': len(values), 'min': quantile(values, 0),
                        'p01': quantile(values, .01), 'median': quantile(values, .5),
                        'p99': quantile(values, .99), 'max': quantile(values, 1),
                        'zero_count': values.count(0), 'negative_count': sum(v < 0 for v in values)})
    for r in nonbunts:
        reasons = []
        speed, angle, distance = [number(r[k]) for k in NUMERIC_FIELDS]
        if speed is not None and (speed <= 0 or speed > 130):
            reasons.append('speed_outside_review_range_(0,130]mph')
        if angle is not None and not -90 <= angle <= 90:
            reasons.append('angle_outside_[-90,90]deg')
        if distance is not None and (distance < 0 or distance > 600):
            reasons.append('distance_outside_[0,600]ft')
        for field in NUMERIC_FIELDS:
            if not missing(r[field]) and number(r[field]) is None:
                reasons.append(field + '_invalid_numeric')
        if reasons:
            suspect.append({**{k: r[k] for k in kept}, 'review_reasons': '|'.join(reasons)})
    write_csv(out / 'numeric_ranges.csv', numeric)
    write_csv(out / 'review_flagged_rows.csv', suspect)
    write_csv(out / 'duplicate_rows.csv', duplicate_rows)
    write_csv(out / 'non_batted_response_rows.csv', non_batted_response_rows)
    write_csv(out / 'bunt_candidates.csv', [{k: r[k] for k in kept} for r in bunts])
    write_csv(out / 'non_bunt_missing_rows.csv', [{k: r[k] for k in (*kept, 'venue_name', 'split')}
                                             for r in nonbunts if any(missing(r[k]) for k in NUMERIC_FIELDS)])
    observed = {r['game_pk'] for r in rows}
    absent_games = [{'game_pk': k, 'date': g['officialDate'], 'venue': g['venue']['name']} for k, g in games.items() if k not in observed]
    unexpected_games = sorted(observed - games.keys())
    date_mismatch = [r for r in rows if r['schedule_official_date'] and r['game_date'] != r['schedule_official_date']]
    schedule_entries = [(day['date'], g) for day in schedule['dates'] for g in day['games']
                        if g['status']['detailedState'] in {'Final', 'Completed Early'}]
    schedule_counts = Counter(str(g['gamePk']) for _, g in schedule_entries)
    duplicate_schedule_entries = [{'schedule_date': day, 'game_pk': str(g['gamePk']), 'official_date': g['officialDate'], 'resume_date': g.get('resumeDate')}
                                  for day, g in schedule_entries if schedule_counts[str(g['gamePk'])] > 1]
    filter_checks = json.loads((ROOT / 'filter-check.json').read_text(encoding='utf-8')) if (ROOT / 'filter-check.json').exists() else []
    quality = {'raw_download_rows': manifest['rows_downloaded'], 'raw_rows': len(rows),
               'non_batted_response_rows': len(non_batted_response_rows),
               'non_batted_response_event_counts': dict(Counter(r['events'] for r in non_batted_response_rows)),
               'unique_pitch_keys': len(key_counts),
               'duplicate_extra_rows': len(rows) - len(key_counts), 'conflicting_duplicate_keys': len(conflicts),
               'games_in_schedule': len(games), 'games_in_statcast': len(observed),
               'completed_schedule_entries': len(schedule_entries),
               'duplicate_schedule_entries': duplicate_schedule_entries,
               'schedule_games_without_statcast': absent_games, 'unexpected_statcast_games': unexpected_games,
               'date_mismatch_rows': len(date_mismatch), 'schema_consistent': all(s == schemas[0] for s in schemas),
               'columns': schemas[0], 'duplicate_header_names': {k: v for k, v in Counter(schemas[0]).items() if v > 1},
               'review_flagged_rows': len(suspect), 'events_all': dict(Counter(r['events'] for r in rows)),
               'bunt_event_counts': dict(Counter(r['events'] for r in bunts)),
               'bunt_detection': 'des case-insensitive word bunt/bunts/bunted/bunting OR sac_bunt/sac_bunt_double_play; candidate flag, not authoritative bunt label',
               'all_raw_hashes_verified': True, 'no_imputation_or_model_training': True,
               'reserved_dates': [first, last]}
    quality['full_pitch_filter_checks'] = filter_checks
    zeros = [r for r in nonbunts if number(r['hit_distance_sc']) == 0]
    quality['zero_distance_non_bunt_by_bb_type'] = dict(Counter(r['bb_type'] for r in zeros))
    result = {'manifest': {k: v for k, v in manifest.items() if k != 'chunks'},
              'overall': overall, 'quality': quality, 'numeric_ranges_non_bunt': numeric,
              'missing_patterns': patterns, 'grouped': grouped}
    (out / 'summary.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    (out / 'reserved-dates.json').write_text(json.dumps({'game_date': [first, last], 'rule': 'Exclude entire dates from future training, tuning, preprocessing fitting and calibration.'}, indent=2), encoding='utf-8')
    write_csv(out / 'chunk_integrity.csv', chunk_checks)
    write_csv(out / 'duplicate_schedule_entries.csv', duplicate_schedule_entries)
    write_report(result)
    print(json.dumps({'overall': overall, 'quality': {k: v for k, v in quality.items() if k != 'columns'}, 'numeric': numeric}, ensure_ascii=False, indent=2), flush=True)


def write_report(result: dict) -> None:
    summary, quality = result['overall'], result['quality']
    main = summary['non_bunt_candidates']
    first, last = quality['reserved_dates']
    zero_count = next(r['zero_count'] for r in result['numeric_ranges_non_bunt'] if r['field'] == 'hit_distance_sc')
    opening = next(r for r in result['grouped']['non_bunt_candidates_by_split'] if r['group'] == 'opening_day_holdout')
    def fmt(value):
        return f'{value:,}' if isinstance(value, int) else str(value)
    def rate(count, n):
        return f'{100 * count / n:.3f}%' if n else '—'
    def table(headers, records):
        return '\n'.join(['| ' + ' | '.join(headers) + ' |', '| ' + ' | '.join(['---'] * len(headers)) + ' |'] + ['| ' + ' | '.join(str(v) for v in row) + ' |' for row in records])
    lines = ['# 2026 MLB Statcast 결측치 사전 보고', '',
             f'분석 기준일: 2026-10-11 KST. 경기 날짜 범위: **{first} ~ {last}**. 정규시즌만 수집.', '',
             '이 보고서는 원본의 품질과 사용 가능한 표본을 조사한다. 결측치 보간·대체, 이상값 삭제, 모델 학습은 수행하지 않았다. 원본은 모든 타구와 번트 후보를 그대로 보관한다.', '',
             '## 핵심 결과', '',
             f"- 실제 타구 {quality['raw_rows']:,}개 중 번트 후보 {summary['bunt_candidates']['n']:,}개. 비번트 후보 **{main['n']:,}개**를 기준으로 주 분석의 결측 상태를 평가했다.",
             f"- 속도·각도·비거리 중 하나 이상이 없는 비번트 타구는 **{main['missing_any_ev_la_distance']:,}개 ({rate(main['missing_any_ev_la_distance'], main['n'])})**다.",
             '- 결측 비율은 전체적으로 낮지만 땅볼과 일부 구장에 집중되어 있다. 완전 사례만 사용하면 표본 구성이 달라지는지 확인할 필요가 있다.',
             f"- 비거리 0인 비번트 타구는 {zero_count:,}개다. 타구 종류별 분포: {quality['zero_distance_non_bunt_by_bb_type']}. 빈 값과 별도로 보관했다.",
             f"- 개막일은 비번트 타구 {opening['n']:,}개, 홈런 {opening['home_runs']:,}개다. 요청한 검증일은 그대로 지정했으며, 이 날짜의 작은 표본과 클래스 분포를 고려해 성능을 해석해야 한다.", '',
             '## 1. 수집 범위와 완전성', '',
             table(['항목', '결과'], [['다운로드 원본 행', fmt(quality['raw_download_rows'])],
                    ['type=X 타구 행', fmt(quality['raw_rows'])],
                    ['응답에 섞인 비타구 행 (별도 보관)', fmt(quality['non_batted_response_rows'])],
                    ['MLB 일정 완료 경기 / Statcast 관측 경기', f"{quality['games_in_schedule']:,} / {quality['games_in_statcast']:,}"],
                    ['일정에는 있지만 타구가 없는 경기', len(quality['schedule_games_without_statcast'])],
                    ['예상 밖 경기 ID', len(quality['unexpected_statcast_games'])],
                    ['고유 투구 키', fmt(quality['unique_pitch_keys'])],
                    ['중복 초과 행 / 충돌 키', f"{quality['duplicate_extra_rows']} / {quality['conflicting_duplicate_keys']}"],
                    ['공식 경기 날짜 불일치 행', quality['date_mismatch_rows']],
                    ['원본 열 수 / 청크 스키마 일치', f"{len(quality['columns'])} / {quality['schema_consistent']}"],
                    ['번트 후보 / 비번트 후보', f"{summary['bunt_candidates']['n']:,} / {main['n']:,}"]]), '',
             '타구 필터: `hfGT=R|`, `hfSea=2026|`, `hfPR=hit_into_play|`. 속도·각도·비거리 필터는 사용하지 않았다. 7일씩 분할 수집하며 각 청크 행 수와 SHA-256을 manifest에 보관하고 다시 검증했다. 개막일 전체 투구의 type=X와 타구 필터 결과를 대조했다.', '',
             f"CSV 응답에는 description=hit_into_play이지만 type=X가 아닌 행이 {quality['non_batted_response_rows']:,}개 포함되어 있었다. 이벤트별 수: {quality['non_batted_response_event_counts']}. 타구 모집단은 type=X로 정의하고, 이 비타구 행은 원본 및 non_batted_response_rows.csv에 보존했다.", '',
             f"공식 일정의 완료 기록은 {quality['completed_schedule_entries']:,}건이고 고유 경기 ID는 {quality['games_in_schedule']:,}개다. 서스펜디드 경기의 재개 일정 등으로 반복된 ID는 audit/duplicate_schedule_entries.csv에 보관했다. 일정은 고유 경기 ID로 대조하고 타구 중복은 별도로 검사했다.", '',
             '경기 ID가 모두 일치해도 개별 타구가 하나도 누락되지 않았음을 완전히 보장하지는 않는다. 개막일과 최종일은 별도 전체 투구 요청의 type=X 키와 필터 타구 키를 직접 대조했다. 대조 결과는 filter-check.json에 보관했다.', '',
             '## 2. 결측치 규모', '',
             table(['항목', '전체 타구 결측', '전체 비율', '비번트 후보 결측', '비번트 비율'],
                   [[label, fmt(summary['all_batted_balls'][field + '_missing']), rate(summary['all_batted_balls'][field + '_missing'], summary['all_batted_balls']['n']),
                     fmt(main[field + '_missing']), rate(main[field + '_missing'], main['n'])]
                    for field, label in [('launch_speed', '타구 속도'), ('launch_angle', '발사각'), ('hit_distance_sc', '추정 비거리'), ('events', '타구 결과'), ('bb_type', '타구 종류')]]), '',
             table(['비번트 후보 기준 가용 표본', '타구 수', '전체 비번트 대비'],
                   [['속도·각도·결과가 있는 타구 (확률 분석 후보)', fmt(main['available_probability']), rate(main['available_probability'], main['n'])],
                    ['속도·각도·비거리가 있는 타구 (비거리 분석 후보)', fmt(main['available_distance']), rate(main['available_distance'], main['n'])],
                    ['속도 또는 각도 결측', fmt(main['missing_ev_or_la']), rate(main['missing_ev_or_la'], main['n'])],
                    ['속도·각도·비거리 중 하나 이상 결측', fmt(main['missing_any_ev_la_distance']), rate(main['missing_any_ev_la_distance'], main['n'])]]), '',
             '가용 표본 수는 결측 상태만을 기준으로 한 후보 수다. 최종 채택 여부는 사용자가 결정한다. 0은 결측으로 처리하지 않았으며, 비거리 0의 처리도 확정하지 않았다.', '',
             table(['비번트 결측 조합', '타구 수'],
                   [[('속도 없음' if r['launch_speed'] else '속도 있음') + ' / ' + ('각도 없음' if r['launch_angle'] else '각도 있음') + ' / ' + ('비거리 없음' if r['hit_distance_sc'] else '비거리 있음'), fmt(r['n'])]
                    for r in result['missing_patterns'] if r['population'] == 'non_bunt_candidates']), '',
             '## 3. 결측이 집중된 조건', '']
    for dim, title in [('month', '월별'), ('bb_type', '타구 종류별'), ('outcome_group', '결과별')]:
        records = result['grouped']['non_bunt_candidates_by_' + dim]
        lines.extend([f'### {title}', '', table(['구분', '타구 수', '속도 결측', '각도 결측', '비거리 결측'],
                     [[r['group'], fmt(r['n']), f"{r['launch_speed_missing']:,} ({rate(r['launch_speed_missing'], r['n'])})",
                       f"{r['launch_angle_missing']:,} ({rate(r['launch_angle_missing'], r['n'])})",
                       f"{r['hit_distance_sc_missing']:,} ({rate(r['hit_distance_sc_missing'], r['n'])})"] for r in records]), ''])
    venues = sorted(result['grouped']['non_bunt_candidates_by_venue_name'], key=lambda r: (r['hit_distance_sc_missing_pct'], r['n']), reverse=True)[:10]
    ground = next(r for r in result['grouped']['non_bunt_candidates_by_bb_type'] if r['group'] == 'ground_ball')
    speed_venue = max(result['grouped']['non_bunt_candidates_by_venue_name'], key=lambda r: r['launch_speed_missing'])
    lines.extend(['### 비거리 결측률 상위 구장', '', table(['구장', '타구 수', '속도 결측', '속도 결측률', '비거리 결측', '비거리 결측률'],
                  [[r['group'], fmt(r['n']), fmt(r['launch_speed_missing']), f"{r['launch_speed_missing_pct']:.3f}%", fmt(r['hit_distance_sc_missing']), f"{r['hit_distance_sc_missing_pct']:.3f}%"] for r in venues]), '',
                  f"속도 결측 {main['launch_speed_missing']:,}개 중 땅볼이 {ground['launch_speed_missing']:,}개({rate(ground['launch_speed_missing'], main['launch_speed_missing'])})이고, 비거리 결측 {main['hit_distance_sc_missing']:,}개 중 땅볼이 {ground['hit_distance_sc_missing']:,}개({rate(ground['hit_distance_sc_missing'], main['hit_distance_sc_missing'])})다. 속도 결측 개수가 가장 많은 구장은 {speed_venue['group']}로, 비번트 타구 {speed_venue['n']:,}개 중 속도 결측 {speed_venue['launch_speed_missing']:,}개({rate(speed_venue['launch_speed_missing'], speed_venue['n'])}), 비거리 결측 {speed_venue['hit_distance_sc_missing']:,}개({rate(speed_venue['hit_distance_sc_missing'], speed_venue['n'])})다. 원인을 측정 실패라고 단정하지는 않는다.", '',
                  '구장은 MLB 일정의 경기 ID에 연결한 실제 venue다. 홈 팀을 구장으로 대신 사용하지 않았다. 모든 날짜·구장·실제 이벤트별 수치는 audit 폴더의 CSV에서 확인할 수 있다.', '',
                  '## 4. 검증용 두 날짜', ''])
    holdouts = sorted([r for r in result['grouped']['non_bunt_candidates_by_split'] if r['group'] != 'middle_dates'], key=lambda r: 0 if r['group'] == 'opening_day_holdout' else 1)
    lines.extend([table(['날짜 / 구분', '경기 수', '비번트 타구', '속도 결측', '각도 결측', '비거리 결측', '확률 후보', '비거리 후보', '홈런'],
                       [[f"{first if r['group'] == 'opening_day_holdout' else last} / {r['group']}", r['games'], fmt(r['n']), r['launch_speed_missing'], r['launch_angle_missing'], r['hit_distance_sc_missing'], r['available_probability'], r['available_distance'], r['home_runs']] for r in holdouts]), '',
                  '두 날짜는 `audit/reserved-dates.json`과 타구 inventory의 split 열에 지정했다. 현재 학습은 없으며, 이후 학습·모델 선택·전처리 적합·확률 보정에서도 두 날짜 전체를 제외해야 한다. 개막일은 한 경기여서 특히 홈런 검증의 불확실성을 따로 확인해야 한다.', '',
                  '개막일은 홈런 양성 사례가 없어 홈런 ROC AUC를 계산할 수 없다. 이후 해당 날짜에서는 Brier score/log loss 같은 확률 오차를 보고하고, 홈런 구분 성능은 최종일 및 두 날짜 합산 결과에서 평가하는 방법을 검토할 수 있다.', '',
                  '## 5. 값의 범위와 번트 분류', '',
                  table(['변수', '최솟값', '1백분위', '중앙값', '99백분위', '최댓값', '0인 값', '음수'],
                        [[r['field'], r['min'], round(r['p01'], 3), r['median'], round(r['p99'], 3), r['max'], r['zero_count'], r['negative_count']] for r in result['numeric_ranges_non_bunt']]), '',
                  f"비번트 후보 중 검토 범위 밖 또는 숫자 해석 불가능한 행: **{quality['review_flagged_rows']:,}개**. 검토 범위는 속도 (0,130]mph, 각도 [-90,90]°, 비거리 [0,600]ft로 설정했으며 자동 삭제하지 않았다. 음수 발사각은 정상적인 관측값일 수 있다.", '',
                  '번트는 희생번트 이벤트뿐 아니라 경기 설명의 bunt/bunts/bunted/bunting 단어도 확인했다. 번트 안타·번트 아웃을 포함하지만 공식 번트 플래그가 아닌 설명 기반 후보이므로 `audit/bunt_candidates.csv`를 보관했다.', '',
                  '속도·각도에는 원본 제공자가 추정한 값이 포함될 수 있다. 이 감사는 CSV의 빈 값과 수치 해석 가능성을 조사하며 측정값/제공자 추정값을 완전히 분리하지 않는다. 비거리는 실제 착지점의 실측 거리가 아닌 Statcast 추정 비거리로 해석한다.', '',
                  '## 6. 처리 방법 결정에 필요한 항목', '',
                  '- 속도·각도 결측 타구를 확률 분석에서 제외할지, 별도 미측정 집단으로 보고할지.',
                  '- 비거리 결측 타구는 비거리 분석에서 제외하되, 속도·각도가 있으면 확률 분석에는 유지할지.',
                  '- 비거리 0 및 검토 대상으로 표시된 값의 처리.',
                  '- 설명 기반 번트 후보를 제외 기준으로 채택할지.',
                  '- 개막일의 작은 표본을 그대로 최종 검증에 사용할지.', '',
                  '## 7. 파일과 재실행', '',
                  '- `raw/statcast/*.csv.gz`: 제공된 모든 열의 원본 타구 CSV, 번트 포함.',
                  '- `raw/schedule.json`, `manifest.json`: 공식 일정, 요청 URL, 원본 해시, 수집 시각.',
                  '- `audit/batted_ball_inventory.csv.gz`: 주요 원본 필드와 감사용 번트·결측·검증 날짜 플래그. 원본값 유지.',
                  '- `audit/summary.json`: 전체 감사 결과.',
                  '- `audit/*_by_*.csv`: 모집단별 날짜·월·구장·타구 종류·결과·검증 구분 집계.',
                  f"- `audit/all_column_missingness.csv`: 원본 {len(quality['columns'])}개 열 전체의 결측 수·비율. 비사용/폐기된 항목의 높은 결측률은 주 분석 변수의 품질과 구분해 해석한다.",
                  '- `audit/non_bunt_missing_rows.csv`, `audit/missing_patterns.csv`: 개별 결측 사례와 조합.',
                  '- `audit/bunt_candidates.csv`, `audit/review_flagged_rows.csv`, `audit/duplicate_rows.csv`: 확인 대상.', '',
                  '프로젝트 루트에서 `python -X utf8 scripts/mlb_statcast_audit.py download`로 원본을 재사용해 수집을 재개하고, `python -X utf8 scripts/mlb_statcast_audit.py audit`로 보고서를 재생성한다. Python 표준 라이브러리만 사용한다.', '',
                  '출처: [Baseball Savant CSV 정의](https://baseballsavant.mlb.com/csv-docs), [Statcast 검색](https://baseballsavant.mlb.com/statcast_search), [MLB 정규시즌 일정 API](https://statsapi.mlb.com/api/v1/schedule?sportId=1&season=2026&gameType=R).', ''])
    (ROOT / 'missingness-report.md').write_text('\n'.join(lines), encoding='utf-8')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['sample', 'download', 'verify', 'audit'])
    args = parser.parse_args()
    if args.action == 'sample':
        sample()
    elif args.action == 'download':
        download()
    elif args.action == 'audit':
        audit()
    elif args.action == 'verify':
        verify()

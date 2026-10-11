"""Export a self-contained unpublished interactive scatterplot from saved data."""
from pathlib import Path
import base64
import hashlib
import json

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'data/mlb/2026'
import pandas as pd

sources = [DATA / 'processed/probability.csv.gz']
hashes = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sources}
frame = pd.read_csv(sources[0])
player = frame.loc[frame['batter'].eq(808959)].sort_values(['game_date', 'game_pk', 'at_bat_number', 'pitch_number'])
assert len(player) == 257 and player['events'].eq('home_run').sum() == 35
assert player['launch_speed'].between(20, 120).all() and player['launch_angle'].between(-90, 90).all()
balls = []
for row in player.itertuples():
    assert 'CWS' in (row.home_team, row.away_team)
    balls.append({'date': row.game_date, 'game': int(row.game_pk),
                  'at_bat': int(row.at_bat_number), 'pitch': int(row.pitch_number),
                  'opponent': row.away_team if row.home_team == 'CWS' else row.home_team,
                  'event': row.events, 'ev': float(row.launch_speed), 'la': float(row.launch_angle),
                  'distance': None if pd.isna(row.hit_distance_sc) else float(row.hit_distance_sc) * .3048,
                  'venue': None if pd.isna(row.venue_name) else str(row.venue_name)})
assert len({(r['game'], r['at_bat'], r['pitch']) for r in balls}) == len(balls)
events = {'field_out': '아웃', 'single': '단타', 'double': '2루타', 'triple': '3루타', 'home_run': '홈런',
          'grounded_into_double_play': '병살타', 'force_out': '포스 아웃', 'double_play': '병살',
          'sac_fly': '희생플라이', 'field_error': '실책 출루', 'fielders_choice': '야수 선택',
          'fielders_choice_out': '야수 선택 아웃', 'triple_play': '삼중살', 'sac_fly_double_play': '희생플라이 병살'}
assert set(player['events']) <= set(events)
payload = {'balls': balls, 'events': events,
           'meanEV': float(player['launch_speed'].mean()), 'hardHit': float(player['launch_speed'].ge(95).mean()),
           'regions': {'A': [65, 75, 20, 35], 'B': [90, 105, 5, 15], 'C': [105, 115, 25, 35], 'D': [85, 100, 25, 35]}}
template = Path(__file__).with_suffix('.html').read_text(encoding='utf-8')
fallback = 'data:image/png;base64,' + base64.b64encode((DATA / 'analysis/player-cases/murakami-contact-map.png').read_bytes()).decode('ascii')
serialized = json.dumps(payload, ensure_ascii=False, allow_nan=False).replace('<', '\\u003c')
document = template.replace('__PAYLOAD__', serialized).replace('__FALLBACK__', fallback)
assert '__PAYLOAD__' not in document and '__FALLBACK__' not in document
assert all(hashlib.sha256(p.read_bytes()).hexdigest() == hashes[str(p.relative_to(ROOT))] for p in sources)
output = ROOT / 'scripts/murakami-dot-plot.html'
output.write_text(document, encoding='utf-8')
audit = DATA / 'analysis/player-cases/interactive-audit.json'
audit.write_text(json.dumps({'source_sha256': hashes, 'rows': len(balls), 'home_runs': 35,
                              'source_unchanged': True, 'model_refitted': False,
                              'output': str(output.relative_to(ROOT))}, indent=2), encoding='utf-8')
print(output.relative_to(ROOT))

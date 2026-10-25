"""Collect 2023/2024 official counts and reuse immutable 2025/2026 snapshots."""
from pathlib import Path
import argparse
import csv
import hashlib
import json

import mlb_clutch_collect as original

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'data/mlb/clutch-2023-2026'
PREVIOUS = ROOT / 'data/mlb/clutch-2026'


def audit():
    # Use the existing audited field definitions, traded-player checks, and
    # reconciliation against all 30 teams for the two newly acquired seasons.
    original.DATA, original.YEARS = DATA, (2023, 2024)
    original.audit()
    new_audit = json.loads((DATA / 'audit.json').read_text(encoding='utf-8'))
    old_audit = json.loads((PREVIOUS / 'audit.json').read_text(encoding='utf-8'))
    new_audit['years'].update(old_audit['years'])
    original.save_json(DATA / 'audit.json', new_audit)

    inventory = DATA / 'processed/player-season-inventory.csv'
    with inventory.open(encoding='utf-8-sig', newline='') as stream:
        reader = csv.DictReader(stream)
        fieldnames, rows = reader.fieldnames, list(reader)
    with (PREVIOUS / 'processed/player-season-inventory.csv').open(encoding='utf-8-sig', newline='') as stream:
        rows.extend(csv.DictReader(stream))
    assert len({(row['season'], row['player_id']) for row in rows}) == len(rows)
    with inventory.open('w', encoding='utf-8-sig', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    sources = []
    for directory, years in [(DATA, ('2023-', '2024-')), (PREVIOUS, ('2025-', '2026-'))]:
        for meta_path in sorted((directory / 'raw').glob('*.meta.json')):
            if not meta_path.name.startswith(years):
                continue
            record = json.loads(meta_path.read_text(encoding='utf-8'))
            path = directory / record['path']
            assert hashlib.sha256(path.read_bytes()).hexdigest() == record['sha256']
            record['path'] = str(path.relative_to(ROOT))
            record['cache_reused'] = directory == PREVIOUS
            sources.append(record)
    original.save_json(DATA / 'manifest.json', {
        'seasons': [2023, 2024, 2025, 2026], 'game_type': 'R',
        'unit': 'Official player-season counts across all teams; same eligibility in each season',
        'client_as_of_kst': '2026-10-25', 'sources': sources,
        'previous_audit_sha256': hashlib.sha256((PREVIOUS / 'audit.json').read_bytes()).hexdigest()})
    print('Four-season audit complete; original 2025/2026 snapshots retained.', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('stage', choices=['collect', 'audit'])
    args = parser.parse_args()
    original.DATA, original.YEARS = DATA, (2023, 2024)
    if args.stage == 'collect':
        original.collect()
    audit()

"""Recalculate saved official H/AB with sacrifice flies counted as outs.

Offline, standard library only. Keep the original 300 AB / 75 RISP AB cohort;
add SF to BOTH total and RISP denominators, without changing official records.
"""
from pathlib import Path
import hashlib
import json
import math
import random
import statistics

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'data/mlb/clutch-2026'
BOOTSTRAP_REPETITIONS = 20000
BOOTSTRAP_SEED = 20261023


def bootstrap_mean_interval(values, repetitions, seed):
    """Percentile 95% CI, resampling players with equal weight."""
    values = list(values)
    rng = random.Random(seed)
    means = [statistics.fmean(rng.choices(values, k=len(values)))
             for _ in range(repetitions)]
    quantiles = statistics.quantiles(means, n=40, method='inclusive')
    return [quantiles[0], quantiles[-1]]


def correlation(x, y):
    mx, my = statistics.mean(x), statistics.mean(y)
    return sum((a-mx)*(b-my) for a,b in zip(x,y)) / math.sqrt(
        sum((a-mx)**2 for a in x) * sum((b-my)**2 for b in y))


def run():
    cohorts, summary, hashes = {}, {}, {}
    for year in (2025, 2026):
        sources = {}
        for kind in ('season', 'risp'):
            path = DATA / f'raw/{year}-players-{kind}.json'
            raw = path.read_bytes()
            hashes[str(path.relative_to(ROOT))] = hashlib.sha256(raw).hexdigest()
            group = json.loads(raw)['stats'][0]
            splits = group['splits']
            sources[kind] = {s['player']['id']: s['stat'] for s in splits}
            assert len(sources[kind]) == len(splits) == group['totalSplits']
        rows = {}
        for pid, t in sources['season'].items():
            r = sources['risp'].get(pid)
            if not r or t['atBats'] < 300 or r['atBats'] < 75:
                continue
            assert 0 <= r['sacFlies'] <= t['sacFlies']
            original = r['hits']/r['atBats'] - t['hits']/t['atBats']
            corrected = r['hits']/(r['atBats']+r['sacFlies']) - t['hits']/(t['atBats']+t['sacFlies'])
            rows[pid] = {'original': original, 'sf_as_out': corrected}
        original_mean = statistics.mean(x['original'] for x in rows.values())
        corrected_mean = statistics.mean(x['sf_as_out'] for x in rows.values())
        summary[str(year)] = {'n':len(rows), 'original_mean':original_mean,
            'sf_as_out_mean':corrected_mean,
            'sf_as_out_mean_95':bootstrap_mean_interval(
                [x['sf_as_out'] for x in rows.values()],
                BOOTSTRAP_REPETITIONS, BOOTSTRAP_SEED + year),
            'reduction_share':(original_mean-corrected_mean)/original_mean}
        cohorts[year] = rows
    shared = sorted(cohorts[2025].keys() & cohorts[2026].keys())
    persistence = {metric:correlation([cohorts[2025][p][metric] for p in shared],
                                    [cohorts[2026][p][metric] for p in shared])
                   for metric in ('original', 'sf_as_out')}
    result = {'definition':'H/(AB+SF), applied to both total and RISP counts',
        'eligibility':'Original official AB >=300 and RISP AB >=75 in each season',
        'weighting':'Equal weight per eligible player',
        'confidence_interval':{
            'method':'Percentile bootstrap of the player mean; resample players with replacement',
            'level':0.95, 'repetitions':BOOTSTRAP_REPETITIONS,
            'seed_by_year':{str(year):BOOTSTRAP_SEED + year for year in (2025, 2026)}},
        'source_hashes':hashes, 'years':summary, 'paired_n':len(shared),
        'pearson':persistence}
    target = DATA / 'analysis/sacrifice-fly.json'
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    print(json.dumps({'years':summary,'paired_n':len(shared),'pearson':persistence},indent=2))


if __name__ == '__main__':
    run()

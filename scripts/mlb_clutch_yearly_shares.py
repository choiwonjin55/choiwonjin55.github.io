"""Offline yearly positive-share intervals and a player-clustered equality test."""
from pathlib import Path
import hashlib
import json

import numpy as np
from scipy.stats import chi2, norm

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'assets/mlb-clutch-2026/four-season-results.json'
OUTPUT = ROOT / 'data/mlb/clutch-2023-2026/analysis/yearly-shares.json'


def main():
    years = json.loads(SOURCE.read_text(encoding='utf-8'))['yearly']
    ids = sorted({p['player_id'] for year in years.values() for p in year['players']})
    index = {pid: i for i, pid in enumerate(ids)}
    n = np.array([year['n'] for year in years.values()])
    shares = np.array([year['positive'] / year['n'] for year in years.values()])
    influence = np.zeros((len(ids), len(years)))
    z = norm.ppf(.975)
    yearly = {}
    for j, (season, year) in enumerate(years.items()):
        rows = year['players']
        assert len(rows) == n[j] == len({p['player_id'] for p in rows})
        positive = [int(p['risp_h'] * p['ab'] > p['h'] * p['risp_ab']) for p in rows]
        assert sum(positive) == year['positive']
        for p, value in zip(rows, positive):
            influence[index[p['player_id']], j] = (value - shares[j]) / n[j]
        # Wilson intervals within each season: one record per eligible player.
        denominator = 1 + z*z / n[j]
        center = (shares[j] + z*z / (2*n[j])) / denominator
        half = z*np.sqrt(shares[j]*(1-shares[j])/n[j] + z*z/(4*n[j]**2)) / denominator
        yearly[season] = {'n': int(n[j]), 'positive': sum(positive),
                          'share': float(shares[j]),
                          'wilson_95': [float(center-half), float(center+half)]}
    # Saturated year-means model; cluster sandwich allows arbitrary dependence
    # across observed seasons of each player, with the CR1 small-sample factor.
    observations, clusters, parameters = int(n.sum()), len(ids), len(years)
    covariance = influence.T @ influence
    covariance *= clusters/(clusters-1) * (observations-1)/(observations-parameters)
    contrast = np.column_stack((-np.ones(parameters-1), np.eye(parameters-1)))
    difference = contrast @ shares
    statistic = float(difference @ np.linalg.solve(contrast @ covariance @ contrast.T, difference))
    result = {
        'spec': {'outcome': 'Official RISP H/AB strictly above overall H/AB',
                 'eligibility': 'Overall AB >= 300 and RISP AB >= 75 in each season',
                 'interval': '95% Wilson, separately within each season',
                 'test': 'Saturated year-means model, player-clustered CR1 covariance; Wald chi-square',
                 'null': 'Equal positive shares across the four yearly eligible-player populations'},
        'yearly': yearly,
        'comparison': {'player_seasons': observations, 'unique_players': clusters,
                       'wald': statistic, 'df': parameters-1,
                       'p': float(chi2.sf(statistic, parameters-1)),
                       'share_covariance': covariance.tolist()},
        'source_hashes': {str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
                          for path in (SOURCE, Path(__file__))}}
    OUTPUT.write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False)+'\n', encoding='utf-8')
    print(json.dumps({'yearly': yearly, 'comparison': result['comparison']}, indent=2))


if __name__ == '__main__':
    main()

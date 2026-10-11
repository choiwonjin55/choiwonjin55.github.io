"""Refresh the offline dashboard in scripts using the saved model grid."""
from pathlib import Path
import json
import pandas as pd
from mlb_statcast_analysis import write_dashboard

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'data/mlb/2026/analysis'

if __name__ == '__main__':
    run = json.loads((OUT / 'results.json').read_text(encoding='utf-8'))
    grid = pd.read_csv(OUT / 'prediction-grid.csv.gz')
    write_dashboard(run, grid)
    destination = ROOT / 'scripts/statcast-dashboard.html'
    destination.write_bytes((OUT / 'dashboard.html').read_bytes())
    print(destination)

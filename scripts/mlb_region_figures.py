"""Render comparison figures from saved summaries without fitting models."""
from pathlib import Path
import ast
import hashlib
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'data/mlb/2026/analysis/hit-regions'
source = (ROOT / 'scripts/mlb_hit_regions.py').read_text(encoding='utf-8')
regions = next(ast.literal_eval(node.value) for node in ast.parse(source).body
               if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'REGIONS' for t in node.targets))
inputs = [OUT.parent / 'prediction-grid.csv.gz', OUT / 'observed-decomposition.csv', OUT / 'region-summary.csv']
hashes = {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs}
grid = pd.read_csv(inputs[0])
cells = pd.read_csv(inputs[1])
rows = pd.read_csv(inputs[2]).to_dict('records')
block = source[source.index('import matplotlib\n'):source.index('\nblocks=[]')]
exec(compile(block, str(ROOT / 'scripts/mlb_hit_regions.py'), 'exec'),
     {'np': np, 'grid': grid, 'cells': cells, 'rows': rows, 'REGIONS': regions, 'OUT': OUT})
assert all(hashlib.sha256(p.read_bytes()).hexdigest() == digest for p, digest in hashes.items())
print('Updated hit-decomposition.png and region-outcomes.png; saved data unchanged.')

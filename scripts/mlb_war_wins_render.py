"""Render a standalone, offline interactive chart from the saved analysis."""
import argparse
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


def render(result, destination):
    template=(ROOT/'scripts/mlb_war_wins_dashboard.html').read_text(encoding='utf-8')
    if template.count('__WAR_WINS_PAYLOAD__')!=1:
        raise ValueError('Expected one payload placeholder')
    encoded=json.dumps(result,ensure_ascii=False,allow_nan=False,separators=(',',':')).replace('<','\\u003c')
    destination.parent.mkdir(parents=True,exist_ok=True)
    destination.write_text(template.replace('__WAR_WINS_PAYLOAD__',encoded),encoding='utf-8',newline='\n')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--results',type=Path,default=ROOT/'assets/mlb-war-wins/results.json')
    parser.add_argument('--output',type=Path,default=ROOT/'scripts/mlb-war-wins-dashboard.html')
    args=parser.parse_args()
    render(json.loads(args.results.read_text(encoding='utf-8')),args.output)
    print(args.output)

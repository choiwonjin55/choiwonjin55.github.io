"""Explain the existing EV/LA hit surface without refitting or changing held-out data."""
from pathlib import Path
import hashlib
import html
import json
import pickle
import runpy
import sys

import numpy as np
import pandas as pd
from scipy.ndimage import label

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'data/mlb/2026'
OUT = DATA / 'analysis/hit-regions'
OUT.mkdir(parents=True, exist_ok=True)
api = runpy.run_path(str(ROOT / 'scripts/mlb_statcast_analysis.py'), run_name='mlb_existing_analysis')
# The trusted, locally generated bundle serialized this class under __main__.
sys.modules['__main__'].TensorSplines = api['TensorSplines']
sources = [DATA / 'processed/probability.csv.gz', DATA / 'processed/cleaning-policy.json',
           DATA / 'analysis/models.pkl', DATA / 'analysis/results.json', DATA / 'analysis/prediction-grid.csv.gz']
hashes = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sources}
p = pd.read_csv(sources[0], dtype={'game_pk': str})
dev = p.loc[p['split'].eq('development')].copy()
held = p.loc[p['split'].ne('development')].copy()
assert len(dev) == 121294 and len(held) == 1246
assert not dev['game_date'].isin(['2026-03-26', '2026-09-27']).any()
with sources[2].open('rb') as f:
    model = pickle.load(f)['probability']
pred = api['probabilities'](model['model'], model['basis'], dev[api['FEATURES']].to_numpy())
dev['pred_hit'] = pred[:, 1:].sum(axis=1)
dev['pred_hr'] = pred[:, 4]
dev['is_hit'] = dev['events'].isin(api['CLASSES'][1:])
dev['is_hr'] = dev['events'].eq('home_run')
held['is_hit'] = held['events'].isin(api['CLASSES'][1:])
held['is_hr'] = held['events'].eq('home_run')

REGIONS = [
    ('A', '약하게 띄운 타구', 65, 75, 20, 35),
    ('B', '빠르고 낮은 타구', 90, 105, 5, 15),
    ('C', '강하게 띄운 타구', 105, 115, 25, 35),
    ('D', '중간 속도의 뜬공', 85, 100, 25, 35),
]
# Region boundaries are descriptive selections after viewing the existing surface,
# not fitted clusters or newly defined validation populations.

def mask(df, r):
    _, _, lo, hi, alo, ahi = r
    return df['launch_speed'].ge(lo) & df['launch_speed'].lt(hi) & df['launch_angle'].ge(alo) & df['launch_angle'].lt(ahi)

def rate(x):
    return f'{100 * x:.1f}%'

games = pd.Index(sorted(dev['game_pk'].unique()))
rng = np.random.default_rng(20261011)
bootstrap_indices = rng.integers(0, len(games), size=(500, len(games)))
rows, monthly, holdouts = [], [], []
for r in REGIONS:
    code, name, lo, hi, alo, ahi = r
    s = dev.loc[mask(dev, r)]
    counts = s['events'].value_counts()
    n = len(s)
    hits, hrs = int(s['is_hit'].sum()), int(s['is_hr'].sum())
    game_counts = s.groupby('game_pk').agg(n=('is_hit', 'size'), hits=('is_hit', 'sum')).reindex(games, fill_value=0)
    a = game_counts['n'].to_numpy()[bootstrap_indices].sum(axis=1)
    b = game_counts['hits'].to_numpy()[bootstrap_indices].sum(axis=1)
    ci = np.quantile(b[a > 0] / a[a > 0], [.025, .975])
    row = {'code': code, 'name': name, 'ev_low': lo, 'ev_high_exclusive': hi,
           'la_low': alo, 'la_high_exclusive': ahi, 'n': n, 'hits': hits, 'home_runs': hrs,
           'observed_hit': hits/n, 'observed_home_run': hrs/n, 'observed_non_hr_hit': (hits-hrs)/n,
           'single_rate': int(counts.get('single', 0))/n, 'double_rate': int(counts.get('double', 0))/n,
           'triple_rate': int(counts.get('triple', 0))/n, 'non_hit_rate': 1-hits/n,
           'home_run_share_of_hits': hrs/hits, 'single_share_of_hits': int(counts.get('single', 0))/hits,
           'predicted_hit_mean': float(s['pred_hit'].mean()), 'predicted_hr_mean': float(s['pred_hr'].mean()),
           'hit_game_bootstrap_lo95': float(ci[0]), 'hit_game_bootstrap_hi95': float(ci[1]),
           'recorded_distance_n': int(s['hit_distance_sc'].notna().sum()),
           'median_projected_distance_m': float(s['hit_distance_sc'].median()*.3048),
           'event_counts': {str(k): int(v) for k, v in counts.items()},
           'bb_type_counts': {str(k): int(v) for k, v in s['bb_type'].value_counts(dropna=False).items()}}
    rows.append(row)
    for month, sub in s.groupby(s['game_date'].str[:7]):
        monthly.append({'region': code, 'month': month, 'n': len(sub), 'hit': float(sub['is_hit'].mean()), 'hr': float(sub['is_hr'].mean())})
    for split in ['early_holdout', 'final_holdout']:
        sub = held.loc[mask(held, r) & held['split'].eq(split)]
        holdouts.append({'region': code, 'split': split, 'n': len(sub), 'hit': float(sub['is_hit'].mean()), 'hr': float(sub['is_hr'].mean())})

grid = pd.read_csv(sources[4])
connectivity = []
for threshold in [.5, .7, .8, .9]:
    eligible = grid['supported'] & grid['launch_speed'].between(40, 118) & grid['launch_angle'].between(-50, 80)
    labeled, components = label((eligible & grid['p_hit'].ge(threshold)).to_numpy().reshape(181, 101), structure=np.ones((3, 3)))
    connectivity.append({'threshold': threshold, 'components_8_neighbor': int(components),
                         'sizes_grid_points': sorted(np.bincount(labeled.ravel())[1:].astype(int).tolist(), reverse=True)})

cells = dev.assign(ev_bin=np.floor(dev['launch_speed']/2).astype(int),
                   la_bin=np.floor((dev['launch_angle']+90)/5).astype(int))
cells = cells.groupby(['ev_bin', 'la_bin']).agg(n=('is_hit', 'size'), hits=('is_hit', 'sum'), hr=('is_hr', 'sum')).reset_index()
cells['observed_hit'] = cells['hits']/cells['n']
cells['observed_non_hr_hit'] = (cells['hits']-cells['hr'])/cells['n']
cells['observed_hr'] = cells['hr']/cells['n']
cells.to_csv(OUT/'observed-decomposition.csv', index=False, encoding='utf-8-sig')
pd.DataFrame([{k:v for k,v in r.items() if not isinstance(v,dict)} for r in rows]).to_csv(OUT/'region-summary.csv',index=False,encoding='utf-8-sig')
pd.DataFrame(monthly).to_csv(OUT/'monthly-regions.csv',index=False,encoding='utf-8-sig')
pd.DataFrame(holdouts).to_csv(OUT/'held-out-regions.csv',index=False,encoding='utf-8-sig')

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
from matplotlib.ticker import PercentFormatter
plt.rcParams.update({'font.family':'Malgun Gothic', 'axes.unicode_minus':False, 'font.size':10})
fig, axes = plt.subplots(2, 3, figsize=(15, 8), layout='constrained')
fields = [('p_hit','observed_hit','안타 전체'), ('p_non_hr_hit','observed_non_hr_hit','홈런 제외 안타'), ('p_home_run','observed_hr','홈런')]
cmap = plt.colormaps['YlGnBu'].copy()
cmap.set_bad('#e7ecee')
for j, (model_field, obs_field, name) in enumerate(fields):
    mat = grid[model_field].to_numpy().reshape(181,101).copy()
    mat[~grid['supported'].to_numpy().reshape(181,101)] = np.nan
    axes[0,j].imshow(mat,origin='lower',extent=[19.5,120.5,-90.5,90.5],aspect='auto',vmin=0,vmax=1,cmap=cmap)
    obs = np.full((36,61),np.nan)
    for cell in cells.itertuples():
        if cell.n>=30 and 0<=cell.ev_bin<61 and 0<=cell.la_bin<36:
            obs[cell.la_bin,cell.ev_bin] = getattr(cell,obs_field)
    im=axes[1,j].imshow(obs,origin='lower',extent=[0,122,-90,90],aspect='auto',vmin=0,vmax=1,cmap=cmap)
    axes[0,j].set_title('모델 · '+name,pad=10)
    axes[1,j].set_title('실제 관측 · '+name,pad=10)
for ax in axes.ravel():
    ax.set(xlim=(50,118),ylim=(-5,55),xlabel='타구 속도 (mph)',ylabel='발사각 (°)')
    for code,name,lo,hi,alo,ahi in REGIONS:
        color={'A':'#91b7a1','B':'#147c9c','C':'#d86240','D':'#64747d'}[code]
        ax.add_patch(Rectangle((lo,alo),hi-lo,ahi-alo,fill=False,edgecolor=color,linewidth=1.7,linestyle='--'))
bar=fig.colorbar(im,ax=axes.ravel().tolist(),fraction=.025,pad=.015)
bar.ax.yaxis.set_major_formatter(PercentFormatter(1))
fig.suptitle('안타 확률을 구성하는 홈런 제외 안타와 홈런',fontsize=19)
handles=[Rectangle((0,0),1,1,fill=False,edgecolor={'A':'#91b7a1','B':'#147c9c','C':'#d86240','D':'#64747d'}[code],linewidth=1.7,linestyle='--',
                   label=f'{name} · {lo}~{hi} mph / {alo}~{ahi}°') for code,name,lo,hi,alo,ahi in REGIONS]
axes[1,1].legend(handles=handles,loc='upper center',bbox_to_anchor=(.5,-.20),ncol=2,fontsize=9,frameon=False)
fig.savefig(OUT/'hit-decomposition.png',dpi=180)
plt.close(fig)

fig, ax=plt.subplots(figsize=(10,5.3),layout='constrained')
x=np.arange(len(rows));bottom=np.zeros(len(rows))
for key,title,color in [('single_rate','단타','#237c98'),('double_rate','2루타','#61b8b2'),('triple_rate','3루타','#afd9b1'),('observed_home_run','홈런','#d96547'),('non_hit_rate','아웃','#dce3e6')]:
    values=np.array([r[key] for r in rows]);ax.bar(x,values,bottom=bottom,label=title,color=color,width=.6);bottom+=values
ax.set_xticks(x,[r['name']+'\nn='+f"{r['n']:,}" for r in rows])
ax.yaxis.set_major_formatter(PercentFormatter(1));ax.set_ylim(0,1)
ax.set_ylabel('각 영역의 전체 타구 대비 비율');ax.set_title('영역별 실제 타구 결과 구성',fontsize=17,pad=16)
ax.legend(loc='upper left',bbox_to_anchor=(1,1),frameon=False)
fig.savefig(OUT/'region-outcomes.png',dpi=180);plt.close(fig)

blocks=[]
def text(value): blocks.append(('text',value))
def heading(value): blocks.append(('heading',value))
def table(headers, entries): blocks.append(('table',(headers,entries)))
def picture(filename,alt): blocks.append(('image',(filename,alt)))
text('안타 확률 지도에서 높은 값이 나타나는 영역을 홈런 제외 안타와 홈런으로 나누어 살펴봤다. 이번 데이터에서는 두 결과가 서로 다른 속도·각도 조합에 집중되어 있었다. 홈런 제외 안타 영역에는 약하게 띄운 타구와 빠르고 낮은 타구가 함께 나타났다.')
text('사용한 데이터는 앞서 확정한 2026년 정규시즌의 비번트 타구다. 아래의 주 집계는 두 검증일을 제외한 development 121,294타구다. 모델은 다시 학습하지 않았고, 기존 모델의 예측값을 그대로 사용했다. 확률의 분모는 해당 영역의 전체 타구이며 타석 전체가 아니다.')
heading('안타 확률의 두 가지 구성')
text('이번 모델에서 P(안타) = P(단타) + P(2루타) + P(3루타) + P(홈런)이다. 따라서 안타 확률 지도의 높은 값이 모두 같은 종류의 타구 결과를 뜻하지는 않는다. 홈런도 안타에 포함된다. [MLB 안타 정의](https://www.mlb.com/glossary/standard-stats/hit)')
picture('hit-decomposition.png','모델과 실제 관측의 안타·홈런 제외 안타·홈런 분해')
text('위쪽은 기존 모델의 예측값이고, 아래쪽은 실제 관측 비율이다. 모든 패널의 색 눈금은 0~100%로 동일하다. 홈런 제외 안타는 전체 타구를 분모로 한 단타·2루타·3루타의 합이며, 홈런 행을 삭제한 뒤 계산한 조건부 안타율이 아니다. 모델 지도는 기존 support 기준을 적용했고, 관측 지도는 2 mph × 5° 구간에서 30타구 이상인 곳만 표시했다.')
heading('대표 영역의 실제 결과')
text('A와 B는 홈런 제외 안타 영역의 서로 다른 부분, C는 홈런 영역, D는 둘 사이의 중간 속도 뜬공 영역이다. 경계는 지도를 읽기 위한 비교 구간이며 군집 분석으로 결정한 그룹이 아니다. 속도와 각도 구간은 하한 포함·상한 제외다.')
table(['영역','속도 / 발사각','타구 수','안타율','홈런 제외 안타율','홈런율'],[[r['code']+' '+r['name'],f"{r['ev_low']}~<{r['ev_high_exclusive']} mph / {r['la_low']}~<{r['la_high_exclusive']}°",f"{r['n']:,}",rate(r['observed_hit']),rate(r['observed_non_hr_hit']),rate(r['observed_home_run'])] for r in rows])
picture('region-outcomes.png','대표 영역의 실제 단타·2루타·3루타·홈런·아웃 구성')
heading('홈런 제외 안타가 많은 영역')
text(f"A의 {rows[0]['n']:,}타구 중 안타는 {rows[0]['hits']:,}개였고, 그중 단타는 {rows[0]['event_counts']['single']:,}개였다. 안타의 {rate(rows[0]['single_share_of_hits'])}가 단타다. B에서도 홈런은 없었으며, 안타의 {rate(rows[1]['single_share_of_hits'])}가 단타였다. 두 영역의 높은 안타율은 주로 단타에서 나왔다.")
text('가능한 설명은 수비수가 도달하기 어려운 위치와 시간의 조합이다. 약하게 띄운 공이 내야수 뒤와 외야수 앞의 공간에 떨어지거나, 빠르고 낮은 타구가 수비수 사이로 지나가면 홈런 제외 안타가 될 수 있다. 이 설명은 관측된 결과 구성과 맞지만, 이번 자료에는 수비수 시작 위치와 opportunity time이 없으므로 개별 타구가 안타가 된 원인까지 확인한 것은 아니다.')
text('MLB의 Catch Probability도 수비수의 이동 거리와 도달 시간을 주요 요소로 다룬다. [MLB Catch Probability](https://www.mlb.com/glossary/statcast/catch-probability)')
text('모델에서 안타 확률이 높은 각도는 70 mph에서 약 28°, 80 mph에서 16°, 90 mph에서 13°, 100 mph에서 11°였다. 홈런 제외 안타 영역은 속도가 높아질수록 유리한 각도가 낮아지는 곡선 형태다. 약한 타구의 경우 공을 어느 정도 띄우는 조합, 빠른 타구의 경우 더 낮게 보내는 조합이 같은 넓은 안타 영역에 포함된 것으로 해석할 수 있다. 선수에게 이 속도와 각도를 목표로 하라는 의미는 아니다.')
heading('홈런이 많은 영역')
text(f"C에서는 안타 {rows[2]['hits']:,}개 중 {rows[2]['home_runs']:,}개가 홈런이었다. 안타의 {rate(rows[2]['home_run_share_of_hits'])}가 홈런이다. 전체 타구 기준으로 안타율은 {rate(rows[2]['observed_hit'])}였지만, 홈런 제외 안타율은 {rate(rows[2]['observed_non_hr_hit'])}였다. 오른쪽 높은 확률 영역은 홈런을 포함한 정의에서 크게 나타나는 영역이다.")
text('강한 타구가 적절한 발사각으로 날아가면 담장 밖으로 넘어갈 가능성이 높아진다는 설명과 맞는다. 홈런 제외 안타 지도에서는 이 영역이 대부분 사라진다. 다만 구장·타구 방향·날씨·회전은 모델 입력에 없으므로 담장을 넘는 정확한 경계는 여기서 결정할 수 없다.')
heading('중간 속도 뜬공의 낮은 안타율')
text(f"D의 {rows[3]['n']:,}타구 중 {rows[3]['event_counts']['field_out']:,}개가 field_out이었다. 전체 안타율은 {rate(rows[3]['observed_hit'])}였다. A와 비슷하게 공을 띄워도, 중간 속도에서는 결과가 크게 달랐다.")
text('이 영역의 타구가 외야수의 수비 범위까지 날아가면서도 담장은 넘지 못하고, 포구할 시간도 주는 경우가 많다는 설명이 가능하다. 수비수 앞에 떨어지는 타구와 담장을 넘는 타구 사이에 포구되기 쉬운 영역이 생긴 것으로 보인다. 다만 실제 수비 위치를 관측하지 않았으므로 수비 범위를 원인으로 확정하지는 않는다.')
heading('두 그룹이라는 표현의 범위')
text('지도의 높은 부분을 두 영역으로 읽는 것은 가능하지만, 정확히 두 개의 독립된 군집이 확인된 것은 아니다. 기존 1 mph × 1° 예측 격자에서 대각선을 포함한 8방향 연결성을 계산하면, 안타 확률 80% 이상은 두 연결 영역이었지만 70% 이상은 하나로 이어졌다. 50% 이상도 하나, 90% 이상은 두 영역이었다. 보이는 그룹 수는 확률 기준과 색상 강조 방식에 영향을 받는다.')
text('이번 분석에서 더 분명하게 확인된 구분은 홈런 제외 안타와 홈런의 결과 구성이다. 왼쪽 곡선 영역 안에도 약하게 띄운 타구와 빠르고 낮은 타구가 함께 있어, 두 그룹을 단순히 약한 타구와 강한 타구로 부르는 것은 충분하지 않다.')
heading('모델의 평활화와 관측값 차이')
table(['영역','실제 안타율','같은 타구의 평균 모델 예측','예측 − 관측','관측 안타율 95% 범위'],[[r['code'],rate(r['observed_hit']),rate(r['predicted_hit_mean']),f"{100*(r['predicted_hit_mean']-r['observed_hit']):+.1f}%p",rate(r['hit_game_bootstrap_lo95'])+'~'+rate(r['hit_game_bootstrap_hi95'])] for r in rows])
text('이 비교는 영역 안의 같은 실제 타구에 모델을 적용해 평균한 값이다. 한 점의 예측과 넓은 주변 구간의 실제 비율을 비교하는 것보다 조건이 가깝다. 다만 development 데이터의 적합 결과이므로 독립 검증 성능을 뜻하지 않는다. 좁은 안타 집중 구간을 spline과 규제가 완만하게 표현하면서 관측값과 차이가 날 수 있다. 형태뿐 아니라 각 영역의 확률 수준도 따로 확인해야 한다.')
text('관측 안타율의 95% 범위는 development 전체 2,404경기를 단위로 500회 재표집해 계산했다. 홈런 제외 안타의 높은 영역과 홈런 영역은 실제 관측 지도에도 나타나므로 모델이 새로 만들어낸 형태만으로 보기는 어렵다. 그러나 이런 지역별 차이를 보고 기존 검증일로 설정을 다시 선택하거나 모델을 수정하지는 않았다.')
heading('기간별 확인')
for r in rows:
    values=[m for m in monthly if m['region']==r['code'] and m['month']>='2026-04']
    text(f"{r['code']}의 4~9월 월별 안타율은 {rate(min(v['hit'] for v in values))}~{rate(max(v['hit'] for v in values))}였다. 해당 월별 표본은 {min(v['n'] for v in values):,}~{max(v['n'] for v in values):,}타구였다.")
table(['영역','3/26 표본 / 안타율','9/27 표본 / 안타율'],[[r['code'],f"{holdouts[2*i]['n']} / {rate(holdouts[2*i]['hit'])}",f"{holdouts[2*i+1]['n']} / {rate(holdouts[2*i+1]['hit'])}"] for i,r in enumerate(rows)])
text('두 검증일에서는 각 영역의 표본이 5~48타구에 그쳤다. 영역별 결과의 대략적인 방향은 확인할 수 있지만, 경계와 최적 각도 및 확률 수준까지 이 표본으로 확정하기는 어렵다. 앞서 확정한 두 검증일은 그대로 유지했다.')
heading('해석에 남는 부분')
text('결측치를 제외한 이후의 표본이라는 점, 번트가 설명 기반 후보 플래그로 제외되었다는 점은 앞선 분석과 같다. 공식 xBA로 값을 대체하지 않았다. EV·LA만으로 선수의 주력, 타구 방향, 수비 배치와 구장 효과를 분리할 수는 없다. 현재 자료로는 결과 구성의 차이를 확인할 수 있고, 포구 가능성과 담장 통과가 그 차이를 만드는 경로라는 설명을 제시할 수 있다.')
heading('파일과 재실행')
text('region-summary.csv에 영역별 집계, monthly-regions.csv에 월별 집계, held-out-regions.csv에 검증일 집계, observed-decomposition.csv에 관측 지도 값을 보관했다. details.json에는 경계·분모·원본 파일 해시와 연결성 계산을 기록했다. 프로젝트 루트에서 data\\mlb\\2026\\.venv\\Scripts\\python.exe -X utf8 scripts/mlb_hit_regions.py로 재현할 수 있다.')

def markdown_link_text(value):
    escaped=html.escape(value)
    return __import__('re').sub(r'\[([^\]]+)\]\((https://[^)]+)\)',r'<a href="\2">\1</a>',escaped)

md=['# 안타 확률의 두 영역과 타구 결과 구성','']
body=['<h1>안타 확률의 두 영역과 타구 결과 구성</h1>']
for kind,value in blocks:
    if kind=='text':md += [value,''];body.append('<p>'+markdown_link_text(value)+'</p>')
    elif kind=='heading':md += ['## '+value,''];body.append('<h2>'+html.escape(value)+'</h2>')
    elif kind=='image':
        filename,alt=value;md += [f'![{alt}]({filename})',''];body.append('<figure><img src="'+filename+'" alt="'+html.escape(alt)+'"><figcaption>'+html.escape(alt)+'</figcaption></figure>')
    else:
        headers,entries=value
        md += ['| '+' | '.join(headers)+' |','| '+' | '.join(['---']*len(headers))+' |']+['| '+' | '.join(map(str,row))+' |' for row in entries]+['']
        body.append('<div class="tablewrap"><table><thead><tr>'+''.join('<th>'+html.escape(v)+'</th>' for v in headers)+'</tr></thead><tbody>'+''.join('<tr>'+''.join('<td>'+html.escape(str(v))+'</td>' for v in row)+'</tr>' for row in entries)+'</tbody></table></div>')
(OUT/'report.md').write_text('\n'.join(md),encoding='utf-8')
doc='<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>안타 확률의 두 영역과 타구 결과 구성</title><style>body{margin:0;background:#f4f7f8;color:#162b36;font-family:"Malgun Gothic",sans-serif;line-height:1.85;word-break:keep-all}main{max-width:1050px;margin:0 auto;padding:36px 24px 70px}h1{font-size:30px;line-height:1.5}h2{font-size:21px;margin:40px 0 12px}p{margin:14px 0}img{width:100%;height:auto}figure{margin:24px 0}figcaption{font-size:13px;color:#64747d}.tablewrap{overflow-x:auto}table{width:100%;border-collapse:collapse;background:white;font-size:14px}th,td{padding:11px 13px;border-bottom:1px solid #dbe4e8;text-align:left;white-space:nowrap}a{color:#167a93}@media(max-width:650px){main{padding:22px 14px}h1{font-size:25px}}</style></head><body><main>'+''.join(body)+'</main></body></html>'
(OUT/'report.html').write_text(doc,encoding='utf-8')
assert all(hashlib.sha256((ROOT/rel).read_bytes()).hexdigest()==value for rel,value in hashes.items())
details={'development_n':len(dev),'held_out_n':len(held),'features':api['FEATURES'],
         'model_refitted':False,'region_selection':'post-hoc descriptive rectangles; lower inclusive / upper exclusive',
         'probability_denominator':'all eligible batted balls within each region, including home runs',
         'source_sha256_unchanged':hashes,'regions':rows,'grid_connectivity':connectivity,
         'bootstrap':'500 game-cluster resamples, all 2404 development games, seed 20261011'}
(OUT/'details.json').write_text(json.dumps(details,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'regions':[{k:r[k] for k in ['code','n','observed_hit','observed_non_hr_hit','observed_home_run','predicted_hit_mean']} for r in rows],
                  'source_hashes_unchanged':True,'output':str(OUT)},ensure_ascii=False,indent=2))

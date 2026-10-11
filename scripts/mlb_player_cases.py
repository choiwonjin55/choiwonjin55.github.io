"""Describe Arraez/Murakami using the saved 2026 data and official stats snapshots.

Offline. No training, cleaning-policy changes, or publishing.
"""
from pathlib import Path
import hashlib
import html
import json
import os

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'data/mlb/2026'
OUT = DATA / 'analysis/player-cases'
RAW = DATA / 'raw/player-cases'
OUT.mkdir(parents=True, exist_ok=True)
os.environ.setdefault('MPLCONFIGDIR', str(DATA / '.matplotlib'))

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.ticker import PercentFormatter

PLAYERS = [('arraez',650333,'루이스 아라에즈'), ('murakami',808959,'무네타카 무라카미')]
REGIONS = [('A','약하게 띄운 타구',65,75,20,35), ('B','빠르고 낮은 타구',90,105,5,15),
           ('C','강하게 띄운 타구',105,115,25,35), ('D','중간 속도의 뜬공',85,100,25,35),
           ('E','선수 비교용 홈런 제외 안타 구간',75,95,10,25)]
HITS = ['single','double','triple','home_run']
sources = [DATA/'processed/probability.csv.gz',DATA/'processed/eligibility-inventory.csv.gz',
           DATA/'analysis/results.json',DATA/'analysis/models.pkl',DATA/'analysis/prediction-grid.csv.gz',
           *[RAW/(p[0]+'-season.json') for p in PLAYERS],RAW/'mlb-team-season.json']
hashes = {str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sources}
prob = pd.read_csv(sources[0])
inventory = pd.read_csv(sources[1])
grid = pd.read_csv(DATA/'analysis/prediction-grid.csv.gz')

def official_player(key, player_id):
    groups = json.loads((RAW/(key+'-season.json')).read_text(encoding='utf-8'))['stats']
    splits = [s for g in groups for s in g['splits'] if s['season']=='2026' and s['player']['id']==player_id]
    totals = [s for s in splits if 'team' not in s]
    # A traded player's total and team splits must not both be added.
    assert len(totals)==1 or (not totals and len(splits)==1)
    return (totals or splits)[0]['stat']

team_splits = json.loads((RAW/'mlb-team-season.json').read_text(encoding='utf-8'))['stats'][0]['splits']
assert len(team_splits)==30 and len({s['team']['id'] for s in team_splits})==30
KEYS = ['plateAppearances','atBats','hits','doubles','triples','homeRuns','baseOnBalls',
        'strikeOuts','hitByPitch','sacFlies','sacBunts','totalBases']
league = {key:sum(s['stat'][key] for s in team_splits) for key in KEYS}
league['avg'] = f"{league['hits']/league['atBats']:.3f}"
league['obp'] = f"{(league['hits']+league['baseOnBalls']+league['hitByPitch'])/(league['atBats']+league['baseOnBalls']+league['hitByPitch']+league['sacFlies']):.3f}"
league['slg'] = f"{league['totalBases']/league['atBats']:.3f}"
league['ops'] = f"{(league['hits']+league['baseOnBalls']+league['hitByPitch'])/(league['atBats']+league['baseOnBalls']+league['hitByPitch']+league['sacFlies'])+league['totalBases']/league['atBats']:.3f}"

def batted_summary(s):
    hits=int(s['events'].isin(HITS).sum());n=len(s)
    return {'batted_n':n,'mean_ev':float(s['launch_speed'].mean()),'mean_la':float(s['launch_angle'].mean()),
            'hard_hit_95_share':float(s['launch_speed'].ge(95).mean()),'ev_under_80_share':float(s['launch_speed'].lt(80).mean()),
            'la_10_25_share':float((s['launch_angle'].ge(10)&s['launch_angle'].lt(25)).mean()),
            'hits':hits,'home_runs':int(s['events'].eq('home_run').sum()),
            'hit_rate':hits/n,'single_share_of_hits':int(s['events'].eq('single').sum())/hits,
            'events':{str(k):int(v) for k,v in s['events'].value_counts().items()},
            'splits':{str(k):int(v) for k,v in s['split'].value_counts().items()}}

summaries=[];region_rows=[];quality=[]
for key,player_id,name in PLAYERS+[('mlb',None,'MLB 전체')]:
    s=prob if player_id is None else prob.loc[prob['batter'].eq(player_id)]
    official=league if player_id is None else official_player(key,player_id)
    pa=official['plateAppearances']
    row={'key':key,'player_id':player_id,'name':name,'official':official,**batted_summary(s),
         'bb_per_pa':official['baseOnBalls']/pa,'k_per_pa':official['strikeOuts']/pa,
         'hr_per_pa':official['homeRuns']/pa,'non_hr_hits_per_pa':(official['hits']-official['homeRuns'])/pa,
         'tto_per_pa':(official['baseOnBalls']+official['strikeOuts']+official['homeRuns'])/pa}
    summaries.append(row)
    if player_id:
        inv=inventory.loc[inventory['batter'].eq(player_id)]
        assert row['hits']==official['hits'] and row['home_runs']==official['homeRuns']
        assert len(inv)==official['plateAppearances']-official['baseOnBalls']-official['strikeOuts']-official['hitByPitch']
        quality.append({'key':key,'raw_batted_n':len(inv),'bunt_candidates':int(inv['is_bunt_candidate'].sum()),
                        'ineligible_probability':int((~inv['eligible_probability']).sum()),'complete_case_n':len(s)})
    for code,label,lo,hi,alo,ahi in REGIONS:
        sub=s.loc[s['launch_speed'].ge(lo)&s['launch_speed'].lt(hi)&s['launch_angle'].ge(alo)&s['launch_angle'].lt(ahi)]
        region_rows.append({'key':key,'name':name,'region':code,'label':label,'n':len(sub),'share':len(sub)/len(s),
                            'hits':int(sub['events'].isin(HITS).sum()),'home_runs':int(sub['events'].eq('home_run').sum()),
                            'hit_rate':float(sub['events'].isin(HITS).mean()) if len(sub) else None})
pd.DataFrame([{k:v for k,v in r.items() if not isinstance(v,dict)} for r in summaries]).to_csv(OUT/'player-summary.csv',index=False,encoding='utf-8-sig')
pd.DataFrame(region_rows).to_csv(OUT/'player-regions.csv',index=False,encoding='utf-8-sig')
pd.DataFrame(quality).to_csv(OUT/'case-coverage.csv',index=False,encoding='utf-8-sig')

plt.rcParams.update({'font.family':'Malgun Gothic','axes.unicode_minus':False,'font.size':11})
fig,axes=plt.subplots(1,2,figsize=(13.5,6.6),layout='constrained',sharex=True,sharey=True)
xs=np.arange(20,121);ys=np.arange(-90,91)
surface=grid['p_non_hr_hit'].to_numpy().reshape(181,101).copy()
surface[~grid['supported'].to_numpy().reshape(181,101)]=np.nan
for ax,(key,player_id,name),r in zip(axes,PLAYERS,summaries):
    s=prob.loc[prob['batter'].eq(player_id)]
    ax.contour(xs,ys,surface,levels=[.5,.7],colors=['#91b7a1','#487f66'],linestyles=['--','-'],linewidths=1.1)
    for cond,label,color,marker,size in [(~s['events'].isin(HITS),'비안타','#a7afb5','x',23),
            (s['events'].isin(HITS[:-1]),'홈런 제외 안타','#147c9c','o',25),(s['events'].eq('home_run'),'홈런','#d86240','*',110)]:
        sub=s.loc[cond];ax.scatter(sub['launch_speed'],sub['launch_angle'],c=color,marker=marker,s=size,alpha=.75,label=label,linewidths=.7)
    ax.set(xlim=(40,120),ylim=(-40,70),xlabel='타구 속도 (mph)',ylabel='발사각 (°)')
    ax.set_title(name+f" · {len(s):,}타구",pad=14)
    ax.text(.03,.97,f"평균 EV {r['mean_ev']:.1f} mph\n95 mph 이상 {100*r['hard_hit_95_share']:.1f}%",transform=ax.transAxes,va='top',bbox={'facecolor':'white','edgecolor':'none','alpha':.9})
axes[1].legend(loc='upper right',frameon=True)
fig.suptitle('아라에즈와 무라카미의 타구 분포',fontsize=19)
fig.supxlabel('초록 등고선: 기존 리그 모델의 홈런 제외 안타 확률 50%·70% · 선수 타구는 2026년 전체 사례',fontsize=10)
fig.savefig(OUT/'player-contact-map.png',dpi=180);plt.close(fig)

fig,axes=plt.subplots(1,2,figsize=(13.5,5.5),layout='constrained')
bins=np.arange(20,126,5)
for r in summaries:
    s=prob if r['player_id'] is None else prob.loc[prob['batter'].eq(r['player_id'])]
    counts,edges=np.histogram(s['launch_speed'],bins=bins)
    axes[0].stairs(counts/len(s),edges,label=r['name'],linewidth=2)
axes[0].axvline(95,linestyle='--',color='#a5abb0',linewidth=1)
axes[0].set(xlim=(40,120),xlabel='타구 속도 (mph)',ylabel='각 선수·리그의 전체 타구 대비 비율',title='타구 속도 분포')
axes[0].yaxis.set_major_formatter(PercentFormatter(1));axes[0].legend(frameon=False)
x=np.arange(3);bottom=np.zeros(3)
fields=[('non_hr','홈런 제외 안타','#147c9c'),('hr','홈런','#d86240'),('bb','볼넷','#b892bf'),
        ('hbp','HBP','#cbd78f'),('k','삼진','#51565c'),('other','기타 타석','#dce3e6')]
for key,label,color in fields:
    vals=[]
    for r in summaries:
        z=r['official'];pa=z['plateAppearances']
        counts={'non_hr':z['hits']-z['homeRuns'],'hr':z['homeRuns'],'bb':z['baseOnBalls'],
                'hbp':z['hitByPitch'],'k':z['strikeOuts'],
                'other':pa-z['hits']-z['baseOnBalls']-z['hitByPitch']-z['strikeOuts']}
        assert sum(counts.values())==pa
        vals.append(counts[key]/pa)
    axes[1].bar(x,vals,bottom=bottom,label=label,color=color,width=.6);bottom+=vals
axes[1].set_xticks(x,['아라에즈','무라카미','MLB']);axes[1].set(ylim=(0,1),ylabel='공식 시즌 전체 타석 대비 비율',title='타석 결과 구성')
axes[1].yaxis.set_major_formatter(PercentFormatter(1));axes[1].legend(loc='upper left',bbox_to_anchor=(1,1),frameon=False)
fig.savefig(OUT/'player-outcome-comparison.png',dpi=180);plt.close(fig)

def pct(v):return '—' if v is None else f'{100*v:.1f}%'
def table(headers,rows):
    return '<div class="tablewrap"><table><thead><tr>'+''.join('<th>'+html.escape(v)+'</th>' for v in headers)+'</tr></thead><tbody>'+''.join('<tr>'+''.join('<td>'+html.escape(str(v))+'</td>' for v in row)+'</tr>' for row in rows)+'</tbody></table></div>'
def paragraph(value):return '<p>'+value+'</p>'
stat_rows=[['PA']+[str(r['official']['plateAppearances']) for r in summaries],
           ['AVG / OBP / SLG']+[' / '.join(r['official'][k] for k in ['avg','obp','slg']) for r in summaries],
           ['OPS']+[r['official']['ops'] for r in summaries],
           ['BB%']+[pct(r['bb_per_pa']) for r in summaries],['K%']+[pct(r['k_per_pa']) for r in summaries],
           ['HR%']+[pct(r['hr_per_pa']) for r in summaries],['홈런 제외 안타 / PA']+[pct(r['non_hr_hits_per_pa']) for r in summaries]]
contact_rows=[['정제 타구 수']+[f"{r['batted_n']:,}" for r in summaries],
              ['평균 EV (mph)']+[f"{r['mean_ev']:.1f}" for r in summaries],
              ['95 mph 이상']+[pct(r['hard_hit_95_share']) for r in summaries],
              ['EV <80 mph']+[pct(r['ev_under_80_share']) for r in summaries],
              ['정제 타구의 안타율']+[pct(r['hit_rate']) for r in summaries],
              ['안타 중 단타 비중']+[pct(r['single_share_of_hits']) for r in summaries]]
a,m,mlb=summaries
e={r['key']:r for r in region_rows if r['region']=='E'}
aa=next(r for r in region_rows if r['key']=='arraez' and r['region']=='A')
body=['<h1>아라에즈와 무라카미의 서로 다른 안타 구성</h1>']
body += [paragraph('아라에즈를 홈런 제외 안타 영역의 사례로 살펴봤다. 그의 평균 EV와 강한 타구 비중은 리그보다 낮았고, 안타에서 단타가 차지하는 비중은 높았다. 다만 앞서 정의한 약하게 띄운 타구의 좁은 영역을 대표하는 선수라고 단정하기에는 그 구간의 표본이 작았다.'),
         paragraph('EV·LA와 결과는 기존 2026년 정규시즌 정제 데이터에서 batter ID로 구분했다. 선수 사례는 시즌 전체를 사용하며, 공식 성적은 같은 시즌·정규시즌 MLB Stats API를 사용했다. 아라에즈의 두 팀 합산과 팀별 기록을 중복 합산하지 않았다. 기존 모델과 두 검증일은 변경하지 않았다.'),
         '<h2>타구 분포와 결과</h2>',table(['항목','아라에즈','무라카미','MLB 정제 타구'],contact_rows),
         '<figure><img src="player-contact-map.png" alt="두 선수의 타구 속도와 발사각 분포"></figure>',
         paragraph('리그의 높은 홈런 제외 안타 확률 등고선에 각 선수의 실제 타구를 겹쳐 표시했다. 이 등고선은 기존 모델의 값이다. 두 선수의 타구도 학습에 포함되어 있으므로 선수 단위 독립 검증으로 해석하지 않는다. 아라에즈의 타구는 두 검증일에 없었고, 무라카미의 타구는 3월 26일 2개·9월 27일 3개가 포함되어 있었다.'),
         paragraph(f"아라에즈는 정제 {a['batted_n']}타구에서 {a['hits']}안타를 기록했다. 단타는 {a['events']['single']}개로 안타의 {pct(a['single_share_of_hits'])}였다. 무라카미는 {m['batted_n']}타구에서 {m['hits']}안타를 기록했고 그중 {m['home_runs']}개가 홈런이었다. 타구당 안타율과 타석 성과는 서로 다른 분모로 계산해야 한다."),
         '<h2>약한 타구 사례라는 표현의 범위</h2>',
         paragraph(f"앞서 A로 정한 65≤EV&lt;75 mph·20≤LA&lt;35° 구간에서 아라에즈의 타구는 {aa['n']}개였고 안타는 {aa['hits']}개였다. 이 구간의 타구가 그의 전체 정제 타구에서 차지하는 비중은 {pct(aa['share'])}다. 이 11개만으로 낮은 EV의 높은 안타율을 대표한다고 단정하기는 어렵다."),
         paragraph(f"아라에즈의 EV&lt;80 mph 타구 비중은 {pct(a['ev_under_80_share'])}로 리그 {pct(mlb['ev_under_80_share'])}보다 낮았다. 평균 EV가 낮다는 사실을 매우 약한 타구가 특별히 많다는 뜻으로 바꾸어 읽으면 안 된다. 아라에즈는 80~95 mph의 중간 속도 타구가 많고 95 mph 이상의 비중이 낮았다."),
         paragraph(f"선수 비교용으로 추가한 75≤EV&lt;95 mph·10≤LA&lt;25° 구간에서 아라에즈는 {e['arraez']['n']}타구, {e['arraez']['hits']}안타였다. 전체 타구에서 차지하는 비중은 아라에즈 {pct(e['arraez']['share'])}, 무라카미 {pct(e['murakami']['share'])}, 리그 {pct(e['mlb']['share'])}였다. 이 구간은 기존 A~D를 변경한 것이 아니라, 아라에즈의 홈런 제외 안타 분포를 읽기 위한 사후 설명용 구간이다."),
         '<h2>타석 결과와 낮은 삼진율</h2>',table(['항목','아라에즈','무라카미','MLB 공식 성적'],stat_rows),
         '<figure><img src="player-outcome-comparison.png" alt="타구 속도 분포와 공식 타석 결과 구성"></figure>',
         paragraph(f"정제 타구의 안타율은 아라에즈 {pct(a['hit_rate'])}, 무라카미 {pct(m['hit_rate'])}였다. 그러나 공식 타율은 각각 {a['official']['avg']}와 {m['official']['avg']}였다. 아라에즈의 K%는 {pct(a['k_per_pa'])}, 무라카미는 {pct(m['k_per_pa'])}였다. 아라에즈는 삼진으로 끝나는 타석이 적어 타구를 만들어낼 기회가 많았다."),
         paragraph(f"공식 655타석에서 아라에즈의 전체 기록 타구는 {quality[0]['raw_batted_n']}개였다. 그중 번트 후보 {quality[0]['bunt_candidates']}개를 제외해 정제 579타구가 되었다. 무라카미는 553타석에서 기록 타구 259개였으며 EV 결측 2개를 제외해 257개였다. 번트와 결측을 제외한 타구 모델의 분모를 선수 타율의 분모로 사용하지 않았다."),
         paragraph('아라에즈의 성과는 낮은 EV만으로 설명할 수 없다. 홈런 제외 안타가 많은 타구 구성과 낮은 삼진율을 함께 보여주는 사례로 쓰는 편이 적절하다. 타구 방향·수비 위치·주력은 이번 모델 입력에 없으므로 높은 타율의 원인을 모두 EV·LA로 설명하지 않는다.'),
         paragraph('무라카미는 높은 HR%와 BB%, 동시에 높은 K%를 보였다. 타율만으로 두 선수의 공격 성과를 비교하면 출루와 장타의 차이를 놓칠 수 있으므로 OBP·SLG·OPS도 함께 제시했다. 어느 유형이 더 좋은지를 이 비교만으로 결론내리지 않는다.'),
         '<h2>대표 구간별 표본</h2>',table(['선수','구간','표본','전체 타구 비중','안타 / 홈런'],[[r['name'],r['region'],r['n'],pct(r['share']),str(r['hits'])+' / '+str(r['home_runs'])] for r in region_rows if r['key']!='mlb']),
         paragraph('A~D 경계는 이전 두 영역 보고서와 동일하다. E는 선수 비교용 추가 구간이다. 지역별 선수 표본은 작을 수 있으므로 성공률 차이를 확정적인 선수 능력 차이로 읽지 않는다.'),
         '<h2>글에 넣을 문단</h2>']
article = [
    '## 강한 타구 비중이 낮은 아라에즈의 안타 구성',
    f"루이스 아라에즈를 홈런 제외 안타 영역의 사례로 살펴봤다. 2026년 정제 타구에서 평균 EV는 {a['mean_ev']:.1f} mph였고, 95 mph 이상 타구의 비중은 {pct(a['hard_hit_95_share'])}였다. 리그 평균은 각각 {mlb['mean_ev']:.1f} mph와 {pct(mlb['hard_hit_95_share'])}였다. 강한 타구 비중은 낮았지만 공식 시즌 타율 {a['official']['avg']}을 기록했다. [아라에즈 공식 기록](https://baseballsavant.mlb.com/savant-player/luis-arraez-650333?season=2026)",
    f"그의 정제 타구에서 안타는 {a['hits']}개였고, 그중 {a['events']['single']}개가 단타였다. 안타의 {pct(a['single_share_of_hits'])}를 단타로 만들었다. 75~95 mph·10~25° 구간에는 {e['arraez']['n']}타구가 있었고 그중 {e['arraez']['hits']}개가 안타였다. 이 구간의 타구 비중은 리그 {pct(e['mlb']['share'])}보다 높은 {pct(e['arraez']['share'])}였다. 여기서 속도와 각도 구간의 상한은 제외했다.",
    '다만 아라에즈를 약하게 띄운 타구의 대표 선수라고 단정하기는 어려웠다. 앞서 비교한 65~75 mph·20~35° 구간에서는 11타구 중 6개가 안타였다. 이 좁은 구간이 그의 안타를 대부분 설명하는 것은 아니다.',
    f"아라에즈의 성과를 볼 때는 삼진도 함께 봐야 했다. 정제 타구의 안타율은 {pct(a['hit_rate'])}로 무라카미의 {pct(m['hit_rate'])}보다 낮았지만, K%는 {pct(a['k_per_pa'])}로 무라카미의 {pct(m['k_per_pa'])}보다 크게 낮았다. 타구가 발생했을 때의 결과와 타석이 어떤 결과로 끝나는지를 나누어 보면 두 선수의 차이가 더 잘 보였다. [무라카미 공식 기록](https://baseballsavant.mlb.com/savant-player/munetaka-murakami-808959?season=2026)",
    '아라에즈는 강한 타구 비중이 낮아도 홈런 제외 안타를 많이 만드는 사례로 볼 수 있다. 그의 타율은 EV 하나보다 타구 속도와 각도의 조합, 타구를 만들어내는 빈도를 함께 놓고 해석할 필요가 있다.',
]
(OUT/'article-section.md').write_text('\n\n'.join(article)+'\n',encoding='utf-8')
import re
body += [paragraph(re.sub(r'\[([^\]]+)\]\((https://[^)]+)\)',r'<a href="\2">\1</a>',html.escape(s))) for s in article[1:]]
body += ['<h2>출처와 재실행</h2>',paragraph('공식 성적: <a href="https://baseballsavant.mlb.com/savant-player/luis-arraez-650333?season=2026">아라에즈</a> · <a href="https://baseballsavant.mlb.com/savant-player/munetaka-murakami-808959?season=2026">무라카미</a>. 원 응답과 URL·조회 시각·해시는 raw/player-cases/manifest.json에 보관했다. 리그 성적은 MLB Stats API의 30팀 기록을 합산했다. 리그의 공식 성적 표본과 번트·결측을 제외한 타구 표본은 다르다.'),
         paragraph('프로젝트 루트에서 data\\mlb\\2026\\.venv\\Scripts\\python.exe -X utf8 scripts/mlb_player_cases.py로 오프라인 재현할 수 있다. 원본 타구·정제 데이터·모델 파일은 보존했다.')]
doc='<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>아라에즈와 무라카미의 서로 다른 안타 구성</title><style>body{margin:0;background:#f4f7f8;color:#162b36;font-family:"Malgun Gothic",sans-serif;line-height:1.85;word-break:keep-all}main{max-width:1050px;margin:auto;padding:36px 24px 70px}h1{font-size:30px;line-height:1.5}h2{font-size:21px;margin:40px 0 12px}p{margin:14px 0}img{width:100%;height:auto}figure{margin:24px 0}.tablewrap{overflow-x:auto}table{width:100%;border-collapse:collapse;background:white;font-size:14px}th,td{padding:11px 13px;border-bottom:1px solid #dbe4e8;text-align:left;white-space:nowrap}a{color:#167a93}@media(max-width:650px){main{padding:22px 14px}h1{font-size:25px}}</style></head><body><main>'+''.join(body)+'</main></body></html>'
(OUT/'report.html').write_text(doc,encoding='utf-8')
assert all(hashlib.sha256((ROOT/rel).read_bytes()).hexdigest()==v for rel,v in hashes.items())
details={'season':2026,'game_type':'R','player_case_scope':'full season descriptive; not independent player holdout',
         'source_sha256_unchanged':hashes,'model_refitted':False,'player_summaries':summaries,'case_coverage':quality,
         'regions':[{'code':r[0],'label':r[1],'ev_low':r[2],'ev_high_exclusive':r[3],'la_low':r[4],'la_high_exclusive':r[5]} for r in REGIONS],
         'region_counts':region_rows,'official_teams_aggregated':30,'statcast_population':'non-bunt EV/LA complete-case batted balls'}
(OUT/'details.json').write_text(json.dumps(details,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'summary':[{k:r[k] for k in ['name','batted_n','mean_ev','hard_hit_95_share','hit_rate','single_share_of_hits','k_per_pa','bb_per_pa','hr_per_pa']} for r in summaries],
                  'source_hashes_unchanged':True,'report':str(OUT/'report.html')},ensure_ascii=False,indent=2))

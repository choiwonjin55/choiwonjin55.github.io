"""Offline pitcher-context checks on official 2026 MLB play-by-play records.

Main outcome official H/AB; sacrifice flies are not charged as at-bats.
Main sample uses the same 237 eligible 2026 batters.
Pitcher changes during a PA, starter first PAs, extra innings and ambiguous
base-state records are excluded. Whole-league and inning sensitivities included.
No causal interpretation is assigned to observational pitcher replacement.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'data/mlb/clutch-2026'
DATA=BASE/'pitcher-context'
os.environ.setdefault('MPLCONFIGDIR',str(BASE/'.matplotlib'))

import numpy as np
import pandas as pd
from scipy import stats
from scipy import sparse


def dump(path, value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')


def interval(x):
    return np.quantile(x,[.025,.975]).tolist()


def raw_comparison(s, seed=20261024):
    assert s.ab.eq(1).all() and s.sf.eq(0).all()
    s=s.copy();s['cell']=s.fresh_reliever*2+s.risp
    rows=[]
    for fresh in (0,1):
        for risp in (0,1):
            t=s[(s.fresh_reliever==fresh)&(s.risp==risp)]
            rows.append({'fresh_reliever':fresh,'risp':risp,'n':len(t),'hits':int(t.hit.sum()),
                         'official_ab':int(t.ab.sum()),'sf':int(t.sf.sum()),
                         'official_avg':float(t.hit.sum()/t.ab.sum())})
    grouped=s.groupby(['game_pk','cell']).agg(n=('hit','size'),h=('hit','sum'))
    games=np.sort(s.game_pk.unique())
    ns=grouped['n'].unstack(fill_value=0).reindex(index=games,columns=range(4),fill_value=0).to_numpy()
    hs=grouped['h'].unstack(fill_value=0).reindex(index=games,columns=range(4),fill_value=0).to_numpy()
    rng=np.random.default_rng(seed)
    weights=rng.multinomial(len(games),np.full(len(games),1/len(games)),size=5000)
    boot=(weights@hs)/(weights@ns)
    rates=np.array([r['official_avg'] for r in rows])
    difference=rates[[1,3]]-rates[[0,2]]
    bootdiff=boot[:,[1,3]]-boot[:,[0,2]]
    return {'cells':rows,'continuing_risp_difference':float(difference[0]),
        'continuing_risp_difference_95':interval(bootdiff[:,0]),
        'fresh_risp_difference':float(difference[1]),'fresh_risp_difference_95':interval(bootdiff[:,1]),
        'fresh_minus_continuing_risp_difference':float(difference[1]-difference[0]),
        'fresh_minus_continuing_risp_difference_95':interval(bootdiff[:,1]-bootdiff[:,0]),
        'games':len(games),'ci':'5000 game-cluster bootstrap replicates'}


def absorb(values, group_codes, tolerance=1e-10, max_iterations=400):
    if len(group_codes)==2:
        # Exact two-way projection via the smaller (batter) Schur complement.
        # This also handles disconnected FE graphs and singleton pitcher-games.
        b,p=group_codes
        nb,npit=np.bincount(b),np.bincount(p)
        v=np.asarray(values,dtype=float)
        pmean=np.column_stack([np.bincount(p,weights=v[:,j])/npit for j in range(v.shape[1])])
        centered=v-pmean[p]
        cross=sparse.coo_matrix((np.ones(len(b)),(b,p)),shape=(len(nb),len(npit))).tocsr()
        schur=np.diag(nb.astype(float))-(cross@sparse.diags(1/npit)@cross.T).toarray()
        rhs=np.column_stack([np.bincount(b,weights=centered[:,j]) for j in range(v.shape[1])])
        effect=np.linalg.lstsq(schur,rhs,rcond=1e-11)[0]
        fitted=effect[b]
        fp=np.column_stack([np.bincount(p,weights=fitted[:,j])/npit for j in range(v.shape[1])])
        out=centered-fitted+fp[p]
        for group,n in ((b,nb),(p,npit)):
            assert max(np.abs(np.bincount(group,weights=out[:,j])/n).max() for j in range(out.shape[1]))<1e-7
        return out,1
    out=np.asarray(values,dtype=float).copy()
    counts=[np.bincount(g) for g in group_codes]
    for iteration in range(max_iterations):
        change=0.
        for g,n in zip(group_codes,counts):
            means=np.column_stack([np.bincount(g,weights=out[:,j],minlength=len(n))/n
                                   for j in range(out.shape[1])])
            change=max(change,float(np.abs(means).max()))
            out-=means[g]
        if change<tolerance:return out,iteration+1
    raise RuntimeError(f'Fixed-effect absorption failed to converge: {change}')


def model(s, daily=False, form=False):
    s=s.copy().reset_index(drop=True)
    columns={'risp':s.risp,'fresh_reliever':s.fresh_reliever,
             'risp_x_fresh':s.risp*s.fresh_reliever,
             'out1':(s.outs==1).astype(int),'out2':(s.outs==2).astype(int),
             'home':(s.half=='bottom').astype(int),
             'opposite_hand':(s.bat_side!=s.pitch_hand).astype(int),
             'reliever':s.reliever,'on_first':s.on_1b}
    for inning in range(2,10):columns[f'inning_{inning}']=(s.inning==inning).astype(int)
    score=s.score_diff.clip(-4,4)
    for diff in (-4,-3,-2,-1,1,2,3,4):columns[f'score_{diff}']=(score==diff).astype(int)
    month=s.date.str.slice(5,7)
    for m in sorted(month.unique())[1:]:columns['month_'+m]=(month==m).astype(int)
    if form:
        columns['recent5_reach_rate']=s.recent5_reached/s.recent_pa_n.clip(lower=1)
    names=list(columns)
    x=np.column_stack([columns[k].to_numpy(dtype=float) for k in names])
    groups=[pd.factorize(s.batter)[0],pd.factorize(s.pitcher.astype(str)+'_'+s.game_pk.astype(str) if daily else s.pitcher)[0]]
    transformed,iterations=absorb(np.column_stack([s.hit.to_numpy(),x]),groups)
    y,x=transformed[:,0],transformed[:,1:]
    keep=np.std(x,axis=0)>1e-9
    names=[n for n,k in zip(names,keep) if k];x=x[:,keep]
    beta,_,rank,_=np.linalg.lstsq(x,y,rcond=None)
    assert rank==len(names),(rank,names)
    residual=y-x@beta
    game_codes,_=pd.factorize(s.game_pk)
    ngames=game_codes.max()+1
    scores=np.column_stack([np.bincount(game_codes,weights=x[:,j]*residual,minlength=ngames)
                            for j in range(x.shape[1])])
    bread=np.linalg.inv(x.T@x)
    # Cluster correction accounts conservatively for absorbed FE degrees of freedom.
    fe_df=sum(len(np.unique(g)) for g in groups)-1
    correction=ngames/(ngames-1)*(len(s)-1)/(len(s)-len(names)-fe_df)
    covariance=bread@(scores.T@scores)@bread*correction
    quantile=stats.t.ppf(.975,ngames-1)
    def contrast(weights):
        v=np.array([weights.get(n,0.) for n in names]);estimate=float(v@beta)
        se=float(np.sqrt(v@covariance@v))
        return {'estimate':estimate,'se':se,'ci95':[estimate-quantile*se,estimate+quantile*se],
                'p':float(2*stats.t.sf(abs(estimate/se),ngames-1)) if se else 1.0}
    output={'n':len(s),'games':int(ngames),'fixed_effects':['batter','pitcher_game' if daily else 'pitcher'],
        'absorption_iterations':iterations,'controls':names,
        'continuing_risp_difference':contrast({'risp':1})}
    if 'fresh_reliever' in names:
        output['fresh_risp_difference']=contrast({'risp':1,'risp_x_fresh':1})
        output['fresh_minus_continuing_difference']=contrast({'risp_x_fresh':1})
    if form:output['recent5_reach_rate_effect']=contrast({'recent5_reach_rate':1})
    return output


def opponent_quality(all_pa, primary):
    """Estimate pitcher hit-allowance from other games only, avoiding target-game leakage."""
    t=all_pa[all_pa.ab>0].copy()
    season=t.groupby('pitcher').agg(n=('hit','size'),h=('hit','sum'))
    game=t.groupby(['pitcher','game_pk']).agg(n=('hit','size'),h=('hit','sum'))
    s=primary.merge(season,left_on='pitcher',right_index=True,validate='many_to_one')
    s=s.merge(game,left_on=['pitcher','game_pk'],right_index=True,suffixes=('_season','_game'),validate='many_to_one')
    remaining_n=s.n_season-s.n_game
    mean=t.hit.mean()
    s['opponent_other_game_rate']=(s.h_season-s.h_game+50*mean)/(remaining_n+50)
    result=[]
    for fresh in (0,1):
        for risp in (0,1):
            z=s[(s.fresh_reliever==fresh)&(s.risp==risp)]
            result.append({'fresh_reliever':fresh,'risp':risp,'n':len(z),
                           'opponent_other_game_rate':float(z.opponent_other_game_rate.mean())})
    return {'cells':result,'prior_ab':50,'prior_rate':float(mean),
            'missing_other_game_samples':int((remaining_n==0).sum()),
            'definition':'Pitcher official H/AB from all OTHER games; 50-AB league-mean shrinkage.'}


def figure(result):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.ticker import FormatStrFormatter
    plt.rcParams.update({'font.family':['Malgun Gothic','DejaVu Sans'],'axes.unicode_minus':False,
        'axes.spines.top':False,'axes.spines.right':False,'font.size':11,
        'figure.facecolor':'#fbfaf7','axes.facecolor':'#fbfaf7','savefig.facecolor':'#fbfaf7'})
    fig,axes=plt.subplots(1,2,figsize=(13,5.3),layout='constrained')
    cells=result['raw_primary']['cells']
    for risp,label,color,offset in [(0,'비득점권','#84959e',-.18),(1,'득점권','#157b8c',.18)]:
        z=[c for c in cells if c['risp']==risp]
        vals=[c['official_avg'] for c in z]
        axes[0].bar(np.arange(2)+offset,vals,width=.34,label=label,color=color)
        for x,y,c in zip(np.arange(2)+offset,vals,z):axes[0].text(x,y+.003,f"{y:.3f}\n{c['n']:,}타수",ha='center',fontsize=9)
    axes[0].set(xticks=[0,1],xticklabels=['기존 투수 계속','구원 투수 첫 타석'],ylim=(0,max(c['official_avg'] for c in cells)+.07),
                ylabel='타율 · 안타 / 타수',title='투수 교체 여부별 실제 성적')
    axes[0].yaxis.set_major_formatter(FormatStrFormatter('%.3f'))
    axes[0].legend(frameon=False,fontsize=10)
    configs=[('raw','단순 비교'),('identity','타자·투수 차이 반영')]
    for fresh,label,color,offset in [(False,'기존 투수 계속','#df744d',-.10),(True,'구원 투수 첫 타석','#157b8c',.10)]:
        for i,(key,_) in enumerate(configs):
            metric='fresh_risp_difference' if fresh else 'continuing_risp_difference'
            if key=='raw':
                estimate=result['raw_primary'][metric];lo,hi=result['raw_primary'][metric+'_95']
            else:
                r=result['models'][key][metric];estimate=r['estimate'];lo,hi=r['ci95']
            axes[1].errorbar(estimate,i+offset,xerr=[[(estimate-lo)],[(hi-estimate)]],
                             fmt='o',color=color,capsize=4,label=label if i==0 else None)
    axes[1].set(yticks=range(len(configs)),yticklabels=[x[1] for x in configs],xlabel='득점권 - 비득점권 차이',
                title='조건 반영 전후 차이와 95% 신뢰구간')
    axes[1].axvline(0,color='#84959e',lw=1);axes[1].invert_yaxis();axes[1].legend(frameon=False,fontsize=9)
    axes[1].xaxis.set_major_formatter(FormatStrFormatter('%.3f'))
    fig.savefig(ROOT/'assets/mlb-clutch-2026/pitcher-context.png',dpi=180);plt.close(fig)


def run():
    audit=json.loads((DATA/'audit.json').read_text(encoding='utf-8'))
    assert audit['complete_schedule']
    assert not any(audit['official_differences'].values()),audit['official_differences']
    all_pa=pd.read_csv(DATA/'plate-appearances.csv.gz')
    valid=all_pa[(all_pa.ab>0)&(all_pa.mid_pa_change==0)&(all_pa.mid_pa_batter_change==0)&(all_pa.starter_first_pa==0)&
                 (all_pa.context_valid==1)&(all_pa.outs.between(0,2))].copy()
    official=pd.read_csv(BASE/'analysis/eligible-2026.csv')
    primary=valid[valid.batter.isin(official.player_id)&(valid.inning<=9)].copy()
    result={'spec':{'season':2026,'outcome':'H/AB','sacrifice_flies':'Excluded from official at-bats; no correction from cause 1 applied',
        'primary_batters':len(official),
        'fresh':'First PA faced by a relief pitcher in a game; exclude changes during PA',
        'controls':'Batter/pitcher FE, outs, inning, batting side advantage, home batting, first-base occupancy, pre-PA score, month',
        'standard_errors':'Game-cluster sandwich, conservative finite-sample FE degrees correction',
        'models':'Linear probability models with two-way absorbed fixed effects',
        'causality':'Observational comparisons; pitcher change is not randomized.'},
        'audit':{'raw_pa':len(all_pa),'primary_ab':len(primary),
            'context_invalid_pa':int((all_pa.context_valid==0).sum()),
            'mid_pa_changes':int(all_pa.mid_pa_change.sum()),'starter_first':int(all_pa.starter_first_pa.sum()),
            'mid_pa_batter_changes':int(all_pa.mid_pa_batter_change.sum()),
            'context_invalid_by_event':all_pa[all_pa.context_valid==0].event.value_counts().to_dict()},
        'raw_primary':raw_comparison(primary),'models':{},'opponent_quality':opponent_quality(all_pa,primary)}
    for key,daily in [('identity',False)]:
        print('fit',key,len(primary),flush=True)
        result['models'][key]=model(primary,daily=daily)
    # Pitcher-game FE condition on a stint's outcome totals. RISP itself is
    # generated by prior outcomes, producing a mechanical negative bias in
    # short stints even when consecutive outcomes are independent. Retain the
    # result only as a rejected-method diagnostic, not evidence of daily form.
    print('diagnostic pitcher-game fixed effects',flush=True)
    result['diagnostics']={'pitcher_game_fe':model(primary,daily=True),
        'pitcher_game_fe_not_used_for_inference':True,
        'reason':'Conditioning on the same stint outcome totals biases a context generated by prior outcomes; use predetermined recent form instead.'}
    rng=np.random.default_rng(20261024)
    y=rng.binomial(1,.25,size=(20000,6)).astype(float)
    x=np.roll(y,1,axis=1)[:,1:];y=y[:,1:]
    raw=correlation_slope(x,y,within=False);within=correlation_slope(x,y,within=True)
    result['diagnostics']['independent_null_previous_outcome_test']={
        'true_effect':0,'unadjusted_slope':raw,'same_stint_fe_slope':within,
        'stints':20000,'scored_observations_per_stint':5,'seed':20261024}
    result['sensitivities']={}
    for name,s in [('all_batters',valid[valid.inning<=9]),
                   ('with_extra_innings',valid[valid.batter.isin(official.player_id)])]:
        print('sensitivity',name,len(s),flush=True)
        result['sensitivities'][name]={'n':len(s),'model':model(s,daily=False)}
    continuing=primary[(primary.fresh_reliever==0)&(primary.recent_pa_n>=3)]
    # Prior five batters' outcomes are known BEFORE the current PA.
    print('recent form',len(continuing),flush=True)
    # No fresh observations in this check: remove zero columns automatically.
    result['recent_form_model']=model(continuing,form=True)
    result['source_hashes']={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()
        for p in [DATA/'manifest.json',DATA/'audit.json',DATA/'special-at-bats.json',DATA/'plate-appearances.csv.gz',Path(__file__),
                  ROOT/'scripts/mlb_pitcher_context_collect.py']}
    dump(DATA/'results.json',result)
    dump(ROOT/'assets/mlb-clutch-2026/pitcher-context-results.json',result)
    figure(result)
    print(json.dumps(result,ensure_ascii=False,indent=2)[:20000])


def correlation_slope(x,y,within=False):
    center=lambda a:a-a.mean(axis=1,keepdims=True) if within else a-a.mean()
    a,b=center(x),center(y)
    return float((a*b).sum()/(a*a).sum())


if __name__=='__main__':
    run()

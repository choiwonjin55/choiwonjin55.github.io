"""Offline 2025 -> 2026 RISP persistence analysis.

Requires numpy, pandas, scipy, matplotlib. See docs/mlb-clutch-analysis.md.
All rates are computed from integer H/AB; published rounded AVG is never input.
"""
from __future__ import annotations

import hashlib
import importlib.metadata
import json
import math
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'data/mlb/clutch-2026'
OUT = DATA / 'analysis'
ASSETS = ROOT / 'assets/mlb-clutch-2026'
os.environ.setdefault('MPLCONFIGDIR', str(DATA / '.matplotlib'))

import numpy as np
import pandas as pd
from scipy import stats

SEED = 20261023
REPS = 20000
BOOT = 10000
METRICS = ('delta', 'contrast', 'z', 'avg', 'risp_avg')
LABELS = {'delta': '득타율 − 전체 타율', 'contrast': '득점권 − 비득점권 타율',
          'z': '표본 수를 반영한 표준화 차이', 'avg': '전체 타율', 'risp_avg': '득점권 타율'}


def dump(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')


def rates(frame):
    s = frame.copy()
    s['avg'] = s.h / s.ab
    s['risp_avg'] = s.risp_h / s.risp_ab
    s['nonrisp_avg'] = s.nonrisp_h / s.nonrisp_ab
    s['delta'] = s.risp_avg - s.avg
    s['contrast'] = s.risp_avg - s.nonrisp_avg
    # Var(H_R | H,N,n_R), without replacement (finite population correction).
    var_hits = s.risp_ab * s.avg * (1-s.avg) * s.nonrisp_ab / (s.ab-1)
    s['null_sd_delta'] = np.sqrt(var_hits) / s.risp_ab
    s['z'] = s.delta / s.null_sd_delta
    assert np.allclose(s.delta, s.nonrisp_ab / s.ab * s.contrast)
    assert np.isfinite(s[list(METRICS)]).all().all()
    return s


def eligible(inventory, year, threshold):
    mask = ((inventory.season == year) & (inventory.ab >= 300) &
            (inventory.risp_ab >= threshold) & (inventory.nonrisp_ab > 0))
    return rates(inventory.loc[mask].sort_values('player_id').reset_index(drop=True))


def interval(values):
    return np.quantile(values, [.025, .975]).tolist()


def probability(null, observed, centered=False):
    if centered:
        return float((1 + np.count_nonzero(np.abs(null) >= abs(observed))) / (len(null)+1))
    return float((1 + np.count_nonzero(null >= observed)) / (len(null)+1))


def holm(pvalues):
    """Holm family-wise adjustment; valid with dependent exploratory tests."""
    p = np.asarray(pvalues)
    order = np.argsort(p)
    adjusted = np.empty(len(p))
    adjusted[order] = np.minimum(1, np.maximum.accumulate(p[order] * np.arange(len(p),0,-1)))
    return adjusted.tolist()


def distribution(s, seed):
    rng = np.random.default_rng(seed)
    h = s.h.to_numpy(dtype=int)
    n = s.ab.to_numpy(dtype=int)
    nr = s.risp_ab.to_numpy(dtype=int)
    nh = rng.hypergeometric(h, n-h, nr, size=(REPS, len(s)))
    null = nh / nr - h / n
    observed = s.delta.to_numpy()
    std_null = null.std(axis=1, ddof=1)
    mean_null = null.mean(axis=1)
    znull = null / s.null_sd_delta.to_numpy()
    # Center each realization to separate a common RISP shift from dispersion.
    z_observed = s.z.to_numpy()
    z_tail = int((np.abs(z_observed-z_observed.mean()) > 1.96).sum())
    z_tail_null = (np.abs(znull-znull.mean(axis=1, keepdims=True)) > 1.96).sum(axis=1)
    bin_edges = np.linspace(-.18, .18, 25)
    hist = np.array([np.histogram(x, bins=bin_edges)[0] for x in null])
    theoretical = stats.norm.ppf((np.arange(len(s))+.5)/len(s))
    shapiro = stats.shapiro(observed)
    result = {'n': len(s), 'mean_delta': float(observed.mean()),
        'sd_delta': float(observed.std(ddof=1)), 'normality_shapiro_w': float(shapiro.statistic),
        'normality_shapiro_p': float(shapiro.pvalue),
        'skewness': float(stats.skew(observed, bias=False)),
        'excess_kurtosis': float(stats.kurtosis(observed, bias=False)),
        'null_sd_median': float(np.median(std_null)), 'null_sd_95': interval(std_null),
        'dispersion_upper_p': probability(std_null, observed.std(ddof=1)),
        'null_mean_95': interval(mean_null),
        'mean_two_sided_p': probability(mean_null, observed.mean(), True),
        'mean_z': float(z_observed.mean()), 'sd_z': float(z_observed.std(ddof=1)),
        'null_sd_z_95': interval(znull.std(axis=1, ddof=1)),
        'z_dispersion_upper_p': probability(znull.std(axis=1, ddof=1), z_observed.std(ddof=1)),
        'centered_abs_z_over_1_96': z_tail, 'null_centered_tail_count_95': interval(z_tail_null),
        'tail_upper_p': probability(z_tail_null, z_tail),
        'figure_data': {'edges': bin_edges.tolist(), 'null_hist_mean': hist.mean(axis=0).tolist(),
            'null_hist_low': np.quantile(hist,.025,axis=0).tolist(),
            'null_hist_high': np.quantile(hist,.975,axis=0).tolist(),
            'qq_theoretical': theoretical.tolist(), 'qq_observed': np.sort(observed).tolist()}}
    return result


def correlation(x, y):
    x, y = np.asarray(x), np.asarray(y)
    xc, yc = x-x.mean(axis=-1, keepdims=True), y-y.mean(axis=-1, keepdims=True)
    return (xc*yc).sum(axis=-1) / np.sqrt((xc*xc).sum(axis=-1)*(yc*yc).sum(axis=-1))


def persistence(pair, seed):
    rng = np.random.default_rng(seed)
    n = len(pair)
    indices = rng.integers(0,n,size=(BOOT,n))
    permutations = np.array([rng.permutation(n) for _ in range(REPS)])
    output = {}
    for metric in METRICS:
        x, y = pair[f'{metric}_2025'].to_numpy(), pair[f'{metric}_2026'].to_numpy()
        observed = float(correlation(x,y))
        rx, ry = stats.rankdata(x), stats.rankdata(y)
        spearman = float(correlation(rx,ry))
        bootx, booty = x[indices], y[indices]
        boot_pearson = correlation(bootx, booty)
        # Re-rank within each resampled pair, including duplicated observations.
        boot_spearman = correlation(stats.rankdata(bootx, axis=1), stats.rankdata(booty, axis=1))
        output[metric] = {'pearson': observed, 'pearson_95': interval(boot_pearson),
            'spearman': spearman, 'spearman_95': interval(boot_spearman),
            'pearson_permutation_p': probability(correlation(np.broadcast_to(x,(REPS,n)), y[permutations]), observed, True),
            'spearman_permutation_p': probability(correlation(np.broadcast_to(rx,(REPS,n)), ry[permutations]), spearman, True)}
    return output


def tail_groups(pair, seed, metric='delta'):
    rng = np.random.default_rng(seed)
    n, k = len(pair), math.floor(len(pair)*.2)
    ordered = pair.sort_values([f'{metric}_2025','player_id'])
    low_ids, high_ids = set(ordered.head(k).player_id), set(ordered.tail(k).player_id)
    order_next = pair.sort_values([f'{metric}_2026','player_id'])
    next_low, next_high = set(order_next.head(k).player_id), set(order_next.tail(k).player_id)
    rows = []
    for name, ids, next_ids in [('bottom',low_ids,next_low),('top',high_ids,next_high)]:
        selected = pair[pair.player_id.isin(ids)]
        a = selected[f'{metric}_2025'].to_numpy()
        b = selected[f'{metric}_2026'].to_numpy()
        ib = rng.integers(0,k,size=(BOOT,k))
        retained = len(ids & next_ids)
        null_retention = rng.hypergeometric(k,n-k,k,size=REPS) / k
        retained_ci = stats.binomtest(retained,k).proportion_ci(method='wilson')
        rows.append({'group': name, 'n':k, 'mean_2025':float(a.mean()),
            'mean_2026':float(b.mean()), 'mean_2026_95':interval(b[ib].mean(axis=1)),
            'mean_change':float((b-a).mean()), 'mean_change_95':interval((b-a)[ib].mean(axis=1)),
            'retained':retained,'retention_rate':retained/k,
            'retention_wilson_95':[float(retained_ci.low),float(retained_ci.high)],
            'null_retention_expected':k/n,'null_retention_95':interval(null_retention),
            'retention_upper_p':float(stats.hypergeom.sf(retained-1,n,k,k))})
    top = pair[pair.player_id.isin(high_ids)][f'{metric}_2026'].to_numpy()
    low = pair[pair.player_id.isin(low_ids)][f'{metric}_2026'].to_numpy()
    diff_boot = top[rng.integers(0,k,size=(BOOT,k))].mean(axis=1)-low[rng.integers(0,k,size=(BOOT,k))].mean(axis=1)
    values = pair[f'{metric}_2026'].to_numpy()
    top_indices = np.flatnonzero(pair.player_id.isin(high_ids))
    low_indices = np.flatnonzero(pair.player_id.isin(low_ids))
    diff_null = np.array([np.subtract(*[a[ix].mean() for ix in (top_indices,low_indices)])
                          for a in (rng.permutation(values) for _ in range(REPS))])
    members = pair.copy()
    members['group_2025'] = ['top' if p in high_ids else 'bottom' if p in low_ids else 'middle' for p in pair.player_id]
    members['group_2026'] = ['top' if p in next_high else 'bottom' if p in next_low else 'middle' for p in pair.player_id]
    result = {'metric':metric,'cohort_n':n,'group_size':k,'groups':rows,
        'top_minus_bottom_2026':float(top.mean()-low.mean()),
        'top_minus_bottom_2026_95':interval(diff_boot),
        'top_minus_bottom_permutation_p':probability(diff_null,top.mean()-low.mean(),True),
        'ci_note':'Bootstrap conditional on selected 2025 groups; Wilson intervals are descriptive; exact hypergeometric null tests retention.'}
    return result, members


def attrition(s25, s26):
    k = math.floor(len(s25)*.2)
    ordered = s25.sort_values(['delta','player_id'])
    ids26 = set(s26.player_id)
    return {name:{'baseline_n':len(s),'eligible_2026_n':int(s.player_id.isin(ids26).sum())}
            for name,s in [('all',s25),('top',ordered.tail(k)),('bottom',ordered.head(k))]}


def figures(s, paired, result):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    ASSETS.mkdir(parents=True,exist_ok=True)
    plt.rcParams.update({'font.family':['Malgun Gothic','DejaVu Sans'],'axes.unicode_minus':False,
        'font.size':11,'axes.spines.top':False,'axes.spines.right':False,
        'figure.facecolor':'#fbfaf7','axes.facecolor':'#fbfaf7','savefig.facecolor':'#fbfaf7'})
    c1,c2,c3 = '#157b8c','#df744d','#768897'
    d = result['distribution_2026']; f = d['figure_data']
    fig,axes=plt.subplots(1,2,figsize=(13,5.3),layout='constrained')
    edges=np.array(f['edges'])*100
    axes[0].hist(s.delta*100,bins=edges,color=c1,alpha=.8,label=f'실제 선수 {len(s)}명')
    mid=(edges[:-1]+edges[1:])/2
    axes[0].plot(mid,f['null_hist_mean'],color=c2,lw=2,label='무작위 배정 평균')
    axes[0].fill_between(mid,f['null_hist_low'],f['null_hist_high'],color=c2,alpha=.15,label='구간별 모의 결과 95% 범위')
    axes[0].axvline(0,c=c3,lw=.8)
    axes[0].set(xlabel='득타율 − 전체 타율 (%p)',ylabel='선수 수',title='2026년 차이의 분포와 우연 모형')
    axes[0].legend(fontsize=9)
    q=np.array(f['qq_theoretical']); obs=np.array(f['qq_observed'])*100
    axes[1].scatter(q,obs,color=c1,s=19,alpha=.7)
    axes[1].plot(q,(s.delta.mean()+s.delta.std(ddof=1)*q)*100,color=c2,lw=1.5)
    axes[1].set(xlabel='정규분포의 이론적 분위수',ylabel='실제 차이의 분위수 (%p)',title='정규 Q–Q plot')
    fig.savefig(ASSETS/'distribution.png',dpi=180);plt.close(fig)
    fig,axes=plt.subplots(1,2,figsize=(13,5.5),layout='constrained')
    for ax,m in zip(axes,['delta','avg']):
        x,y=paired[f'{m}_2025']*100,paired[f'{m}_2026']*100
        groups=paired.group_2025
        for g,label,col in [('middle','중간 60%',c3),('top','2025년 상위 20%',c2),('bottom','2025년 하위 20%',c1)]:
            mask=groups==g
            ax.scatter(x[mask],y[mask],s=25,c=col,label=label,alpha=.8)
        if m=='delta':
            ax.axhline(0,color=c3,lw=.7);ax.axvline(0,color=c3,lw=.7)
        slope,intercept=np.polyfit(x,y,1)
        lim=[min(x.min(),y.min())-1,max(x.max(),y.max())+1]
        ax.plot(lim,np.array(lim)*slope+intercept,color=c2,lw=1.5)
        r=result['persistence'][m]
        ax.set(xlim=lim,ylim=lim,xlabel=f'2025년 {LABELS[m]}'+(' (%p)' if m=='delta' else ' (%)'),
               ylabel=f'2026년 {LABELS[m]}'+(' (%p)' if m=='delta' else ' (%)'),
               title=f"{LABELS[m]} · r={r['pearson']:.3f}")
        ax.set_aspect('equal',adjustable='box')
    axes[0].legend(fontsize=9)
    fig.suptitle(f'같은 선수 {len(paired)}명의 연도 간 비교',fontsize=17)
    fig.savefig(ASSETS/'persistence.png',dpi=180);plt.close(fig)
    fig,axes=plt.subplots(1,2,figsize=(13,5),layout='constrained')
    gs=result['groups_delta']['groups']
    for g,col,label in zip(gs,[c1,c2],['2025년 하위 20%','2025년 상위 20%']):
        vals=np.array([g['mean_2025'],g['mean_2026']])*100
        axes[0].plot([0,1],vals,marker='o',color=col,lw=2,label=label)
        lo,hi=np.array(g['mean_2026_95'])*100
        axes[0].errorbar(1,vals[1],yerr=[[vals[1]-lo],[hi-vals[1]]],color=col,capsize=5)
    axes[0].axhline(0,c=c3,lw=.8)
    axes[0].set(xticks=[0,1],xticklabels=['2025','2026'],xlim=(-.2,1.25),ylabel='평균 득타율 − 전체 타율 (%p)',title='상·하위권의 다음 해 평균과 95% 신뢰구간')
    axes[0].legend(fontsize=9)
    for i,g in enumerate(gs):
        axes[1].bar(i,g['retention_rate']*100,color=[c1,c2][i],width=.5)
        axes[1].text(i,g['retention_rate']*100+1,f"{g['retained']}/{g['n']}명",ha='center')
    axes[1].axhline(gs[0]['null_retention_expected']*100,c=c3,ls='--',label='무작위 순위의 기대 잔류율')
    axes[1].set(xticks=[0,1],xticklabels=['하위권 유지','상위권 유지'],ylim=(0,max(40,max(g['retention_rate'] for g in gs)*100+10)),
                ylabel='2026년 같은 집단에 남은 비율 (%)',title='같은 순위 집단의 잔류율')
    axes[1].legend(fontsize=9)
    fig.savefig(ASSETS/'groups.png',dpi=180);plt.close(fig)


def dashboard(pair, primary):
    payload = json.dumps({'players':pair.to_dict(orient='records'),
                          'persistence':primary['persistence']},ensure_ascii=False,allow_nan=False).replace('<','\\u003c')
    template = (ROOT/'scripts/mlb_clutch_dashboard.html').read_text(encoding='utf-8')
    assert template.count('__CLUTCH_PAYLOAD__') == 1
    (ROOT/'scripts/mlb-clutch-dashboard.html').write_text(template.replace('__CLUTCH_PAYLOAD__',payload),encoding='utf-8')


def run():
    OUT.mkdir(parents=True,exist_ok=True)
    inv=pd.read_csv(DATA/'processed/player-season-inventory.csv')
    audit=json.loads((DATA/'audit.json').read_text(encoding='utf-8'))
    assert all(v['player_team_totals_match'] and v['missing_risp_with_300_ab']==0 for v in audit['years'].values())
    sensitivity=[]; primary=None; primary_pair=None; primary_s26=None
    for threshold in [50,75,100]:
        s25,s26=[eligible(inv,y,threshold) for y in (2025,2026)]
        pair=s25.merge(s26,on='player_id',suffixes=('_2025','_2026'),validate='one_to_one').sort_values('player_id').reset_index(drop=True)
        result={'threshold_risp_ab':threshold,'min_total_ab':300,'eligible_2025':len(s25),'eligible_2026':len(s26),
            'paired_n':len(pair),'attrition':attrition(s25,s26),
            'distribution_2026':distribution(s26,SEED+threshold),
            'persistence':persistence(pair,SEED+threshold+1000)}
        result['groups_delta'],members=tail_groups(pair,SEED+threshold+2000)
        result['groups_contrast'],_=tail_groups(pair,SEED+threshold+3000,'contrast')
        sensitivity.append(result)
        if threshold==75:
            primary=result;primary_pair=members;primary_s26=s26
            s25.to_csv(OUT/'eligible-2025.csv',index=False,encoding='utf-8-sig')
            s26.to_csv(OUT/'eligible-2026.csv',index=False,encoding='utf-8-sig')
            members.to_csv(OUT/'paired-players.csv',index=False,encoding='utf-8-sig')
        print('threshold',threshold,'paired',len(pair),'delta r',result['persistence']['delta']['pearson'],flush=True)
    # Report all 12 exploratory retention tests, including apparently positive ones.
    retention = [g for s in sensitivity for metric in ('delta','contrast') for g in s['groups_'+metric]['groups']]
    for g, adjusted in zip(retention, holm([g['retention_upper_p'] for g in retention])):
        g['retention_holm_p_12_tests'] = adjusted
    # Empirical cohort-level average and player-specific standardized dispersion are separate.
    hashes={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()
            for p in [DATA/'manifest.json',DATA/'audit.json',DATA/'processed/player-season-inventory.csv',
                      ROOT/'scripts/mlb_clutch_collect.py',Path(__file__)]}
    result={'spec':{'seasons':[2025,2026],'game_type':'R','seed':SEED,'null_repetitions':REPS,
        'python':sys.version,'packages':{p:importlib.metadata.version(p) for p in ('numpy','pandas','scipy','matplotlib')},
        'bootstrap_repetitions':BOOT,'primary_threshold':75,'min_total_ab':300,
        'groups':'floor(0.2*N), sorted by metric then player_id within shared eligible cohort',
        'null':'Within each player-season, fix total H, AB, RISP AB; hypergeometric allocation of H.',
        'bootstrap':'Resample paired players for correlations; resample within fixed 2025 groups for means.',
        'null_retention':'Exact hypergeometric random reassignment of the 2026 ranking.',
        'exploratory_retention_family':'12 tests: 3 thresholds x 2 metrics x 2 tails; Holm correction.'},
        'source_hashes':hashes,'primary':primary,'sensitivity':sensitivity}
    dump(OUT/'results.json',result)
    dump(ASSETS/'results.json',result)
    figures(primary_s26,primary_pair,primary)
    dashboard(primary_pair,primary)
    print(json.dumps({k:v for k,v in primary.items() if k not in ('distribution_2026','attrition')},ensure_ascii=False,indent=2))


if __name__=='__main__':
    run()

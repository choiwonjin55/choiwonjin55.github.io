"""Conditional binomial WAR/wins checks, cohort maxima, and historical comparisons.

Standard-library analysis; add --figures with matplotlib installed to export PNGs.
This model fixes p_i at the same-season WAR-based win estimate divided by games.
It draws team-seasons independently, without enforcing MLB schedule constraints.
"""
from __future__ import annotations

import argparse
from bisect import bisect_right
import json
import math
import os
from pathlib import Path
import random
from statistics import mean, pstdev

from mlb_war_wins_collect import DATA, ROOT, digest, load_snapshot, save_json

ASSETS = ROOT / 'assets/mlb-war-wins'


def binomial_pmf(n, p):
    if not isinstance(n, int) or n < 0 or not math.isfinite(p) or not 0 <= p <= 1:
        raise ValueError('Invalid binomial parameters')
    if p in (0, 1):
        return [float(k == (n if p else 0)) for k in range(n+1)]
    masses = [math.comb(n, k)*p**k*(1-p)**(n-k) for k in range(n+1)]
    total = math.fsum(masses)
    return [mass/total for mass in masses]


def quantile(masses, probability):
    cumulative = 0.
    for k, mass in enumerate(masses):
        cumulative += mass
        if cumulative >= probability:
            return k
    return len(masses)-1


def two_sided(masses, observed):
    """Probability-ordered exact two-sided test, as in scipy.stats.binomtest."""
    return min(1., math.fsum(v for v in masses if v <= masses[observed]*(1+1e-12)))


def holm_adjust(pvalues):
    order = sorted(range(len(pvalues)), key=pvalues.__getitem__)
    adjusted = [0.] * len(pvalues)
    previous = 0.
    for rank, index in enumerate(order):
        previous = max(previous, min(1., (len(pvalues)-rank)*pvalues[index]))
        adjusted[index] = previous
    return adjusted


def maximum_cdf_less(distributions, threshold):
    """P(max_i |W_i-mu_i| < threshold), for independent binomial W_i."""
    log_probability = 0.
    for mu, masses in distributions:
        probability = math.fsum(mass for wins, mass in enumerate(masses)
                                if abs(wins-mu) < threshold-1e-12)
        if probability == 0:
            return 0.
        log_probability += math.log(min(1., probability))
    return math.exp(log_probability)


def simulate_maxima(distributions, observed, repetitions, seed):
    if repetitions <= 0:
        raise ValueError('Positive simulation size required')
    prepared = []
    for mu, masses in distributions:
        cumulative, total = [], 0.
        for mass in masses:
            total += mass
            cumulative.append(total)
        cumulative[-1] = 1.
        prepared.append((mu, cumulative))
    generator = random.Random(seed)
    histogram, exceedances, total_maximum = {}, 0, 0.
    for _ in range(repetitions):
        maximum = 0.
        for mu, cumulative in prepared:
            maximum = max(maximum, abs(bisect_right(cumulative, generator.random())-mu))
        bucket = math.floor(maximum*2)
        histogram[bucket] = histogram.get(bucket, 0)+1
        exceedances += maximum >= observed-1e-12
        total_maximum += maximum
    probability = exceedances/repetitions
    return dict(repetitions=repetitions, seed=seed, exceedances=exceedances,
                tail_probability=probability,
                monte_carlo_standard_error=math.sqrt(probability*(1-probability)/repetitions),
                mean_maximum=total_maximum/repetitions,
                histogram=[dict(lower=k/2, upper=(k+1)/2, count=v)
                           for k, v in sorted(histogram.items())])


def analyze(base, repetitions=100000, seed=20261107):
    if base['status'] != 'complete' or len(base['rows']) != 150:
        raise ValueError('Complete 150-team-season base analysis required')
    rows, distributions = [], []
    for row in base['rows']:
        n, mu, observed = row['games'], row['fwar_expected'], row['wins']
        if n <= 0 or not 0 <= observed <= n or not 0 < mu < n:
            raise ValueError('Invalid season record or WAR-based mean')
        p = mu/n
        masses = binomial_pmf(n, p)
        distributions.append((mu, masses))
        history = [r for r in base['rows'] if r['season'] != row['season']]
        if len(history) != 120:
            raise ValueError('Historical comparison requires 120 other-season observations')
        count = sum(abs(r['fwar_error']) >= abs(row['fwar_error'])-1e-12 for r in history)
        rows.append(dict(row, assumed_win_probability=p, binomial_sd=math.sqrt(n*p*(1-p)),
                         binomial_95_interval=[quantile(masses,.025),quantile(masses,.975)],
                         exact_two_sided_p=two_sided(masses, observed),
                         historical_n=120, historical_at_least_as_large=count))
    for row, adjusted in zip(rows, holm_adjust([r['exact_two_sided_p'] for r in rows])):
        row['holm_p_150'] = adjusted
    maximum = max(abs(r['fwar_error']) for r in rows)
    exact_tail = 1-maximum_cdf_less(distributions, maximum)
    simulation = simulate_maxima(distributions, maximum, repetitions, seed)
    # Verify the Monte Carlo implementation against the exact independent-cohort result.
    tolerance = 6*math.sqrt(exact_tail*(1-exact_tail)/repetitions)+1/repetitions
    if abs(simulation['tail_probability']-exact_tail) > tolerance:
        raise ValueError('Simulated cohort tail does not match exact calculation')
    bins, previous = [], 0.
    upper_limit = math.ceil(max(max(mu, len(masses)-1-mu) for mu,masses in distributions)*2)/2
    for k in range(1, round(upper_limit*2)+2):
        upper = k/2
        cdf = maximum_cdf_less(distributions, upper)
        bins.append(dict(lower=upper-.5, upper=upper, probability=max(0.,cdf-previous)))
        previous = cdf
    if abs(sum(b['probability'] for b in bins)-1) > 1e-10:
        raise ValueError('Maximum distribution is not normalized')
    by_key = {(r['season'], r['team_id']):r for r in rows}
    cases = [by_key[r['season'],r['team_id']] for r in base['outliers']['fwar']]
    atlanta = by_key[2026,144]
    pythagorean = dict(
        decision='Retain a short run-based comparison after the probability analysis.',
        role='Expected wins from runs scored/allowed; does not specify the variance or a tail probability.',
        exponent=2,
        war_mae=mean(abs(r['fwar_error']) for r in rows),
        pythagorean_mae=mean(abs(r['pythagorean_error']) for r in rows),
        cases=[dict(season=r['season'],team_id=r['team_id'],team=r['team'],
                    war_based_wins=r['fwar_expected'],run_based_wins=r['pythagorean_wins'],actual_wins=r['wins'],
                    run_based_minus_war=r['pythagorean_wins']-r['fwar_expected'],
                    actual_minus_run_based=r['pythagorean_error']) for r in cases])
    for r in pythagorean['cases']:
        if abs(r['run_based_minus_war']+r['actual_minus_run_based']-(r['actual_wins']-r['war_based_wins'])) > 1e-10:
            raise ValueError('Pythagorean error decomposition does not reconcile')
    return dict(rows=rows,cases=cases,observed_maximum_gap=maximum,
                exact_cohort_tail_probability=exact_tail,simulation=simulation,
                maximum_distribution=bins,
                binomial_rms_sd=math.sqrt(mean(r['binomial_sd']**2 for r in rows)),
                observed_error_sd=pstdev(r['fwar_error'] for r in rows),
                expected_count_over_10=math.fsum(m for (mu,masses) in distributions for k,m in enumerate(masses) if abs(k-mu)>10),
                pythagorean_assessment=pythagorean,
                atlanta=atlanta,
                atlanta_distribution=binomial_pmf(atlanta['games'],atlanta['assumed_win_probability']),
                methods=dict(
                    unit='150 team-seasons, 2022-2026 regular season',
                    mean='48*games/162 + fWAR, without refitting to actual wins',
                    null='Each game is an independent Bernoulli trial with fixed team-season p=WAR-based wins/games.',
                    cohort='150 independent binomial team-season draws; not an MLB schedule simulation. Paired wins/losses, league totals, and schedule-dependent probabilities are not enforced.',
                    p_value='Probability-ordered exact two-sided binomial p-value; Holm adjustment across all 150 observations.',
                    maximum='P(max_i |W_i-mu_i| >= observed max), exact product CDF and seeded simulation.',
                    history='Count other-season absolute errors >= the target absolute error (120 records); descriptive ranks, not calibrated p-values.',
                    interpretation='Conditional model compatibility only. Same-season WAR is estimated from overlapping performance records; fitted mean uncertainty and observed dependence are not represented. Results do not establish that the discrepancies are caused by luck.'))


def render_figures(result):
    os.environ.setdefault('MPLCONFIGDIR',str(DATA/'.matplotlib'))
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.ticker import PercentFormatter
    plt.rcParams.update({'font.family':['Malgun Gothic','DejaVu Sans'], 'font.size':13,
                         'axes.unicode_minus':False, 'axes.spines.top':False, 'axes.spines.right':False,
                         'figure.facecolor':'#fbfaf7','axes.facecolor':'#fbfaf7','savefig.facecolor':'#fbfaf7'})
    teal, orange, muted = '#157b8c','#df744d','#768897'
    atlanta = result['atlanta']
    masses = result['atlanta_distribution']
    fig, ax = plt.subplots(figsize=(8,4.8),layout='constrained')
    support=list(range(len(masses)))
    ax.bar(support,masses,color=teal,width=.85,alpha=.75)
    ax.axvline(atlanta['fwar_expected'],color=muted,ls='--',lw=1.5,label=f"WAR 기반 {atlanta['fwar_expected']:.2f}승")
    ax.axvline(atlanta['wins'],color=orange,lw=2,label=f"실제 {atlanta['wins']}승")
    ax.set(xlim=(55,108),xlabel='시즌 승수',ylabel='확률',title='2026 애틀랜타 · 이항모형의 승수 분포')
    ax.yaxis.set_major_formatter(PercentFormatter(1))
    ax.legend(frameon=False,fontsize=11)
    fig.savefig(ASSETS/'binomial-atlanta.png',dpi=180);plt.close(fig)
    bins=result['maximum_distribution']
    fig, ax = plt.subplots(figsize=(8,4.8),layout='constrained')
    ax.bar([(b['lower']+b['upper'])/2 for b in bins],[b['probability'] for b in bins],
           width=.48,color=teal,alpha=.75)
    ax.axvline(result['observed_maximum_gap'],color=orange,lw=2,
               label=f"관측 최대 {result['observed_maximum_gap']:.2f}승")
    visible=next(b['upper'] for i,b in enumerate(bins) if sum(x['probability'] for x in bins[:i+1])>=.9999)
    ax.set(xlim=(7,visible+1),xlabel='150개 팀·시즌 중 최대 절대차이 (승)',ylabel='확률',
           title='독립 이항모형 · 최대 승수 차이의 분포')
    ax.yaxis.set_major_formatter(PercentFormatter(1))
    ax.legend(frameon=False,fontsize=11)
    fig.savefig(ASSETS/'maximum-gap.png',dpi=180);plt.close(fig)


def report(result):
    lines=['# WAR 승수 차이의 확률분포 분석','',
           '기준은 2022~2026년 MLB 150개 팀·시즌의 기존 fWAR 결과다. 원본을 새로 수집하거나 기준 승수를 재적합하지 않았다.','',
           '## 조건부 이항모형','',
           '- 팀별 p = WAR 기반 승수/경기 수. 각 경기 및 팀·시즌을 독립으로 놓는다.',
           '- 실제 대진이나 한 경기의 승패 쌍을 재현하는 리그 모형은 아니다. 리그 총승수 제약도 적용하지 않았다.',
           '- WAR는 같은 시즌 기록에서 계산된 값이다. 모형은 p를 고정하고 그 추정 불확실성과 실제 종속성을 반영하지 않는다.',
           '- 양측 p값은 관측 승수보다 PMF가 작거나 같은 승수들의 확률 합이다. 150개 전체에 Holm 보정을 적용한다.',
           '- 아래 확률은 이 모형 아래의 조건부 값이며, 차이가 운에서 비롯됐다는 확률이 아니다.','',
           '| 시즌 | 팀 | WAR 승수 | 실제 승수 | 양측 p | Holm p (150개) | 다른 4시즌에서 같거나 큰 차이 |',
           '| --- | --- | ---: | ---: | ---: | ---: | ---: |']
    for r in result['cases']:
        lines.append(f"| {r['season']} | {r['team']} | {r['fwar_expected']:.2f} | {r['wins']} | {r['exact_two_sided_p']:.6f} | {r['holm_p_150']:.6f} | {r['historical_at_least_as_large']}/120 |")
    s=result['simulation']
    lines += ['', '## 150개 중 최대 차이','',
              f"- 관측 최대 절대차이: {result['observed_maximum_gap']:.8f}승.",
              f"- 이 값 이상이 적어도 하나 나올 정확한 독립모형 확률: {result['exact_cohort_tail_probability']:.8%}.",
              f"- {s['repetitions']:,}회 모의실험: {s['exceedances']:,}회 ({s['tail_probability']:.5%}); seed={s['seed']}.",
              f"- Monte Carlo 표준오차: {s['monte_carlo_standard_error']:.8f}.",
              '- 정확한 최대차이 CDF는 각 팀의 P(|W−mu|<t)를 곱한다. 시뮬레이션이 이 값과 일치하는지 검증했다.','',
              '## 다른 시즌의 관측 오차','',
              '- 대상 팀이 속한 시즌 전체를 제외한 120개 기록과 절대오차를 비교한다. 빈도와 순위를 기술하며 이를 이항검정 p값과 동일하게 해석하지 않는다.',
              f"- 독립 이항모형의 개별 팀 표준편차 RMS: {result['binomial_rms_sd']:.5f}승.",
              f"- 실제 150개 WAR 오차의 기술적 표준편차(분모 N): {result['observed_error_sd']:.5f}승.",
              '- 실제 WAR 오차의 분포가 이항모형보다 좁다. 이항모형에서 큰 최대차이가 흔하다는 결과를 현실의 운에 대한 판정으로 확대하지 않는다.','',
              '## 피타고리안 유지 판단','',
              '- 득실점 기반 기대승수는 평균의 기준을 바꾸는 비교다. 분산이나 꼬리확률을 주지 않으므로 이번 확률 검정의 기준으로 사용하지 않는다.',
              '- 본문에서는 WAR→득실점 기대승수와 득실점 기대승수→실제 승수 사이의 차이를 구분하는 짧은 보조 비교로 유지한다.',
              '- 기존 지수 2 계산을 유지한다. 다른 제공처의 공식 기대승수나 인과효과로 명명하지 않는다.','',
              '## 재현','',
              '```powershell','python -X utf8 scripts/mlb_war_wins_probability.py',
              'python -m pip install -r scripts/requirements-mlb-war-wins.txt',
              'python -X utf8 scripts/mlb_war_wins_probability.py --figures','```','',
              '시드·반복 횟수·입력/코드 해시는 `assets/mlb-war-wins/probability.json`에 기록한다. 분석은 표준 라이브러리만 사용하고 PNG 생성에만 matplotlib가 필요하다.','',
              '## 출처','',
              '- [SciPy 이항검정](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.binomtest.html)',
              '- [MLB 피타고리안 승률 설명](https://www.mlb.com/glossary/advanced-stats/pythagorean-winning-percentage)',
              '- [FanGraphs WAR 해석](https://library.fangraphs.com/war/limitations-war/)','']
    return '\n'.join(lines)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repetitions',type=int,default=100000)
    parser.add_argument('--seed',type=int,default=20261107)
    parser.add_argument('--figures',action='store_true')
    args=parser.parse_args()
    base_path=ASSETS/'results.json';base=json.loads(base_path.read_text(encoding='utf-8'))
    for name, sha in base['source_hashes'].items():
        _,meta=load_snapshot(DATA,name)
        if meta['sha256']!=sha:raise ValueError('Base analysis snapshot hash mismatch')
    result=analyze(base,args.repetitions,args.seed)
    result.update(base_result_sha256=digest(base_path.read_bytes()),code_sha256=digest(Path(__file__).read_bytes()))
    save_json(DATA/'analysis/probability.json',result)
    save_json(ASSETS/'probability.json',result)
    (ROOT/'docs/mlb-war-wins-probability.md').write_text(report(result),encoding='utf-8')
    if args.figures:render_figures(result)
    print(json.dumps({k:result[k] for k in ('observed_maximum_gap','exact_cohort_tail_probability','binomial_rms_sd','observed_error_sd')}))
    print(json.dumps({k:result['simulation'][k] for k in
                      ('repetitions','seed','exceedances','tail_probability','mean_maximum')}))


if __name__=='__main__':main()

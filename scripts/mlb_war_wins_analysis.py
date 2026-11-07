"""Analyze audited WAR snapshots; export a report and chart payload, never impute WAR."""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from statistics import mean

from mlb_war_wins_collect import DATA, ROOT, YEARS, audit, audit_cases, digest, load_snapshot, save_json


def ranks(values):
    ordered = sorted(range(len(values)), key=lambda i: values[i])
    result = [0.] * len(values)
    start = 0
    while start < len(values):
        end = start + 1
        while end < len(values) and values[ordered[end]] == values[ordered[start]]:
            end += 1
        for i in ordered[start:end]:
            result[i] = (start + end + 1) / 2
        start = end
    return result


def correlation(x, y):
    if len(x) < 2:
        return None
    xm, ym = mean(x), mean(y)
    xx = sum((v-xm)**2 for v in x)
    yy = sum((v-ym)**2 for v in y)
    if xx == 0 or yy == 0:
        return None
    return max(-1., min(1., sum((a-xm)*(b-ym) for a,b in zip(x,y))/math.sqrt(xx*yy)))


def regression(x, y):
    r = correlation(x, y)
    xm, ym = mean(x), mean(y)
    xx = sum((v-xm)**2 for v in x)
    if xx == 0:
        return dict(pearson=r, spearman=correlation(ranks(x), ranks(y)),
                    intercept=None, slope=None, r_squared=None)
    slope = sum((a-xm)*(b-ym) for a,b in zip(x,y))/xx
    return dict(pearson=r, spearman=correlation(ranks(x), ranks(y)),
                intercept=ym-slope*xm, slope=slope, r_squared=r*r if r is not None else None)


def enrich(row):
    row = dict(row)
    g, w = row['games'], row['wins']
    rs, ra = row['runs_scored'], row['runs_allowed']
    row['wins_162'] = w*162/g
    row['pythagorean_wins'] = g*rs**2/(rs**2+ra**2)
    row['pythagorean_error'] = w-row['pythagorean_wins']
    for provider in ('fwar',):
        war = row[provider]
        row[f'{provider}_162'] = war*162/g if war is not None else None
        row[f'{provider}_expected'] = 48*g/162+war if war is not None else None
        row[f'{provider}_error'] = w-row[f'{provider}_expected'] if war is not None else None
    return row


def summarize(rows, provider='fwar'):
    if not rows or any(r[provider] is None for r in rows):
        return None
    x, y = [r[provider] for r in rows], [r['wins'] for r in rows]
    errors = [r[f'{provider}_error'] for r in rows]
    return dict(n=len(rows), raw=regression(x,y),
                normalized=regression([r[f'{provider}_162'] for r in rows], [r['wins_162'] for r in rows]),
                bias=mean(errors), mae=mean(abs(e) for e in errors),
                rmse=math.sqrt(mean(e*e for e in errors)), within_5=mean(abs(e)<=5 for e in errors))


def analyze(rows):
    enriched = [enrich(row) for row in rows]
    summaries, outliers = {}, {}
    for provider in ('fwar',):
        ready=len(enriched)==150 and all(r[provider] is not None for r in enriched)
        summaries[provider] = {'all': summarize(enriched, provider) if ready else None}
        for year in YEARS:
            summaries[provider][str(year)] = summarize([r for r in enriched if r['season']==year], provider) if ready else None
        outliers[provider] = sorted((r for r in enriched if r[provider] is not None),
                                   key=lambda r: (-abs(r[f'{provider}_error']), r['season'], r['team_id']))[:5] if ready else []
    return dict(rows=enriched, summaries=summaries, outliers=outliers)


def fmt(value, digits=3):
    return '미확보' if value is None else f'{value:.{digits}f}'


def report(result):
    complete = result['status'] == 'complete'
    lines = ['# MLB 2022~2026 팀 WAR와 실제 승수', '',
             '**상태: '+('완료' if complete else '미완료 — fWAR 자료 또는 사례 검증 미확보')+'**', '',
             f"공식 성적 {len(result['rows'])}/150행. fWAR {result['coverage']['fwar']}/150행.", '',
             '[인터랙티브 그래프](../scripts/mlb-war-wins-dashboard.html)', '',
             '## 현재 확인된 결과', '']
    for provider in ('fwar',):
        label = 'fWAR'
        overall = result['summaries'][provider]['all']
        if overall is None:
            lines += [f'- **{label}: 계산 보류.** 150개 팀–시즌의 원본이 모두 확보되기 전에는 부분 표본이나 다른 지표로 대체하지 않는다.']
        else:
            lines += [f"- **{label}:** Pearson r={fmt(overall['raw']['pearson'])}, R²={fmt(overall['raw']['r_squared'])}. 공통 근사 기준의 MAE **{fmt(overall['mae'],2)}승**, RMSE {fmt(overall['rmse'],2)}승, ±5승 이내 {overall['within_5']:.1%}."]
    lines += ['', '## 분석 방법', '',
              '- 모집단: 2022~2026 MLB 정규시즌, 각 시즌 30팀. 동일 팀의 연도별 기록이며 독립적인 150회 실험으로 해석하지 않는다.',
              '- 팀 WAR는 FanGraphs의 타격·주루·수비 WAR와 투수 WAR 합계다. 음수 WAR와 이적·방출 선수의 해당 팀 기록을 포함한다.',
              '- 산점도와 회귀는 실제 승수와 팀 WAR를 사용한다. Pearson·Spearman, 절편·기울기·R²를 전체와 시즌별로 계산한다.',
              '- 경기 수 민감도는 승수와 WAR에 각각 162/경기 수를 곱해 확인한다.',
              '- 공통 근사 추정 승수 = 48×경기 수/162 + WAR. 제공처의 정밀한 공식 기대승수가 아니며 실제 승수에 맞춰 보정하지 않는다.',
              '- 오차 = 실제 승수−추정 승수. 양수는 추정치보다 많이 이겼다는 뜻이다. MAE·RMSE는 회귀 잔차가 아닌 이 공통 근사 기준의 오차다.',
              '- 피타고리안 기대승수 = 경기 수×득점²/(득점²+실점²). 지수 2를 고정한 보조 기준이며 공식 예상승수와 구분한다.',
              '- 같은 시즌을 설명하는 분석이다. 높은 상관관계는 개별 선수 WAR의 정확성·인과효과·미래 예측력을 입증하지 않는다.',
              '- WAR 원본의 수집 시점과 공식 성적의 갱신 시점은 원본 메타데이터에 보관한다. 현재 제공처의 소급 개정값을 분석하며 당시 발표값을 복원하지 않는다.', '']
    for provider in ('fwar',):
        label = provider[0]+'WAR'
        if result['summaries'][provider]['all'] is None:
            continue
        lines += [f'## {label} 연도별 결과', '',
                  '| 시즌 | N | Pearson | Spearman | 절편 | 기울기 | R² | 평균 차이 | MAE | RMSE | ±5승 |',
                  '| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |']
        for key, s in result['summaries'][provider].items():
            reg=s['raw']
            vals=[fmt(reg[k]) for k in ('pearson','spearman','intercept','slope','r_squared')]
            lines.append(f"| {'전체' if key=='all' else key} | {s['n']} | "+' | '.join(vals)+f" | {s['bias']:.2f} | {s['mae']:.2f} | {s['rmse']:.2f} | {s['within_5']:.1%} |")
        lines += ['', '### 162경기 환산 민감도', '',
                  '| 시즌 | Pearson | Spearman | 절편 | 기울기 | R² |',
                  '| --- | ---: | ---: | ---: | ---: | ---: |']
        for key, s in result['summaries'][provider].items():
            reg=s['normalized']
            lines.append(f"| {'전체' if key=='all' else key} | "+' | '.join(fmt(reg[k]) for k in ('pearson','spearman','intercept','slope','r_squared'))+' |')
        lines += ['', '### 절대오차가 큰 5개 팀–시즌', '',
                  '| 시즌 | 팀 | 경기 | 실제 승수 | WAR | 근사 승수 | 차이 | 피타고리안 승수 | 실제−피타고리안 |',
                  '| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |']
        for r in result['outliers'][provider]:
            lines.append(f"| {r['season']} | {r['team']} | {r['games']} | {r['wins']} | {r[provider]:.2f} | {r[provider+'_expected']:.2f} | {r[provider+'_error']:+.2f} | {r['pythagorean_wins']:.2f} | {r['pythagorean_error']:+.2f} |")
        lines += ['', 'WAR 기반 승수와 피타고리안 승수의 차이는 성적을 승수로 환산하는 방식의 차이도 포함한다. 실제 승수와 피타고리안 승수의 차이는 득실점 총합만으로 설명되지 않는 부분이며, 감독 능력이나 운의 직접 측정치가 아니다.', '']
    lines += ['## 수집·사례 검증 상태', '']
    checks = result['case_checks']
    lines += [f"- fWAR 사례: {checks.get('fwar','pending')}."]
    for e in checks.get('evidence',[]):
        if e['check'] == 'player_team_sum':
            lines += [f"- fWAR 2023 {e['team']} {e['kind']}: {e['player_count']}명(음수 WAR {e['negative_count']}명) 합계와 팀 WAR 차이 {e['difference']:.10f}; 허용 오차 {e['tolerance']}."]
        elif e['check'] == 'traded_player':
            lines += [f"- {e['season']} {e['player']}: "+', '.join(f"{s['team']} {s['war']:.4f}" for s in e['stints'])+f"; 시즌 합계 {e['season_total']:.4f}, 팀별 합계와 차이 {e['difference']:.6f}. 팀별 기록을 사용하며 시즌 합계는 재합산하지 않는다."]
        elif e['check'] == 'two_way_player':
            lines += [f"- {e['season']} {e['player']}: 타격 {e['components']['bat']:.4f} + 투구 {e['components']['pit']:.4f} = {e['combined']:.4f}. 각 기여가 팀별 명단에서 한 번씩 나타나고 개별 조회값과 일치함을 확인했다."]
    lines += ['', '자료 누락·검증 문제:', '']
    for issue in result['issues']:
        lines += [f"- `{issue['source']}`: {issue.get('collection_error',issue['error'])}"]
    if not result['issues']:
        lines += ['- 팀 기록의 누락·정합성 문제 없음. 사례 검증 상태는 별도로 확인한다.']
    lines += ['', '## 재현', '',
              'Python 3.10 이상, 외부 패키지 없이 실행한다. 네트워크 접근은 collect 단계에만 필요하다. 기존 원본은 덮어쓰지 않고 URL·SHA-256을 검증해 재사용한다.', '',
              '```powershell', 'python -X utf8 scripts/mlb_war_wins_collect.py collect',
              'python -X utf8 scripts/mlb_war_wins_collect.py collect-cases',
              'python -X utf8 scripts/mlb_war_wins_analysis.py',
              'python -X utf8 scripts/mlb_war_wins_render.py',
              'python -X utf8 -m unittest discover -s tests -p test_mlb_war_wins.py',
              'python -X utf8 scripts/check_mlb_war_wins.py', '```', '',
              '오프라인 재실행은 `audit-cases`, `audit`, 분석, 렌더 순서다. 완료 기준은 150개 팀·시즌의 MLB 공식 성적과 fWAR, 이적·투타 겸업 사례 검증 통과다.', '',
              '- 원본·정제 CSV·manifest·audit·사례 증거: `data/mlb/war-wins-2022-2026/` (Git 제외).',
              '- 공유 결과: `assets/mlb-war-wins/results.json`. 입력 원본과 실행 코드의 SHA-256을 포함한다.',
              '- 모든 수치는 원본 정밀도로 계산하고 표시 단계에서만 반올림한다.', '',
              '- `python -X utf8 scripts/mlb_war_wins_analysis.py --require-complete`는 자료 또는 사례 검증이 미완료이면 산출물에 상태를 기록한 뒤 종료 코드 2를 반환한다.',
              '',
              '## 공식 출처', '',
              '- [FanGraphs 팀 페이지와 팀 소속 기간 기록](https://library.fangraphs.com/features/team-pages/)',
              '- [FanGraphs WAR 계산](https://library.fangraphs.com/war/war-position-players/)',
              '- [FanGraphs 대체선수 기준과 약 48승 설명](https://library.fangraphs.com/getting-started/)',
              '- [MLB 2026 공식 정규시즌 순위 API](https://statsapi.mlb.com/api/v1/standings?leagueId=103,104&season=2026&standingsTypes=regularSeason)', '']
    return '\n'.join(lines)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data', type=Path, default=DATA)
    parser.add_argument('--require-complete', action='store_true')
    args=parser.parse_args()
    audit_cases(args.data)
    audited=audit(args.data)
    rows=json.loads((args.data/'processed/team-seasons.json').read_text(encoding='utf-8'))
    if len(rows)!=150 or len({(r['season'],r['team_id']) for r in rows})!=150:
        raise ValueError('Analysis requires all 150 official team-seasons')
    # Only missing sources are allowed in a provisional analysis, never data errors.
    bad=[i for i in audited['issues'] if not i['error'].startswith('FileNotFoundError:')]
    if bad:
        raise ValueError(f'Unresolved data validation errors: {bad}')
    if audited['case_checks'].get('fwar') != 'pass':
        raise ValueError('Run collect-cases / audit-cases before analysis')
    for source in audited['case_checks'].get('sources',[]):
        _, meta=load_snapshot(args.data,source['name'])
        if meta['sha256']!=source['sha256']:
            raise ValueError('Case evidence no longer matches snapshot')
    result=analyze(rows)
    result.update(status=audited['status'], seasons=list(YEARS), coverage=audited['available'],
                  issues=audited['issues'], case_checks=audited['case_checks'],
                  source_hashes={s['name']:s['sha256'] for s in audited['sources']},
                  code_hashes={p.name:digest(p.read_bytes()) for p in
                               (Path(__file__),ROOT/'scripts/mlb_war_wins_collect.py',
                                ROOT/'scripts/mlb_war_wins_render.py',ROOT/'scripts/mlb_war_wins_dashboard.html')})
    save_json(args.data/'analysis/results.json',result)
    save_json(ROOT/'assets/mlb-war-wins/results.json',result)
    (ROOT/'docs/mlb-war-wins-analysis.md').write_text(report(result),encoding='utf-8')
    print('Report and results written:',result['status'])
    if args.require_complete and result['status']!='complete':
        parser.exit(2,'Required sources or case validation are incomplete.\n')


if __name__=='__main__':
    main()

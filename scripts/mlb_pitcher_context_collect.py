"""Official 2026 MLB plate appearances and pitcher-entry context.

collect [--limit N] is online/resumable; prepare is offline. Keeps projected raw
MLB playByPlay responses, source URLs, hashes, and a row-level context inventory.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import csv
import gzip
import hashlib
import json
from pathlib import Path
import time
import urllib.parse
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'data/mlb/clutch-2026'
DATA = BASE / 'pitcher-context'
FIELDS = ('allPlays,result,event,eventType,rbi,isOut,about,atBatIndex,halfInning,inning,isComplete,'
          'matchup,batter,pitcher,id,batSide,code,pitchHand,postOnFirst,postOnSecond,postOnThird,'
          'runners,movement,originBase,start,end,outBase,outNumber,details,runner,responsiblePitcher,'
          'isScoringEvent,playIndex,playEvents,index,type,player,count,outs,balls,strikes,isPitch,'
          'pitchNumber,homeScore,awayScore,base')
HITS = {'single','double','triple','home_run'}
NO_AB = {'walk','intent_walk','hit_by_pitch','sac_fly','sac_fly_double_play',
         'sac_bunt','sac_bunt_double_play','catcher_interf'}
SF = {'sac_fly','sac_fly_double_play'}


def dump(path, obj):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(obj,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')


def schedule():
    d = json.loads((BASE/'raw/2026-schedule.json').read_text(encoding='utf-8'))
    return {g['gamePk']:{'date':day['date'],'home':g['teams']['home']['team']['id'],
                       'away':g['teams']['away']['team']['id']}
            for day in d['dates'] for g in day['games']
            if g['gameType']=='R' and g['status']['abstractGameState']=='Final'
            and g['status']['detailedState'] not in ('Cancelled','Postponed')}


def request(url):
    for attempt in range(3):
        try:
            q=urllib.request.Request(url,headers={'User-Agent':'MLB-pitcher-context-research/1.0',
                                                 'Accept-Encoding':'gzip'})
            with urllib.request.urlopen(q,timeout=45) as response:
                raw=response.read()
                if response.headers.get('Content-Encoding')=='gzip':raw=gzip.decompress(raw)
            json.loads(raw)
            return raw
        except Exception:
            if attempt==2:raise
            time.sleep(1+attempt)
    raise RuntimeError('unreachable')


def fetch(game, info):
    target=DATA/f'raw/{game}.json.gz'
    meta=target.with_suffix('.meta.json')
    url=f'https://statsapi.mlb.com/api/v1/game/{game}/playByPlay?'+urllib.parse.urlencode({'fields':FIELDS})
    if target.exists():
        record=json.loads(meta.read_text(encoding='utf-8'))
        assert record['url']==url
        assert hashlib.sha256(gzip.decompress(target.read_bytes())).hexdigest()==record['sha256']
        return record
    raw=request(url);d=json.loads(raw)
    assert isinstance(d.get('allPlays'),list) and len(d['allPlays'])>=20,(game,'invalid response')
    target.parent.mkdir(parents=True,exist_ok=True)
    target.write_bytes(gzip.compress(raw,mtime=0))
    record={'game_pk':game,**info,'url':url,'bytes_json':len(raw),
            'sha256':hashlib.sha256(raw).hexdigest(),
            'retrieved_at_utc':datetime.now(timezone.utc).isoformat(),'plays':len(d['allPlays'])}
    dump(meta,record)
    return record


def collect(limit=None):
    games=schedule();ids=sorted(games,key=lambda k:(games[k]['date'],k))
    if limit:ids=ids[:limit]
    et=DATA/'event-types.json'
    if not et.exists():
        raw=request('https://statsapi.mlb.com/api/v1/eventTypes')
        et.parent.mkdir(parents=True,exist_ok=True);et.write_bytes(raw)
    records=[];failed=[]
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures={pool.submit(fetch,k,games[k]):k for k in ids}
        for i,future in enumerate(as_completed(futures),1):
            try:records.append(future.result())
            except Exception as exc:failed.append({'game_pk':futures[future],'error':str(exc)})
            if i%100==0 or i==len(ids):print(f'{i}/{len(ids)} games; failed={len(failed)}',flush=True)
    dump(DATA/'manifest.json',{'season':2026,'game_type':'R','expected_games':len(games),
        'requested_games':len(ids),'complete':len(ids)==len(games) and not failed,
        'schedule_sha256':hashlib.sha256((BASE/'raw/2026-schedule.json').read_bytes()).hexdigest(),
        'event_types_sha256':hashlib.sha256(et.read_bytes()).hexdigest(),
        'sources':sorted(records,key=lambda r:r['game_pk']),'failed':failed})
    if failed:raise RuntimeError(f'{len(failed)} game requests failed; rerun collect to resume')


def validate_special_at_bats():
    """Resolve unusual no-AB events using official game logs and fielding credits."""
    season=json.loads((BASE/'raw/2026-players-season.json').read_text(encoding='utf-8'))['stats'][0]['splits']
    with gzip.open(DATA/'plate-appearances.csv.gz','rt',encoding='utf-8') as f:rows=list(csv.DictReader(f))
    evidence=[];exclusions=[]
    folder=DATA/'validation';folder.mkdir(exist_ok=True)
    def fetch_validation(name,url):
        path=folder/name
        if not path.exists():path.write_bytes(request(url))
        raw=path.read_bytes()
        evidence.append({'path':str(path.relative_to(DATA)),'url':url,'sha256':hashlib.sha256(raw).hexdigest(),
                         'file_mtime_utc':datetime.fromtimestamp(path.stat().st_mtime,timezone.utc).isoformat()})
        return json.loads(raw)
    for s in season:
        st=s['stat'];pid=s['player']['id']
        gap=st['plateAppearances']-sum(st[k] for k in ('atBats','baseOnBalls','hitByPitch','sacFlies','sacBunts','catchersInterference'))
        if not gap:continue
        logs=fetch_validation(f'{pid}-game-log.json',f'https://statsapi.mlb.com/api/v1/people/{pid}/stats?stats=gameLog&group=hitting&season=2026&gameType=R')
        actual=Counter()
        for r in rows:
            if int(r['batter'])==pid:actual[int(r['game_pk'])]+=r['event'] not in NO_AB
        found=0
        for g in logs['stats'][0]['splits']:
            game=g['game']['gamePk'];delta=actual[game]-g['stat']['atBats']
            if not delta:continue
            d=fetch_validation(f'{game}-full.json',f'https://statsapi.mlb.com/api/v1/game/{game}/playByPlay')
            for p in d['allPlays']:
                if p['matchup']['batter']['id']!=pid:continue
                credits=[c.get('credit') for r in p.get('runners',[]) for c in r.get('credits',[])]
                if 'f_defensive_shift_violation_error' in credits:
                    exclusions.append({'game_pk':game,'at_bat_index':p['about']['atBatIndex'],
                        'reason':'Defensive shift violation: official game log charges PA but no AB.',
                        'description':p['result'].get('description'),'batter':pid})
                    found+=1
        assert found==gap,(pid,gap,found)
    dump(DATA/'special-at-bats.json',{'exclusions':exclusions,'evidence':evidence})
    print(json.dumps(exclusions,ensure_ascii=False,indent=2))


def post_bases(play):
    return {base:play['matchup'][key]['id'] for base,key in [('1B','postOnFirst'),('2B','postOnSecond'),('3B','postOnThird')]
            if key in play['matchup']}


def collapse_movements(movements):
    """One runner can advance through several bases on the same play index."""
    grouped={}
    for r in movements:
        pid=r['details']['runner']['id']
        if pid not in grouped:
            grouped[pid]={'movement':dict(r['movement']),'details':r['details']}
        else:
            start=grouped[pid]['movement']['start']
            grouped[pid]['movement']=dict(r['movement'],start=start)
    return list(grouped.values())


def move(state, movements):
    result=state.copy()
    for r in movements:
        m=r['movement'];pid=r['details']['runner']['id']
        for base in list(result):
            if result[base]==pid or base==m.get('start'):result.pop(base,None)
    for r in movements:
        m=r['movement'];end=m.get('end')
        if not m['isOut'] and end in ('1B','2B','3B'):
            result[end]=r['details']['runner']['id']
    return result


def unmove(state, movements):
    result=state.copy()
    for r in movements:
        m=r['movement'];pid=r['details']['runner']['id']
        for base in list(result):
            if result[base]==pid or base==m.get('end'):result.pop(base,None)
    for r in movements:
        m=r['movement'];start=m.get('start')
        if start in ('1B','2B','3B'):result[start]=r['details']['runner']['id']
    return result


def parse_game(game, info, data, event_types, ab_exclusions=()):
    rows=[];issues=[];event_counts=Counter();seen_by_side=defaultdict(set);prior_pa=Counter();starters={}
    history=defaultdict(list)
    state={};outs=0;half=None;scores={'top':0,'bottom':0}
    plays=sorted(data['allPlays'],key=lambda p:p['about']['atBatIndex'])
    assert len({p['about']['atBatIndex'] for p in plays})==len(plays)
    for p in plays:
        issue_start=len(issues)
        a=p['about'];side=a['halfInning'];key=(a['inning'],side)
        if key!=half:state={};outs=0;half=key
        pid=p['matchup']['pitcher']['id'];bid=p['matchup']['batter']['id'];event=p['result'].get('eventType')
        starters.setdefault(side,pid)
        assert event in event_types,(game,event)
        event_counts[event]+=1
        first=pid not in seen_by_side[side];is_reliever=bool(seen_by_side[side]) if first else None
        seen_by_side[side].add(pid)
        fresh=bool(first and is_reliever)
        starter_first=bool(first and not is_reliever)
        events=sorted(p.get('playEvents',[]),key=lambda e:e['index'])
        pitches=[e for e in events if e.get('isPitch')]
        substitutions=[e for e in events if e.get('details',{}).get('eventType')=='pitching_substitution']
        midchange=any(e.get('count',{}).get('balls',0)>0 or e.get('count',{}).get('strikes',0)>0 or
                      (pitches and e['index']>pitches[0]['index']) for e in substitutions)
        midbatter=any(e.get('details',{}).get('eventType')=='offensive_substitution'
                      and e.get('player',{}).get('id')==bid
                      and (e.get('count',{}).get('balls',0)>0 or e.get('count',{}).get('strikes',0)>0
                           or (pitches and e['index']>pitches[0]['index'])) for e in events)
        movements=defaultdict(list)
        for r in p.get('runners',[]):movements[r['details'].get('playIndex',-1)].append(r)
        movements={i:collapse_movements(rs) for i,rs in movements.items()}
        ending=[i for i,rs in movements.items() if any(r['details'].get('eventType')==event and
                   r['details']['runner']['id']==bid for r in rs)]
        terminal=max(ending) if ending else max([e['index'] for e in pitches] or [e['index'] for e in events] or [-1])
        before_terminal=None;terminal_outs=None
        for e in events:
            i=e['index'];kind=e.get('details',{}).get('eventType')
            if kind=='runner_placed':
                base=e.get('base','2B');base=str(base)+'B' if str(base) in ('1','2','3') else base
                state[base]=e['player']['id']
            if i==terminal:before_terminal=state.copy();terminal_outs=outs
            if movements.get(i):
                state=move(state,movements[i])
                outs+=sum(r['movement']['isOut'] is True for r in movements[i])
        if before_terminal is None:before_terminal=state.copy();terminal_outs=outs
        after=post_bases(p)
        if set(state)!=set(after) and p['count']['outs']<3:
            issues.append({'game_pk':game,'at_bat_index':a['atBatIndex'],'kind':'post_base_mismatch',
                           'calculated':state,'official':after,'event':event})
        # Independent backward reconstruction checks the RISP status before outcome.
        back=after.copy()
        for i in sorted((i for i in movements if i>=terminal),reverse=True):back=unmove(back,movements[i])
        back_risp=bool({'2B','3B'}&set(back));forward_risp=bool({'2B','3B'}&set(before_terminal))
        if back_risp!=forward_risp and p['count']['outs']<3:
            issues.append({'game_pk':game,'at_bat_index':a['atBatIndex'],'kind':'pre_risp_mismatch',
                           'forward':before_terminal,'backward':back,'event':event})
        if event_types[event]['plateAppearance'] and a.get('isComplete'):
            is_ab=event not in NO_AB and (game,a['atBatIndex']) not in ab_exclusions
            rows.append({'game_pk':game,'date':info['date'],'at_bat_index':a['atBatIndex'],
                'batter':bid,'pitcher':pid,'inning':a['inning'],'half':side,
                'outs':terminal_outs,'risp':int(forward_risp),'on_1b':int('1B' in before_terminal),
                'on_2b':int('2B' in before_terminal),'on_3b':int('3B' in before_terminal),
                'event':event,'hit':int(event in HITS),'ab':int(is_ab),'sf':int(event in SF),
                'fresh_reliever':int(fresh),'starter_first_pa':int(starter_first),'mid_pa_change':int(midchange),
                'mid_pa_batter_change':int(midbatter),
                'reliever':int(pid!=starters[side]),
                'context_valid':int(len(issues)==issue_start),
                'prior_pa_pitcher_game':prior_pa[(side,pid)],
                'recent_pa_n':len(history[(side,pid)][-5:]),
                'recent5_reached':sum(history[(side,pid)][-5:]),
                'bat_side':p['matchup'].get('batSide',{}).get('code',''),
                'pitch_hand':p['matchup'].get('pitchHand',{}).get('code',''),
                'score_diff':scores[side]-scores['bottom' if side=='top' else 'top'],
                'home_team':info['home'],'away_team':info['away']})
            prior_pa[(side,pid)]+=1
            if event!='intent_walk':history[(side,pid)].append(int(event in HITS|{'walk','hit_by_pitch'}))
        state=after;outs=p['count']['outs']
        scores={'top':p['result'].get('awayScore',scores['top']),
                'bottom':p['result'].get('homeScore',scores['bottom'])}
    return rows,issues,event_counts


def prepare():
    manifest=json.loads((DATA/'manifest.json').read_text(encoding='utf-8'))
    et={x['code']:x for x in json.loads((DATA/'event-types.json').read_text(encoding='utf-8'))}
    games=schedule();rows=[];issues=[];events=Counter()
    special=DATA/'special-at-bats.json'
    ab_exclusions={(e['game_pk'],e['at_bat_index']) for e in json.loads(special.read_text(encoding='utf-8'))['exclusions']} if special.exists() else set()
    for i,record in enumerate(manifest['sources'],1):
        game=record['game_pk'];path=DATA/f'raw/{game}.json.gz';raw=gzip.decompress(path.read_bytes())
        assert hashlib.sha256(raw).hexdigest()==record['sha256']
        rs,es,ec=parse_game(game,games[game],json.loads(raw),et,ab_exclusions)
        rows.extend(rs);issues.extend(es);events.update(ec)
        if i%500==0:print('parsed',i,flush=True)
    assert len({(r['game_pk'],r['at_bat_index']) for r in rows})==len(rows)
    counts={'pa':len(rows),'ab':sum(r['ab'] for r in rows),'h':sum(r['hit'] for r in rows),
        'sf':sum(r['sf'] for r in rows),'risp_ab':sum(r['ab']*r['risp'] for r in rows),
        'risp_h':sum(r['hit']*r['risp'] for r in rows),'risp_sf':sum(r['sf']*r['risp'] for r in rows)}
    audit={'complete_schedule':manifest['complete'],'games':len(manifest['sources']),
           'counts':counts,'event_counts':dict(events),'context_issue_counts':dict(Counter(e['kind'] for e in issues)),
           'issue_examples':issues[:100],
           'missing_core_fields':sum(any(r[k] in ('',None) for k in ('batter','pitcher','outs','bat_side','pitch_hand')) for r in rows)}
    if manifest['complete']:
        official=json.loads((BASE/'audit.json').read_text(encoding='utf-8'))['years']['2026']['totals']
        expected={'pa':official['season']['plateAppearances'],'ab':official['season']['atBats'],
                  'h':official['season']['hits'],'sf':official['season']['sacFlies'],
                  'risp_ab':official['risp']['atBats'],'risp_h':official['risp']['hits'],'risp_sf':official['risp']['sacFlies']}
        audit['official_expected']=expected
        audit['official_differences']={k:counts[k]-v for k,v in expected.items()}
    DATA.mkdir(parents=True,exist_ok=True)
    with gzip.open(DATA/'plate-appearances.csv.gz','wt',encoding='utf-8',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    dump(DATA/'audit.json',audit)
    print(json.dumps(audit,ensure_ascii=False,indent=2)[:10000])


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode',choices=('collect','prepare','validate'))
    parser.add_argument('--limit',type=int)
    args=parser.parse_args()
    if args.mode=='collect':collect(args.limit)
    elif args.mode=='validate':validate_special_at_bats()
    else:prepare()

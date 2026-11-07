"""Exercise the real-data fWAR chart in headless Edge/Chromium."""
import argparse
import html
import json
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

from mlb_war_wins_collect import DATA, ROOT, save_json
from mlb_war_wins_render import render

HARNESS=r'''
<script>
window.addEventListener('error',e=>document.documentElement.dataset.check='error: '+e.message);
setTimeout(async()=>{try{
 const check=(ok,msg)=>{if(!ok)throw Error(msg);};
 const pause=()=>new Promise(resolve=>setTimeout(resolve,180));
 check($('season').options.length===6,'five seasons plus all');
 check($('team').options.length===31,'30 team identities plus all');
 check($('season').value==='all','all years default');
 check($('scatter').querySelectorAll('.point').length===150,'150 actual team-seasons');
 check(!$('additional').open,'secondary analysis starts collapsed');
 check($('summary').getBoundingClientRect().height===0,'summary cards absent from first view');
 check($('errors').getBoundingClientRect().height===0,'error graph absent from first view');
 check($('trend').getBoundingClientRect().height===0,'trend graph absent from first view');
 const firstDot=$('scatter').querySelector('.point');firstDot.dispatchEvent(new MouseEvent('click',{bubbles:true}));
 check(!$('detail').textContent.includes('WAR 기반'),'first-view details use WAR and actual wins');
 $('additional').open=true;await pause();
 check($('errors').getBoundingClientRect().height>0,'expanded error graph visible');
 check($('trend').getBoundingClientRect().height>0,'expanded trend visible');
 check($('detail').textContent.includes('WAR 기반'),'expanded details include estimated wins');
 check(!$('detail').textContent.includes('피타고리안'),'no unrelated detail metric');
 check($('errors').querySelectorAll('.point').length===150,'150 errors');
 const originalSummary=$('summary').textContent;
 const team=payload.rows[0].team_id;
 $('team').value=String(team);$('team').dispatchEvent(new Event('change'));
 check($('summary').textContent===originalSummary,'highlight leaves summary unchanged');
 check($('scatter').querySelectorAll('.point').length===150,'highlight leaves all teams visible');
 check($('scatter').querySelectorAll('.dim').length===145,'five years highlighted');
 check($('trend').querySelectorAll('.point').length===5,'five team trend records');
 const p='fwar';
 for(const year of payload.seasons){
  $('season').value=String(year);$('season').dispatchEvent(new Event('change'));
  check($('scatter').querySelectorAll('.point').length===30,'30 teams in each season');
  check($('errors').querySelectorAll('.point').length===30,'30 errors per season');
  check($('summary').dataset.n==='30','summary uses selected season');
  check($('summary').textContent.includes(payload.summaries[p][String(year)].mae.toFixed(2)),'summary correct MAE');
  const row=payload.rows.find(r=>r.season===year);
  const dot=$('scatter').querySelector(`[data-key="${year}-${row.team_id}"]`);
  dot.dispatchEvent(new MouseEvent('click',{bubbles:true}));
  check(!$('detail').hidden&&$('detail').textContent.includes(row.team),'point detail matches team');
  check($('detail').textContent.includes(row[p].toFixed(2)),'point detail matches WAR');
  check($('detail').textContent.includes(row[p+'_expected'].toFixed(2)),'detail expected wins');
 }
 check(!$('provider'),'no redundant metric selector');
 check(payload.status==='complete','fWAR analysis complete');
 check($('status').hidden,'no acquisition warning after verification');
 check($('comparison').querySelectorAll('tbody tr').length===1,'one fWAR summary row');
 const contentWidth=document.body.clientWidth;
 check(document.documentElement.scrollWidth<=innerWidth+1&&document.body.scrollWidth<=contentWidth+1,'no expanded page overflow');
 for(const id of ['scatter','errors','trend']){const b=$(id).getBoundingClientRect();check(b.width>0&&b.right<=Math.min(innerWidth,contentWidth)+1,'expanded chart fits width');}
 $('reset').click();
 check($('season').value==='all'&&$('team').value==='all','reset filters');
 check($('scatter').querySelectorAll('.point').length===150,'restore all 150 points');
 check($('summary').textContent===originalSummary,'restored summary');
 check($('detail').hidden,'reset closes detail');
 check(!$('additional').open,'reset restores collapsed first view');
 const first=$('scatter').querySelector('.point');first.dispatchEvent(new KeyboardEvent('keydown',{key:'Enter',bubbles:true}));
 check(!$('detail').hidden,'keyboard selection');
 document.dispatchEvent(new KeyboardEvent('keydown',{key:'Escape',bubbles:true}));check($('detail').hidden,'Escape closes detail');
 check(document.documentElement.scrollWidth<=innerWidth+1&&document.body.scrollWidth<=contentWidth+1,'no page overflow');
 const b=$('scatter').getBoundingClientRect();check(b.width>0&&b.right<=Math.min(innerWidth,contentWidth)+1,'overview chart fits width');
 document.documentElement.dataset.check='pass';
 document.documentElement.dataset.evidence=JSON.stringify({rows:150,seasons:5,highlightPreservesSample:true,summaryUpdates:true,pointDetails:true,keyboard:true,reset:true,collapsedOverview:true,secondaryAnalysis:true,metric:'fwar',width:innerWidth,contentWidth,overflow:false});
}catch(e){document.documentElement.dataset.check='fail: '+e.message;}},500);
</script>
'''


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--browser',type=Path)
    args=parser.parse_args()
    candidates=[args.browser,Path('C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe'),
                Path('C:/Program Files/Microsoft/Edge/Application/msedge.exe')]
    candidates += [Path(p) for cmd in ['chromium','chromium-browser','google-chrome'] if (p:=shutil.which(cmd))]
    browser=next((p for p in candidates if p and p.is_file()),None)
    if browser is None:raise RuntimeError('Pass --browser with an Edge/Chromium executable')
    real=json.loads((ROOT/'assets/mlb-war-wins/results.json').read_text(encoding='utf-8'))
    out=DATA/'analysis/browser-check';out.mkdir(parents=True,exist_ok=True)
    checks=[]
    with tempfile.TemporaryDirectory(prefix='war-wins-check-') as temp:
        temporary=Path(temp)
        for name, data in [('real',real)]:
            for width in [1440,375]:
                page=temporary/f'{name}-{width}.html';render(data,page)
                source=page.read_text(encoding='utf-8')
                # Edge's minimum window width exceeds a phone viewport; enforce content width.
                if width==375:source=source.replace('</style>','html,body{width:375px!important;max-width:375px!important}</style>',1)
                page.write_text(source.replace('</body>',HARNESS+'</body>'),encoding='utf-8')
                command=[str(browser),'--headless','--disable-gpu','--no-first-run','--no-default-browser-check',
                         '--disable-background-networking','--disable-extensions','--force-device-scale-factor=1',
                         '--user-data-dir='+str(temporary/f'profile-{name}-{width}'),f'--window-size={width},1100',
                         '--virtual-time-budget=2000','--dump-dom',page.as_uri()]
                result=subprocess.run(command,capture_output=True,timeout=40)
                dom=result.stdout.decode('utf-8',errors='replace')
                status=re.search(r'data-check="([^"]+)"',dom)
                if not status or status.group(1)!='pass':
                    raise AssertionError((name,width,status.group(1) if status else result.stderr.decode('utf-8',errors='replace')[-1800:]))
                evidence=json.loads(html.unescape(re.search(r'data-evidence="([^"]+)"',dom).group(1)))
                record=dict(dataset=name,requested_width=width,**evidence)
                checks.append(record);print(json.dumps(record))
        # Capture the production chart without the test harness.
        for width in [1440,375]:
            page=temporary/f'preview-{width}.html';render(real,page)
            if width==375:
                source=page.read_text(encoding='utf-8').replace('</style>','html,body{width:375px!important;max-width:375px!important}</style>',1)
                page.write_text(source,encoding='utf-8')
            command=[str(browser),'--headless','--disable-gpu','--no-first-run','--no-default-browser-check',
                     '--disable-background-networking','--disable-extensions','--force-device-scale-factor=1',
                     '--user-data-dir='+str(temporary/f'preview-profile-{width}'),f'--window-size={width},1900',
                     '--virtual-time-budget=1500','--screenshot='+str(out/f'dashboard-{width}.png'),page.as_uri()]
            subprocess.run(command,capture_output=True,timeout=40,check=True)
    save_json(out/'results.json',checks)


if __name__=='__main__':main()

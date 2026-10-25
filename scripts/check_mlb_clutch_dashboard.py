"""Check the standalone clutch chart in local headless Edge (no web server)."""
from pathlib import Path
import html
import json
import re
import subprocess
import tempfile
from html.parser import HTMLParser

ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / 'scripts/mlb-clutch-dashboard.html'
BROWSER = Path('C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe')
OUT = ROOT / 'data/mlb/clutch-2026/analysis/browser-check'

HARNESS = r'''
<style>__WIDTH_STYLE__</style>
<script>
window.addEventListener('error',e=>document.documentElement.dataset.check='error: '+e.message);
setTimeout(()=>{try{
 const check=(v,m)=>{if(!v)throw Error(m);};
 check(players.length===163,'shared cohort');
 check($('scatter').querySelectorAll('.point').length===players.length,'plotted count');
 check($('player').options.length===players.length+1,'selector count');
 const p=players[0];$('player').value=String(p.player_id);$('player').dispatchEvent(new Event('change'));
 check(!$('details').hidden&&$('selected-name').textContent===p.name_2026,'selected player');
 check($('detail-rows').children[2].children[1].textContent===String(p.risp_ab_2025),'correct RISP AB');
 check($('detail-rows').children[4].children[1].textContent===p.avg_2025.toFixed(3),'decimal AVG detail');
 check($('detail-rows').children[6].children[1].textContent===((p.delta_2025>=0?'+':'')+p.delta_2025.toFixed(3)),'decimal gap detail');
 for(const metric of ['contrast','avg','risp_avg','delta']){
  $('metric').value=metric;$('metric').dispatchEvent(new Event('change'));
  check($('scatter').querySelectorAll('.point').length===163,'metric sample');
  check($('correlation').textContent.includes(payload.persistence[metric].pearson.toFixed(3)),'metric correlation');
  check(Number($('player').value)===p.player_id,'selection preserved');
  const ticks=[...$('scatter').querySelectorAll('.drawing text')].map(node=>node.textContent).filter(text=>!text.includes('년'));
  check(ticks.length>0&&ticks.every(text=>/^-?\d+\.\d{3}$/.test(text)),'three-decimal axis ticks');
  check(!$('scatter').textContent.includes('%'),'decimal axes without percent units');
  const point=$('scatter').querySelector('.point');
  const shown=['delta','contrast'].includes(metric)?((players[0][metric+'_2025']>=0?'+':'')+players[0][metric+'_2025'].toFixed(3)):players[0][metric+'_2025'].toFixed(3);
  check(point.getAttribute('aria-label').includes(shown),'decimal point values');
 }
 check($('season-pair').options.length===3,'three adjacent-season pairs');
 for(const [key,pair] of Object.entries(payload.pairs)){
  $('season-pair').value=key;$('season-pair').dispatchEvent(new Event('change'));
  check(players.length===pair.n,'pair-specific cohort');
  check($('scatter').querySelectorAll('.point').length===pair.n,'pair-specific plotted count');
  check($('before-year').textContent===String(pair.before)&&$('after-year').textContent===String(pair.after),'pair-specific years');
  const first=pair.players[0];$('player').value=String(first.player_id);$('player').dispatchEvent(new Event('change'));
  check($('selected-name').textContent===first['name_'+pair.after],'pair-specific player');
  check($('detail-rows').children[2].children[1].textContent===String(first['risp_ab_'+pair.before]),'pair-specific raw counts');
  for(const metric of ['delta','contrast','avg','risp_avg']){
   $('metric').value=metric;$('metric').dispatchEvent(new Event('change'));
   check($('correlation').textContent.includes(pair.persistence[metric].pearson.toFixed(3)),'pair-specific correlation');
   check($('scatter').querySelectorAll('.point').length===pair.n,'pair-metric sample');
  }
 }
 $('season-pair').value=payload.default_pair;$('season-pair').dispatchEvent(new Event('change'));
 $('reset').click();check($('details').hidden&&!$('player').value,'reset');
 const dot=$('scatter').querySelector('.point');dot.dispatchEvent(new KeyboardEvent('keydown',{key:'Enter',bubbles:true,cancelable:true}));
 check(!$('details').hidden,'keyboard select');
 document.dispatchEvent(new KeyboardEvent('keydown',{key:'Escape',bubbles:true}));check($('details').hidden,'escape');
 dot.dispatchEvent(new MouseEvent('click',{bubbles:true}));check(!$('details').hidden,'point click');
 check($('scatter').querySelectorAll('.selected').length===1,'single selected point');
 check(document.documentElement.scrollWidth<=innerWidth+1,'page overflow');
 const box=$('scatter').getBoundingClientRect();
 check(box.width>0&&box.right<=Math.min(innerWidth,__WIDTH__)+1,'chart fits content');
 document.documentElement.dataset.check='pass';
 document.documentElement.dataset.evidence=JSON.stringify({contentWidth:document.body.clientWidth,
  chartWidth:Math.round(box.width),documentHeight:document.documentElement.scrollHeight,players:players.length,metrics:4,seasonPairs:3,selection:true,keyboard:true,overflow:false});
}catch(e){document.documentElement.dataset.check='fail: '+e.message;}},700);
</script>
'''


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    class References(HTMLParser):
        def handle_starttag(self,tag,attrs):
            for key,value in attrs:
                if key in ('src','href') and value and not value.startswith(('https:','http:','#')):
                    assert (PAGE.parent/value).resolve().is_file(),value
    References().feed(PAGE.read_text(encoding='utf-8'))
    checks=[]
    with tempfile.TemporaryDirectory(prefix='mlb-clutch-check-') as directory:
        temporary=Path(directory)
        for width in (1440,375):
            style='html,body{width:375px!important;max-width:375px!important}' if width==375 else ''
            harness=HARNESS.replace('__WIDTH_STYLE__',style).replace('__WIDTH__',str(width))
            source=PAGE.read_text(encoding='utf-8')
            source=source.replace('<head>','<head><base href="'+PAGE.parent.as_uri()+'/">')
            page=temporary/f'check-{width}.html'
            page.write_text(source.replace('</body>',harness+'</body>'),encoding='utf-8')
            args=[str(BROWSER),'--headless','--disable-gpu','--no-first-run',
                  '--no-default-browser-check','--disable-background-networking','--disable-extensions',
                  '--force-device-scale-factor=1','--user-data-dir='+str(temporary/f'profile-{width}'),
                  f'--window-size={width},1200','--virtual-time-budget=2500','--dump-dom',page.as_uri()]
            result=subprocess.run(args,capture_output=True,timeout=35)
            dom=result.stdout.decode('utf-8',errors='replace')
            status=re.search(r'data-check="([^"]+)"',dom)
            assert status and status.group(1)=='pass',(width,status.group(1) if status else result.stderr.decode('utf-8',errors='replace')[-1500:])
            evidence=json.loads(html.unescape(re.search(r'data-evidence="([^"]+)"',dom).group(1)))
            checks.append({'requested_width':width,**evidence})
            print(json.dumps(checks[-1],ensure_ascii=False))
            screenshot_args=[a for a in args if a!='--dump-dom']
            screenshot_args.insert(-1,'--screenshot='+str(OUT/f'dashboard-{width}.png'))
            subprocess.run(screenshot_args,capture_output=True,timeout=35,check=True)
    (OUT/'results.json').write_text(json.dumps(checks,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')


if __name__=='__main__':
    main()

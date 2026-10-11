"""Check the draft chart in headless Edge with an isolated temporary profile.

The narrow sample constrains the page content to 375 CSS pixels because Edge's
headless window has a larger minimum viewport. No public blog output is built.
"""
from pathlib import Path
import json
import re
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
page = ROOT / 'scripts/murakami-dot-plot.html'
browser = Path('C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe')
harness = r'''
<style>__TEST_WIDTH_STYLE__</style>
<script>
window.addEventListener('error',e=>{document.documentElement.dataset.check='error: '+e.message;});
setTimeout(()=>{
try {
 const check=(value,message)=>{if(!value)throw Error(message);};
 const total=data.balls.length;
 check(total===257,'sample count');
 check(svg.querySelectorAll('.dot').length===257,'rendered dots');
 check(!$('regions')?.checked,'overlays default hidden');
 const counts={all:257,hit:59,hr:35,nonhit:163};
 const click=key=>document.querySelector('[data-filter="'+key+'"]').click();
 const expect=(count,message)=>{check(svg.querySelectorAll('.dot').length===count,message);check($('ballselect').options.length===count+1,message+' list');};
 for(const [key,count] of [['hit',198],['hr',163],['nonhit',0],['hr',35],['nonhit',198],['hr',163],['all',257]]){
  click(key);expect(count,'toggle '+key);
 }
 check([...document.querySelectorAll('[data-filter]')].every(b=>b.getAttribute('aria-pressed')==='true'),'all categories active');
 click('nonhit');click('hr');expect(59,'only non-home-run hits');
 check(visible.every(({r})=>['single','double','triple'].includes(r.event)),'hits exclude home runs');
 click('all');click('hit');click('nonhit');expect(35,'only home runs');
 const i=+$('ballselect').options[1].value;
 $('ballselect').value=String(i);$('ballselect').dispatchEvent(new Event('change'));
 check($('outcome').textContent==='홈런','selected actual outcome: '+$('outcome').textContent+' index '+i+' event '+data.balls[i].event+' error '+document.documentElement.dataset.check);
 check($('date').textContent===data.balls[i].date,'selected date');
 check($('opponent').textContent===data.balls[i].opponent,'selected opponent');
 check($('distance').textContent===data.balls[i].distance.toFixed(1)+' m','distance conversion');
 if($('regions')){
 $('regions').checked=true;$('regions').dispatchEvent(new Event('change'));
 check(!$('regionlegend').hidden&&svg.querySelectorAll('rect[fill-opacity]').length===4,'region overlay');
 }
 check(!$('model')&&!$('modelnote')&&!('contours' in data),'probability contours removed');
 if($('reset'))$('reset').click();
 else {document.querySelector('[data-filter="all"]').click();choose(null);}
 check(svg.querySelectorAll('.dot').length===257&&!$('regions')?.checked,'reset');
 const first=svg.querySelector('.dot');
 first.dispatchEvent(new PointerEvent('pointerenter',{pointerType:'mouse'}));
 check(!$('details').hidden,'mouse hover');
 svg.dispatchEvent(new PointerEvent('pointerleave'));
 check($('details').hidden,'hover release');
 first.dispatchEvent(new PointerEvent('pointerenter',{pointerType:'touch'}));
 check($('details').hidden,'touch does not hover');
 first.dispatchEvent(new KeyboardEvent('keydown',{key:'Enter',bubbles:true,cancelable:true}));
 check($('ballselect').value===first.dataset.index,'keyboard selection');
 first.dispatchEvent(new KeyboardEvent('keydown',{key:'ArrowRight',bubbles:true,cancelable:true}));
 check($('ballselect').value===String(visible[1].i),'keyboard next');
 document.dispatchEvent(new KeyboardEvent('keydown',{key:'Escape',bubbles:true}));
 check($('details').hidden,'escape clears');
 // A synthetic pointer click at the first plotted coordinate follows the same
 // event path used by touch taps and clicks, including SVG scaling.
 const rect=svg.getBoundingClientRect(),p=positions[0];
 svg.dispatchEvent(new MouseEvent('click',{bubbles:true,clientX:rect.left+p.x/layout.width*rect.width,clientY:rect.top+p.y/layout.height*rect.height}));
 check(!$('details').hidden,'point click');
 check(document.documentElement.scrollWidth<=window.innerWidth+1,'page horizontal overflow');
 const box=$('chartbox').getBoundingClientRect();
 check(box.width>0&&box.right<=Math.min(window.innerWidth,__TEST_WIDTH__)+1,'chart fits content width');
 check(data.balls.filter(r=>r.distance===null).length===0,'expected distance coverage');
 document.documentElement.dataset.check='pass';
 document.documentElement.dataset.evidence=JSON.stringify({windowWidth:innerWidth,contentWidth:document.body.clientWidth,plotWidth:Math.round(box.width),dots:total,counts,overlays:true,keyboard:true,touchPath:true,overflow:false});
}catch(error){document.documentElement.dataset.check='fail: '+error.message;}
},400);
</script>
'''
with tempfile.TemporaryDirectory(prefix='mlb-dot-check-') as directory:
    temporary = Path(directory)
    testpage = temporary / 'check.html'
    for width in [1440, 375]:
        style = 'html,body{width:375px!important;max-width:375px!important}' if width == 375 else ''
        checkscript = harness.replace('__TEST_WIDTH_STYLE__', style).replace('__TEST_WIDTH__', str(width))
        testpage.write_text(page.read_text(encoding='utf-8').replace('</body>', checkscript + '</body>'), encoding='utf-8')
        result = subprocess.run([str(browser), '--headless', '--disable-gpu', '--no-first-run',
                                 '--no-default-browser-check', '--disable-background-networking',
                                 '--disable-extensions', '--force-device-scale-factor=1',
                                 '--user-data-dir=' + str(temporary / ('profile-' + str(width))),
                                 '--window-size=' + str(width) + ',1200', '--virtual-time-budget=2000',
                                 '--dump-dom', testpage.as_uri()], capture_output=True, timeout=35)
        output = result.stdout.decode('utf-8', errors='replace')
        status = re.search(r'data-check="([^"]+)"', output)
        assert status and status.group(1) == 'pass', (width, status.group(1) if status else result.stderr.decode('utf-8', errors='replace')[-1000:])
        evidence = re.search(r'data-evidence="([^"]+)"', output)
        import html
        print(json.dumps(json.loads(html.unescape(evidence.group(1))), ensure_ascii=False))

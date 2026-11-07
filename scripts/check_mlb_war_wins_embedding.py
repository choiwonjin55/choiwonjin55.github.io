"""Check the generated WAR article and naturally resizing chart over local HTTP."""
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import html
import json
from pathlib import Path
import re
import subprocess
import tempfile
import threading

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'data/mlb/war-wins-2022-2026/analysis/article-browser-check'
BROWSER = Path('C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe')

HARNESS = r'''<script>
document.querySelectorAll('iframe,img').forEach(f=>f.loading='eager');
const pause=()=>new Promise(resolve=>setTimeout(resolve,220));
setTimeout(async()=>{let stage='initial';try{
 const check=(v,m)=>{if(!v)throw Error(m);};
 check(document.querySelector('h1').textContent==='팀 WAR와 실제 승수','article title');
 check(document.querySelector('time').dateTime==='2026-11-03','article date');
 check(document.querySelector('.post-badge').textContent==='데이터분석','category');
 const tags=[...document.querySelectorAll('.post-tag')].map(n=>n.textContent);
 check(tags.join(',')==='MLB,WAR,데이터분석,시각화','tag order');
 const frames=[...document.querySelectorAll('iframe')];check(frames.length===1,'one graph embed');
 const f=frames[0],doc=f.contentDocument,w=f.contentWindow;
 check(doc&&doc.getElementById('scatter'),'loaded local chart');
 check(doc.querySelectorAll('#scatter .point').length===150,'all 150 observations');
 const measure=()=>({height:f.clientHeight,naturalHeight:Math.ceil(doc.body.getBoundingClientRect().height),scrollHeight:doc.documentElement.scrollHeight,width:f.clientWidth,contentWidth:doc.documentElement.scrollWidth});
 const fits=()=>{const m=measure();check(m.height>=m.naturalHeight,'frame clipped');check(m.height<=m.naturalHeight+12,'excess frame height');check(m.scrollHeight<=m.height+1,'inner vertical scrollbar');check(m.contentWidth<=m.width+1,'inner horizontal overflow');check(document.body.scrollWidth<=document.body.clientWidth+1,'article horizontal overflow');};
 fits();const initial=measure();
 check(!doc.getElementById('additional').open,'scatter-only first view');
 check(doc.getElementById('errors').getBoundingClientRect().height===0,'secondary graph initially folded');
 check(f.previousElementSibling.textContent.includes('0.929'),'relationship result precedes graph');
 stage='season change';doc.getElementById('season').value='2026';doc.getElementById('season').dispatchEvent(new w.Event('change'));await pause();fits();
 check(doc.querySelectorAll('#scatter .point').length===30,'season selection inside article');
 stage='team highlight';const summary=doc.getElementById('summary').textContent;doc.getElementById('team').value='144';doc.getElementById('team').dispatchEvent(new w.Event('change'));await pause();fits();
 check(doc.getElementById('summary').textContent===summary,'team highlight preserves summary');
 stage='point selection';doc.querySelector('#scatter [data-key="2026-144"]').dispatchEvent(new w.MouseEvent('click',{bubbles:true}));await pause();fits();
 check(!doc.getElementById('detail').hidden,'embedded detail visible');
 check(doc.getElementById('detail').textContent.includes('Atlanta Braves'),'correct case team');const selected=measure();
 check(!doc.getElementById('detail').textContent.includes('WAR 기반'),'simple overview detail');
 stage='expand secondary analysis';doc.getElementById('additional').open=true;await pause();fits();
 check(doc.getElementById('errors').getBoundingClientRect().height>0,'secondary graph visible');
 check(doc.getElementById('detail').textContent.includes('WAR 기반'),'expanded estimated-wins detail');
 check(!doc.getElementById('detail').textContent.includes('피타고리안'),'unrelated metric removed');const expanded=measure();
 check(expanded.height>selected.height,'expanded frame grows');
 stage='collapse secondary analysis';doc.getElementById('additional').open=false;await pause();fits();
 check(measure().height===selected.height,'collapsed frame shrinks to selected overview');
 stage='reset';doc.getElementById('reset').click();await pause();fits();
 check(doc.querySelectorAll('#scatter .point').length===150,'restore all');
 check(doc.getElementById('detail').hidden,'detail closed');
 const expectedTables=__EXPECTED_TABLES__,expectedImages=__EXPECTED_IMAGES__;
 check(document.querySelectorAll('.post-table').length===expectedTables,'all source tables rendered');
 const images=[...document.images];
 check(images.length===expectedImages.length,'source figure count');
 check(expectedImages.every(src=>images.some(img=>img.getAttribute('src')===src)),'source figure paths');
 check(images.every(img=>img.complete&&img.naturalWidth>0),'article figures loaded');
 document.documentElement.dataset.audit=JSON.stringify({pass:true,contentWidth:document.body.clientWidth,initial,selected,expanded,reset:measure(),metadata:true,tables:expectedTables,figures:images.length,embeddedInteractions:true});
}catch(e){const f=document.querySelector('iframe');document.documentElement.dataset.audit=JSON.stringify({pass:false,stage,error:e.message,frameHeight:f?.clientHeight,bodyHeight:f?.contentDocument?.body?.getBoundingClientRect().height});}},1000);
</script>'''

FILE_CHILD = r'''<script>
setTimeout(async()=>{
 const wait=()=>new Promise(resolve=>setTimeout(resolve,220));
 const report=stage=>parent.postMessage({type:'war-file-check',stage,
  bodyHeight:Math.ceil(document.body.getBoundingClientRect().height),
  scrollHeight:document.documentElement.scrollHeight,
  rows:document.querySelectorAll('#scatter .point').length,
  detailOpen:!document.getElementById('detail').hidden,
  analysisOpen:document.getElementById('additional').open},'*');
 await wait();report('initial');
 document.getElementById('season').value='2026';document.getElementById('season').dispatchEvent(new Event('change'));
 document.querySelector('#scatter [data-key="2026-144"]').dispatchEvent(new MouseEvent('click',{bubbles:true}));
 await wait();report('selected');
 document.getElementById('additional').open=true;await wait();report('expanded');
 document.getElementById('additional').open=false;await wait();report('collapsed');
 document.getElementById('reset').click();await wait();report('reset');
},400);
</script>'''

FILE_PARENT = r'''<script>
const fileStages=[];
document.querySelectorAll('iframe').forEach(f=>f.loading='eager');
window.addEventListener('message',event=>{
 const frame=document.querySelector('iframe'),m=event.data;
 if(event.source!==frame.contentWindow||m?.type!=='war-file-check')return;
 try{
  if(frame.clientHeight<m.bodyHeight||frame.clientHeight>m.bodyHeight+12)throw Error('local-file frame height mismatch');
  if(m.scrollHeight>frame.clientHeight+1)throw Error('local-file content clipped');
  const selected=['selected','expanded','collapsed'].includes(m.stage);
  if(m.rows!==(selected?30:150))throw Error('local-file chart cohort');
  if(m.detailOpen!==selected)throw Error('local-file details');
  if(m.analysisOpen!==(m.stage==='expanded'))throw Error('local-file secondary analysis');
  fileStages.push({...m,frameHeight:frame.clientHeight});
  if(m.stage==='reset'){
   window.postMessage({type:'mlb-war-wins-height',height:5900},'*');
   setTimeout(()=>{
    const pass=frame.clientHeight<=m.bodyHeight+12&&fileStages.length===5;
    document.documentElement.dataset.audit=JSON.stringify({pass,mode:'file',contentWidth:document.body.clientWidth,stages:fileStages,ignoresUnrelatedMessages:pass});
   },120);
  }
 }catch(e){document.documentElement.dataset.audit=JSON.stringify({pass:false,mode:'file',error:e.message,frameHeight:frame.clientHeight,...m});}
});
</script>'''


def main():
    original = (ROOT / 'blog/mlb-war-wins.html').read_text(encoding='utf-8')
    source = (ROOT / 'posts/2026-11-03-mlb-war-wins.md').read_text(encoding='utf-8')
    tables = len(re.findall(r'^\|\s*:?-{3,}', source, re.M))
    images = re.findall(r'^!\[[^\n]*\]\(([^\n)]+)\)\s*$', source, re.M)
    harness = HARNESS.replace('__EXPECTED_TABLES__', str(tables)).replace(
        '__EXPECTED_IMAGES__', json.dumps(images))
    index = (ROOT / 'blog/index.html').read_text(encoding='utf-8')
    if 'href="./mlb-war-wins.html"' not in index:
        raise AssertionError('WAR article missing from blog index')
    OUT.mkdir(parents=True, exist_ok=True)
    checks = []
    with tempfile.TemporaryDirectory(prefix='war-article-check-') as directory:
        temporary = Path(directory)

        class Handler(SimpleHTTPRequestHandler):
            def translate_path(self, path):
                if path.split('?',1)[0] == '/blog/war-article-check.html':
                    return str(temporary / 'article.html')
                return super().translate_path(path)

            def log_message(self, *_args):
                pass

        server = ThreadingHTTPServer(('127.0.0.1',0),partial(Handler,directory=str(ROOT)))
        thread = threading.Thread(target=server.serve_forever,daemon=True)
        thread.start()
        try:
            url=f'http://127.0.0.1:{server.server_port}/blog/war-article-check.html'
            for width in (1440,375):
                style='<style>html,body{width:375px!important;max-width:375px!important}</style>' if width==375 else ''
                page=temporary/'article.html'
                page.write_text(original.replace('</body>',style+harness+'</body>'),encoding='utf-8')
                command=[str(BROWSER),'--headless','--disable-gpu','--no-first-run','--no-default-browser-check',
                         '--disable-background-networking','--disable-extensions','--force-device-scale-factor=1',
                         '--user-data-dir='+str(temporary/f'profile-{width}'),f'--window-size={width},1200',
                         '--virtual-time-budget=4500','--dump-dom',url]
                result=subprocess.run(command,capture_output=True,timeout=40)
                dom=result.stdout.decode('utf-8',errors='replace')
                match=re.search(r'data-audit="([^"]+)"',dom)
                if not match:raise AssertionError(result.stderr.decode('utf-8',errors='replace')[-1600:])
                evidence=json.loads(html.unescape(match.group(1)))
                print(json.dumps(dict(requested_width=width,**evidence)))
                if not evidence['pass']:raise AssertionError(evidence)
                checks.append(dict(requested_width=width,**evidence))
                # Capture the original article after the browser has fitted the iframe.
                page.write_text(original.replace('</body>',style+"<script>document.querySelectorAll('iframe,img').forEach(f=>f.loading='eager')</script></body>"),encoding='utf-8')
                screenshot=[a for a in command if a!='--dump-dom']
                screenshot.insert(-1,'--screenshot='+str(OUT/f'article-{width}.png'))
                subprocess.run(screenshot,capture_output=True,timeout=40,check=True)
            child=temporary/'mlb-war-wins-dashboard.html'
            child.write_text((ROOT/'scripts/mlb-war-wins-dashboard.html').read_text(encoding='utf-8').replace('</body>',FILE_CHILD+'</body>'),encoding='utf-8')
            for width in (1440,375):
                style='<style>html,body{width:375px!important;max-width:375px!important}</style>' if width==375 else ''
                local=original.replace('<head>','<head><base href="'+(ROOT/'blog').as_uri()+'/">',1)
                local=local.replace('../scripts/mlb-war-wins-dashboard.html',child.as_uri())
                local=local.replace('</body>',style+FILE_PARENT+'</body>')
                page=temporary/f'local-{width}.html';page.write_text(local,encoding='utf-8')
                command=[str(BROWSER),'--headless','--disable-gpu','--no-first-run','--no-default-browser-check',
                         '--disable-background-networking','--disable-extensions','--force-device-scale-factor=1',
                         '--user-data-dir='+str(temporary/f'file-profile-{width}'),f'--window-size={width},1200',
                         '--virtual-time-budget=4500','--dump-dom',page.as_uri()]
                result=subprocess.run(command,capture_output=True,timeout=40)
                dom=result.stdout.decode('utf-8',errors='replace')
                match=re.search(r'data-audit="([^"]+)"',dom)
                if not match:raise AssertionError(('file',width,result.stderr.decode('utf-8',errors='replace')[-1200:]))
                evidence=json.loads(html.unescape(match.group(1)))
                print(json.dumps(dict(requested_width=width,**evidence)))
                if not evidence['pass']:raise AssertionError(evidence)
                checks.append(dict(requested_width=width,**evidence))
        finally:
            server.shutdown();server.server_close();thread.join()
    (OUT/'results.json').write_text(json.dumps(checks,indent=2)+'\n',encoding='utf-8')


if __name__=='__main__':
    main()

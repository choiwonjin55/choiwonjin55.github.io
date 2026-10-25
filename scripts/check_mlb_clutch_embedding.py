"""Check natural chart resizing in temporary published pages over local HTTP."""
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import html
import json
import re
import subprocess
import sys
import tempfile
import threading
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import build_blog

BROWSER = Path('C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe')
HARNESS = r'''<script>
document.querySelectorAll('iframe,img').forEach(n=>n.loading='eager');
const pause=()=>new Promise(resolve=>setTimeout(resolve,180));
setTimeout(async()=>{
 let stage='initial';
 const frames=[...document.querySelectorAll('iframe')];
 const measure=()=>frames.map(f=>({height:f.clientHeight,naturalHeight:Math.ceil(f.contentDocument.body.getBoundingClientRect().height),scrollHeight:f.contentDocument.documentElement.scrollHeight,width:f.clientWidth,contentWidth:f.contentDocument.documentElement.scrollWidth}));
 try{
  const check=(v,m)=>{if(!v)throw Error(m);};
  const fits=()=>{for(const m of measure()){
   check(m.height>=m.naturalHeight,'frame content clipped');
   check(m.scrollHeight<=m.height+1,'inner vertical scrollbar');
   check(m.height<=m.naturalHeight+12,'frame has excess height');
   check(m.contentWidth<=m.width+1,'horizontal frame overflow');
  }};
  fits();const initial=measure();
  const overview=frames[0].contentDocument;
  stage='year change';overview.getElementById('season').value='2023';overview.getElementById('season').dispatchEvent(new Event('change'));await pause();fits();
  stage='overview selection';overview.querySelector('#rates .point').dispatchEvent(new MouseEvent('click',{bubbles:true}));await pause();fits();
  const comparison=frames[1].contentDocument,select=comparison.getElementById('player');
  stage='player selection';select.selectedIndex=1;select.dispatchEvent(new Event('change'));await pause();fits();const selected=measure();
  stage='reset';comparison.getElementById('reset').click();await pause();fits();
  check([...document.images].every(i=>i.complete&&i.naturalWidth>0),'loaded image');
  document.documentElement.dataset.audit=JSON.stringify({pass:true,initial,selected,reset:measure()});
 }catch(e){document.documentElement.dataset.audit=JSON.stringify({pass:false,stage,error:e.message,frames:measure()});}
},1000);
</script>'''


def main():
    with tempfile.TemporaryDirectory(prefix='mlb-http-check-') as folder:
        temporary = Path(folder)
        previous_output = build_blog.OUT_DIR
        try:
            build_blog.OUT_DIR = temporary
            for name in ('2026-10-25-mlb-clutch.md', '2026-10-25-mlb-clutch-persistence.md'):
                build_blog.build_post(ROOT / 'posts' / name)
        finally:
            build_blog.OUT_DIR = previous_output
        page = temporary / 'mlb-2026-clutch-persistence.html'
        original = page.read_text(encoding='utf-8')

        class Handler(SimpleHTTPRequestHandler):
            def translate_path(self, path):
                name = path.split('?', 1)[0]
                if name.startswith('/blog/') and (temporary / Path(name).name).is_file():
                    return str(temporary / Path(name).name)
                return super().translate_path(path)

            def log_message(self, *_args):
                pass

        server = ThreadingHTTPServer(('127.0.0.1', 0), partial(Handler, directory=str(ROOT)))
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            base = f'http://127.0.0.1:{server.server_port}'
            with urlopen(base + '/blog/mlb-2026-risp-average-gap.html') as response:
                assert response.status == 200
            for width in (1440, 375):
                style = '<style>html,body{width:375px!important;max-width:375px!important}</style>' if width == 375 else ''
                page.write_text(original.replace('</body>', style + HARNESS + '</body>'), encoding='utf-8')
                args = [str(BROWSER), '--headless', '--disable-gpu', '--no-first-run',
                        '--no-default-browser-check', '--disable-background-networking',
                        '--disable-extensions', '--force-device-scale-factor=1',
                        '--user-data-dir=' + str(temporary / f'profile-{width}'),
                        f'--window-size={width},1200', '--virtual-time-budget=4500', '--dump-dom',
                        base + '/blog/mlb-2026-clutch-persistence.html']
                result = subprocess.run(args, capture_output=True, timeout=35)
                match = re.search(r'data-audit="([^"]+)"', result.stdout.decode('utf-8', errors='replace'))
                assert match, result.stderr.decode('utf-8', errors='replace')[-1000:]
                evidence = json.loads(html.unescape(match[1]))
                print(json.dumps({'content_width': width, **evidence}))
                assert evidence['pass'], evidence
        finally:
            server.shutdown()
            server.server_close()
            thread.join()


if __name__ == '__main__':
    main()

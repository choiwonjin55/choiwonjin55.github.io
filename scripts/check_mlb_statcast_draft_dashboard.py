"""Check dashboard controls at desktop and 375px content widths in Edge."""
from pathlib import Path
import html
import json
import re
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / 'scripts/statcast-dashboard.html'
BROWSER = Path('C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe')
HARNESS = r'''
<style>__STYLE__</style><script>
window.addEventListener('error',e=>document.documentElement.dataset.check='error: '+e.message);
setTimeout(()=>{try{
 const check=(value,message)=>{if(!value)throw Error(message);};
 const initial=el('distance').textContent;
 el('speed').value=110;el('angle').value=30;el('speed').dispatchEvent(new Event('input'));
 check(el('distance').textContent!==initial,'slider updates');
 check(el('hr').textContent===pct(data.hr[idx(110,30)]),'HR prediction');
 check(el('hit').textContent===pct(data.hit[idx(110,30)]),'hit prediction');
 document.querySelector('[data-field="hit"]').click();
 check(field==='hit'&&document.querySelector('[data-field="hit"]').getAttribute('aria-pressed')==='true','map tab');
 const r=canvas.getBoundingClientRect();
 canvas.dispatchEvent(new MouseEvent('click',{clientX:r.left+(plot.left+plot.width/2)*r.width/1000,clientY:r.top+(plot.top+plot.height/2)*r.height/520}));
 check(Math.abs(+el('speed').value-80)<=1&&Math.abs(+el('angle').value-15)<=1,'map selection');
 el('speed').value=118;el('angle').value=80;el('angle').dispatchEvent(new Event('input'));
 check(el('distance').textContent==='표본 부족','sparse data');
 check(el('optima').children.length===data.optima.length,'table');
 check(document.documentElement.scrollWidth<=document.documentElement.clientWidth+1,'horizontal overflow');
 check(ctx.getImageData(200,200,1,1).data[3]===255,'canvas render');
 document.documentElement.dataset.check='pass';
 document.documentElement.dataset.evidence=JSON.stringify({contentWidth:document.body.clientWidth,canvasWidth:Math.round(r.width),slider:true,tabs:true,mapSelection:true,overflow:false});
 }catch(e){document.documentElement.dataset.check='fail: '+e.message;}},400);
</script>'''

if __name__ == '__main__':
    source = PAGE.read_text(encoding='utf-8')
    assert '__PAYLOAD__' not in source
    assert not re.search(r'<script[^>]+src=|fetch\(', source)
    saved = (ROOT / 'data/mlb/2026/analysis/dashboard.html').read_text(encoding='utf-8')
    assert re.search(r'const data=(.*);', source).group(1) == re.search(r'const data=(.*);', saved).group(1)
    with tempfile.TemporaryDirectory(prefix='mlb-dashboard-check-') as directory:
        temporary = Path(directory)
        for width in (1440, 375):
            style = 'html,body{width:375px!important;max-width:375px!important}' if width == 375 else ''
            page = temporary / 'check.html'
            page.write_text(source.replace('</body>', HARNESS.replace('__STYLE__', style) + '</body>'), encoding='utf-8')
            result = subprocess.run([str(BROWSER), '--headless', '--disable-gpu', '--no-first-run',
                '--no-default-browser-check', '--disable-background-networking', '--disable-extensions',
                '--force-device-scale-factor=1', '--user-data-dir=' + str(temporary / str(width)),
                '--window-size=' + str(width) + ',1200', '--virtual-time-budget=2000', '--dump-dom',
                page.as_uri()], capture_output=True, timeout=35)
            output = result.stdout.decode('utf-8', errors='replace')
            status = re.search(r'data-check="([^"]+)"', output)
            assert status and status.group(1) == 'pass', (width, status.group(1) if status else result.stderr.decode('utf-8', errors='replace')[-1000:])
            evidence = re.search(r'data-evidence="([^"]+)"', output)
            print(json.dumps(json.loads(html.unescape(evidence.group(1))), ensure_ascii=False))

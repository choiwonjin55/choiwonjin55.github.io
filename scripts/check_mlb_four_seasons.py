"""Check the four-season overview and complete local article in headless Edge."""
import argparse
from pathlib import Path

import check_mlb_clutch_dashboard as browser

ROOT = Path(__file__).resolve().parents[1]

OVERVIEW = r'''
<style>__WIDTH_STYLE__</style><script>
window.addEventListener('error',e=>document.documentElement.dataset.check='error: '+e.message);
setTimeout(()=>{try{
 const check=(v,m)=>{if(!v)throw Error(m);};
 check($('season').options.length===5,'all and four seasons');
 check($('season').value==='all','default all seasons');
 const total=Object.values(overview.years).reduce((sum,year)=>sum+year.n,0);
 const unique=new Set(Object.values(overview.years).flatMap(year=>year.players.map(p=>p.player_id))).size;
 const checkAll=()=>{
  check($('rates').querySelectorAll('.point').length===total,'all player-season points');
  check([...$('distribution').querySelectorAll('.histogram-bin')].reduce((sum,bar)=>sum+Number(bar.dataset.count),0)===total,'all histogram records');
  check($('summary').textContent.includes(unique+'명')&&$('summary').textContent.includes(total+'개 시즌 기록'),'distinct players and season records');
  for(const [year,data] of Object.entries(overview.years))check($('rates').querySelectorAll('.point[data-season="'+year+'"]').length===data.n,'all season membership');
 };
 checkAll();
 const fixedRateLabels=[...$('rates').querySelectorAll('text')].map(node=>node.textContent).join('|');
 const fixedHistogramTicks=[...$('distribution').querySelectorAll('text')].map(node=>node.textContent).filter(text=>/^-?\d/.test(text)).join('|');
 for(const [year,data] of Object.entries(overview.years)){
  $('season').value=year;$('season').dispatchEvent(new Event('change'));
  const points=[...$('rates').querySelectorAll('.point')];
  check(points.length===data.n,'eligible players');
  check(points.filter(point=>point.getAttribute('fill')==='#157b8c').length===data.positive,'exact positive count');
  check([...$('distribution').querySelectorAll('.histogram-bin')].reduce((sum,bar)=>sum+Number(bar.dataset.count),0)===data.n,'histogram complete');
  points[0].dispatchEvent(new MouseEvent('click',{bubbles:true}));
  check($('detail').textContent.includes(data.players[0].name),'point selection');
  check($('detail').textContent.includes(year+'년'),'selected season');
  check($('detail').textContent.includes(data.players[0].avg.toFixed(3)),'decimal rates');
  check(!$('detail').textContent.includes('%'),'decimal differences');
  const labels=[...$('rates').querySelectorAll('text')].map(node=>node.textContent);
  check(labels.filter(text=>/^-?\d/.test(text)).every(text=>/^-?\d+\.\d{3}$/.test(text)),'decimal axis ticks');
  check(labels.join('|')===fixedRateLabels,'fixed scatter axes');
  check([...$('distribution').querySelectorAll('text')].map(node=>node.textContent).filter(text=>/^-?\d/.test(text)).join('|')===fixedHistogramTicks,'fixed histogram axes');
 }
 $('season').value='all';$('season').dispatchEvent(new Event('change'));checkAll();
 const first=$('rates').querySelector('.point');first.dispatchEvent(new KeyboardEvent('keydown',{key:'Enter',bubbles:true}));
 check($('detail').textContent.includes(first.dataset.season),'all season keyboard selection');
 const box=$('rates').getBoundingClientRect();
 check(box.width>0&&box.right<=Math.min(innerWidth,__WIDTH__)+1,'responsive plot');
 check(document.documentElement.scrollWidth<=innerWidth+1,'page overflow');
 document.documentElement.dataset.check='pass';
 document.documentElement.dataset.evidence=JSON.stringify({seasons:4,allRecords:total,uniquePlayers:unique,restoredAll:true,fixedAxes:true,selectedPlayers:true,histograms:true,decimalRates:true,overflow:false,chartWidth:Math.round(box.width)});
}catch(e){document.documentElement.dataset.check='fail: '+e.message;}},700);
</script>
'''

ARTICLE = r'''
<style>__WIDTH_STYLE__</style><script>
window.addEventListener('error',e=>document.documentElement.dataset.check='error: '+e.message);
document.querySelectorAll('iframe,img').forEach(node=>node.loading='eager');
setTimeout(()=>{try{
 const check=(v,m)=>{if(!v)throw Error(m);};
 const frames=[...document.querySelectorAll('iframe[data-chart]')];
 check(frames.length===2,'two local embedded charts');
 const overview=frames[0].contentDocument,comparison=frames[1].contentDocument;
 check(overview.getElementById('season').options.length===5,'overview in article');
 check(overview.getElementById('season').value==='all'&&overview.querySelectorAll('#rates .point').length===946,'embedded all seasons default');
 check(comparison.getElementById('season-pair').options.length===3,'three pairs in article');
 overview.getElementById('season').value='2023';overview.getElementById('season').dispatchEvent(new Event('change'));
 check(overview.querySelectorAll('#rates .point').length===236,'embedded overview year change');
 overview.getElementById('season').value='all';overview.getElementById('season').dispatchEvent(new Event('change'));
 check(overview.querySelectorAll('#rates .point').length===946,'embedded restore all seasons');
 comparison.getElementById('season-pair').value='2023-2024';comparison.getElementById('season-pair').dispatchEvent(new Event('change'));
 check(comparison.querySelectorAll('#scatter .point').length===158,'embedded comparison year change');
 check(document.querySelectorAll('.post-table').length===5,'all five article tables');
 check([...document.images].every(image=>image.complete&&image.naturalWidth>0),'loaded article figure');
 check(document.documentElement.scrollWidth<=innerWidth+1,'article overflow');
 document.documentElement.dataset.check='pass';
 document.documentElement.dataset.evidence=JSON.stringify({iframes:2,tables:5,loadedImages:document.images.length,yearSwitching:true,overflow:false});
}catch(e){document.documentElement.dataset.check='fail: '+e.message;}},1200);
</script>
'''


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('kind', choices=['overview', 'article'])
    kind = parser.parse_args().kind
    if kind == 'article':
        import check_mlb_clutch_embedding
        check_mlb_clutch_embedding.main()
        raise SystemExit(0)
    browser.PAGE = ROOT / ('scripts/mlb-clutch-season-overview.html' if kind == 'overview'
                           else 'blog/mlb-2026-clutch-persistence.html')
    browser.OUT = ROOT / f'data/mlb/clutch-2023-2026/analysis/browser-check/{kind}'
    browser.HARNESS = OVERVIEW if kind == 'overview' else ARTICLE
    browser.main()

"""Render a clutch-analysis draft as local HTML, without building the site."""
from pathlib import Path
import argparse
import html
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from build_blog import markdown_to_html, parse_front_matter
from social_metadata import SITE_URL


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', nargs='?', type=Path,
                        default=ROOT / 'drafts/2026-10-23-mlb-clutch.md')
    source = parser.parse_args().source.resolve()
    output = source.with_suffix('.html')
    meta, body = parse_front_matter(source.read_text(encoding='utf-8'))
    rendered = markdown_to_html(body)
    # Keep canonical article links in Markdown; open sibling previews locally.
    if source.parent == ROOT / 'drafts':
        for sibling in source.parent.glob('*.md'):
            sibling_meta, _ = parse_front_matter(sibling.read_text(encoding='utf-8'))
            if sibling_meta.get('slug'):
                public = SITE_URL + '/blog/' + sibling_meta['slug'] + '.html'
                rendered = rendered.replace('href="' + html.escape(public, quote=True) + '"',
                    'href="' + html.escape(sibling.with_suffix('.html').name, quote=True) + '"')
    rendered = re.sub(r'(<table\b.*?</table>)',
        r'<div class="post-table" role="region" aria-label="표 (가로 스크롤)" tabindex="0">\1</div>',
        rendered, flags=re.S)
    # srcdoc keeps the chart readable directly from file:// and lets the parent
    # resize it without requesting cross-file DOM access or a local web server.
    def embed_chart(match):
        frame = match.group(0)
        reference = re.search(r'\bsrc="([^"]+)"', frame)
        assert reference, 'Preview chart requires a local src'
        path = (source.parent / reference.group(1)).resolve()
        assert path.is_relative_to(ROOT)
        chart = path.read_text(encoding='utf-8')
        return frame[:reference.start()] + 'data-chart="true" srcdoc="' + html.escape(chart, quote=True) + '"' + frame[reference.end():]
    rendered = re.sub(r'<iframe\b[^>]*></iframe>', embed_chart, rendered)
    title = html.escape(meta['title'])
    page = '''<!doctype html>
<html lang="ko"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex,nofollow">
<meta name="description" content="__DESCRIPTION__">
<title>__TITLE__ · 초안</title>
<link rel="stylesheet" href="../styles.css">
<style>
.blog-post main{max-width:1040px} .preview-label{font-size:14px;color:var(--muted);margin:0 0 18px}
.post-body iframe{display:block;margin:28px 0}.post-body .post-table table{min-width:580px}
@media print{.post-body iframe{display:none}.post-body .post-table{overflow:visible}.post-body table{min-width:0!important}}
</style></head>
<body class="blog-page blog-post">
<a class="skip-link" href="#main-content">본문으로 건너뛰기</a>
<main id="main-content" tabindex="-1">
<header class="blog-hero"><p class="preview-label">데이터분석 · 초안</p><h1>__TITLE__</h1>
<div class="post-meta"><time datetime="__DATE__">__DATE__</time><span>__PERIOD__</span></div></header>
<article class="post-body">__BODY__</article>
</main>
<script>
document.querySelectorAll('iframe[data-chart]').forEach(frame=>frame.addEventListener('load',()=>{
 const doc=frame.contentDocument;
 if(!doc?.body)return;
 const resize=()=>{const height=Math.ceil(doc.body.getBoundingClientRect().height)+8;if(Math.abs(frame.getBoundingClientRect().height-height)>2)frame.style.height=height+'px';};
 new ResizeObserver(()=>requestAnimationFrame(resize)).observe(doc.body);resize();
}));
</script></body></html>
'''.replace('__TITLE__', title).replace('__DESCRIPTION__',html.escape(meta.get('description',''))).replace('__DATE__',html.escape(meta['date'])).replace('__PERIOD__',html.escape(meta.get('analysis_period','2025·2026 MLB'))).replace('__BODY__',rendered)
    output.write_text(page, encoding='utf-8')
    print(output)


if __name__ == '__main__':
    main()

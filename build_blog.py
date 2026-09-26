from __future__ import annotations

import datetime as dt
import html
import os
import re
from pathlib import Path

from social_metadata import BLOG_DESCRIPTION, post_description, post_image, render_social_metadata

ROOT = Path(__file__).resolve().parent
POSTS_DIR = ROOT / "posts"
OUT_DIR = ROOT / "blog"

POSTS_DIR.mkdir(exist_ok=True)
OUT_DIR.mkdir(exist_ok=True)

FRONT_MATTER_RE = re.compile(r"^---\s*\r?\n(.*?)\r?\n---\s*\r?\n", re.S)
TAG_RE = re.compile(r"<[^>]+>")
DATE_FROM_STEM_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})-")
TITLE_PREFIX_RE = re.compile(r"^\s*\d+(?:\.\d+)*[\.)]?\s+")
LEGACY_DATE_HTML_RE = re.compile(r"^\d{4}-\d{2}-\d{2}-tistory-\d+\.html$")
MARKDOWN_LINK_RE = re.compile(r"\[([^\]\n]+)\]\((https?://[^\s)]+)\)")


def strip_html(text: str) -> str:
    return TAG_RE.sub(" ", text)


def categorize(title: str, desc: str, tags: str, body: str) -> str:
    hay = " ".join([title, desc, tags, strip_html(body)]).lower()
    if any(k in hay for k in ["ai", "llm", "gpt", "rag", "transformer", "langchain", "mistral", "qwen", "deepseek", "prompt"]):
        return "AI"
    if any(k in hay for k in ["경제", "금리", "물가", "환율", "주식", "채권", "인플레이션", "gdp", "거시", "시장"]):
        return "경제"
    if any(k in hay for k in ["데이터", "분석", "통계", "회귀", "모델", "ml", "머신러닝", "시각화", "pandas", "sql", "분포"]):
        return "데이터분석"
    return "AI"


def normalize_title(title: str) -> str:
    cleaned = TITLE_PREFIX_RE.sub("", title).strip()
    return cleaned or title.strip()


def clean_tistory_html(body: str) -> str:
    content = body.strip()

    # Keep only the main Tistory content area when present.
    main_start = content.find('<div class="contents_style">')
    if main_start != -1:
        content = content[main_start:]
        # Imported pages often append extra blocks after this marker.
        tail_markers = [
            "<!-- System - START -->",
            '<div class="container_postbtn',
            '<div class="another_category',
            '<div id="tt-body-page"',
        ]
        cut_positions = [content.find(m) for m in tail_markers if content.find(m) > 0]
        if cut_positions:
            content = content[: min(cut_positions)]

    # Fallback cleanup for cases without contents_style.
    fallback_markers = [
        '<div class="container_postbtn',
        '<div class="another_category',
        "' 카테고리의 다른 글",
    ]
    cut_positions = [content.find(m) for m in fallback_markers if content.find(m) > 0]
    if cut_positions:
        content = content[: min(cut_positions)]

    return content.strip()


def parse_front_matter(text: str) -> tuple[dict[str, str], str]:
    # Some imported markdown files contain UTF-8 BOM at the beginning.
    text = text.lstrip("\ufeff")
    match = FRONT_MATTER_RE.match(text)
    if not match:
        return {}, text
    raw = match.group(1)
    body = text[match.end():]
    data: dict[str, str] = {}
    for line in raw.splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        data[key.strip().lower()] = value.strip()
    return data, body


def extract_markdown_title_and_body(text: str) -> tuple[str | None, str]:
    lines = text.splitlines()
    first_content_idx = None
    for idx, line in enumerate(lines):
        if line.strip():
            first_content_idx = idx
            break

    if first_content_idx is None:
        return None, text

    first_line = lines[first_content_idx].strip()
    if not first_line.startswith("# "):
        return None, text

    title = first_line[2:].strip()
    remaining = lines[:first_content_idx] + lines[first_content_idx + 1 :]
    body = "\n".join(remaining).lstrip()
    return title or None, body


def infer_markdown_description(text: str) -> str:
    lines = text.splitlines()
    in_code = False
    parts: list[str] = []

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("```"):
            in_code = not in_code
            continue
        if in_code or not stripped:
            continue
        if stripped.startswith("# ") or stripped.startswith("## ") or stripped.startswith("### "):
            continue
        if stripped.startswith("- "):
            continue
        parts.append(stripped)
        if len(" ".join(parts)) >= 160:
            break

    summary = " ".join(parts).strip()
    return summary[:160].strip()


def demote_markdown_headings(text: str) -> str:
    lines = []
    for line in text.splitlines():
        if line.startswith("# "):
            lines.append("## " + line[2:])
        elif line.startswith("## "):
            lines.append("### " + line[3:])
        else:
            lines.append(line)
    return "\n".join(lines)


def slugify(value: str) -> str:
    value = value.strip().lower()
    value = re.sub(r"[^a-z0-9\-\s]", "", value)
    value = re.sub(r"\s+", "-", value)
    return value or "post"


def markdown_inline_to_html(text: str) -> str:
    parts = []
    cursor = 0

    for match in MARKDOWN_LINK_RE.finditer(text):
        parts.append(html.escape(text[cursor : match.start()]))
        label = html.escape(match.group(1))
        url = html.escape(match.group(2), quote=True)
        parts.append(
            f'<a href="{url}" target="_blank" rel="noopener noreferrer">{label}</a>'
        )
        cursor = match.end()

    parts.append(html.escape(text[cursor:]))
    return "".join(parts)


def markdown_to_html(text: str) -> str:
    lines = text.splitlines()
    out = []
    in_code = False
    in_list = False

    def close_list():
        nonlocal in_list
        if in_list:
            out.append("</ul>")
            in_list = False

    for line in lines:
        if line.strip().startswith("```"):
            if not in_code:
                close_list()
                out.append("<pre><code>")
                in_code = True
            else:
                out.append("</code></pre>")
                in_code = False
            continue

        if in_code:
            out.append(html.escape(line))
            continue

        if not line.strip():
            close_list()
            continue

        if line.startswith("### "):
            close_list()
            out.append(f"<h3>{markdown_inline_to_html(line[4:].strip())}</h3>")
        elif line.startswith("## "):
            close_list()
            out.append(f"<h2>{markdown_inline_to_html(line[3:].strip())}</h2>")
        elif line.startswith("# "):
            close_list()
            out.append(f"<h1>{markdown_inline_to_html(line[2:].strip())}</h1>")
        elif line.strip().startswith("- "):
            if not in_list:
                out.append("<ul>")
                in_list = True
            item = line.strip()[2:]
            out.append(f"<li>{markdown_inline_to_html(item)}</li>")
        else:
            close_list()
            out.append(f"<p>{markdown_inline_to_html(line.strip())}</p>")

    if in_code:
        out.append("</code></pre>")
    close_list()
    return "\n".join(out)


def build_post(post_path: Path) -> dict[str, str]:
    raw = post_path.read_text(encoding="utf-8")
    meta, body = parse_front_matter(raw)

    inferred_title = None
    if meta.get("format") != "html" and not meta.get("title"):
        inferred_title, body = extract_markdown_title_and_body(body)
        if inferred_title:
            body = demote_markdown_headings(body)

    raw_title = meta.get("title") or inferred_title or post_path.stem
    title = normalize_title(raw_title)
    stem_date = ""
    stem_match = DATE_FROM_STEM_RE.match(post_path.stem)
    if stem_match:
        stem_date = stem_match.group(1)
    date = meta.get("date") or stem_date or dt.date.today().isoformat()
    desc = meta.get("description") or ""
    slug = meta.get("slug") or slugify(post_path.stem)
    category = meta.get("category") or ""
    tags = meta.get("tags") or ""

    if meta.get("format") == "html":
        content_html = clean_tistory_html(body)
    else:
        if not desc:
            desc = infer_markdown_description(body)
        content_html = markdown_to_html(body)

    if not category:
        category = categorize(title, desc, tags, content_html)

    share_image, share_image_alt = post_image(meta)
    social_tags = render_social_metadata(
        title=title, description=post_description(meta, content_html, title),
        path=f"/blog/{slug}.html", page_type="article", published=date,
        image=share_image, image_alt=share_image_alt,
    )

    # Keep wide imported tables and code keyboard-scrollable within the article.
    content_html = re.sub(
        r"(<table\b.*?</table>)",
        r'<div class="post-table" role="region" aria-label="표 (가로 스크롤)" tabindex="0">\1</div>',
        content_html,
        flags=re.S | re.I,
    )
    content_html = re.sub(r"<pre(?=[\s>])", '<pre tabindex="0"', content_html)
    badge_label = "공지" if meta.get("pinned") == "true" else category
    category_badge = (
        f'<span class="post-badge">{html.escape(badge_label)}</span>' if badge_label else ""
    )
    tag_list = [tag.strip() for tag in tags.split(",") if tag.strip()]
    tags_html = (
        '<div class="post-tags" aria-label="태그">'
        + "".join(f'<span class="post-tag">{html.escape(tag)}</span>' for tag in tag_list)
        + '</div>'
        if tag_list else ""
    )

    page = f"""<!doctype html>
<html lang=\"ko\">
<head>
  <meta charset=\"utf-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
  <title>{html.escape(title)} | Blog</title>
  <meta name=\"description\" content=\"{html.escape(desc)}\" />
{social_tags}
  <link rel=\"preconnect\" href=\"https://fonts.googleapis.com\" />
  <link rel=\"preconnect\" href=\"https://fonts.gstatic.com\" crossorigin />
  <link href=\"https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;600;700&family=IBM+Plex+Sans:wght@300;400;500;600&display=swap\" rel=\"stylesheet\" />
  <link rel=\"stylesheet\" href=\"../styles.css\" />
</head>
<body class=\"blog-page blog-post\">
  <a class=\"skip-link\" href=\"#main-content\">본문으로 건너뛰기</a>
  <header class=\"nav\">
    <a class=\"logo\" href=\"../index.html\">Wonjin</a>
    <nav aria-label=\"주 메뉴\">
      <a href=\"../index.html\">Home</a>
      <a href=\"./index.html\" aria-current=\"location\">Blog</a>
      <a href=\"../index-en.html\" lang=\"en\" hreflang=\"en\" aria-label=\"영문 홈페이지\">EN</a>
    </nav>
  </header>

  <main id=\"main-content\" tabindex=\"-1\">
    <section class=\"blog-hero\">
      <h1>{html.escape(title)}</h1>
      <div class=\"post-meta\">
        <time datetime=\"{html.escape(date)}\">{html.escape(date)}</time>
        {category_badge}
      </div>
{tags_html}
    </section>

    <article class=\"post-body\">
      {content_html}
    </article>
    <nav class=\"post-back\" aria-label=\"글 탐색\">
      <a href=\"./index.html\">← 모든 글 보기</a>
    </nav>
  </main>

  <footer class=\"footer\">
    <span>© 2026 Wonjin Choi</span>
  </footer>
</body>
</html>
"""

    out_path = OUT_DIR / f"{slug}.html"
    out_path.write_text(page, encoding="utf-8")

    return {
        "title": title,
        "date": date,
        "description": desc,
        "slug": slug,
        "category": category,
        "tags": tags,
        "pinned": meta.get("pinned", "false"),
    }


def build_index(
    posts: list[dict[str, str]], notice: dict[str, str] | None = None,
) -> None:
    notice_html = ""
    if notice:
        notice_html = f'''
    <aside class="blog-notice" aria-label="블로그 공지">
      <a class="blog-notice-link" href="./{html.escape(notice['slug'], quote=True)}.html">
        <span class="blog-notice-label">공지</span>
        <span class="blog-notice-title">{html.escape(notice['title'])}</span>
        <span class="blog-notice-arrow" aria-hidden="true">→</span>
      </a>
    </aside>
'''

    category_counts: dict[str, int] = {}
    for post in posts:
        category = post.get("category", "").strip()
        if category:
            category_counts[category] = category_counts.get(category, 0) + 1

    sorted_categories = sorted(
        category_counts.items(), key=lambda item: (-item[1], item[0])
    )

    filters_html = "".join(
        f'<button type="button" class="filter-btn" data-filter="{html.escape(cat)}" '
        f'aria-pressed="false" aria-controls="post-list">{html.escape(cat)} '
        f'<span class="filter-count">{count}</span></button>'
        for cat, count in sorted_categories
    )

    script = """
  <script>
    const filterButtons = document.querySelectorAll('.filter-btn');
    const posts = document.querySelectorAll('.post-row');
    const yearGroups = document.querySelectorAll('.post-year-group');
    const filterStatus = document.querySelector('.filter-status');

    filterButtons.forEach((btn) => {
      btn.addEventListener('click', () => {
        filterButtons.forEach((b) => {
          const selected = b === btn;
          b.classList.toggle('active', selected);
          b.setAttribute('aria-pressed', String(selected));
        });
        const filter = btn.dataset.filter;
        let visibleCount = 0;
        posts.forEach((post) => {
          const category = post.dataset.category || '';
          post.hidden = filter !== 'all' && category !== filter;
          if (!post.hidden) visibleCount += 1;
        });
        yearGroups.forEach((group) => {
          group.hidden = !group.querySelector('.post-row:not([hidden])');
        });
        filterStatus.textContent = `${filter === 'all' ? '전체' : filter} 글 ${visibleCount}개`;
      });
    });
  </script>
"""

    items = []
    current_year = None
    for post in posts:
        date = post.get("date", "")
        year = date[:4] if len(date) >= 4 else "날짜 미상"
        category = post.get("category", "")

        if year != current_year:
            if current_year is not None:
                items.append("</section>")
            current_year = year
            year_id = f"year-{len(items)}"
            items.append(
                f'<section class="post-year-group" aria-labelledby="{year_id}">'
                f'<h2 class="post-year" id="{year_id}">{html.escape(year)}</h2>'
            )

        title = html.escape(post["title"])
        slug = html.escape(post["slug"])
        date_html = html.escape(date)
        category_attr = html.escape(category)
        items.append(
            f"""
            <article class=\"post-row\" data-category=\"{category_attr}\">
              <h3 class=\"post-title-row\">
                <a class=\"post-title\" href=\"./{slug}.html\">{title}</a>
              </h3>
              <time class=\"post-date\" datetime=\"{date_html}\">{date_html}</time>
            </article>"""
        )

    if current_year is not None:
        items.append("</section>")
    body = "\n".join(items) or "<p class=\"post-empty\">아직 글이 없습니다. 첫 글을 작성해 보세요.</p>"
    social_tags = render_social_metadata(
        title="Research & Notes · Wonjin", description=BLOG_DESCRIPTION, path="/blog/",
    )

    page = f"""<!doctype html>
<html lang=\"ko\">
<head>
  <meta charset=\"utf-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
  <title>Blog | Wonjin Choi</title>
  <meta name=\"description\" content=\"데이터 사이언티스트 최원진의 글 목록\" />
{social_tags}
  <link rel=\"preconnect\" href=\"https://fonts.googleapis.com\" />
  <link rel=\"preconnect\" href=\"https://fonts.gstatic.com\" crossorigin />
  <link href=\"https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;600;700&family=IBM+Plex+Sans:wght@300;400;500;600&display=swap\" rel=\"stylesheet\" />
  <link rel=\"stylesheet\" href=\"../styles.css\" />
</head>
<body class=\"blog-page blog-index\">
  <a class=\"skip-link\" href=\"#main-content\">본문으로 건너뛰기</a>
  <header class=\"nav\">
    <a class=\"logo\" href=\"../index.html\">Wonjin</a>
    <nav aria-label=\"주 메뉴\">
      <a href=\"../index.html\">Home</a>
      <a href=\"./index.html\" aria-current=\"page\">Blog</a>
      <a href=\"../index-en.html\" lang=\"en\" hreflang=\"en\" aria-label=\"영문 홈페이지\">EN</a>
    </nav>
  </header>

  <main id=\"main-content\" tabindex=\"-1\">
    <section class=\"blog-hero\">
      <h1>Research & Notes</h1>
      <p class=\"hero-desc\">데이터와 AI, 산업 트렌드에 대한 생각을 정리합니다.</p>
    </section>
{notice_html}
    <div class=\"post-filters\" role=\"group\" aria-label=\"글 카테고리\">
      <button type=\"button\" class=\"filter-btn active\" data-filter=\"all\" aria-pressed=\"true\" aria-controls=\"post-list\">전체 <span class=\"filter-count\">{len(posts)}</span></button>
      {filters_html}
    </div>
    <p class=\"filter-status\" role=\"status\">전체 글 {len(posts)}개</p>

    <section class=\"post-list\" id=\"post-list\" aria-label=\"글 목록\">
      {body}
    </section>
  </main>

  <footer class=\"footer\">
    <span>© 2026 Wonjin Choi</span>
  </footer>

{script}
</body>
</html>
"""

    (OUT_DIR / "index.html").write_text(page, encoding="utf-8")


def remove_legacy_html_files() -> None:
    for html_path in OUT_DIR.glob("*.html"):
        if LEGACY_DATE_HTML_RE.match(html_path.name):
            html_path.unlink(missing_ok=True)


def main() -> None:
    remove_legacy_html_files()
    posts = []
    for post_path in sorted(POSTS_DIR.glob("*.md")):
        posts.append(build_post(post_path))

    posts.sort(key=lambda p: p["date"], reverse=True)
    notice = next((post for post in posts if post["pinned"] == "true"), None)
    build_index([post for post in posts if post is not notice], notice=notice)


if __name__ == "__main__":
    main()

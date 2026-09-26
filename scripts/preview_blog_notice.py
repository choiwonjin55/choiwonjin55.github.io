#!/usr/bin/env python3
"""Preview the notice draft without adding it to the published blog.

Run: python3 scripts/preview_blog_notice.py --port 8000
Then open http://127.0.0.1:8000/blog/ . Restart after editing the draft.
"""

from __future__ import annotations

import argparse
import datetime as dt
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import re
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import build_blog


def build_preview(destination: Path, draft: Path) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    output = destination / "blog"
    output.mkdir()
    for name in ("index.html", "index-en.html", "styles.css", "app.js", "assets"):
        (destination / name).symlink_to(ROOT / name)
    (output / "assets").symlink_to(ROOT / "blog/assets", target_is_directory=True)

    raw = draft.read_text(encoding="utf-8")
    title, body = build_blog.extract_markdown_title_and_body(raw)
    if not title:
        raise ValueError("The notice draft must start with a Markdown H1 title.")

    # Map the draft's bold section label and recommended links to semantic headings.
    # Keep its wording and the original Markdown file intact.
    body = re.sub(r"^\*\*(.+)\*\*\s*$", r"## \1", body, flags=re.M)
    body = re.sub(r"^- \*\*(\[.+?\]\(https?://[^\s)]+\))\*\*[^\S\n]*$",
                  r"### \1", body, flags=re.M)
    content = build_blog.markdown_to_html(body)
    content = re.sub(
        r'<a href="https://choiwonjin55\.github\.io/blog/([^"/]+)" '
        r'target="_blank" rel="noopener noreferrer">',
        r'<a href="./\1">', content,
    )
    source = destination / "notice-source.md"
    source.write_text(
        f"---\ntitle: {title}\ndate: {dt.date.today().isoformat()}\n"
        "slug: blog-introduction\ncategory: 공지\nformat: html\n"
        "description: 블로그에서 다루는 주제와 처음 방문한 독자를 위한 대표 글 안내.\n"
        f"---\n{content}\n", encoding="utf-8",
    )

    original_output = build_blog.OUT_DIR
    try:
        build_blog.OUT_DIR = output
        posts = [build_blog.build_post(path) for path in sorted(build_blog.POSTS_DIR.glob("*.md"))]
        posts.sort(key=lambda post: post["date"], reverse=True)
        notice = build_blog.build_post(source)
        posts = [post for post in posts if post["slug"] != notice["slug"]]
        build_blog.build_index(posts, notice=notice)
    finally:
        build_blog.OUT_DIR = original_output
        source.unlink(missing_ok=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="blog-notice-preview-") as temp_dir:
        destination = Path(temp_dir)
        build_preview(destination, ROOT / "drafts/blog-introduction.md")
        handler = partial(SimpleHTTPRequestHandler, directory=str(destination))
        with ThreadingHTTPServer(("127.0.0.1", args.port), handler) as server:
            print(f"Preview: http://127.0.0.1:{args.port}/blog/", flush=True)
            print(f"Files: {destination}", flush=True)
            try:
                server.serve_forever()
            except KeyboardInterrupt:
                pass


if __name__ == "__main__":
    main()

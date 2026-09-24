#!/usr/bin/env python3
"""Validate the published metadata in homepage and generated blog HTML."""

from __future__ import annotations

import sys
from collections import defaultdict
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from build_blog import normalize_title, parse_front_matter
from social_metadata import (BLOG_DESCRIPTION, HOME_PAGES, SITE_NAME, SITE_URL,
                             image_info, post_description, post_image, site_url)


class HeadMetadata(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.in_head = False
        self.values = defaultdict(list)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "head":
            self.in_head = True
        if not self.in_head:
            return
        if tag == "meta":
            key = attrs.get("property") or attrs.get("name")
            if key:
                self.values[key].append(attrs.get("content", ""))
        elif tag == "link" and attrs.get("rel") == "canonical":
            self.values["canonical"].append(attrs.get("href", ""))

    def handle_endtag(self, tag):
        if tag == "head":
            self.in_head = False


REQUIRED = ("canonical", "og:title", "og:description", "og:type", "og:url",
            "og:site_name", "og:locale", "og:image", "og:image:type",
            "og:image:width", "og:image:height", "og:image:alt",
            "twitter:card", "twitter:title", "twitter:description",
            "twitter:image", "twitter:image:alt")


def check_page(path: Path, expected: dict[str, str]) -> list[str]:
    errors = []
    if not path.exists():
        return [f"{path.relative_to(ROOT)}: missing page"]
    parser = HeadMetadata()
    parser.feed(path.read_text(encoding="utf-8"))
    values = parser.values
    for key in REQUIRED:
        if len(values[key]) != 1 or not values[key][0].strip():
            errors.append(f"{key}: expected exactly one nonempty tag")
    single = {key: vals[0] for key, vals in values.items() if len(vals) == 1}
    for key, value in expected.items():
        if single.get(key) != value:
            errors.append(f"{key}: expected {value!r}, got {single.get(key)!r}")
    for left, right in [("canonical", "og:url"), ("twitter:title", "og:title"),
                        ("twitter:description", "og:description"),
                        ("twitter:image", "og:image"), ("twitter:image:alt", "og:image:alt")]:
        if single.get(left) != single.get(right):
            errors.append(f"{left} does not match {right}")
    if single.get("og:site_name") != SITE_NAME or single.get("twitter:card") != "summary_large_image":
        errors.append("site name or card type differs from shared settings")
    if len(single.get("og:description", "")) > 160:
        errors.append("description exceeds the project limit of 160 characters")
    for key in ("og:url", "og:image", "canonical"):
        if not single.get(key, "").startswith(SITE_URL + "/"):
            errors.append(f"{key}: expected a public HTTPS URL on this site")
    try:
        image = single.get("og:image", "").removeprefix(SITE_URL)
        mime, width, height = image_info(image)
        if (single.get("og:image:type"), single.get("og:image:width"), single.get("og:image:height")) != (mime, str(width), str(height)):
            errors.append("image format/dimensions do not match the file")
    except (ValueError, OSError) as exc:
        errors.append(str(exc))
    return [f"{path.relative_to(ROOT)}: {error}" for error in errors]


def main() -> int:
    from social_metadata import DEFAULT_IMAGE, DEFAULT_IMAGE_ALT, summarize
    from build_blog import clean_tistory_html, markdown_to_html

    pages = []
    for filename, info in HOME_PAGES.items():
        pages.append((ROOT / filename, {
            "og:title": info["title"], "og:description": summarize(info["description"]),
            "og:url": site_url(info["path"]), "og:type": "website", "og:locale": info["locale"],
            "og:image": site_url(info["image"]), "og:image:alt": info["image_alt"],
        }))
    pages.append((ROOT / "blog/index.html", {
        "og:title": "Research & Notes · Wonjin", "og:description": BLOG_DESCRIPTION,
        "og:url": site_url("/blog/"), "og:type": "website", "og:locale": "ko_KR",
        "og:image": site_url(DEFAULT_IMAGE), "og:image:alt": DEFAULT_IMAGE_ALT,
    }))
    for source in sorted((ROOT / "posts").glob("*.md")):
        meta, body = parse_front_matter(source.read_text(encoding="utf-8"))
        title = normalize_title(meta["title"])
        content = clean_tistory_html(body) if meta.get("format") == "html" else markdown_to_html(body)
        image, alt = post_image(meta)
        pages.append((ROOT / "blog" / (meta["slug"] + ".html"), {
            "og:title": title, "og:description": post_description(meta, content, title),
            "og:url": site_url(f'/blog/{meta["slug"]}.html'), "og:type": "article",
            "og:locale": "ko_KR", "article:published_time": meta["date"],
            "og:image": site_url(image), "og:image:alt": alt,
        }))
    errors = [error for path, expected in pages for error in check_page(path, expected)]
    for error in errors:
        print(f"ERROR: {error}")
    print(f"Checked social metadata on {len(pages)} pages: {len(errors)} error(s).")
    return bool(errors)


if __name__ == "__main__":
    sys.exit(main())

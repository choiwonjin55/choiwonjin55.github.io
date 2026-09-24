"""Shared, dependency-free metadata for static homepage and blog previews."""

from __future__ import annotations

import html
import re
import struct
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import quote, unquote, urlsplit

ROOT = Path(__file__).resolve().parent
SITE_URL = "https://choiwonjin55.github.io"
SITE_NAME = "Wonjin"
DEFAULT_IMAGE = "/assets/og/blog-v1.png"
DEFAULT_IMAGE_ALT = "Wonjin — Research & Notes. 데이터와 AI, 그리고 일상의 기록."
BLOG_DESCRIPTION = "데이터 분석과 AI, 경제, 일상에 관한 생각을 기록합니다."
HOME_PAGES = {
    "index.html": {
        "title": "Wonjin · 데이터 사이언티스트 최원진",
        "description": "데이터의 맥락을 이해하고 가설을 검증해 운영 가능한 AI 시스템을 만듭니다. 프로젝트 경험과 데이터 분석, AI에 관한 기록을 공유합니다.",
        "path": "/", "locale": "ko_KR",
        "image": "/assets/og/home-ko-v1.png",
        "image_alt": "Wonjin — 데이터 사이언티스트 최원진. 데이터의 맥락을 읽고, 작동하는 AI를 만듭니다.",
    },
    "index-en.html": {
        "title": "Wonjin Choi · Data Scientist & AI Engineer",
        "description": "I build operational AI systems through data analysis and hypothesis testing. Explore my projects and notes on data and AI.",
        "path": "/index-en.html", "locale": "en_US",
        "image": "/assets/og/home-en-v1.png",
        "image_alt": "Wonjin — Data Scientist & AI Engineer. From data and hypotheses to working AI systems.",
    },
}


class ReadableText(HTMLParser):
    """Extract prose without code, table contents, scripts or styling."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.paragraphs: list[str] = []
        self.current: list[str] | None = None
        self.blocked = 0

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style", "pre", "code", "table"}:
            self.blocked += 1
        if not self.blocked:
            if tag == "p":
                self.current = []
            if tag in {"p", "br", "div", "li", "h1", "h2", "h3"}:
                self.handle_data(" ")

    def handle_endtag(self, tag):
        if tag in {"script", "style", "pre", "code", "table"}:
            self.blocked = max(0, self.blocked - 1)
        elif tag == "p" and self.current is not None:
            paragraph = " ".join("".join(self.current).split())
            if paragraph:
                self.paragraphs.append(paragraph)
            self.current = None
        if tag in {"p", "div", "li", "h1", "h2", "h3"}:
            self.handle_data(" ")

    def handle_data(self, data):
        if not self.blocked:
            self.parts.append(data)
            if self.current is not None:
                self.current.append(data)


def plain_text(value: str) -> str:
    parser = ReadableText()
    parser.feed(value)
    return " ".join("".join(parser.parts).split())


def summarize(value: str, limit: int = 160) -> str:
    text = plain_text(value)
    if len(text) <= limit:
        return text
    excerpt = text[:limit - 1]
    endings = list(re.finditer(r"[.!?。](?=\s|$)", excerpt))
    if endings and endings[-1].end() >= limit // 2:
        excerpt = excerpt[:endings[-1].end()]
    elif excerpt.rfind(" ") >= limit * 2 // 3:
        excerpt = excerpt[:excerpt.rfind(" ")]
    return excerpt.rstrip(" .…") + "…"


def post_description(meta: dict[str, str], content_html: str, title: str) -> str:
    for field in ("og_description", "description"):
        value = summarize(meta.get(field, ""))
        if value:
            return value
    parser = ReadableText()
    parser.feed(content_html)
    return summarize(parser.paragraphs[0] if parser.paragraphs else f"{title}. {BLOG_DESCRIPTION}")


def site_url(path: str) -> str:
    parsed = urlsplit(path)
    decoded = unquote(parsed.path)
    if (not path.startswith("/") or parsed.scheme or parsed.netloc
            or parsed.query or parsed.fragment or "\\" in decoded
            or any(p in {".", ".."} for p in decoded.split("/"))):
        raise ValueError(f"Expected a site-root path without traversal/query/fragment: {path!r}")
    return SITE_URL + quote(decoded, safe="/-._~")


def image_info(path: str) -> tuple[str, int, int]:
    """Read PNG dimensions; published preview images intentionally use PNG only."""
    site_url(path)
    asset = (ROOT / unquote(urlsplit(path).path).lstrip("/")).resolve()
    if not asset.is_relative_to(ROOT):
        raise ValueError(f"Image must be inside the site: {path}")
    if asset.suffix.lower() != ".png":
        raise ValueError(f"Share images must be PNG files: {path}")
    with asset.open("rb") as handle:
        header = handle.read(24)
    if len(header) != 24 or header[:8] != b"\x89PNG\r\n\x1a\n" or header[12:16] != b"IHDR":
        raise ValueError(f"Invalid PNG image: {path}")
    width, height = struct.unpack(">II", header[16:24])
    if not width or not height:
        raise ValueError(f"Invalid PNG dimensions: {path}")
    return "image/png", width, height


def post_image(meta: dict[str, str]) -> tuple[str, str]:
    path = meta.get("og_image", "").strip()
    if not path:
        return DEFAULT_IMAGE, DEFAULT_IMAGE_ALT
    alt = plain_text(meta.get("og_image_alt", ""))
    if not alt:
        raise ValueError("og_image_alt is required when og_image is specified")
    return path, alt


def render_social_metadata(*, title: str, description: str, path: str,
                           locale: str = "ko_KR", image: str = DEFAULT_IMAGE,
                           image_alt: str = DEFAULT_IMAGE_ALT,
                           page_type: str = "website", published: str = "") -> str:
    url = site_url(path)
    image_url = site_url(image)
    mime, width, height = image_info(image)
    description = summarize(description)
    values = {
        "og:title": title, "og:description": description,
        "og:type": page_type, "og:url": url, "og:site_name": SITE_NAME,
        "og:locale": locale, "og:image": image_url,
        "og:image:type": mime, "og:image:width": str(width),
        "og:image:height": str(height), "og:image:alt": image_alt,
    }
    if page_type == "article" and published:
        values["article:published_time"] = published
    lines = [f'  <link rel="canonical" href="{html.escape(url, quote=True)}" />']
    lines.extend(f'  <meta property="{key}" content="{html.escape(value, quote=True)}" />'
                 for key, value in values.items())
    card = {"twitter:card": "summary_large_image", "twitter:title": title,
            "twitter:description": description, "twitter:image": image_url,
            "twitter:image:alt": image_alt}
    lines.extend(f'  <meta name="{key}" content="{html.escape(value, quote=True)}" />'
                 for key, value in card.items())
    return "\n".join(lines)

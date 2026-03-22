from __future__ import annotations

import datetime as dt
import re
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

BASE = "https://changgeun-sql.tistory.com"
CATEGORY_URLS = ["https://changgeun-sql.tistory.com/category"]
CUTOFF_DATE = dt.date(2024, 8, 1)
OUT_DIR = Path(__file__).resolve().parent / "posts"
OUT_DIR.mkdir(exist_ok=True)

HEADERS = {"User-Agent": "Mozilla/5.0"}


def fetch(url: str) -> BeautifulSoup:
    resp = requests.get(url, headers=HEADERS, timeout=20)
    resp.raise_for_status()
    return BeautifulSoup(resp.text, "html.parser")


def is_post_url(url: str) -> bool:
    parsed = urlparse(url)
    if not parsed.netloc.endswith("tistory.com"):
        return False
    if parsed.fragment:
        return False
    return re.fullmatch(r"/\d+", parsed.path or "") is not None


def collect_category_pages(category_url: str) -> list[str]:
    pages = {category_url}
    queue = [category_url]
    category_path = urlparse(category_url).path

    while queue:
        url = queue.pop()
        soup = fetch(url)
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if category_path not in href:
                continue
            full = urljoin(BASE, href)
            if full not in pages:
                pages.add(full)
                queue.append(full)
    return sorted(pages)


def collect_post_links(category_url: str) -> list[str]:
    links: list[str] = []
    for page in collect_category_pages(category_url):
        soup = fetch(page)
        for a in soup.find_all("a", href=True):
            href = urljoin(BASE, a["href"])
            parsed = urlparse(href)
            normalized = parsed._replace(query="", fragment="").geturl()
            if is_post_url(normalized) and normalized not in links:
                links.append(normalized)
    return links


def clean_html(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")

    for img in soup.find_all("img"):
        src = img.get("src") or img.get("data-original") or img.get("data-src")
        if src:
            if src.startswith("//"):
                src = "https:" + src
            elif src.startswith("/"):
                src = urljoin(BASE, src)
            img["src"] = src

    for tag in soup.find_all(["script", "style"]):
        tag.decompose()

    return str(soup)


def parse_date(value: str | None) -> dt.date:
    if not value:
        return dt.date.today()
    try:
        parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed.date()
    except ValueError:
        return dt.date.today()


def extract_post(url: str) -> dict[str, str | dt.date]:
    soup = fetch(url)

    title = None
    meta_title = soup.find("meta", property="og:title")
    if meta_title and meta_title.get("content"):
        title = meta_title["content"].strip()
    if not title:
        h1 = soup.find(["h1", "h2", "h3"])
        title = h1.get_text(strip=True) if h1 else "Untitled"

    meta_pub = soup.find("meta", property="article:published_time")
    date_obj = parse_date(meta_pub["content"] if meta_pub and meta_pub.get("content") else None)

    meta_desc = soup.find("meta", property="og:description")
    description = meta_desc["content"].strip() if meta_desc and meta_desc.get("content") else ""

    category = ""
    meta_section = soup.find("meta", property="article:section")
    if meta_section and meta_section.get("content"):
        category = meta_section["content"].strip()

    tags: list[str] = []
    for tag_meta in soup.find_all("meta", property="article:tag"):
        if tag_meta.get("content"):
            tags.append(tag_meta["content"].strip())
    if not tags:
        meta_keywords = soup.find("meta", attrs={"name": "keywords"})
        if meta_keywords and meta_keywords.get("content"):
            tags = [t.strip() for t in meta_keywords["content"].split(",") if t.strip()]

    content_el = soup.select_one("div.tt_article_useless_p_margin")
    if not content_el:
        content_el = soup.select_one("div.article-view")
    if not content_el:
        content_el = soup.select_one("div.entry-content")
    if not content_el:
        raise RuntimeError(f"content not found for {url}")

    content_html = clean_html(content_el.decode_contents())

    if not description:
        text_only = content_el.get_text(" ", strip=True)
        description = text_only[:160]

    post_id = urlparse(url).path.strip("/")
    slug = f"tistory-{post_id}"

    return {
        "title": title,
        "date": date_obj,
        "description": description,
        "slug": slug,
        "body": content_html,
        "tags": ", ".join(tags),
        "category": category,
    }


def write_post(data: dict[str, str | dt.date]) -> Path:
    date_obj = data["date"]
    date_str = date_obj.isoformat() if isinstance(date_obj, dt.date) else str(date_obj)
    filename = f"{date_str}-{data['slug']}.md"
    path = OUT_DIR / filename

    front_matter = (
        "---\n"
        f"title: {data['title']}\n"
        f"date: {date_str}\n"
        f"description: {data['description']}\n"
        f"slug: {data['slug']}\n"
        f"category: {data['category']}\n"
        f"tags: {data['tags']}\n"
        "format: html\n"
        "---\n\n"
    )

    path.write_text(front_matter + str(data["body"]).strip() + "\n", encoding="utf-8")
    return path


def purge_existing() -> None:
    for path in OUT_DIR.glob("*tistory-*.md"):
        path.unlink()


def main() -> None:
    purge_existing()

    all_links: list[str] = []
    for category_url in CATEGORY_URLS:
        all_links.extend(collect_post_links(category_url))

    seen = set()
    filtered = 0
    for url in all_links:
        if url in seen:
            continue
        seen.add(url)
        data = extract_post(url)
        date_obj = data["date"]
        if isinstance(date_obj, dt.date) and date_obj < CUTOFF_DATE:
            continue
        filtered += 1
        write_post(data)

    print(f"Imported {filtered} posts (since {CUTOFF_DATE.isoformat()})")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Validate blog source metadata and optionally generated HTML alignment."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
POSTS_DIR = ROOT / "posts"
BLOG_DIR = ROOT / "blog"

FRONT_MATTER_RE = re.compile(r"^---\s*\r?\n(.*?)\r?\n---\s*\r?\n", re.S)
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
HTML_SRC_RE = re.compile(r"\bsrc\s*=\s*[\"']([^\"']+)[\"']", re.I)
MARKDOWN_IMAGE_RE = re.compile(r"!\[[^\]]*\]\(([^)]+)\)")
REQUIRED_FIELDS = ("title", "date", "slug", "format")
ALLOWED_FORMATS = {"markdown", "html"}
ALLOWED_CATEGORIES = {"AI", "경제", "데이터분석", "생각"}


def parse_front_matter(text: str) -> tuple[dict[str, str], str]:
    text = text.lstrip("\ufeff")
    match = FRONT_MATTER_RE.match(text)
    if not match:
        return {}, text

    metadata: dict[str, str] = {}
    for line in match.group(1).splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        metadata[key.strip().lower()] = value.strip()
    return metadata, text[match.end() :]


def local_asset_path(raw_path: str) -> Path | None:
    path = raw_path.strip().split("#", 1)[0].split("?", 1)[0]
    if not path or path.startswith(("http://", "https://", "data:", "//", "#")):
        return None
    if path.startswith("/"):
        return ROOT / path.lstrip("/")
    return (BLOG_DIR / path).resolve()


def validate_sources() -> tuple[list[str], list[str], set[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    slugs: dict[str, Path] = {}
    legacy_empty = {"description": 0, "category": 0, "tags": 0}

    for post_path in sorted(POSTS_DIR.glob("*.md")):
        metadata, body = parse_front_matter(post_path.read_text(encoding="utf-8"))
        label = post_path.relative_to(ROOT)

        if not metadata:
            errors.append(f"{label}: missing front matter")
            continue

        missing = [field for field in REQUIRED_FIELDS if field not in metadata]
        if missing:
            errors.append(f"{label}: missing fields: {', '.join(missing)}")
        for field in ("title", "date", "slug", "format"):
            if field in metadata and not metadata[field]:
                errors.append(f"{label}: {field} is empty")

        date = metadata.get("date", "")
        if not DATE_RE.fullmatch(date):
            errors.append(f"{label}: invalid date: {date or '<empty>'}")
        elif not post_path.name.startswith(f"{date}-"):
            errors.append(f"{label}: filename date does not match front matter date {date}")

        slug = metadata.get("slug", "")
        if not SLUG_RE.fullmatch(slug):
            errors.append(f"{label}: slug must be non-empty ASCII kebab-case: {slug or '<empty>'}")
        elif slug in slugs:
            other = slugs[slug].relative_to(ROOT)
            errors.append(f"{label}: duplicate slug {slug!r}; first used by {other}")
        else:
            slugs[slug] = post_path

        post_format = metadata.get("format", "")
        if post_format not in ALLOWED_FORMATS:
            errors.append(f"{label}: format must be one of {sorted(ALLOWED_FORMATS)}")

        is_legacy_import = "tistory" in post_path.stem
        for field in ("description", "category", "tags"):
            if metadata.get(field, ""):
                continue
            if is_legacy_import:
                legacy_empty[field] += 1
            else:
                errors.append(f"{label}: {field} is missing or empty")

        category = metadata.get("category", "")
        if category and category not in ALLOWED_CATEGORIES:
            warnings.append(f"{label}: category {category!r} is outside the current category set")

        if post_format == "markdown":
            if body.count("```") % 2:
                errors.append(f"{label}: unclosed fenced code block")
            if MARKDOWN_IMAGE_RE.search(body):
                errors.append(f"{label}: markdown images are unsupported; use format: html")

        if post_format == "html":
            for raw_src in HTML_SRC_RE.findall(body):
                asset_path = local_asset_path(raw_src)
                if asset_path is not None and not asset_path.exists():
                    warnings.append(f"{label}: referenced local asset does not exist: {raw_src}")

    for field, count in legacy_empty.items():
        if count:
            warnings.append(
                f"{count} legacy Tistory post(s) have an empty or missing {field} field"
            )

    return errors, warnings, set(slugs)


def validate_generated(slugs: set[str]) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    expected = {"index", *slugs}
    actual = {path.stem for path in BLOG_DIR.glob("*.html")}

    for missing in sorted(expected - actual):
        errors.append(f"blog/{missing}.html: missing generated page")
    for orphan in sorted(actual - expected):
        warnings.append(f"blog/{orphan}.html: no matching posts/*.md source")

    return errors, warnings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--generated",
        action="store_true",
        help="also require generated pages for every source slug and report orphan HTML",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="treat warnings as failures",
    )
    args = parser.parse_args()

    errors, warnings, slugs = validate_sources()
    if args.generated:
        generated_errors, generated_warnings = validate_generated(slugs)
        errors.extend(generated_errors)
        warnings.extend(generated_warnings)

    for warning in warnings:
        print(f"WARNING: {warning}")
    for error in errors:
        print(f"ERROR: {error}")

    print(
        f"Checked {len(slugs)} posts: "
        f"{len(errors)} error(s), {len(warnings)} warning(s)."
    )
    return 1 if errors or (args.strict and warnings) else 0


if __name__ == "__main__":
    sys.exit(main())

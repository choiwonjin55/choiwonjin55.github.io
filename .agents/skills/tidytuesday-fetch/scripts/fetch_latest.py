from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import re
import shutil
import sys
import unicodedata
from pathlib import Path
from typing import Iterable
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen


REPO_API = "https://api.github.com/repos/rfordatascience/tidytuesday/contents"
RAW_BASE = "https://raw.githubusercontent.com/rfordatascience/tidytuesday/main"
USER_AGENT = "homepage-tidytuesday-fetch/1.0"
WEEK_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def request_json(url: str) -> object:
    req = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/vnd.github+json"})
    with urlopen(req) as resp:
        return json.load(resp)


def request_text(url: str) -> str:
    req = Request(url, headers={"User-Agent": USER_AGENT})
    with urlopen(req) as resp:
        return resp.read().decode("utf-8")


def request_bytes(url: str) -> bytes:
    req = Request(url, headers={"User-Agent": USER_AGENT})
    with urlopen(req) as resp:
        return resp.read()


def slugify(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    ascii_only = normalized.encode("ascii", "ignore").decode("ascii")
    ascii_only = ascii_only.lower().strip()
    ascii_only = re.sub(r"[^a-z0-9\s-]", "", ascii_only)
    ascii_only = re.sub(r"\s+", "-", ascii_only)
    ascii_only = re.sub(r"-{2,}", "-", ascii_only).strip("-")
    return ascii_only or "week"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fetch a TidyTuesday week into a structured local workspace.")
    parser.add_argument("--week", help="Week to fetch in YYYY-MM-DD format. Defaults to the latest released week.")
    parser.add_argument(
        "--target-date",
        default=dt.date.today().isoformat(),
        help="Use this date when choosing the latest released week. Default: today.",
    )
    parser.add_argument(
        "--out-root",
        default="data/tidytuesday",
        help="Output root for fetched datasets. Default: data/tidytuesday",
    )
    parser.add_argument("--force", action="store_true", help="Overwrite an existing local copy.")
    return parser.parse_args()


def parse_iso_date(value: str) -> dt.date:
    try:
        return dt.date.fromisoformat(value)
    except ValueError as exc:
        raise SystemExit(f"Invalid date: {value}") from exc


def list_year_directories() -> list[str]:
    payload = request_json(f"{REPO_API}/data")
    years = []
    for item in payload:
        if item.get("type") != "dir":
            continue
        name = item.get("name", "")
        if name.isdigit() and len(name) == 4:
            years.append(name)
    return sorted(years, reverse=True)


def list_week_directories(year: str) -> list[str]:
    payload = request_json(f"{REPO_API}/data/{quote(year)}")
    weeks = []
    for item in payload:
        if item.get("type") != "dir":
            continue
        name = item.get("name", "")
        if WEEK_RE.match(name):
            weeks.append(name)
    return sorted(weeks, reverse=True)


def find_latest_week(target_date: dt.date) -> str:
    for year in list_year_directories():
        for week_name in list_week_directories(year):
            week_date = parse_iso_date(week_name)
            if week_date <= target_date:
                return week_name
    raise SystemExit("Could not find a released TidyTuesday week.")


def list_week_files(week: str) -> list[dict[str, str]]:
    year = week[:4]
    payload = request_json(f"{REPO_API}/data/{quote(year)}/{quote(week)}")
    files: list[dict[str, str]] = []
    for item in payload:
        if item.get("type") != "file":
            continue
        name = item["name"]
        download_url = item.get("download_url")
        html_url = item.get("html_url")
        if not download_url:
            continue
        files.append({"name": name, "download_url": download_url, "html_url": html_url or ""})
    return sorted(files, key=lambda item: item["name"])


def extract_title(readme_text: str) -> str:
    for line in readme_text.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return "TidyTuesday Week"


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def write_bytes(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)


def iter_csv_rows(path: Path, delimiter: str) -> Iterable[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle, delimiter=delimiter)
        for row in reader:
            yield row


def profile_delimited_file(path: Path, delimiter: str) -> dict[str, object]:
    rows = list(iter_csv_rows(path, delimiter))
    fieldnames: list[str] = []
    if rows:
        fieldnames = list(rows[0].keys())
    else:
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle, delimiter=delimiter)
            fieldnames = reader.fieldnames or []

    preview_path = path.parent.parent / "preview" / f"{path.stem}.head.csv"
    preview_path.parent.mkdir(parents=True, exist_ok=True)
    preview_rows = rows[:5]
    with preview_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        if fieldnames:
            writer.writeheader()
            writer.writerows(preview_rows)

    column_profiles = []
    for field in fieldnames:
        values = [row.get(field, "") for row in rows]
        non_empty = [value for value in values if value not in ("", None)]
        examples = []
        seen = set()
        for value in non_empty:
            if value in seen:
                continue
            seen.add(value)
            examples.append(value)
            if len(examples) >= 5:
                break
        column_profiles.append(
            {
                "name": field,
                "missing": len(values) - len(non_empty),
                "examples": examples,
            }
        )

    return {
        "type": "delimited",
        "rows": len(rows),
        "columns": fieldnames,
        "delimiter": delimiter,
        "preview_file": str(preview_path),
        "column_profiles": column_profiles,
    }


def build_notes(week_dir: Path, week: str, title: str, readme_url: str, files_meta: list[dict[str, object]]) -> None:
    summary_lines = [
        f"# {title}",
        "",
        f"- Week: `{week}`",
        f"- Source README: `{readme_url}`",
        f"- Local folder: `{week_dir}`",
        "",
        "## Files",
    ]
    for item in files_meta:
        line = f"- `{item['name']}`"
        if item.get("rows") is not None:
            line += f": {item['rows']} rows"
        summary_lines.append(line)
    write_text(week_dir / "notes" / "summary.md", "\n".join(summary_lines) + "\n")

    column_lines = [f"# {title} Columns", ""]
    for item in files_meta:
        if item.get("type") != "csv" and item.get("type") != "tsv":
            continue
        column_lines.append(f"## {item['name']}")
        column_lines.append("")
        column_lines.append(f"- Rows: `{item['rows']}`")
        column_lines.append(f"- Preview: `{item['preview_file']}`")
        column_lines.append("")
        for col in item.get("column_profiles", []):
            examples = ", ".join(f"`{example}`" for example in col["examples"]) or "(no example values)"
            column_lines.append(f"- `{col['name']}`: missing `{col['missing']}`, examples {examples}")
        column_lines.append("")
    write_text(week_dir / "notes" / "columns.md", "\n".join(column_lines).strip() + "\n")


def main() -> int:
    args = parse_args()
    target_date = parse_iso_date(args.target_date)
    week = args.week or find_latest_week(target_date)
    week_date = parse_iso_date(week)
    if week_date > target_date:
        raise SystemExit(f"Week {week} is in the future relative to target date {target_date.isoformat()}.")

    files = list_week_files(week)
    readme_entry = next((item for item in files if item["name"].lower() == "readme.md"), None)
    if readme_entry is None:
        raise SystemExit(f"No readme.md found for week {week}.")

    readme_text = request_text(readme_entry["download_url"])
    title = extract_title(readme_text)
    slug = slugify(title)

    out_root = Path(args.out_root)
    week_dir = out_root / week[:4] / f"{week}-{slug}"
    if week_dir.exists():
        if args.force:
            shutil.rmtree(week_dir)
        else:
            raise SystemExit(f"{week_dir} already exists. Use --force to overwrite.")

    week_dir.mkdir(parents=True, exist_ok=True)
    (week_dir / "raw").mkdir(exist_ok=True)
    (week_dir / "preview").mkdir(exist_ok=True)
    (week_dir / "notes").mkdir(exist_ok=True)

    write_text(week_dir / "readme.md", readme_text)

    source_urls = [
        f"repo=https://github.com/rfordatascience/tidytuesday",
        f"readme={readme_entry['html_url']}",
    ]
    files_meta: list[dict[str, object]] = []

    for entry in files:
        name = entry["name"]
        if name.lower() == "readme.md":
            continue
        destination = week_dir / "raw" / name
        content = request_bytes(entry["download_url"])
        write_bytes(destination, content)
        source_urls.append(f"{name}={entry['download_url']}")

        suffix = destination.suffix.lower()
        file_meta: dict[str, object] = {
            "name": name,
            "path": str(destination),
            "source_url": entry["download_url"],
            "type": suffix.lstrip(".") or "file",
        }
        if suffix in {".csv", ".tsv"}:
            delimiter = "," if suffix == ".csv" else "\t"
            profile = profile_delimited_file(destination, delimiter)
            file_meta.update(
                {
                    "rows": profile["rows"],
                    "columns": profile["columns"],
                    "preview_file": profile["preview_file"],
                    "column_profiles": profile["column_profiles"],
                }
            )
        files_meta.append(file_meta)

    write_text(week_dir / "source_urls.txt", "\n".join(source_urls) + "\n")
    build_notes(week_dir, week, title, readme_entry["html_url"], files_meta)

    manifest = {
        "week": week,
        "title": title,
        "slug": slug,
        "target_date": target_date.isoformat(),
        "local_root": str(week_dir),
        "source": {
            "repository": "https://github.com/rfordatascience/tidytuesday",
            "readme": readme_entry["html_url"],
        },
        "files": [
            {
                key: value
                for key, value in item.items()
                if key not in {"column_profiles"}
            }
            for item in files_meta
        ],
    }
    write_text(week_dir / "manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")

    print(str(week_dir))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (HTTPError, URLError) as exc:
        print(f"Network error: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc

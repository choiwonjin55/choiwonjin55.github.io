from __future__ import annotations

import argparse
import json
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Initialize viz folders for a fetched TidyTuesday week.")
    parser.add_argument("week_dir", help="Week folder under data/tidytuesday/")
    parser.add_argument(
        "--asset-root",
        default="blog/assets/tidytuesday",
        help="Root folder for final public chart assets.",
    )
    return parser.parse_args()


def read_manifest(week_dir: Path) -> dict:
    manifest_path = week_dir / "manifest.json"
    if not manifest_path.exists():
        raise SystemExit(f"manifest.json not found in {week_dir}")
    return json.loads(manifest_path.read_text(encoding="utf-8"))


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def main() -> int:
    args = parse_args()
    week_dir = Path(args.week_dir)
    manifest = read_manifest(week_dir)

    viz_dir = week_dir / "viz"
    code_dir = viz_dir / "code"
    figures_dir = viz_dir / "figures"
    notes_dir = viz_dir / "notes"
    asset_dir = Path(args.asset_root) / week_dir.name

    for path in [viz_dir, code_dir, figures_dir, notes_dir, asset_dir]:
        ensure_dir(path)

    plan_path = notes_dir / "chart-plan.md"
    if not plan_path.exists():
        content = "\n".join(
            [
                f"# {manifest.get('title', 'TidyTuesday Week')} Chart Plan",
                "",
                f"- Week: `{manifest.get('week', '')}`",
                f"- Local folder: `{week_dir}`",
                f"- Final assets: `{asset_dir}`",
                "",
                "## Main Chart",
                "",
                "- Question:",
                "- Dataset:",
                "- Columns:",
                "- Chart type:",
                "- Expected insight:",
                "- Output file:",
                "",
                "## Secondary Charts",
                "",
                "- Chart 2:",
                "- Chart 3:",
                "",
            ]
        )
        plan_path.write_text(content + "\n", encoding="utf-8")

    print(str(viz_dir))
    print(str(asset_dir))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

---
name: tidytuesday-fetch
description: Fetch the latest or a specified TidyTuesday week into this repo's local data workspace. Use when finding the newest released week, downloading the README and raw files from the official TidyTuesday repo, generating previews and metadata under data/tidytuesday/, and handing off a structured week folder for later analysis or blog writing.
---

# Fetch TidyTuesday Week

## Overview

Use this skill before analysis or blog writing when the dataset is not already saved locally.
The canonical local workspace is `data/tidytuesday/YYYY/YYYY-MM-DD-slug/`.

Keep responsibilities split:

- `tidytuesday-fetch`: obtain and profile the dataset locally
- `tidytuesday-post`: turn a chosen week into a blog post
- `homepage-build` or `publish-blog-post`: refresh generated blog output

## Subagents

Use subagents freely when parallel work will help.

Good delegation targets:

- compare recent candidate weeks in parallel before choosing one
- inspect multiple raw files at once after fetching
- generate independent chart-angle ideas from the saved `manifest.json` and `notes/`
- review the fetched week folder for missing files or weak summaries

## Local Folder Contract

Each fetched week should end up in a folder like:

```text
data/tidytuesday/2026/2026-03-17-salmonid-mortality/
  manifest.json
  readme.md
  source_urls.txt
  raw/
  preview/
  notes/
```

Rules:

- Save original downloaded files in `raw/` without rewriting them.
- Save small machine-generated previews in `preview/`.
- Save human-readable summaries in `notes/`.
- Keep publishable chart images out of this workspace. Final blog assets belong in `blog/assets/tidytuesday/`.

## Script

Use the bundled script:

```bash
py -3 .agent/skills/tidytuesday-fetch/scripts/fetch_latest.py
```

Common variants:

```bash
py -3 .agent/skills/tidytuesday-fetch/scripts/fetch_latest.py --week 2026-03-17
py -3 .agent/skills/tidytuesday-fetch/scripts/fetch_latest.py --target-date 2026-03-19
py -3 .agent/skills/tidytuesday-fetch/scripts/fetch_latest.py --force
```

## What The Script Produces

- `readme.md`: the official weekly README
- `source_urls.txt`: source URLs used for the local copy
- `manifest.json`: machine-readable metadata about the week and downloaded files
- `preview/*.head.csv`: small head previews for CSV and TSV files
- `notes/columns.md`: per-file columns and sample values
- `notes/summary.md`: a concise week summary with row counts and paths
- keep any extra official files that ship with the week, such as `intro.md`, `meta.yaml`, or dataset-specific `*.md` dictionaries

## When To Use

- Identify the latest released week as of a specific date
- Download a chosen TidyTuesday week into a stable local folder
- Check row counts, columns, and sample values before planning charts
- Prepare a clean handoff path for later analysis or blog drafting

## Handoff

- Use `tidytuesday-viz` after the week folder exists and you want actual chart code or exported figures.
- Use `tidytuesday-post` after the week folder exists and the dataset is understood.
- Before charting or writing, read `readme.md` and any available `intro.md`, `meta.yaml`, or `*_data.md` files to recover official metric definitions and source wording.
- If the user wants chart ideas, read `notes/summary.md`, `notes/columns.md`, and `manifest.json` before proposing plots.
- If the user wants public figures, export them later to `blog/assets/tidytuesday/`.

## Verification

After fetching, confirm:

- the chosen week is not in the future relative to the requested date
- `manifest.json` exists
- every downloaded file listed in `source_urls.txt` exists locally
- CSV or TSV files have matching `preview/*.head.csv` files
- `notes/summary.md` includes row counts and file paths

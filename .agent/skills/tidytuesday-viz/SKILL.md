---
name: tidytuesday-viz
description: Design and produce TidyTuesday charts from a fetched local week folder in this repo. Use when planning chart angles, writing reproducible R or Python plotting scripts, exporting figures to the week workspace, and preparing final image assets for the blog without writing the post itself.
---

# Build TidyTuesday Visuals

## Overview

Use this skill after `tidytuesday-fetch` and before `tidytuesday-post`.
This skill owns chart planning, plotting code, and image export. It does not own final blog writing or blog index updates.

Keep responsibilities split:

- `tidytuesday-fetch`: fetch and profile the dataset
- `tidytuesday-viz`: design and export charts
- `tidytuesday-post`: write the blog post
- `homepage-build` or `publish-blog-post`: refresh generated blog output

## Subagents

Use subagents freely when parallel work helps.

Good delegation targets:

- propose multiple chart directions from `manifest.json` and `notes/`
- inspect different raw files in parallel
- review code/output alignment after one main chart is drafted
- compare whether a chart reads better as a line chart, heatmap, or composition chart

## Inputs

Start from a fetched folder such as:

```text
data/tidytuesday/2026/2026-03-17-salmonid-mortality-data/
```

Read these first:

- `manifest.json`
- `notes/summary.md`
- `notes/columns.md`
- relevant `raw/*.csv`

## Workspace Contract

Within the chosen week folder, keep visualization work here:

```text
viz/
  code/
  figures/
  notes/
```

Save final publishable assets here:

```text
blog/assets/tidytuesday/<week-folder-name>/
```

Rules:

- Keep one primary purpose per chart script.
- Use ASCII filenames with numeric prefixes.
- Save working figures in `viz/figures/`.
- Copy or export final blog images to `blog/assets/tidytuesday/<week-folder-name>/`.
- Do not write `posts/*.md` in this skill.

## Script

Use the bundled initializer before starting a new week:

```bash
py -3 .agent/skills/tidytuesday-viz/scripts/init_viz.py data/tidytuesday/2026/2026-03-17-salmonid-mortality-data
```

## Toolchain Rule

Prefer the plotting toolchain that is actually installed.

- If `Rscript` and required packages are available, `ggplot2` is a good default.
- If R is unavailable, use Python with `pandas` and `matplotlib`.
- Do not assume R is installed just because the dataset came from TidyTuesday.

## Output Pattern

Recommended filenames:

- `viz/code/01_main_chart.py`
- `viz/code/02_composition_chart.py`
- `viz/figures/01-main-chart.png`
- `viz/notes/chart-plan.md`
- `blog/assets/tidytuesday/<week-folder-name>/chart-01-main.png`

## Chart Rules

- Start with one main chart that carries the post.
- If you add more charts, keep them secondary and support a single narrative.
- Favor descriptive analysis over causal claims.
- Use titles, labels, and legends that can stand alone inside the exported image.
- Store a short note in `viz/notes/` explaining what each chart is supposed to show.
- If a composition chart would be too dense at monthly level, aggregate to a clearer level such as year or quarter before plotting.
- When a metric name is easy to misread, state the formula in the subtitle or caption. Example: `losses = dead + discarded + escaped + other`.
- A good secondary chart often explains structure rather than trend, for example a 100% stacked composition chart next to a time-series main chart.
- If the main story depends on seasonality, add one compact summary chart that compresses the pattern, such as a seasonal mean dot plot, dumbbell plot, or small bar chart.
- A useful order for multi-chart posts is: main trend chart -> compact summary chart -> structural chart.
- For compact summary charts, prefer simple labels and direct values over a separate legend-heavy design.
- Localize chart text to Korean when the post is in Korean. Keep raw field names or raw category values such as `salmon`, `rainbowtrout`, `dead`, `discarded`, `escaped`, and `other` unchanged unless the user explicitly wants translated labels.
- When a chart label refers directly to a raw dataset column, prefer the raw field name itself, such as `losses`, instead of a translated synonym.
- Prefer noun-phrase chart titles and subtitles over sentence endings. Avoid Korean declarative endings such as `-다` inside chart text unless the user explicitly wants a sentence-style annotation.
- Reserve explicit top margin for chart titles, subtitles, legends, and panel labels. If a facet title like `salmon` overlaps with a subtitle or legend, reduce subplot height and place the legend lower instead of relying only on automatic layout.
- When charting `median`, label it as `중앙값` rather than a vague phrase like `중앙 사망률`. If possible, spell out the statistic once as `월별 사망률 중앙값`.

## Handoff

- Hand the final image paths and code paths to `tidytuesday-post`.
- The post should usually lead with `chart-01-main.png`.
- If useful, include a short `viz/notes/chart-plan.md` summary so the post can reuse the same narrative.

## Verification

After generating visuals, confirm:

- the script runs from the repo root or the week folder without path edits
- at least one figure exists in `viz/figures/`
- the final blog asset exists under `blog/assets/tidytuesday/<week-folder-name>/`
- the chosen chart matches the story you intend to write

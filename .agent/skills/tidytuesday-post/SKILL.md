---
name: tidytuesday-post
description: Draft and structure TidyTuesday visualization posts for this homepage project. Use when creating or revising a TidyTuesday article in posts/*.md, choosing title/date/slug/category/tags, deciding between markdown and format: html, and organizing the post so code, EDA, and chart output read cleanly in the current blog system.
---

# Write TidyTuesday Post

## Overview

Use this skill when adding or revising a TidyTuesday practice post in this repo.
Treat `posts/*.md` as the source of truth. Use `homepage-build` or `publish-blog-post` after writing the post if the generated HTML also needs to be refreshed.
If the dataset has not been fetched or profiled yet, use `tidytuesday-fetch` first.
If the chart code or final image assets do not exist yet, use `tidytuesday-viz` first.

## Subagents

Use subagents freely when parallel work helps.

Good delegation targets:

- inspect the fetched dataset while drafting the post structure locally
- generate multiple visualization or headline options in parallel
- review the finished draft for metadata, slug, and structure issues
- check whether the chosen week is better written as `markdown` or `format: html`

## Repo Constraints

- The markdown renderer in `build_blog.py` only supports headings, paragraphs, unordered lists, and fenced code blocks.
- Markdown in this repo does not currently support links, images, tables, blockquotes, captions, or inline HTML.
- If the post needs chart images, figure captions, or richer layout, prefer `format: html`.
- In `format: html`, write the body with explicit HTML tags such as `<h2>`, `<p>`, `<ul>`, `<figure>`, and `<pre><code>`.
- Always set `slug` explicitly using ASCII. The fallback slugifier removes Korean and may collapse to `post`.
- Keep `category: 데이터분석` unless the user explicitly wants a new category strategy.
- Always include `TidyTuesday` in `tags` so the series uses a consistent tag badge on the blog index.

## File Naming

- Use `posts/YYYY-MM-DD-tidytuesday-XX-topic.md`.
- Keep the front matter `date` aligned with the filename unless the user asks for a different publish date.
- Keep the numeric sequence stable once published. Do not renumber older posts unless the user explicitly asks.

## Recommended Metadata

```yaml
---
title: TidyTuesday #01 - Cars dataset visualization
date: 2026-03-20
description: First TidyTuesday practice post comparing the distribution and relationships in a cars dataset.
slug: tidytuesday-01-cars
category: 데이터분석
tags: TidyTuesday, R, ggplot2, tidyverse, visualization
format: html
---
```

## Format Choice

- Use `format: markdown` only for text-first notes with simple lists and fenced code blocks.
- Use `format: html` for the normal TidyTuesday workflow when code and visualization output should appear together.
- If using local chart exports, store them under `blog/assets/tidytuesday/` and reference them from the generated page with paths like `./assets/tidytuesday/2026-03-20-cars-main.png`.
- Do not assume the build script copies image assets. Place image files where the generated HTML can already reach them.

## Post Structure

Use this section order unless the user asks for a different narrative:

1. Dataset
2. EDA
3. Question
4. Approach
5. Visualization
6. Insight
7. Code
8. Sources
9. Reproducibility

## Body Template

For `format: html`, keep the markup simple and consistent with the current blog page styles:

```html
<h2>Dataset</h2>
<ul>
  <li>What the dataset covers</li>
  <li>Time span</li>
  <li>Original source</li>
  <li>Any metric definition the reader could confuse</li>
</ul>

<h2>EDA</h2>
<p>List the first observations that made the chart question worth asking.</p>
<ul>
  <li>What dominates in raw totals?</li>
  <li>What pattern changes by time, species, or region?</li>
  <li>What metric needs definition before interpretation?</li>
</ul>

<h2>Question</h2>
<p>Write the question as a consequence of the EDA, not as a disconnected headline.</p>

<h2>Approach</h2>
<ul>
  <li>Toolchain used</li>
  <li>Filtering or aggregation decisions</li>
  <li>Why this chart form matches the question</li>
</ul>

<h2>Visualization</h2>
<figure>
  <img src="./assets/tidytuesday/2026-03-20-cars-main.png" alt="Main chart" />
  <figcaption>Show one representative chart first.</figcaption>
</figure>

<h2>Insight</h2>
<p>State the main interpretation in 2 to 4 sentences.</p>

<h2>Code</h2>
<pre><code>library(tidyverse)

# plotting code here
</code></pre>

<h2>Sources</h2>
<ul>
  <li>TidyTuesday weekly README</li>
  <li>Original data publisher or app/API</li>
  <li>Any dataset-specific dictionary or intro file used to define metrics</li>
</ul>

<h2>Reproducibility</h2>
<ul>
  <li>Data source: TidyTuesday and the original publisher</li>
  <li>Toolchain: tidyverse, ggplot2</li>
  <li>Next improvement: color, annotation, or scale changes</li>
</ul>
```

For `format: markdown`, keep the same section order but omit images and captions.

## Writing Rules

- Let the analytical question come out of the EDA. Do not jump straight from dataset description to a conclusion.
- If the dataset has ambiguous metric names, define them early. Examples: total losses vs deaths, rates vs counts, raw values vs normalized values.
- When referring to a raw field name in prose, prefer the raw variable name itself, such as `losses`, over a translated Korean label that could drift from the dataset.
- If the dataset uses summary statistics such as `median`, `q1`, or `q3`, describe them with statistical names like `중앙값` and `사분위수` instead of vague wording.
- Attribute both TidyTuesday and the original data source when that source is available from the weekly files.
- Add a `Sources` section when the post uses official definitions, app text, README language, or dataset dictionaries.
- Show one representative chart first, then explain why it matters.
- Keep the code section to the minimum needed to reproduce the visible result.
- Prefer a short interpretation over a long diary-style log.
- If the user prefers a compact read, write the `Insight` section as bullet points instead of paragraphs.
- Each `Insight` paragraph should add a new point, not restate the previous paragraph or the chart title.
- Avoid filler paragraphs such as generic causality disclaimers unless the user specifically wants a limitations section.
- Prefer quantified insight sentences over abstract summaries.
- Prefer short, high-contrast insight sentences. Lead with the difference, then give the number.
- If two `Insight` paragraphs are really one point, merge them. Prefer 2 to 3 sharp paragraphs over 4 repetitive ones.
- Keep the tone natural. Avoid both diary-style filler and copy-like punchlines.
- Use tags for the toolchain and theme, for example `TidyTuesday, R, ggplot2, tidyverse, visualization`.
- If the post includes multiple charts, keep one main chart in the main flow and keep the rest compact.
- If the main chart suggests seasonality or another repeated pattern, add one compact summary figure so the reader can confirm the pattern at a glance.
- When using multiple figures, a good sequence is main chart -> compact summary -> structure/composition chart.
- If the summary is only a small matrix such as 2 species x 4 seasons, prefer a compact table over an over-labeled chart.
- Avoid meta writing such as `차트 대신 표로 정리했다`. Describe what the reader is seeing and what the values mean instead.

## When To Hand Off

- Use `tidytuesday-fetch` when the requested week is not yet saved under `data/tidytuesday/`.
- Use `tidytuesday-viz` when the post needs an exported chart image or a plotting script first.
- Use `homepage-build` when the whole blog output should be regenerated.
- Use `publish-blog-post` when only one new or edited post needs to be reflected manually.
- Use `homepage-edit` if the user asks for better figure, image, or post-body styling.

## Verification

After writing the source post, confirm:

- the file name, `date`, and `slug` all agree
- `category` is set deliberately rather than left to auto-detection
- `TidyTuesday` is present in `tags`
- `format` matches the content type
- any local chart images exist at the referenced path
- the `Sources` section names both TidyTuesday and the original source when available

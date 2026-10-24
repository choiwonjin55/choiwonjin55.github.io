---
name: write-blog-post
description: "Create or revise Korean blog posts for this repository from the user's notes, outline, or draft. Use when planning, drafting, editing, fact-checking, or preparing posts/*.md for AI, data analysis, economics, or personal-thought articles while preserving the author's voice. Do not use for TidyTuesday posts, Tistory imports, site builds, or UI changes."
---

# Write Blog Post

## Overview

Create or revise the source article in `posts/*.md` without replacing the author's intent with a generic AI voice.
Use `tidytuesday-post` instead for TidyTuesday articles.

Read [references/voice-and-style.md](references/voice-and-style.md) before drafting or materially rewriting prose. Skip it only for metadata-only corrections.

## Workflow

1. Read the user's notes or draft and any directly relevant posts.
2. State the article's purpose and main point in one sentence for internal guidance.
3. Choose the least invasive mode that satisfies the request:
   - revise an existing draft while preserving its meaning and distinctive phrases
   - turn the user's notes into an outline and draft
   - create an outline with explicit gaps when the user has not supplied enough personal experience or opinion
4. Verify factual claims that are current, numerical, disputed, or important to the argument. Prefer primary sources and never invent a citation.
5. Organize the article around one clear thread rather than forcing every post into the same template.
6. For a published article, edit its existing `posts/*.md` file as the single source of truth. Use `drafts/` only for unpublished work that should remain outside the build. When consolidating a draft into a post, preserve the latest author edits, metadata, and asset links before removing the redundant draft.
7. Review voice, factual support, metadata, and renderer compatibility.
8. Use `homepage-build` only when the request also includes publishing or refreshing generated output.

## Structure Guidance

Choose a structure that matches the material:

- Personal observation: concrete experience or observation -> context -> examples and reasoning -> modest conclusion
- Explanatory analysis: topic and purpose -> evidence or comparison -> interpretation -> limits -> conclusion
- Practical reflection: problem -> available choices -> decision criteria -> lesson or next action

For this author's blog, use noun-phrase titles and headings rather than complete sentences ending in `~다` or `~습니다`. Openings should state the topic, observation, or purpose. Do not open with a rhetorical question or add question-form headings unless the user explicitly requests them. This title preference is separate from the body's `~다` style.

Use section headings when they help navigation. Do not add numbered sections merely to make a short article look complete.

Check whether each section addresses a distinct question or adds evidence. Merge sections that repeat the same claim, and use a short transition instead of a separate heading when that is enough. Choose the number of sections to fit the article.

## Content Rules

- Keep the user's lived experience, opinion, and uncertainty intact.
- Do not invent anecdotes, motivations, reactions, or conclusions on the user's behalf.
- Separate verified facts from inference and personal opinion in the prose.
- Preserve strong original sentences unless the user asks for a full rewrite.
- Remove repetition before adding new material.
- Prefer concrete examples and quantities over abstract summaries when evidence is available.
- End when the main thought is complete; do not append a generic lesson or motivational closing.

## Metadata and Format

Create new files as `posts/YYYY-MM-DD-ascii-topic.md` and include every field:

```yaml
---
title: Korean title
date: YYYY-MM-DD
description: One concise sentence describing the actual article
slug: ascii-kebab-case
category: AI
tags: AI, 글쓰기
format: markdown
---
```

Apply these rules:

- Keep the filename date and front matter `date` identical.
- The builder reads every `posts/*.md`; it has no draft flag or future-date exclusion. Keep unpublished drafts in `drafts/` until the user asks to include them in the blog.
- Set an explicit ASCII `slug`; do not rely on the Korean fallback slugifier.
- Choose an existing category deliberately: `AI`, `경제`, `데이터분석`, or `생각`.
- Use a small, stable set of topic tags rather than sentence-like tags.
- Prefer `format: markdown` for author-editable posts: headings, paragraphs, unordered lists, fenced code blocks, bold text, pipe tables, standalone Markdown images, and absolute HTTP(S) links are supported. Embed an interactive graph as a complete one-line `<iframe src="..." ...></iframe>`; keep its HTML file at the established asset path. Markdown image and iframe paths resolve relative to the generated `blog/` page.
- Use `format: html` only for layout or syntax the Markdown builder does not support, such as custom captions, blockquotes, inline code styling, relative text links, or arbitrary raw HTML. Do not require HTML format solely for tables, images, or interactive graph iframes.
- Write explicit HTML body tags when using `format: html`; do not mix unsupported Markdown into that body.
- Front matter uses a simple one-line `key: value` parser, not full YAML: use plain values and comma-separated tags, without YAML quotes, lists, or multiline scalars.
- Optional sharing overrides are `og_description`, `og_image`, and `og_image_alt`. A custom `og_image` must reference an existing PNG using a site-root path and requires `og_image_alt`; otherwise the shared default applies.

## Verification

Before finishing, confirm:

- the main point can be summarized in one sentence
- the draft does not introduce invented personal material
- important factual claims have support and sources where appropriate
- the opening reaches the actual topic without generic setup
- each section adds a new point and the conclusion does not merely repeat the introduction
- the voice follows `references/voice-and-style.md`
- title, description, date, slug, category, tags, and format are present and deliberate
- filename, local asset paths, and chosen format match the repository rules

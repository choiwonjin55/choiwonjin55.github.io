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
6. Write or update the source file in `posts/`.
7. Review voice, factual support, metadata, and renderer compatibility.
8. Use `homepage-build` only when the request also includes publishing or refreshing generated output.

## Structure Guidance

Choose a structure that matches the material:

- Personal observation: concrete experience or observation -> question -> examples and reasoning -> modest conclusion
- Explanatory analysis: question and context -> evidence or comparison -> interpretation -> limits -> conclusion
- Practical reflection: problem -> available choices -> decision criteria -> lesson or next action

Use section headings when they help navigation. Do not add numbered sections merely to make a short article look complete.

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
- Set an explicit ASCII `slug`; do not rely on the Korean fallback slugifier.
- Choose an existing category deliberately: `AI`, `경제`, `데이터분석`, or `생각`.
- Use a small, stable set of topic tags rather than sentence-like tags.
- Use `format: markdown` for text-first posts containing only headings, paragraphs, unordered lists, and fenced code blocks.
- Use `format: html` when the body needs clickable links, images, tables, captions, inline code styling, blockquotes, or other rich layout.
- Write explicit HTML body tags when using `format: html`; do not mix unsupported Markdown into that body.

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

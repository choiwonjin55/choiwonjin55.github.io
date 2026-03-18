---
name: homepage-build
description: Build and refresh the blog output for this homepage project. Use when regenerating blog pages from posts/*.md, rebuilding blog/index.html, removing legacy tistory html files, or checking generated output after post edits.
---

# Build Homepage Blog

## Overview

Use this skill to turn the local `posts/` markdown files into the generated `blog/` site.
The canonical build path is `build_blog.py`.

## Workflow

1. Read the source post(s) in `posts/`.
2. Run or update `build_blog.py` if the generation rules need changes.
3. Regenerate the blog output so every post page and `blog/index.html` match the current sources.
4. Verify that generated slugs, categories, dates, and tag badges still look correct.

## Build Rules

- Treat `posts/*.md` as the source of truth.
- Keep generated files in `blog/` out of manual drift unless the build script itself changes.
- Remove legacy dated Tistory HTML files from `blog/` when the build script does so.
- Preserve the site-wide header, footer, and typography used by the generated pages.

## When To Touch The Script

Update `build_blog.py` if you need to change any of these behaviors:

- markdown-to-HTML conversion
- Tistory HTML cleanup
- category detection
- title normalization
- blog index filtering or grouping

## Verification

After changes, compare the regenerated output against the source post content and confirm:

- every post file builds successfully
- `blog/index.html` includes the newest posts first
- category filters still work
- no unexpected files were deleted

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
2. Validate source metadata before building:

   ```bash
   python3 .agents/skills/homepage-build/scripts/check_posts.py
   ```

3. Run or update `build_blog.py` if the generation rules need changes.
4. Regenerate the blog output:

   ```bash
   python3 build_blog.py
   ```

5. Check generated page coverage and social metadata:

   ```bash
   python3 .agents/skills/homepage-build/scripts/check_posts.py --generated
   python3 scripts/check_social_metadata.py
   ```

6. Verify that generated slugs, categories, dates, and tag badges still look correct.

`check_posts.py --generated` checks page filenames and existence, not rendered content or index links. Inspect the changed post and its index entry separately to catch stale output.

## Build Rules

- Treat `posts/*.md` as the source of truth.
- Keep `posts/*.md`, `build_blog.py`, and `import_tistory.py` tracked in git; do not rely on generated `blog/*.html` as the only persisted state.
- Change generated layout in `build_blog.py` and rebuild; do not edit generated HTML directly during normal work.
- If generated output disagrees with the source, determine whether the source metadata or the generator is wrong, fix that input, and rebuild.
- Remove legacy dated Tistory HTML files from `blog/` when the build script does so.
- Preserve the site-wide header, footer, and typography used by the generated pages.
- Investigate generated HTML without a matching `posts/*.md` source before removing it; it may be an intentional standalone page.
- Treat empty legacy categories and tags as warnings unless the task includes archive cleanup.

## When To Touch The Script

Update `build_blog.py` if you need to change any of these behaviors:

- markdown-to-HTML conversion
- Tistory HTML cleanup
- category detection
- title normalization
- blog index filtering or grouping

Sharing metadata is generated through `social_metadata.py`. Post front matter can optionally set `og_description`, `og_image`, and `og_image_alt`. A custom image must be an existing PNG at a site-root path, and requires `og_image_alt`.

## Verification

Use [homepage-verify](../homepage-verify/SKILL.md) for a broader site review or browser checks after generation changes. Reuse checks already completed for unchanged output.

After changes, compare the regenerated output against the source post content and confirm:

- every post file builds successfully
- `blog/index.html` includes the newest posts first
- source metadata and generated tag badges match
- tags appear on individual post pages; the current index rows show title and date without tag badges
- category filters still work
- `check_posts.py --generated` reports no errors
- `scripts/check_social_metadata.py` reports no errors
- any orphan-page or empty-metadata warnings were reviewed deliberately
- no unexpected files were deleted
- the git diff includes both source-file changes and the regenerated `blog/` output when content changed

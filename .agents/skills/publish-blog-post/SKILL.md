---
name: publish-blog-post
description: "Manually publish one posts/*.md source into blog/*.html and update blog/index.html as an emergency fallback. Use only when explicitly invoked and build_blog.py cannot run; do not use for normal publishing or when homepage-build is available."
---

# Publish Blog Post

## Overview

Use this skill only as an emergency fallback when `build_blog.py` cannot run.
For normal publishing, use `homepage-build` so generated output stays deterministic.

## Preconditions

Before editing generated HTML:

1. Confirm that `build_blog.py` is unavailable or fails for an environment reason unrelated to the post.
2. Stop and use `homepage-build` if the full build can run.
3. Treat `posts/*.md` as the source of truth even during fallback publishing.

## Workflow

1. Read the source markdown in `posts/`.
2. Add or correct source front matter first if title, date, category, tags, description, or slug metadata is missing.
3. Determine the post title, date, category, tags, and slug from the file content or filename.
4. Create or update the matching `blog/<slug>.html` file using the shared blog layout.
5. Add the post to `blog/index.html` in the correct year section and date order.
6. Render tag badges next to the title in the index when tags are available, using the same `post-tags` / `post-tag` structure as existing rows.
7. Update category counts or filter labels if the new post changes them.

## Rules

- Keep the generated post page consistent with the existing blog template.
- If a post has no front matter, derive the title from the first heading and the slug from the filename convention used in this repo.
- If tags exist in front matter or source metadata, show them beside the title in the index and keep the order stable.
- Do not patch only `blog/index.html` when the source metadata is wrong; update `posts/*.md` so the next rebuild preserves the change.
- Prefer the build rules already used by `build_blog.py` when choosing slugs, dates, and categories.
- Never use this fallback merely to save build time.
- After the build environment is restored, run `homepage-build` and confirm it reproduces the manual result.
- Treat `posts/*.md` and generated `blog/*.html` as a pair for review and commit.

## Verification

After publishing, confirm:

- the new `blog/*.html` file exists
- the index links to the correct slug
- the post appears under the correct year
- source metadata and rendered badges still match
- category filters or counts still make sense
- a later full build reproduces the same post page and index entry

---
name: publish-blog-post
description: Publish a single blog post from posts/*.md into blog/*.html and update blog/index.html. Use when one new or edited post needs to be reflected manually, especially if the full build script cannot run.
---

# Publish Blog Post

## Overview

Use this skill when a single post needs to be reflected in the generated blog without rebuilding everything.
The goal is to keep `posts/`, `blog/`, and `blog/index.html` aligned.

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
- If the full site build is available, use `homepage-build` instead of manual publishing.
- Treat `posts/*.md` and generated `blog/*.html` as a pair for review and commit.

## When To Use

- Add one new post to the blog index.
- Reflect a changed markdown post in the generated blog.
- Fix a single generated HTML page without touching unrelated posts.
- Work around a missing Python runtime or unavailable build script.

## Verification

After publishing, confirm:

- the new `blog/*.html` file exists
- the index links to the correct slug
- the post appears under the correct year
- source metadata and rendered badges still match
- category filters or counts still make sense

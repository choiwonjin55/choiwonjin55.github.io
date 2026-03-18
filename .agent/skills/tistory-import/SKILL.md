---
name: tistory-import
description: Import Tistory posts into local markdown files for this homepage project. Use when syncing new or updated Tistory content, rebuilding the posts/ archive, or adjusting the scraper in import_tistory.py.
---

# Import Tistory Posts

## Overview

Use this skill to pull Tistory articles into `posts/` as markdown files with front matter and embedded HTML.
The canonical import path is `import_tistory.py`.

## Workflow

1. Inspect the current import script before changing scraping rules.
2. Run the importer when the goal is to refresh the local archive from Tistory.
3. Keep the generated files in `posts/` consistent with the imported metadata.
4. Rebuild the blog after importing so `blog/` reflects the new source files.

## Import Rules

- Preserve the front matter fields expected by `build_blog.py`.
- Keep the cutoff date logic aligned with the importer's current behavior.
- Do not hand-edit imported post bodies unless the imported HTML itself needs cleanup.
- Prefer deterministic filename and slug handling so the build step stays stable.

## When To Update The Script

Update `import_tistory.py` if you need to change any of these behaviors:

- category or post discovery
- HTML cleanup for imported content
- metadata extraction from Tistory pages
- filename generation
- post cutoff filtering

## Verification

After import, check that:

- new markdown files were created in `posts/`
- front matter includes title, date, description, slug, category, tags, and format
- the imported HTML content is intact enough for the build step
- the next blog build renders the imported posts correctly

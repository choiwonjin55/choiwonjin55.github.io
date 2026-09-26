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
2. When refreshing the archive, first stage the import in a temporary output directory by setting the imported module's `OUT_DIR` before calling `main()`. Compare the result with existing imported sources before replacing them.
3. Keep the generated files in `posts/` consistent with the imported metadata.
4. Rebuild the blog after importing so `blog/` reflects the new source files.

## Import Rules

- Preserve the front matter fields expected by `build_blog.py`.
- Imported `posts/*tistory-*.md` files are source files and should stay tracked in git after review.
- Keep the cutoff date logic aligned with the importer's current behavior.
- Treat imports as destructive for existing `posts/*tistory-*.md`; `purge_existing()` removes prior imported files before writing new ones.
- `main()` purges before its first network fetch. Keep the live archive intact until the staged import succeeds, and preserve local changes before replacing imported sources. A failed or unexpectedly empty import must not replace the archive.
- Do not hand-edit imported post bodies unless the imported HTML itself needs cleanup.
- Prefer deterministic filename and slug handling so the build step stays stable.
- The importer depends on `requests` and `bs4`, and it needs network access to fetch Tistory pages.
- The current source blog and cutoff are defined in `import_tistory.py` by `BASE` and `CUTOFF_DATE`.

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
- the resulting git diff contains the source `posts/` changes before any generated `blog/` output is committed
- source validation and sharing-metadata checks pass using `homepage-build`

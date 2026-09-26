---
name: homepage-edit
description: Edit the homepage, blog landing pages, and shared styling for this project. Use when changing index.html, index-en.html, styles.css, app.js, or other presentation code while preserving the existing visual system.
---

# Edit Homepage UI

## Overview

Use this skill for changes to the public-facing homepage and shared UI styling.
The important files are `index.html`, `index-en.html`, `styles.css`, and `app.js`.

## Workflow

1. Inspect the current layout, typography, colors, and responsive behavior before editing.
2. Keep changes aligned between the Korean and English entry points when relevant.
3. Update shared styles in `styles.css` before adding page-specific overrides.
4. Verify the page still works on desktop and mobile widths.

## Design Rules

- Preserve the established visual identity unless the task explicitly asks for a redesign.
- Keep the homepage, blog index, and generated blog pages visually coherent.
- Prefer targeted edits over broad rewrites.
- If adding new markup, make sure the CSS supports it at common viewport sizes.

## When To Update Files

- `index.html` for content or structure changes on the main landing page
- `index-en.html` for mirrored English content changes
- `styles.css` for layout, spacing, typography, color, and responsiveness
- `app.js` for interactive behavior or motion logic
- `build_blog.py` for generated blog index or post markup; use `homepage-build` after changing it
- `social_metadata.py` for shared link-preview settings; refresh homepage metadata with `python3 scripts/update_home_social_metadata.py` when those settings change

Do not manually edit `blog/index.html`, generated post pages, or the managed social-metadata blocks in the homepage HTML. Update their generator or settings instead.

## Verification

Use [homepage-verify](../homepage-verify/SKILL.md) for shared-layout or interaction checks across affected page types. Select checks by the change rather than running a full-site review for every edit.

After edits, confirm:

- the main layout still loads cleanly
- navigation links still point to the right pages
- spacing and hierarchy remain readable on narrow screens
- no blog-specific styling accidentally leaks into the homepage
- `blog/index.html` and at least one generated `blog/*.html` page still render correctly, since they share `styles.css`
- when sharing metadata changes, `python3 scripts/check_social_metadata.py` reports no errors
- if useful, preview the site locally before finalizing changes

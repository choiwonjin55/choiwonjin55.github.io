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

## Verification

After edits, confirm:

- the main layout still loads cleanly
- navigation links still point to the right pages
- spacing and hierarchy remain readable on narrow screens
- no blog-specific styling accidentally leaks into the homepage

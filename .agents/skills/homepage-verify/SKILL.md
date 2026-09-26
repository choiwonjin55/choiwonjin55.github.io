---
name: homepage-verify
description: Verify this homepage project's source, generated blog output, sharing metadata, and browser behavior. Use for a site review, checks after homepage or blog changes, or local verification before release. Select checks by the affected files; use homepage-build for generation and homepage-edit for UI changes.
---

# Verify Homepage

## Scope

Verify the current working tree or the comparison explicitly requested by the user. Start with `git status --short` and the relevant diff, including untracked source or asset files. Distinguish existing warnings from regressions introduced by the change.

A review request produces findings and evidence. If the task includes fixes, correct the source or generator through the appropriate skill, then rerun affected checks. Local verification does not establish that the public site has been deployed.

## Select Checks

Use the affected rows below. Reuse checks already completed against unchanged files during the current task; do not automatically run every check or every page-width combination.

| Changed area | Automated or source checks | Browser sample |
| --- | --- | --- |
| `drafts/` only | Review the draft against the writing request; confirm it stays outside `posts/` | None unless a preview was requested |
| `posts/*.md` or post assets | Source validation; generated page coverage if output is in scope; inspect the changed article and its index link | Changed article, its images or links, and its index entry |
| `build_blog.py` | Source validation, generated coverage, sharing metadata, source-to-output comparison | Index plus representative Markdown, imported HTML, and table/code/image content affected by the change |
| `styles.css` or shared markup | Inspect affected selectors and pages | Korean home, English home, blog index, and representative post types using the changed styles |
| `index.html`, `index-en.html`, or `app.js` | Check changed links, language attributes, and script behavior; sharing check if head metadata changed | Affected homepages; scroll through reveal sections for `app.js` changes |
| `social_metadata.py`, sharing scripts, or `assets/og/` | Sharing metadata validation; relevant unit tests if generator logic changed | Inspect changed share images at reduced size for readability and clipping |

For a full site review, cover both homepages, the index, and representative posts. Select examples from the actual source files and slugs rather than hard-coding post counts or old URLs.

## Repository Checks

Run relevant commands from the repository root:

```bash
python3 .agents/skills/homepage-build/scripts/check_posts.py
python3 .agents/skills/homepage-build/scripts/check_posts.py --generated
python3 scripts/check_social_metadata.py
git diff --check
```

- The first command validates source metadata and some local asset references. Missing HTML assets and empty legacy Tistory metadata can be warnings even when the command succeeds; inspect warnings that affect the requested change.
- `--generated` adds checks for missing or orphan page filenames. It does **not** prove that article content, index links, dates, categories, or tags match the source. Compare those for changed posts separately.
- The sharing checker validates canonical, Open Graph, and Twitter metadata against project settings and sources, including image files. A pass does not prove an external service has refreshed its preview cache.
- Run source validation before the sharing checker; malformed source metadata may prevent the sharing checker from completing.
- For changes to sharing-generation logic, run `python3 -m unittest discover -s tests -p 'test_social_metadata.py'`. Choose tests relevant to other changed code instead of adding tests for prose or styling alone.

If output is missing or stale, use `homepage-build` when rebuilding is part of the task. During a review-only task, report the mismatch before regenerating files so the original finding remains visible. If shared homepage metadata needs regeneration, its command is `python3 scripts/update_home_social_metadata.py`.

## Browser Verification

Use the installed `browser:control-in-app-browser` skill for local browser control and follow its tool setup. Reuse an existing preview server only after confirming that it serves this repository. Otherwise a local preview can be started from the repository root:

```bash
python3 -m http.server 8000 --bind 127.0.0.1
```

Choose another free port if needed; keep track of the process and stop only the server you started when finished. If browser tools are unavailable, complete source and HTML checks and explicitly mark visual and interaction checks as unverified.

For affected pages:

- Inspect a narrow mobile width and a desktop width, for example 375 and 1440 CSS pixels. Add 320 or 768 only when tight layouts or breakpoints warrant it; these are examples, not a fixed test matrix.
- Check visible content, header/footer alignment, text wrapping, Korean fonts, image loading, and page-wide horizontal overflow. Wide tables and code may scroll inside their own containers without making the entire page scroll sideways.
- For shared navigation changes, follow Korean home → blog index → article → English home → Korean home. Check article back links and visible keyboard focus where affected.
- For index/filter changes, exercise each category and the all-posts button. Confirm visible rows match `data-category`, counts agree, empty year groups disappear, and `aria-pressed` / `.filter-status` update.
- For changed article content, compare the rendered title, date, category, tag order, images, and links with its source. Index rows currently show title and date; tag badges belong in the article header.
- Inspect relevant browser console errors and failed resource loads. Separate external network/font failures from local missing files or script errors.

Capture screenshots or measurements when they substantiate a finding or a substantial visual change. Keep temporary evidence outside the published site, and report reproducible page paths and viewport sizes.

## Completion Report

Report the result, affected pages, checks actually run, and actionable failures with source-file locations. For visual defects, include the viewport and reproduction steps. Separate failures, reviewed warnings, and checks not performed; do not call an untested behavior verified.

Use `homepage-build` for stale generation, `homepage-edit` for UI fixes, and the relevant writing skill for source corrections. After an authorized fix, rerun the failing check and directly affected checks. Stop when the selected checks pass and remaining limitations are clearly reported.

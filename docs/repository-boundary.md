# Repository boundary

This repository contains the public homepage and blog. Keep data analysis in the separate private `analysis-private` repository, cloned beside this one.

| Public here | Private in `analysis-private` |
| --- | --- |
| `index.html`, `index-en.html`, `styles.css`, `app.js` | Raw and processed datasets |
| `build_blog.py`, `social_metadata.py`, and site checks | Analysis scripts, notebooks, working notes, and working figures |
| Published `posts/*.md` and generated `blog/*.html` | TidyTuesday fetch, visualization, and drafting tools |
| Approved images in `blog/assets/` | Unpublished analysis and candidate charts |

Publish from the private repository by copying only approved article text into `posts/` and approved images into `blog/assets/`. Run `python build_blog.py`, review the public `git diff`, then commit the selected files. A public post must not refer to a private local path as though readers can access it.

The public repository ignores `data/`, `analysis/`, and `notebooks/` as a safeguard. Git ignore rules do not hide files that were already committed. Anything committed to a public repository can remain visible in its history after deletion.

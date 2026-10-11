# Existing 2026 analysis

This is a handoff for the existing repository analysis, not a default dataset or a fixed result for future seasons. Confirm live files and user changes before running anything.

## Current editable and published files

- Article source: `posts/2026-10-11-mlb-hit-regions.md`, ordinary Markdown with iframe embeds.
- Generated article: `blog/mlb-2026-hit-regions.html`; generated listing: `blog/index.html`.
- Live interactive documents: `scripts/statcast-dashboard.html`, `scripts/murakami-dot-plot.html`.
- Generator templates: `scripts/mlb_statcast_dashboard.html`, `scripts/mlb_murakami_dot_plot.html`. These contain placeholders and are not the public graphs. Manual edits in the live HTML may be newer than these templates.
- Published article images: `assets/mlb-2026/01-response-maps.png`, `hit-decomposition.png`, `region-outcomes.png`.
- The former `drafts/mlb-2026/` folder and `scripts/mlb_prepare_blog_post.py` were removed after consolidating the source. Do not recreate them for normal edits.

## Existing analysis choices

- Individual regular-season in-play batted balls; bunts separated; source precision retained.
- Small amounts of missing required velocity/angle were excluded after the user reviewed an audit. Distance rows have their own eligibility; missing distance does not automatically remove a probability row.
- Season source coverage was March 25 through September 27, 2026.
- Existing distance model: tensor spline features with ridge regression. Existing outcome model: tensor spline features with regularized multinomial logistic regression over single/double/triple/home-run/non-hit outcomes. These are custom models, not official xBA.
- Saved model/grid/result files are under `data/mlb/2026/analysis/`; processed probability rows are in `data/mlb/2026/processed/probability.csv.gz`. Raw collection responses and missingness metadata are local under `data/mlb/2026/`.
- Do not copy old numeric results into a new article without checking the current dataset and denominator.

## Descriptive regions used in this article

All bounds include the lower value and exclude the upper value.

| Public name | Exit velocity (mph) | Launch angle (degrees) |
| --- | --- | --- |
| 약하게 띄운 타구 | 65–75 | 20–35 |
| 빠르고 낮은 타구 | 90–105 | 5–15 |
| 강하게 띄운 타구 | 105–115 | 25–35 |
| 중간 속도의 뜬공 | 85–100 | 25–35 |

The argument compares two concentrations of hits and the low-hit intermediate fly-ball region. Overlapping angle ranges and differing speed ranges are deliberate descriptive choices. A region is not a universal good/bad-contact rule.

## Player example

Murakami's player ID is 808959 in this analysis. The current complete-case plot has 257 batted balls: 59 home-run-excluded hits, 35 home runs, and 163 records in the existing `nonhit` class. Inspect actual event codes before treating that internal class as a rigorous out count.

The author chose this player to examine hard contact and home-run hitting. Arraez was investigated and removed from the article; do not restore him automatically. Murakami's league-probability contours and the duplicate standalone PNG were also removed. Current interactive result categories can be selected in combination.

Official season snapshots were used to check season totals against the Statcast aggregation. Velocity/angle comparisons and interactive points come from Statcast records, not the season-stats API.

## Useful scripts

- `scripts/mlb_statcast_audit.py`: inspect its modes before collecting or cleaning.
- `scripts/mlb_statcast_analysis.py`: models and primary dashboard generation; avoid full fitting for copy edits.
- `scripts/mlb_hit_regions.py`: region analysis; its legacy report-writing output is not the editable published post.
- `scripts/mlb_region_figures.py`: refresh region figures from saved analysis products.
- `scripts/mlb_murakami_dot_plot.py`, `scripts/mlb_murakami_figure.py`: interactive export and static fallback; generation may overwrite manual graph edits.
- `scripts/mlb_player_cases.py`, `scripts/mlb_player_case_suitability.py`: player summaries and example suitability. Inspect old reports before reusing them; they can contain removed player cases and retired presentation choices.
- `scripts/check_mlb_murakami_dot_plot.py`, `scripts/check_mlb_statcast_draft_dashboard.py`: checks target the live `scripts/` HTML despite the latter filename.

Run `build_blog.py` after editing `posts/`; validate with `.agents/skills/homepage-build/scripts/check_posts.py --generated` and `scripts/check_social_metadata.py`. Use an interpreter with the dependencies actually installed; the previous local `.venv` location is not a shared dependency contract.

## Official reference entry points

- [Baseball Savant Statcast Search](https://baseballsavant.mlb.com/statcast_search)
- [Baseball Savant CSV field documentation](https://baseballsavant.mlb.com/csv-docs)
- [Murakami 2026 MLB season stats request](https://statsapi.mlb.com/api/v1/people/808959/stats?stats=season&group=hitting&season=2026&gameType=R)

These are reference/query entry points. For a fresh collection, verify their current responses and preserve a dated local manifest instead of assuming stable live totals.

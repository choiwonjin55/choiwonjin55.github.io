---
name: mlb-statcast-analysis
description: "Analyze MLB Statcast batted-ball data and official situational batting records: audit data, compare contact outcomes and batting averages, investigate player examples, and create interactive charts. Use for MLB analysis plans, execution, or revisions in this repository; use write-blog-post for article prose and homepage-build for site generation."
---

# MLB Statcast Analysis

Analyze the baseball question the user is asking. Use the author's established preferences as defaults, not as fixed conclusions or requirements for every future analysis. A request to create or update this skill does not authorize collecting data, fitting models, or publishing.

## Start with the question and existing work

- Read the user's latest question, relevant scripts, saved manifests/results, and current post before acting. Reuse session decisions and preserve direct user edits.
- Prefer inspecting saved data and rerunning the smallest relevant calculation over downloading the season or refitting everything.
- For this repository's existing analysis and file locations, read [references/existing-2026-analysis.md](references/existing-2026-analysis.md). Do not hard-code that season or its conclusions into new work.
- When the user requests feedback or proposals, present findings and concrete options before changing the article. When they ask to apply a change, complete the authorized edit and verification.

## Data and missingness

- Prefer direct programmatic access to official Baseball Savant/Statcast CSV downloads and MLB Stats API records. The user should not need to visit a page to download data. Verify provider documentation, current schema, units, coverage, and endpoints before collecting.
- Define season, actual covered dates, game types, and observation unit explicitly. Do not treat an ongoing season's future dates as observed data.
- Distinguish batted-ball, plate-appearance, at-bat, and player-season analyses before choosing inclusion rules. Official batting-average analyses retain strikeouts and hit bunts in at-bats; walks, hit-by-pitches, sacrifice flies, sacrifice bunts, and catcher interference are excluded from official at-bats. Do not carry contact-analysis bunt exclusions or velocity/angle complete-case rules into official batting records.
- For velocity/angle analyses, start with individual in-play batted balls in regular-season games. Strikeouts and walks are outside this observation unit; they are not additional cleaning exclusions. Keep them when separately analyzing plate appearances or season records.
- For contact analyses, keep bunts as a separate flagged group and exclude them from the main contact comparison by default. Check how the source identifies bunts instead of assuming a perfect flag. Exclude foul balls from the in-play sample and games outside the agreed population.
- Preserve original responses, precision, row identifiers, and acquisition metadata. Use bins to show sample support and summarize comparisons, not to round away individual observations before fitting.
- Audit missingness before choosing treatment unless the user has already authorized a rule. An audit-only request stops before cleaning or modeling. Show raw/in-scope counts, relevant column and joint missingness, outcome/time/player patterns, duplicates, and usable counts by target.
- For this author's contact analyses, excluding rows with missing required values is an accepted preference when the affected share is small. Assess the scale first, report the impact, and reuse an already authorized decision. Do not turn this into automatic deletion of all rows with any missing column.
- Keep distance and probability eligibility separate: a row missing distance may still support hit/home-run analysis. Preserve raw data and export derived rows plus exclusion reasons.

The available `dataset-collect-clean` skill can help with acquisition and cleaning. Its personal installation is optional; the requirements above must remain usable after this skill is shared through Git.

## Official batting records and situational comparisons

- Check returned record counts against the API's reported total and verify player-season identifiers are unique within each split. Reconcile player totals with team totals for the same season, game type, and situation, including H, AB, PA, strikeouts, walks, hit-by-pitches, sacrifice flies, sacrifice bunts, and catcher interference where available. Investigate mismatches before using the records.
- Inspect traded-player records: use the all-team season aggregate once, without also adding its team-level rows. Cross-check traded-player examples against individual-player responses. Count unique completed games by game ID when checking schedule coverage; resumed games can appear more than once.
- Preserve players with absent situational records in the inventory, distinguish absent records from explicit zero counts, and report their effect on eligibility. Do not automatically replace an absent RISP record with zero. Check integer count ranges, H <= AB <= PA, and that situational hits and at-bats and their complementary counts are consistent with the overall totals.
- Calculate batting averages from original integer H/AB rather than the API's rounded AVG. Define the comparison, denominator, eligibility, and weighting explicitly: an equal-weight mean of player differences and a pooled, at-bat-weighted comparison answer different questions. Determine positive, negative, or equal differences before display rounding; integer cross-products can compare H/AB exactly.
- Distinguish RISP minus overall average from RISP minus non-RISP average: the overall record includes RISP. With total hits/at-bats H/N and RISP hits/at-bats H_R/n_R, define D = H_R/n_R - H/N and C = H_R/n_R - (H-H_R)/(N-n_R). Where both subsets have positive at-bats, verify D = ((N-n_R)/N) * C; do not present them as interchangeable measures.
- Before attributing a situational difference to performance, inspect whether the statistic's counting rules contribute to it. For example, compare official H/AB with H/(AB+SF) to assess the effect of excluding sacrifice flies. Label the latter as an alternative calculation, preserve the original eligible player cohort and weighting, and change the intended counting rule alone. Report the original difference, recalculated difference, and their change without treating the arithmetic change as a causal estimate of player behavior.

## Outcomes, comparisons, and models

- Analyze distance, any hit, home-run-excluded hits, and home runs as distinct outcomes. Any hit includes singles, doubles, triples, and home runs; home-run-excluded hits include singles, doubles, and triples.
- Audit actual event codes before reporting counts. Count an out outcome from the actual out-producing events; do not silently equate every non-hit with an out or count the two outs of a double play as two batted balls. Preserve errors and fielder's choices in detailed summaries.
- Public labels should use `안타 전체`, `홈런 제외 안타`, and `홈런`. Use `타구` or `분석 대상 타구` instead of `비번트`; use `아웃` for genuinely out-producing events. Keep internal event/class identifiers stable when revising copy.
- Study combinations of exit velocity and launch angle. Define each comparison region with both coordinates and explicit lower/upper boundary rules; report sample counts with rates.
- Keep region comparisons descriptive. Use meaningful names such as weakly lofted contact or intermediate-speed fly balls rather than A–D labels in public charts and prose.
- Verify a claim using its actual comparison: hit count and hit rate differ, as do all hits and home-run-excluded hits. Comparisons at a fixed angle answer a different question from comparisons across rectangular regions.
- Distinguish observed outcomes, custom model probabilities, and provider metrics. Explain the actual model to the user and retain reproducible specifications; never imply that a custom prediction is official Statcast xBA.
- Select a model appropriate to the task and available support. For the existing article, reuse the saved models/grid unless a refit is requested. Do not make one fitted model family a universal requirement.
- Use out-of-sample observations for performance checks and report suitable distance and probability metrics. Exclude reserved samples from fitting, preprocessing selection, tuning, and support thresholds learned from training data.

## Player cases and baseball interpretation

- Choose a player because the measured contact distribution fits the example. Check player ID, season, games, complete-case count, velocity/angle distribution, outcome composition, and the corresponding league baseline.
- Compare player and league under the same inclusion rules and result categories. A famous reputation, total home runs, or a few highlighted dots alone does not establish representativeness.
- The author's Murakami example emphasizes hard contact and home runs. Do not rewrite it as deliberate weak-contact hitting simply because the player also has singles. Examine non-home-run hit velocity as well as home-run velocity/angle when testing that interpretation.
- Treat player intent as interpretation unless directly supported. Preserve the user's hypothesis without inventing strategy, motivation, or causal evidence.
- Inspect fielding depth, direction, flight time, park, or other variables before claiming a specific defensive mechanism is demonstrated. Plausible baseball explanations can accompany the observations, but should remain recognizably interpretations.
- A league probability surface is not a scatterplot of other players. If comparing a player's outcomes inside a model region with the league, calculate both samples under the same boundary rule rather than inferring from point colors.

## Charts and article handoff

- Favor a league overview, meaningful region comparisons, and a player case when they advance one main argument. Do not force every analysis into that exact outline.
- An interactive player scatterplot should show velocity and angle, actual outcome color/shape, and selectable details such as date, opponent, distance, and venue when recorded. Preserve the source precision.
- For this project, outcome buttons are independent visibility toggles. Clicking again hides that category; multiple categories can remain visible; `전체` restores all categories. Active button styling must match visible outcomes.
- Keep marker colors/shapes consistent if the same chart also has a static export. Do not add a duplicate PNG directly below an interactive chart by default; a no-JavaScript fallback can serve a different purpose.
- The author removed league-probability contours from the Murakami chart. Do not restore those contours or related controls unless requested or a new question makes them useful and the user agrees.
- Keep visible graph copy concise. Show key quantities in bold, define comparison ranges near the relevant table, and avoid repeating table values at length in paragraphs.
- Give the user model details, methodological cautions, and unresolved interpretation issues separately. Do not automatically add cushion sentences or methodological disclaimers to the public article. Do not remove information needed to make a factual statement accurate.
- Use `write-blog-post` for Korean prose: direct openings, concise noun-phrase titles/headings, the author's voice, and unchanged technical terms unless simplification is requested.
- Published articles have one editable source in `posts/*.md`. Prefer Markdown with one-line iframe embeds. Reserve `drafts/` for unpublished work; do not recreate a parallel report after publication.

## Shared files and verification

- Keep this skill and its references in `.agents/skills/mlb-statcast-analysis/`. Keep reproducible analysis code in `scripts/` and published images in `assets/`; do not hide reusable code or skill instructions inside ignored `data/` folders.
- Large raw data, caches, local environments, and private credentials may remain outside Git. Share collection instructions, query metadata without secrets, dependencies, and analysis rules needed to reproduce the work. No new installation should depend on a hard-coded local environment path.
- Use the established graph paths for this article: `scripts/statcast-dashboard.html` and `scripts/murakami-dot-plot.html`. Check the actual file a post embeds, not an obsolete copy or a template containing payload placeholders.
- Verify counts, identifier uniqueness, boundary rules, sample splits, and source hashes where affected. Recheck derived tables after changing labels or definitions.
- For interaction changes, test the requested behavior at desktop and narrow content widths, including independent filters, all restoration, point selection, and overflow. Removed controls must not leave JavaScript references that stop rendering.
- Use `homepage-build` and `homepage-verify` when generated blog output is requested. Compare prose, tables, asset paths, and embeds after conversion; do not overwrite manual graph edits by blindly regenerating from a stale template.
- Commit, push, and public deployment require scope that authorizes them. Skill creation or a local article revision alone does not imply publication.

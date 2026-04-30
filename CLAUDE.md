# CLAUDE.md

**Project:** Basira (بصيرة) — Saudi satellite change monitoring
**Last updated:** 2026-04-29 (late evening, post-session 2.0)
**Purpose of this doc:** Minimum context needed to be immediately useful in a fresh chat. Not a changelog.

> For employer-specific context on the current deliverable target, load `.private/context.md` at session start. That file is gitignored and contains the specific opportunity this work is shaped for.

---

## Who I am

Ahmed Zainaddin. Electrical engineer, based in Dammam, Saudi Arabia. Early-career — still building, still choosing direction deliberately.

**Upstream background.** Hands-on satellite systems work at KACST (King Abdulaziz City for Science and Technology). Qualification-model build on SHAMS satellite. Mission analysis documentation for previous satellite launches. Three weeks as a space systems engineer handling communications-systems documentation. This is where my technical roots are: hardware, systems integration, comms.

**Downstream direction.** Over the last eight months, deliberate self-study in earth observation and machine learning. Basira is the product of that effort — the intent was always to build something real rather than just complete courses. I'm applying to KAUST Academy ML Program and to MSc programs at GMU, Edinburgh, and Glasgow. The deliberate trajectory is to become credible at both ends of the space value chain — upstream satellite engineering and downstream data products — because the most interesting roles in the Saudi space sector sit at that intersection, and few people are building on both sides simultaneously.

**How I work.** I move fast, I change course when evidence says I should, and I prefer shipping over deliberating. I keep persistent notes across sessions (this doc, session logs, master plan) because context-switching between strategy chats and code execution burns more energy than most people admit. I value direct pushback over polite agreement — if I'm about to make a mistake, I'd rather hear that in the moment than discover it later. When I say "do your recommendations" or "proceed," I sometimes mean it and sometimes I'm fatigued; a fresh Claude is right to flag when a decision is big enough that a real review is warranted.

**What I'm building toward.** Near term: a credible entry into the Saudi space sector through a role that lets me work on both satellite systems and EO products. Longer term: Basira (or its successor) as a product company that produces value from satellite data, potentially expanding into upstream capability. The company ambition is real but it's the north star, not the current objective. Right now I'm focused on building evidence that I can scope, execute, and communicate.

**Who's around me.** Mutual contacts at multiple Saudi space-sector entities. Small sector, warm introductions matter, reputation compounds. I am deliberate about not overpromising.

**Language.** English primary for technical work. Arabic native. The project name Basira (بصيرة) means insight.

---

## Current objective

**Phase 1 deliverable: portfolio-with-research-engine — cinematic homepage as table of contents, real research pages underneath.**

Three Vision 2030 megaproject chapters on the homepage (Qiddiya hero, King Salman Park, Diriyah Gate), each linking to a research deep-dive that answers one umbrella question with rigor:

> *"What can satellites honestly say about Saudi Arabia's transformation, and what are they missing?"*

This is shaped for a specific employment opportunity in the Saudi space sector — a role that rewards breadth, scoping judgment, and clean communication rather than deep methodological novelty. Framing of every artifact should reflect that: execution story and upstream-downstream narrative, not depth competition.

For the specific target, context, and timing of the outreach, see `.private/context.md`.

Approximate timeline: 4–6 months for the first two research pieces (revised from the original 4–6 week estimate when the architecture pivoted on 2026-04-27).

Full strategic framing: see `basira_master_plan.md`.

---

## Current state (as of 2026-04-29, late evening)

**Project shape.** Basira's Phase 1 deliverable is a portfolio-with-research-engine. The cinematic homepage at root `index.html` stays as-is for now; new research pages live at `/research/<slug>/`. Live at https://a7zain.github.io/basira/.

**First two research pieces, locked sequence B → A:**

### Research piece B (dust-honesty) — IN PROGRESS

Question: how does Sen2Cor's known underestimation of aerosols over deserts (Goyens 2024) translate into NDVI bias for change monitoring over Riyadh, and how often does it matter? Sources: Sentinel-2 L2A (subject), TROPOMI UVAI + VIIRS Deep Blue AOD (validation), HLS NDVI (cross-check). Method: faithful port of Lolli 2024 DBB index, recalibrate for AP. 7 sub-questions (SQ1–SQ7) plus committed SQ8 (KAUST AERONET validation). Lives at `research/dust-honesty/`.

**Sub-question status:**

- **SQ1 (port DBB index, sample 30 scenes)** — DONE. Commit `47ac3f9`. 30 scenes pulled across 3 sub-AOIs. Non-uniform stratification: **6 diriyah_gate / 11 king_salman_park / 13 qiddiya_core = 30**. DBB values uniformly negative (−0.315 to −0.219) over bright desert. Lolli formulation flagged as inspired-not-faithful in 2026-04-28 audit; superseded by faithful port (SQ1D Part B). Old `sq1_dbb_values.csv` preserved as research history.

- **SQ1 thumbnails** — iterated twice for usable labeling (commits `5bdb106`, `91a7077`). Per-AOI 2/98 percentile stretches:
  - qiddiya_core: R [0.279, 0.635], G [0.213, 0.520], B [0.136, 0.398] — preserved as SQ1-original; persisted to `sq1d_qiddiya_stretch.json`.
  - king_salman_park (old 29.93 km² bbox): R [0.185, 0.637], G [0.147, 0.534], B [0.095, 0.410] — superseded.
  - king_salman_park (new 16.6 km² bbox): R [0.162, 0.470], G [0.156, 0.368], B [0.159, 0.300] — persisted to `sq1d_ksp_stretch.json`. Hi values shrunk markedly; the bbox change shifted the radiometric calibration target.
  - diriyah_gate: R [0.070, 0.513], G [0.062, 0.454], B [0.031, 0.387]

- **SQ1 manual labels (original visual)** — DONE. Commits `9b73a75`, `442d7b0`. Distribution: 23 clean / 4 light_haze / 2 heavy_dust / 1 cloud / 0 mixed. Superseded for KSP+Qiddiya by the 2026-04-29 visually-blind relabel; preserved as `old_label` column in the relabel CSVs.

- **SQ1B (threshold tuning with bootstrap CI, original)** — STOP RULE FIRED. Commit `3d3b511`. AUC 0.55/0.51, CI half-width 0.026 vs 0.020 budget. Superseded by 2026-04-29 SQ1B re-run on faithful values.

- **SQ1D (faithful Lolli port + reference selection + visually-blind relabel + faithful compute + sensitivity)** — DONE.
  - **Lolli audit (2026-04-28).** SQ1's `dbb_index.py` was inspired-not-faithful: single-image visible-vs-SWIR ratio on L2A inputs vs Lolli's actual per-band TOA differential normalized by L2A reference reflectance. Pivot to faithful port via GEE locked.
  - **KSP bbox tightened from 29.93 km² to 16.6 km²** (commit `119db1b`). Old bbox encompassed surrounding urban perimeter; new bbox is a 4.07×4.07 km rectangle centered on Wikipedia KSP coordinates.
  - **All three reference scenes locked.** Canonical config at `research/dust-honesty/data/sq1d_references.json` (commit `859450e`):

    | AOI | Primary reference | UVAI | Sensitivity alternate |
    |---|---|---|---|
    | qiddiya_core | 2024-01-20 | +0.310 | 2021-01-10 (UVAI −1.166) |
    | king_salman_park | 2023-10-27 | −0.067 | 2024-12-05 (UVAI +0.336) |
    | diriyah_gate | 2020-04-25 | +0.082 | none (surface-stable) |

    Selection rule: cleanest UVAI from a date with surface-state representative of test scenes (not pure UVAI minimization).

  - **Visually-blind relabel (2026-04-29).** KSP (11 scenes, tightened bbox) and Qiddiya (13 scenes, unchanged bbox, SQ1-original stretch) re-rendered with date-only captions. AI pre-labeled blind to UVAI and old labels using explicit rubric (see Methodology footnote below). Researcher (Ahmed) confirmed all 24 against full-resolution montages. `final_label = ai_prelabel` for all rows. Diriyah test scenes not relabeled — surface-stable AOI, original labels stand.
  - **Final relabeled distributions:**
    - king_salman_park: 7 clean / 3 light_haze / 1 heavy_dust (was 9/1/1)
    - qiddiya_core: 11 clean / 2 light_haze / 0 heavy_dust (was 9/3/1)
    - diriyah_gate (unchanged): 5 clean / 0 light_haze / 0 heavy_dust / 1 cloud / 0 mixed
    - Combined: 23 clean / 5 light_haze / 1 heavy_dust / 1 cloud / 0 mixed
  - **Bidirectional disagreement finding (10/24 disagreements).** KSP under-flagged haze (2→4 non-clean); Qiddiya over-flagged haze (4→2 non-clean). Visual atmospheric labeling at construction-active AOIs is unreliable in BOTH directions, depending on scene content. Discussion-section paragraph for piece B.
  - **Stretch shrinkage finding.** Tightened KSP bbox produces materially different per-AOI stretch (R hi 0.637→0.470). The bbox change isn't just a scoping decision — it shifts the radiometric calibration target. Appendix-worthy.
  - **Faithful Lolli formula compute (Part B, commits `25a4233`, `76ca513`).** Spec doc at `research/dust-honesty/docs/sq1d_lolli_formula.md` documents the equation, masking, scaling, and 7 implementation choices the paper underspecifies. Implementation at `research/dust-honesty/scripts/sq1d_lolli_faithful.py` (with `--ref-mode {primary, alternate}` flag). Output at `research/dust-honesty/data/sq1d_dbb_faithful.csv` (30 rows, primary references). Self-reference unit test passed: Diriyah row with `test_id == ref_id` returned `dbb_faithful = 0` exactly. KSP monotone clean −0.022 → light_haze +0.064 → heavy_dust +0.218; sign convention matches paper (dust → DBB > 0). Old-vs-new median deltas per AOI (Diriyah +0.226, KSP +0.214, Qiddiya +0.354) confirm the formula port did the work it was meant to.
  - **Sensitivity-alternate compute (Part B', commit `31d7579`).** Output at `research/dust-honesty/data/sq1d_dbb_faithful_alt.csv` (24 rows: KSP + Qiddiya, Diriyah skipped — no alternate). Primary-vs-alternate Spearman ρ = 0.97 KSP / 0.92 Qiddiya. Ordering is stable; alternate uniformly shifts test-scene DBB by a near-uniform offset per AOI. Calibration set is robust to reference choice within the surface-state-matching constraint.
  - **§7 SZA caveat appended to formula spec.** Lolli's TOA-differential numerator cancels surface albedo to first order but not path radiance (which scales `1/cos(SZA)`). Diriyah surface-stable AOI shows the predicted seasonal pattern: clean scenes near reference date (high-sun) ≈ 0; clean scenes 6+ months from reference (low-sun) strongly negative. Marked open question for piece B discussion section. **Constraint propagated to SQ1C: positive-month selection must be SZA-aware** so the calibration-set expansion doesn't compound the confound.
  - **`n_valid_pixels > n_total_pixels` bug in primary CSV.** Root cause identified (bestEffort scale drift between two separate `reduceRegion` calls). Fix verified on alternate run; primary CSV NOT regenerated this session — md5 unchanged. Fix lands in next legitimate Part B re-run.

- **SQ1B re-run on faithful values (commit `2a019b1`)** — STOP RULE FIRED, but on sample size, not signal. 4 binary task variants + sensitivity check. Stop rule from commit `3d3b511` reused verbatim: CI half-width < 0.020 AND AUC > 0.75. Cloud-labeled row dropped from all variants.

  | variant | source | n_pos | n_neg | AUC | t_youden | CI_hw | ships |
  |---|---|---:|---:|---:|---:|---:|---|
  | V1 (heavy_dust vs clean, all) | primary | 1 | 23 | 1.000 | +0.1753 | 0.0272 | stop |
  | V2 (any-non-clean vs clean, all) | primary | 6 | 23 | 0.688 | +0.0477 | 0.1197 | stop |
  | V3 (KSP-only any-non-clean vs clean) | primary | 4 | 7 | 0.839 | +0.0558 | 0.0599 | stop |
  | V4 (KSP+Diriyah any-non-clean vs clean) | primary | 4 | 12 | 0.823 | +0.0274 | 0.0457 | stop |
  | V1_alt (V1 on alternate refs) | alternate | 1 | 18 | 1.000 | +0.2420 | 0.0320 | stop |

  AUC jumped 0.55 → 0.82–0.84 on V3/V4 vs the inspired-not-faithful baseline — formula port did the work it was meant to. Blocker is sample size: n_pos ≤ 6 across all variants, n_pos ≤ 4 on the cleanest-label scope. **Continuous DBB cleared for SQ2–SQ7 as a covariate. Binarized `is_dust_flagged` GATED behind SQ1C calibration expansion.** "Ship V4 with caveats" rejected: CI 0.046 → ~25–40% swing in flagged-day count over the 6-year window. Outputs: `sq1b_threshold_results.csv`, `sq1b_threshold_spec.md`, `sq1b_roc_curves.png`, `sq1b_bootstrap_thresholds.png`. Script: `sq1b_rerun.py`.

- **SQ1C (calibration-set expansion via UVAI-anchored positives)** — NEXT. Use TROPOMI UVAI as instrument-anchored selector for high-aerosol days; pull S2 scenes from each AOI on those days; visually-blind-label them with the same protocol (date-only caption, construction-substrate exclusion). Target n_pos ≥ 10 per AOI for V3/V4 scopes. **Constraint: SZA-aware positive-month selection** — target seasons that already exist in the negative class so the §7 SZA confound doesn't compound. Document as a new sub-question so the methodology footnote can cite cleanly.

- **SQ1B re-re-run** — QUEUED behind SQ1C output. Re-fit threshold; ship if CI < 0.020.

- **SQ2–SQ7** — QUEUED. Decide ordering when SQ1C lands. Continuous DBB usable now; binarized flag waits for SQ1C.

- **SQ8 (KAUST AERONET validation)** — committed for piece B before publishing. External validation chapter using AERONET coarse-mode AOD as gold-standard ground truth at KAUST Thuwal. Defer until SQ1D Part B–SQ7 ship.

### Research piece A (churn, hardened) — QUEUED

Inherits B's dust-flag pipeline. Re-runs Phase 4 churn analysis with dust correction applied. Approximately 5 sessions after B.

### Cut from scope

- Vision 2030 progress audit — political risk vs target sector, deferred.
- MODIS as primary source — being decommissioned (Terra Dec 2025, Aqua Aug 2026). Replaced by VIIRS + TROPOMI.
- Bird migration / cross-domain — wrong fit for my positioning.

---

## Methodology footnote (binding for B writeups)

This must appear in any SQ1B / SQ1D / B-final writeup:

> "The 30-scene calibration set was originally pre-labeled by an AI assistant (Claude) against a written rubric for atmospheric clarity (clean / light_haze / heavy_dust / cloud / mixed) and reviewed by the researcher with focus on low-confidence calls. Following the SQ1D Part A.5 finding that visual labels at construction-active AOIs were contaminated by construction substrate visually mimicking haze, the 24 scenes from construction-active AOIs (Qiddiya, King Salman Park) were re-rendered with date-only captions and re-labeled visually-blind (no UVAI, no prior label visible to the labeler) using the same rubric, augmented with an explicit construction-substrate exclusion rule: 'Construction substrate (bare beige/tan ground that is sharp-edged and stable across multiple dates) is a SURFACE feature, not atmospheric. Atmospheric features must be scene-wide veiling, not localized.' The researcher confirmed all 24 AI pre-labels without override. UVAI cross-check is a separate audit step, never an input to the label."

> "The SQ1C calibration-set expansion (2026-04-30, 43 UVAI-anchored positive candidates across all three AOIs) was AI-pre-labeled by chat-Claude against the same rubric and the same construction-substrate exclusion rule. Researcher confirmation at full resolution was deferred to a later cleanup pass; `final_label = ai_prelabel` for every row in the current state. Six of the 43 scenes (Qiddiya 2022-04-10, Qiddiya 2024-03-10, KSP 2025-07-15, Diriyah 2022-05-10, Diriyah 2022-05-20, Diriyah 2022-05-25) had partial UVAI exposure to chat-Claude during pre-labeling and are flagged with `bias_exposed_during_ai_labeling=True` in the SQ1C relabel CSVs. SQ1B re-re-run results derived from the combined 73-scene set (30 SQ1D + 43 SQ1C) are PRELIMINARY pending researcher review and must be reported as such; do not propagate to external communication before review."

---

## Flags before next session

- **Diriyah all-months UVAI CSV doesn't exist yet.** Generate `sq1d_diriyah_uvai_all.csv` to enable cross-check of the Diriyah reference (2020-04-25, UVAI 0.082) against the same data source as Qiddiya/KSP. Surface-stable AOI so likely no reference change, but the validation closes a small audit gap, and **SQ1C needs Diriyah UVAI to do positive-month selection across all 3 AOIs**. Pre-flight curl check on CDSE before any agentic prompt — **CDSE returned 503 three times this week (2026-04-28, 2026-04-28 retry, 2026-04-29 closer), do not retry-loop.** CDSE OData fallback (raw netCDF, bypasses Sentinel Hub) is the eventual production path per 2026-04-28 spike notes if 503s persist.

- **Helper port for SQ1C thumbnail batch.** `array_has_data` and `render_skip_panel` (skip-with-marker guard, commit `ec88f93`) are local to `sq1d_ksp_render_candidates_v2.py`. SQ1C will reuse `sq1d_ksp_test_blind.py` and `sq1d_qiddiya_test_blind.py` for the positive-month thumbnail batch — port the helpers there as the first step of the SQ1C kickoff prompt. ~5 minutes.

- **§7 SZA dependency in TOA differential — open question for piece B discussion.** Lolli's formula has a winter-vs-summer artifact at high-latitude or high-SZA-range targets that is not aerosol load. Documented in `sq1d_lolli_formula.md` §7. **Constrains SQ1C design:** positive-month selection must target seasons that exist in the negative class, not just whatever month UVAI is highest. Otherwise SQ1B re-re-run inherits the confound. Formal investigation (regress Diriyah residuals on `1/cos(SZA_test) − 1/cos(SZA_ref)`, or port to L2A SR to bypass TOA-path) deferred to a separate sub-question or appendix; **not in current SQ1B / SQ1C scope.**

- **`sq1d_dbb_faithful.csv` (primary) has known `n_valid > n_total` count drift.** Root cause identified and fixed in the alternate-mode run; primary CSV not regenerated this session. Fix will land in next legitimate Part B re-run (e.g., post-SQ1C re-compute on expanded calibration set).

- **Two test scripts coexist for KSP and Qiddiya:** `sq1d_ksp_render_test_v2.py` (UVAI-augmented, superseded) and `sq1d_ksp_test_blind.py` (date-only caption, current). Same pair for Qiddiya. Prune in next cleanup pass after SQ1C ships.

- **KSP bbox change → tech debt (piece A):** Phase 4 KSP greening result (3.82× new-to-lost green ratio) was computed on the old 29.93 km² bbox. Not invalidated, but no longer measures what its label claims. Decide before piece A ships: either re-run Phase 4 KSP on new 16.6 km² bbox, or document both versions with the bbox-change note.

- **GEE project `basira-494617`, Community Tier (150 EECU/mo).** `GEE_PROJECT=basira-494617` in `.env`. Now load-bearing for SQ1D Part B and onward. Tested end-to-end across 30 + 24 scenes without budget incident.

- **TROPOMI via Sentinel Hub strips qa_value** — production needs raw netCDF via Copernicus CDSE OData. SQ3 concern, not yet.

- **Sentinel Hub PU consumption** — track via SH dashboard. Free tier is 30k/month. Secondary post-GEE pivot but still credentialed.

---

## What works right now

- **SAR pipeline** (`src/preprocess_v2.py`, `src/change_detect_v2.py`): Sentinel-1 download → GCP correction → UTM → Lee filter → log-ratio change detection → K-means (k=5)
- **Sentinel-2 monthly time series**: 76 scenes Jan 2020 – Apr 2026, Riyadh AOI, 20m, 4 bands (B02/B03/B04/B08), UTM 38N
- **NDVI analytics**: per-pixel time series, greening map, ROI time series, anomaly detection, hotspot ranking, pixel-level classification
- **Web dashboard**: Leaflet.js, deployed GitHub Pages, shows greening map, ROI polygons, before/after slider, hotspots, per-cell charts
- **Auto-generated PDF report**: `src/generate_report_pdf.py`
- **Phase 1 pipeline**: KML-based AOI registry (with tightened KSP bbox), polygon-clipped Sentinel-2 downloader, RGB timelapse generator. Scripts: `src/phase1_aois.py`, `src/phase1_download.py`, `src/phase1_quicklook.py`, `src/phase1_timelapse.py`
- **Phase 1 data**: 76 months × 3 AOIs, 10 m, 6 bands (B02/03/04/08/11/12), ~387 MB total
- **Phase 1 timelapses**: RGB GIFs per AOI, fixed cross-stack contrast, 4 fps, polygon-outlined
- **Basira cinematic site** (`index.html`): 8-chapter skeleton, per-GIF blurred Sentinel-2 context via CSS mask-image, IntersectionObserver autoplay + scale/fade. Served locally at port 8888.
- **Wide-context backdrops** (`assets/backdrops/`) and **polygon masks** (`assets/masks/`).
- **Aerosol spike infrastructure**: TROPOMI UVAI accessible via Sentinel Hub Process API on CDSE for any single date. VIIRS Deep Blue AOD via GEE (project `basira-494617`).
- **SQ1D faithful-Lolli pipeline (DONE — both arms):**
  - All-months TROPOMI UVAI search at Qiddiya (302 rows) and KSP on tightened bbox (320 rows). Diriyah pending (CDSE 503).
  - Stratified candidate selection (Pool A early-clean + Pool B recent-clean).
  - Per-AOI 2/98 stretch with no-data filter (`v > 0` before percentile).
  - Date-only caption rendering for visually-blind labeling.
  - AI pre-label + researcher-review workflow with explicit construction-substrate rubric.
  - Canonical references config at `sq1d_references.json` consolidating all 3 AOIs (primary + sensitivity alternates).
  - 24 visually-blind relabels merged into `sq1d_ksp_relabel.csv` and `sq1d_qiddiya_relabel.csv`.
  - **Faithful Lolli formula spec at `sq1d_lolli_formula.md`** (equation, masking, scaling, 7 paper-underspecified implementation choices, §7 SZA caveat).
  - **Faithful Lolli compute at `sq1d_lolli_faithful.py`** (GEE, `--ref-mode {primary, alternate}`, single-image single-reducer count handling).
  - **30-scene primary DBB at `sq1d_dbb_faithful.csv`**; 24-scene sensitivity-alternate DBB at `sq1d_dbb_faithful_alt.csv`. Primary-vs-alternate Spearman ρ = 0.97 KSP / 0.92 Qiddiya — ranking stable.
- **SQ1B re-run pipeline (DONE):** 4 binary task variants + sensitivity check at `sq1b_rerun.py`. Outputs at `sq1b_threshold_results.csv`, `sq1b_threshold_spec.md`, `sq1b_roc_curves.png`, `sq1b_bootstrap_thresholds.png`. Stop rule extracted from `3d3b511` reused verbatim.
- **Hardened thumbnail batch silent-failure guard.** `array_has_data` + `render_skip_panel` skip-with-marker mode in `sq1d_ksp_render_candidates_v2.py` (commit `ec88f93`). Standard going forward; pending port to test-scene renderers.

## What's parked or incomplete

- **SQ1C (calibration-set expansion)**: not yet started. SQ1B re-re-run gated on this. SQ1C is also gated on Diriyah UVAI CSV (CDSE 503 retry) and on porting the array-has-data helpers to test-scene renderers.
- Multi-city (Jeddah, etc.): on `wip/phase5-multicity` branch, not in Phase 1 scope.
- Before/after sliders: placeholder in HTML, JS not yet written.
- MP4 timelapses: GIFs used for now; MP4 render + `<video>` swap is next.
- All cinematic-site prose: `[DRAFT]` markers throughout Ch 1–6; written after research pages exist.
- SAR-optical fusion as a clean single product: not yet done.
- Technical memo: not yet written.
- Cosmetic cleanup: per-AOI stretch + bbox crop convention worth applying to other figures across the project as a separate cleanup pass after B ships.

---

## Working rhythm

- **This chat (Claude)**: strategy, planning, document drafting, review. No code execution here.
- **Claude Code**: all file operations, commits, code changes. Prompts from this chat are pasted into Claude Code.
- **Per-objective cleanup pass**: one cleanup at each objective boundary. Not two.
- **Per-session logs**: committed to `docs/sessions/YYYY-MM-DD.md` at session end. One day = one log even if multiple chats; combine in a single file with Part 1 / Part 2 sections.
- **End-of-session ritual**: at session end, Claude produces COMPLETE drop-in versions of `CLAUDE.md` and the dated `docs/sessions/YYYY-MM-DD.md` (full file replacements, not section edits). Ahmed overwrites the local files entirely, runs `git add -A && git commit && git push`, then clicks "Sync now" in the Claude Project to pull the latest from GitHub into the Project snapshot. Sync now is required because Projects don't auto-sync from GitHub — they're snapshots.
- **Claude Code prompts**: phrased as full sequences with verification at end. Single review point at end, not interleaved approvals. Only stop for destructive/irreversible operations (force push, mass delete, credential exposure, history rewrite).

---

## Operational guardrails (learned the hard way)

**Worktree drift.** Claude Code has previously created git worktrees under `.claude/worktrees/` and silently broken sessions multiple times. Every Claude Code prompt must include: *"Work directly on the main working tree. Do NOT create a git worktree under .claude/worktrees/. If you think you need one, stop and ask."*

**Verification discipline.** Claude Code has reported success on operations it hadn't completed multiple times. Always verify artifacts directly using `grep`, `ls -la`, `head`, `wc -l`, and `git status` as ground truth — never trust a success message alone. Visual review of generated images is also part of verification: 2026-04-29 caught a silent render failure (2025-11-27 KSP candidate) that the stop-on-fail guard didn't fire on. Now hardened with skip-with-marker (commit `ec88f93`).

**Force-add precedent.** Files under `research/dust-honesty/data/` are covered by a broad gitignore. Calibration data that must be reproducible (CSVs, stretch JSON, manual labels, relabel artifacts, faithful-DBB CSVs, threshold-result CSVs, ROC plots) is force-added per `442d7b0` precedent (`git add -f`).

**Self-reference unit tests.** When implementing a formula on a calibration set, design in a test where test-input == reference-input so the math reduces to a known answer (typically zero). Costs nothing; catches numerical artifacts and pairing bugs the moment the formula is implemented. Used 2026-04-29 to validate Part B's faithful Lolli compute (Diriyah 2020-04 / 2020-04-25 → DBB = 0 exactly).

**Single-reducer counts on GEE.** `bestEffort=True` + multiple `reduceRegion` calls on the same image can return slightly different sample counts at scale boundaries (silent drift). Standard pattern: single image, single reducer combining `sum + count`, no `bestEffort`, identical scale across runs.

**Skip-with-marker over raise-loudly for batch operations.** A failed slot in a batch render either should raise loudly with full context (killing the batch) or render a visibly-blank panel with a labeled skip reason (preserving batch). The unacceptable middle ground is silent failure (zero-array → stretched → captioned → looks-rendered). Pattern locked 2026-04-29 (`array_has_data`, `render_skip_panel`).

**CDSE multi-day 503 pattern.** CDSE has returned 503 on three separate days this week. Pre-flight `curl -s -o /dev/null -w "%{http_code}\n" https://sh.dataspace.copernicus.eu` before any agentic prompt that depends on CDSE. If 503, abort the dependent phase and continue with independent work; do not retry-loop. CDSE OData fallback (raw netCDF, bypasses Sentinel Hub) is the eventual production path per 2026-04-28 spike notes.

**Credential hygiene.** Sentinel Hub OAuth credentials, GEE project name, and any API tokens stay in `.env` only. `.env` is gitignored. `.private/context.md` for SARsatX-specific framing also gitignored.

---

## Open questions and things to decide

- Chart design per project chapter (Qiddiya = built area, KSP = NDVI, Diriyah = TBD — probably vegetation/built blend). Defer until research pages and cinematic-site exit ramps are wired together.
- SAR-optical fusion design spec: to be drafted before Phase 1 build begins. Held for now pending research-piece completion.
- Outreach message framing: draft closer to send date, not now.
- **§7 SZA dependency formal investigation.** Open question for piece B discussion section. Two paths if elevated to a sub-question: (a) regress Diriyah residuals on `1/cos(SZA_test) − 1/cos(SZA_ref)` and report slope; (b) port Lolli to L2A SR to bypass TOA-path. Decision deferred until SQ1B re-re-run lands; do not let this expand current scope.
- **KAUST AERONET validation chapter (committed for piece B).** Active AERONET stations in/near KSA during 2020-2026: KAUST Campus (Thuwal, 22.3N 39.1E, operational through 2024), Mezaira UAE, Bahrain. Solar Village (Riyadh, 24.91N 46.41E — only ~25 km from current AOIs) is dead since January 2013, so no AERONET ground truth exists for the exact Riyadh atmospheric column during the study window. Plan: piece B's primary calibration stays at the 3 Riyadh AOIs against TROPOMI UVAI as ground truth. KAUST Thuwal added as SQ8 — external validation chapter using AERONET coarse-mode AOD as gold-standard. KAUST surface differs from Riyadh (coastal, not bright desert), so this is also a generalization test, not pure replication. Hard commitment, not optional. Defer until SQ1D Part B–SQ7 ship; do not let it expand current scope.

---

## What NOT to do

- Do not re-litigate the TPM-track vs. EO-specialist framing. Decision made 2026-04-20.
- Do not expand Phase 1 scope. The three projects are the scope.
- Do not suggest paid imagery (Planet, Maxar) for Phase 1. Sentinel is the constraint, deliberately.
- Do not treat the longer-arc company vision as the active objective. North star, not map.
- Do not re-litigate the cinematic NYT-feature direction. Locked 2026-04-21.
- Do not re-litigate the portfolio-with-research-engine pivot. Locked 2026-04-27.
- Do not auto-label calibration scenes from UVAI as a shortcut. UVAI selects which months to pull; visual labels remain the calibration target. Conflating the two collapses SQ3 validation into circularity.
- **Do not re-render test thumbnails with UVAI in caption.** Visually-blind protocol established 2026-04-29. UVAI is post-labeling audit, never input.
- **Do not propagate any V1–V4 SQ1B threshold to SQ2–SQ7 as a production dust flag.** Continuous DBB is the covariate; binarized flag is gated behind SQ1C.
- **Do not pick SQ1C positive months on max-UVAI alone.** Must be SZA-aware: target seasons that already exist in the negative class so SQ1B re-re-run isn't compounding the §7 confound.

---

## Active credentials and infrastructure

- Copernicus Dataspace: ahmadxgpx@gmail.com
- Sentinel Hub OAuth client: active (30K PU/month free tier)
- GEE project: `basira-494617` (Community Tier, 150 EECU/mo)
- GitHub: `a7zain/basira` (repo renamed from `sar-change-detection`)
- Local path: `/Users/a7zain/basira`
- Conda env: `sarsat`
- Deployed dashboard: GitHub Pages at https://a7zain.github.io/basira/

# CLAUDE.md

**Project:** Basira (بصيرة) — Saudi satellite change monitoring
**Last updated:** 2026-05-02 (post-SQ8-ship, operational null with quantified upper bound across the loading regime at Riyadh)
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

## Current state (as of 2026-05-02, end of long session)

**Project shape.** Basira's Phase 1 deliverable is a portfolio-with-research-engine. The cinematic homepage at root `index.html` stays as-is for now; new research pages live at `/research/<slug>/`. Live at https://a7zain.github.io/basira/.

**Piece B (dust-honesty) — DATA + ANALYSIS COMPLETE; PIECE B PROSE IS THE NEXT ACTIVE WORK.** All six executed sub-questions have shipped findings notes; no remaining sub-question is on the piece B critical path. The umbrella question is fundamentally answered at this site at this loading regime.

**Piece B headline (locked across SQ2/SQ3/SQ4/SQ4B/SQ5/SQ8):** Across two correction chains (Sen2Cor + LaSRC), two NIR bands (B8 broad + B8A narrow), paired and per-scene regression designs, and reanalysis-AOD up to Q4 dust loadings at Riyadh, AOD-dependent NDVI bias does not exist at operationally meaningful magnitude. The largest detectable AOD–NDVI relationship at this site is −0.002 NDVI per IQR of AOD, with 95% CI lower bound −0.003 — sub-operational across the loading regime spanned by the SQ2 manifest. NDVI-as-ratio cancellation between Red and NIR perturbations is the surviving mechanism after correction-chain-specific absorption (SQ4), NIR-band-shift artifacts (SQ4B), and high-AOD threshold breakdown (SQ8) are all ruled out at operational magnitude.

---

## Sub-question status

### Piece B (dust-honesty) — `research/dust-honesty/`

Question: how does Sen2Cor's known underestimation of aerosols over deserts (Goyens 2024) translate into NDVI bias for change monitoring over Riyadh, and how often does it matter? Sources: Sentinel-2 L2A (subject), TROPOMI UVAI (validation, all three AOIs from GEE COPERNICUS/S5P/OFFL/L3_AER_AI), HLS NDVI (cross-check at SQ4/SQ4B), MERRA-2 DUEXTTAU + CAMS NRT (high-AOD regression at SQ8). Method: faithful port of Lolli 2024 DBB index, recalibrated for AP.

- **SQ1, SQ1B (original), SQ1C, SQ1D (faithful Lolli port + reference selection + visually-blind relabel + faithful compute + sensitivity)** — DONE 2026-04-28 to 2026-05-01. Confirmed labels: 73-scene calibration set, 12 researcher overrides (27.9% disagreement vs AI pre-labels), AOI-dependent bias direction (Qiddiya/KSP softened toward clean, Diriyah hardened toward heavy_dust). V4 (KSP+Diriyah any-non-clean vs clean) ships at AUC 0.853, CI half-width 0.012, threshold +0.034. Lead calibration result.

- **SQ2 (apply calibrated DBB flag to operational 228-scene set)** — DONE 2026-05-01. V4 fire rates: Diriyah 11.8% (concentrated Apr–Jul, matches independent shamal climatology), KSP 32.4%, Qiddiya 75.0%. The 75% rate at Qiddiya is the **fifth** independent line of evidence for bidirectional construction-substrate contamination at that AOI.

- **SQ3 (NDVI bias on V4-flagged vs unflagged scenes)** — DONE 2026-05-02. Paired temporal-neighbor design, ±60-day window. KSP halfwidth 0.0076 tight_null, Qiddiya halfwidth 0.0055 tight_null (28.1% retention accepted with caveat — structural consequence of the 75% V4 fire rate, not a noise problem), Diriyah wide_inconclusive at n=8. Conditional null at moderate Riyadh-region atmospheric loadings.

- **SQ4 (HLS S30 NDVI cross-check, B8A LaSRC)** — DONE 2026-05-02. Reused SQ3's 38 pairs, computed Δ_HLS − Δ_Sen2Cor per pair. KSP halfwidth 0.0071 tight_null, Qiddiya halfwidth 0.0047 tight_null, Diriyah wide_inconclusive at n=8. The SQ3 conditional null is **not Sen2Cor-specific.** Coverage 100%/93.8%/100%; one Qiddiya pair lost to a fully-Fmask-rejected fully-clouded scene (honest drop). In-build correction surfaced: `coll.first()` was losing 39/65 tuples to MGRS sliver-coverage tiles; switched to `coll.mosaic()` and re-ran.

- **SQ4B Arm A (B8 NIR sensitivity on HLS S30 LaSRC)** — DONE 2026-05-02. Same SQ3 pairs, B8 broad NIR (~833nm) instead of B8A narrow (~865nm). KSP halfwidth 0.0028 tight_null, Qiddiya halfwidth 0.0022 tight_null, Diriyah wide_inconclusive at n=8. Halfwidths 3–4× tighter than SQ4 — narrow-to-broad NIR swap on the same chain is a smaller perturbation than chain-change at fixed band. Spearman B8-vs-B8A = 0.868 across 64 shared (aoi, date) rows with ~0.02–0.03 NDVI absolute offset (narrow consistently > broad), which the per-pair Δ design absorbs cleanly. The diff_of_diffs design's insensitivity to absolute-level band offsets is itself a methodology robustness story.

- **SQ4B Arm B (HLS L30 cross-correction-chain at high-AOD)** — DEFERRED to SQ4C. Pre-registered 50% L30 coverage floor failed in two of three AOIs (Qiddiya 33.3%, Diriyah 42.9%; KSP 54.2%; total 43.1%). Root cause: structural cadence mismatch (S2A+B ~5d revisit vs L8+L9 ~8d, prior of L30 within ±1d of any S2 date ~37.5%). Halt-and-defer per pre-registration discipline. The L30 coverage probe ships as recon receipt at commit `71327ec`.

- **SQ5 (high-AOD subset analysis via TROPOMI UVAI Q4-vs-Q1 paired design)** — HALTED-WITH-RECEIPT 2026-05-02. Pre-registered 30% retention floor failed in all three AOIs (KSP 0.0%, Qiddiya 11.1%, Diriyah 11.1%). Root cause: Riyadh's UVAI seasonality clusters Q1 (low) in winter and Q4 (high) in spring/summer; the two quartiles do not temporally interleave at ±60d. Paired temporal-neighbor designs are mathematically incompatible with this site's UVAI seasonality. Goyens-regime test inherited to SQ8 with regression design. **Two findings ride out of SQ5 despite the halt:** (1) seasonal-stratification methodology finding — paired designs cannot probe high-AOD vs low-AOD contrasts at moderate-aridity Saudi sites; (2) UVAI×V4 contingency (Diriyah Q4∧¬V4 = 12 scenes is the cleanest Goyens-regime cell; Qiddiya Q4∧V4 = 16/18 scenes is a **sixth** independent line of evidence for the construction-substrate finding; KSP Q4 splits ~evenly between V4-fired and not).

- **SQ8 (Goyens-regime per-scene regression at Riyadh, reanalysis-AOD primary)** — DONE 2026-05-02. AERONET R1 halt confirmed no operational station within 500km of Riyadh during the SQ2 window (Solar_Village dead 2015-10-12, ~30km in-AOI; Bahrain dead 2007-03-06, ~424km; UAE cluster ~750–800km outside the 500km outer ring). Retargeted to MERRA-2 DUEXTTAU primary (dust-specific extinction, mechanistic match to TROPOMI UVAI) with CAMS NRT total AOD as cross-check. Per-scene NDVI residual (relative to per-AOI monthly climatology) regressed on per-scene AOD, AOI fixed effects, HC3 robust SEs.

  **Pre-registered classifier and magnitude criterion BOTH fired on this result** — that disagreement is itself surfaced as a methodology observation. Classifier output: `goyens_consistent_bias_detected` (CI excludes zero, β<0, p=0.024, replicated by CAMS at p=0.017 with sign agreement and CI overlap). Magnitude criterion: `tight_null` (β × IQR = −0.0018 NDVI, 2.8× below the pre-registered 0.005 NDVI operational-significance threshold and ~25× below typical change-detection thresholds). Per-AOI regressions all individually null (p = 0.138 / 0.169 / 0.208 for KSP / Qiddiya / Diriyah). Diriyah Q4∧¬V4 anchor cell prediction CI [−0.0046, +0.0011] straddles zero. R² = 0.028 (primary), 0.013 (cross-check) — AOD explains 1–3% of residual variance.

  **Framing decision (Option 4):** read as **power-confirmation of the SQ3/SQ4/SQ4B operational null, not as Goyens transfer.** The regression had sensitivity to detect a 0.002 NDVI effect, and that is what it detected. The Bayesian inverse holds: the test demonstrably has the power to detect operationally relevant magnitudes if they were present at high loadings, and they are not. Operational-magnitude criterion is the load-bearing one for the umbrella question.

### Deferred (post-piece-B, no piece B critical path)

- **SQ4C (native L30 pair construction)** — Different pair design than SQ4B Arm B's failed reuse: Landsat pairs built on Landsat overpass dates, Sen2Cor matched via ±k-day window. Two open scoping questions: (a) value of k; (b) V4-on-Landsat vs V4-on-Sentinel-2 as trigger. SQ8's operational null obviates the urgency — adding a third correction chain doesn't change the headline.

- **SQ8B (KAUST Thuwal AERONET as Saudi-coastal generalization test)** — Different scientific question from SQ8 (generalization across surface and coastal-vs-inland regime). KAUST is ~820km from Riyadh, coastal not bright-desert. The CLAUDE.md "hard commitment" framing pre-dating SQ8 is reconciled here: SQ8-as-shipped delivers the Riyadh Goyens question; SQ8B is the coastal generalization question that the AERONET commitment now points at. Defer until piece B prose surfaces a need.

- **Original-SQ5 (seasonal modulation)** and **SQ6 (per-AOI continuous bias regression)** — SQ6 partially answered by SQ8's AOI fixed effects (per-AOI betas all individually null). Both elaborate the existing finding chain; defer until piece B prose surfaces a need.

- **§7 SZA dependency formal investigation** — open question for piece B discussion section. Decision deferred. Two paths if elevated: (a) regress Diriyah residuals on `1/cos(SZA_test) − 1/cos(SZA_ref)` and report slope; (b) port Lolli to L2A SR to bypass TOA-path. Do not let this expand current scope.

- **Naming rationalization** — `sq1d_*` / `sq1c_*` / `sq1b_rerun_v2_*` / `sq1b_rerun_v2_confirmed_*` / `sq2_*` / `sq3_*` / `sq4_*` / `sq4b_*` / `sq5_*` / `sq8_*` are process-of-discovery names; end-state taxonomy needed (suggested grouping: calibration-sets / DBB-compute / threshold-fits / operational / NDVI-bias / cross-correction / high-AOD-regression). Owed before piece B prose; can ride along inside any execution session, not a gate on piece B prose drafting.

### Open piece B prose decision (not a methodology decision)

- **Qiddiya construction-substrate finding — own subsection vs threaded through SQ2 narrative?** The convergence is now **six independent lines** of evidence: (1) SQ1D Pass 5 visually-blind relabel direction; (2) SQ1D Part B' sensitivity ρ=0.92; (3) V2 prelim AUC drop; (4) V2 confirmed AUC drop; (5) SQ2 baseline DBB +0.091 well above threshold (75% V4 fire rate); (6) SQ5 R5 contingency Q4∧V4 = 16/18 = 89%. Plus SQ8's AOI fixed effects validating the AOI-baseline-difference reading at the regression level. Six-fold convergence is structurally novel for a satellite-only methodology piece; whether it warrants its own subsection or stays threaded through SQ2 depends on the piece B narrative arc. Decide when prose drafting is in flight.

---

## What works right now

- **Phase 1 data**: 76 months × 3 AOIs, 10 m, 6 bands (B02/03/04/08/11/12), ~387 MB total.
- **Phase 1 timelapses**: RGB GIFs per AOI, fixed cross-stack contrast, 4 fps, polygon-outlined.
- **Basira cinematic site** (`index.html`): 8-chapter skeleton, per-GIF blurred Sentinel-2 context via CSS mask-image, IntersectionObserver autoplay + scale/fade. Served locally at port 8888.
- **Wide-context backdrops** (`assets/backdrops/`) and **polygon masks** (`assets/masks/`).
- **TROPOMI UVAI** all three AOIs from GEE `COPERNICUS/S5P/OFFL/L3_AER_AI` band `absorbing_aerosol_index` (KSP 320, Qiddiya 302, Diriyah 300 rows). Schema asymmetry: per-AOI CSVs lack an `aoi` column; AOI is implicit in filename and must be injected on load. Documented at SQ5.
- **VIIRS Deep Blue AOD** via GEE (project `basira-494617`) — listed as available in earlier sessions, but no cached CSV exists in `research/dust-honesty/data/`. Fresh GEE pass would be required if invoked. Surfaced at SQ8 R3.
- **MERRA-2 dust extinction** via GEE `NASA/GSFC/MERRA/aer/2` band `DUEXTTAU` (550nm dust optical depth). Hourly cadence. ~55×70km native resolution. Established at SQ8.
- **CAMS Near-Real-Time AOD** via GEE `ECMWF/CAMS/NRT` band `total_aerosol_optical_depth_at_550nm_surface`. **3-hourly cadence** at validity 00/03/06/09/12/15/18/21 UTC. ~44km native resolution. Established at SQ8.
- **HLS S30** (LaSRC-corrected Sentinel-2 surface reflectance) via GEE `NASA/HLS/HLSS30/v002`. B4 (Red), B8 (NIR broad ~833nm), B8A (NIR narrow ~865nm), Fmask. Established at SQ4/SQ4B. **Use `coll.mosaic()` not `coll.first()`** — `first()` silently drops MGRS sliver-coverage tiles.
- **HLS L30** (LaSRC-corrected Landsat 8/9 surface reflectance) via GEE `NASA/HLS/HLSL30/v002`. B4 (Red), B5 (NIR ~865nm), Fmask. **L30 ±1d coverage on Sentinel-2 acquisition dates is ~37–54% at Riyadh** due to cadence mismatch (S2A+B ~5d vs L8+L9 ~8d). Native L30 pair construction (SQ4C) is required for usable retention.
- **SQ1D faithful-Lolli pipeline** (DONE — both arms, bug-fixed reducer): per-AOI 2/98 stretch, persisted to `sq1d_<aoi>_stretch.json`; date-only caption rendering for visually-blind labeling; AI pre-label + researcher-review workflow with explicit construction-substrate rubric; canonical references at `sq1d_references.json`; 24 visually-blind relabels merged into `sq1d_<aoi>_relabel.csv`; faithful Lolli formula spec at `sq1d_lolli_formula.md`; faithful Lolli compute at `sq1d_lolli_faithful.py` (single-image single-reducer count handling); 30-scene primary DBB at `sq1d_dbb_faithful.csv`; 24-scene sensitivity-alternate at `sq1d_dbb_faithful_alt.csv` (Spearman ρ = 0.97 KSP / 0.92 Qiddiya).
- **Scene manifest pattern** (DONE 2026-04-30): `sq1d_scene_manifest.csv` (30), `sq1c_scene_manifest.csv` (43), `sq2_scene_manifest.csv` (228). Test renderers read manifest first; deterministic-pick fallback with WARNING log. Date-based fetch + `assert_manifest_match(system_index)` is the safe pattern.
- **SQ1C pipeline** (DONE 2026-05-01 — confirmed labels): GEE TROPOMI UVAI source-check, Diriyah UVAI all-months search, per-AOI negative-class month distribution + month-bin SZA-aware seasonal balance constraint, top-15 candidate selection per AOI, S2 L2A scene matching at ±3d / ≤20% cloud, manifest-locked render, per-AOI test montages, relabel CSVs, confirmation tooling (`sq1c_label_review.py`, `sq1c_label_comparison.py`, `sq1b_rerun_v2_confirmed.py`), confirmation audit at `sq1c_confirmation_audit.csv`.
- **SQ1B pipelines**: original re-run at `sq1b_rerun.py`; re-re-run on combined preliminary at `sq1b_rerun_v2.py`; re-re-run on combined confirmed at `sq1b_rerun_v2_confirmed.py`. Combined 73-scene calibration at `sq1bc_combined_calibration_confirmed.csv`. Confirmed-vs-preliminary comparison table emitted in `sq1b_rerun_v2_confirmed_threshold_spec.md`.
- **SQ2 operational pipeline** (DONE 2026-05-01 late evening): V4 (+0.034) and V3 KSP-only (+0.053) thresholds applied to 228 (aoi, year, month) operational scenes via `sq2_apply_flag.py`. Manifest-locked at `sq2_scene_manifest.csv` (30 cal_lock_sq1d + 27 cal_lock_sq1c + 171 gee_pick). Self-reference unit test at run start (DBB = 0 exactly). AOI-local cloud handling via QA60 bits 10+11. Cross-check vs `sq1bc_combined_calibration_confirmed.csv` at 1e-4 tolerance; failures logged to `sq2_cross_check_failures.csv`. Per-AOI + combined timeseries plots at `sq2_plot_timeseries.py`. Findings note at `research/dust-honesty/docs/sq2_findings.md` (§2 framing tightened + §6 cross-validation sentence in `a6d4a12`).
- **SQ3 NDVI-bias pipeline** (DONE 2026-05-02): fresh GEE NDVI compute on locked SQ2 manifest at `sq3_compute_ndvi.py`; pairing + bootstrap at `sq3_pair_and_diff.py` (±60-day same-AOI nearest unflagged neighbor, 1000-resample bootstrap on pairs); plots at `sq3_plot_deltas.py`; findings note at `sq3_findings.md`. Outputs: `sq3_ndvi_per_scene.csv` (228 rows, 226 with NDVI), `sq3_ndvi_bias.csv` (38 pair rows), `sq3_pairing_audit.csv`.
- **SQ4 HLS S30 cross-correction-chain pipeline** (DONE 2026-05-02): NDVI compute on SQ3 pair dates at `sq4_compute_hls_ndvi.py` (B8A LaSRC, mosaic() pattern, Fmask bits 1–4 masked); diff-of-diffs + bootstrap at `sq4_pair_diff.py`; figures at `sq4_summary.py`; findings note at `sq4_findings.md`. Outputs: `sq4_hls_ndvi.csv`, `sq4_diff_of_diffs.csv` (37 rows), `sq4_signal_class.csv`.
- **SQ4B Arm A B8 NIR-sensitivity pipeline** (DONE 2026-05-02): same shape as SQ4 with B8 broad NIR, mosaic() pattern, Fmask bits 1–4. L30 coverage probe at `sq4b_probe_l30_coverage.py` ships as recon receipt for the Arm B → SQ4C deferral. Findings note at `sq4b_findings.md`. Outputs: `sq4b_b8_s30_ndvi.csv`, `sq4b_arm_a_b8_sensitivity.csv` (37 rows), `sq4b_two_by_two_summary.csv`, `sq4b_l30_coverage_probe.csv`.
- **SQ5 halt-with-receipt** (DONE 2026-05-02): UVAI quartile labeling at `sq5_uvai_subset.py`; pair retention probe at `sq5_pair_retention_probe.py`; seasonal stratification chart at `sq5_seasonal_stratification_chart.py`; findings note at `sq5_findings.md`. No pair-and-diff scripts written — the design halted in recon. Outputs: `sq5_uvai_labels.csv`, `sq5_uvai_v4_contingency.csv`, `sq5_pair_retention_probe.csv`, `sq5_seasonal_stratification.csv`, one figure.
- **SQ8 Goyens-regime regression pipeline** (DONE 2026-05-02): AOD fetch (MERRA-2 DUEXTTAU + CAMS NRT) at `sq8_aod_fetch.py` with **per-source temporal windows** (MERRA-2 ±60min, CAMS ±120min — CAMS is 3-hourly not hourly); per-AOI per-month NDVI climatology + residuals at `sq8_climatology_residuals.py`; OLS with AOI fixed effects + HC3 + cross-check + sensitivity at `sq8_regression.py`; figures + summary stats + findings note at `sq8_summary.py`. Outputs: `sq8_aod_per_scene.csv` (228 rows), `sq8_ndvi_residuals.csv` (226 rows, sensitivity_flag=False all), `sq8_regression_primary.csv`, `sq8_regression_crosscheck.csv`, `sq8_regression_sensitivity.csv`, `sq8_predicted_residuals.csv`, `sq8_signal_class.csv`, `sq8_summary_stats.md`, five figures, findings note.

---

## Working rhythm

- **This chat (Claude)**: strategy, planning, document drafting, review. No code execution here.
- **Claude Code**: all file operations, commits, code changes. Prompts from this chat are pasted into Claude Code.
- **Per-objective cleanup pass**: one cleanup at each objective boundary. Not two.
- **Per-session logs**: committed to `docs/sessions/YYYY-MM-DD.md` at session end. One day = one log even if multiple chats; combine in a single file with Part 1 / Part 2 / Part 3 sections.
- **End-of-session ritual**: at session end, Claude produces COMPLETE drop-in versions of `CLAUDE.md` and the dated `docs/sessions/YYYY-MM-DD.md` (full file replacements, not section edits). Ahmed overwrites the local files entirely, runs `git add -A && git commit && git push`, then clicks "Sync now" in the Claude Project to pull the latest from GitHub into the Project snapshot. Sync now is required because Projects don't auto-sync from GitHub — they're snapshots.
- **Claude Code prompts**: phrased as full sequences with verification at end. Single review point at end, not interleaved approvals. Only stop for destructive/irreversible operations (force push, mass delete, credential exposure, history rewrite).
- **Permissions config**: `.claude/settings.local.json` configured with `defaultMode: acceptEdits` plus deny rules for the patterns that have actually burned this project (worktree creation, force push, hard reset, blanket rm, `.env` reads). Auto-mode replaces `--dangerously-skip-permissions` with classifier-backed approval for routine ops; deny rules still fire even in bypass mode.

---

## Operational guardrails (learned the hard way)

**Worktree drift.** Claude Code has previously created git worktrees under `.claude/worktrees/` and silently broken sessions multiple times. Every Claude Code prompt must include: *"Work directly on the main working tree. Do NOT create a git worktree under .claude/worktrees/. If you think you need one, stop and ask."*

**Verification discipline.** Claude Code has reported success on operations it hadn't completed multiple times. Always verify artifacts directly using `grep`, `ls -la`, `head`, `wc -l`, and `git status` as ground truth — never trust a success message alone.

**Force-add precedent.** Files under `research/dust-honesty/data/` are covered by a broad gitignore. Calibration data that must be reproducible is force-added per `442d7b0` precedent (`git add -f`).

**Self-reference unit tests.** When implementing a formula on a calibration set, design in a test where test-input == reference-input so the math reduces to a known answer (typically zero). Costs nothing; catches numerical artifacts and pairing bugs the moment the formula is implemented. Re-asserted at SQ2 run start: DBB = 0 exactly when KSP test = ref. Generalized at SQ3/SQ4/SQ4B/SQ8: same date queried twice must produce exactly identical output values.

**Cross-check across runs.** Any time a scene has been computed in a prior pipeline, cross-check the new compute against the old at tight tolerance (1e-4 standard). Failures surface drift mechanisms; passing rows confirm value-stability. The SQ2 cross-check vs `sq1bc_combined_calibration_confirmed.csv` was the only reason GEE drift mechanism #3 surfaced.

**GEE drift mechanism #1 — catalog backfill on deterministic pick.** GEE can backfill scenes with updated processing baselines that change which scene wins a deterministic-pick query. Defense pattern: lock `system:index` per (aoi, slot) in a sidecar manifest at first labeling; renderers read manifest first; deterministic-pick is fallback only with WARNING log. Date-based fetch + `assert_manifest_match(system_index)` is the safe pattern.

**GEE drift mechanism #2 — `bestEffort` scale drift on multiple reducers.** `bestEffort=True` + multiple `reduceRegion` calls on the same image can return slightly different sample counts at scale boundaries (silent drift). Standard pattern: single image, single reducer combining `sum + count`, no `bestEffort`, identical scale across runs.

**GEE drift mechanism #3 — baseline reprocessing on locked `system:index`.** GEE retains the right to backfill the underlying L1C/L2A pixel content for a scene whose `system:index` is already locked in a manifest. The manifest pattern protects scene IDENTITY but NOT pixel CONTENT. Surfaced 2026-05-01 via SQ2 cross-check: 2 of 57 KSP overlap rows shifted ≤1.6% in pixel value while keeping V4 flag classifications stable. Mitigation: cross-check value-stability across runs at tight tolerance, surface failures honestly, and rely on threshold margin to absorb sub-classification-flip drift. Above ~5% pixel drift, classifications would flip and a frozen GEE asset export becomes the only protection — out of scope for piece B.

**GEE drift mechanism #4 — single-image queries on tile-boundary AOIs (HLS).** `coll.first()` on HLS S30 silently returns MGRS sliver-coverage tiles when an AOI sits near a tile boundary. SQ4 lost 39/65 tuples this way before the pattern was caught and replaced with `coll.mosaic()`. Standard pattern for HLS: `coll.mosaic()` not `coll.first()`. Document mosaic() vs first() rationale in script header for any HLS query.

**GEE pattern note — reanalysis temporal cadence is per-source.** MERRA-2 aerosol is hourly (8760 timesteps/year). CAMS NRT is 3-hourly at validity 00/03/06/09/12/15/18/21 UTC (2920 timesteps/year). A naive ±60min matching window around an S2 acquisition (typical 07:30 UTC over Riyadh) fails CAMS entirely. Per-source windows are required: MERRA-2 ±60min, CAMS ±120min. Surfaced at SQ8 mid-run; not strictly a drift mechanism but the same shape — a default that looks safe and isn't.

**Single-reducer counts on GEE.** Reiterate: single image, single reducer (sum + count combined), no `bestEffort`, identical scale across runs. Mechanism #2 prevention.

**Skip-with-marker over raise-loudly for batch operations.** A failed slot in a batch render either should raise loudly with full context (killing the batch) or render a visibly-blank panel with a labeled skip reason (preserving batch). The unacceptable middle ground is silent failure.

**CDSE multi-day 503 pattern (post-upgrade residue).** Networking-layer upgrades at CDSE scale routinely leave SH-fronted endpoints flaky for several days while underlying catalog/object-storage stabilizes. Pre-flight `curl -s -o /dev/null -w "%{http_code}\n" https://sh.dataspace.copernicus.eu` before any agentic prompt that depends on CDSE.

**Methodology contamination via partial UVAI exposure in chat output.** Pattern locked: do not surface candidate UVAI values in chat output before labeling completes. Post-labeling cross-checks are fine; pre-labeling intermediate summaries that include UVAI values are not.

**AI pre-labeling produces optimistic class separation.** Confirmed across all four SQ1B variants 2026-05-01: V1 0.924→0.626, V2 0.711→0.578, V3 0.934→0.837, V4 0.924→0.853. Pattern-matchers push borderline scenes toward the nearest cluster centroid; real visual judgment is messier and that mess is signal. Researcher confirmation pass is the load-bearing methodology step, not a procedural appendix.

**AOI-dependent AI bias direction.** Construction-active AOIs (Qiddiya, KSP) → AI over-flags haze (substrate confusion). Desert-edge AOI (Diriyah) → AI under-flags real dust. This pattern won't surface from a smaller calibration set; the 43-scene SQ1C pass was load-bearing for finding it.

**Cold-protocol audits can return null results.** 4/6 cold-confirmed labels agreed with AI; 2/6 disagreed in directions consistent with the AOI-level pattern. The bias_exposure during pre-labeling did not produce a detectably different judgment pattern at this n. Negative results from contamination audits are still results — methodology footnote stays, but no separate finding to report.

**Long prompts to long work.** Single autonomous Claude Code prompt with recon-before-build, full multi-script execution, atomic commits, single review point at end — load-bearing protocol for any multi-step SQ. Confirmed working at SQ1C tooling build, SQ1C confirmation rerun, SQ2 operational, SQ3 NDVI-bias, SQ4 HLS cross-check, SQ4B B8 sensitivity, SQ5 halt-with-receipt, SQ8 reanalysis regression. Interleaved approval gates burn momentum; recon-build-verify in one shot does not.

**Internal cross-validation between methods.** When two methods that didn't share decision-time inputs agree on the same finding, that's load-bearing for piece B's discussion section. SQ1C cold-protocol blind labeling and SQ2 continuous DBB independently identified the 2022-05-10 Diriyah peak event — name this kind of agreement explicitly when it surfaces; it doesn't surface often. SQ3/SQ4/SQ4B/SQ8 jointly establishing the operational null across paired and per-scene designs is a stronger version of the same pattern.

**Stop rules are scope-decision points, not failures.** Proven across four sub-questions in different shapes:
- SQ3: paired retention < 30% (Qiddiya 28.1%) → halt, surface four scope options, accept caveat.
- SQ4B: pre-registered 50% L30 coverage floor failed in two AOIs → halt, surface, defer Arm B → SQ4C.
- SQ5: pre-registered 30% retention floor failed in all three AOIs → halt-with-receipt, defer Goyens-regime test → SQ8.
- SQ8: AERONET R1 (no station within 500km) → halt, surface, retarget to reanalysis primary.

Halting in the middle of the run is the cheapest possible scope review. Pattern: when designing a sub-question, write the stop rule as a multi-option scope decision rather than a binary fail/pass — the agent's job at threshold is to pause and surface, not to choose.

**The "different question" temptation when a stop rule fires.** When an analysis hits a stop-rule edge, the tempting move is to switch to a different design that bypasses the constraint (e.g. SQ3 paired-difference → continuous DBB-vs-NDVI regression; SQ4B L30 coverage → native-L30 dates; SQ5 retention → Q4-vs-Q3 contrast). That switch is exactly what the stop rule is designed to catch: it conflates "we got a borderline retention" with "we should answer a different question." Pre-registered designs ship or halt on their own terms; new questions become new sub-questions (SQ3B, SQ4C, SQ8, SQ8B). Confirmed at SQ3, SQ4B, SQ5, SQ8 — all four halts produced sub-question deferrals rather than mid-run design switches.

**Recon-before-build catches infra mismatches in 4 commands.** SQ3's R1–R4 recon block resolved NDVI-not-in-CSV, EECU estimate, column names, and denominator count before any new code was written. Saved a build pass that would have referenced `scene_date` (manifest col is `acquisition_date`) and assumed NDVI columns that didn't exist. Generalized at SQ4 (HLS coverage probe), SQ4B (L30 coverage probe), SQ5 (UVAI quartile + retention probe), SQ8 (AERONET station survey + reanalysis source check). Standard for any sub-question that touches an existing pipeline.

**Conditional nulls are findings, not setbacks.** SQ3's tight nulls at halfwidths 0.0076 and 0.0055 were scope-bounded informative results. The same pattern repeats at SQ4 (LaSRC chain), SQ4B (B8 broad NIR), SQ8 (high-AOD regression). Honest framing names what the result *does* say (no measurable bias at this design at this loading regime on this correction chain on this NIR band) and what it *does not* say (Sen2Cor is universally fine; Goyens is wrong). Goyens describes a TOA / extreme-AOD regime; transfer to L2A at moderate-to-high loadings is not assumed in either direction. The scope-conditional framing tightens, layer by layer, into the unconditional null in piece B's headline.

**Halt-with-receipt as a sub-question shape.** SQ4B Arm B → SQ4C deferral preserved the L30 coverage probe in git history (commit `71327ec`). SQ5 halt preserved UVAI quartile labels, retention probe, contingency table, and seasonal stratification figure as committed receipts. The receipts are themselves piece B substance — SQ5's seasonal-stratification methodology finding and Q4∧¬V4 anchor cell would not exist without the halt being shipped as a finding rather than discarded. Pattern: when a sub-question halts on a structural constraint, the recon artifacts ride into the ship as findings, not just diagnostics.

**Dual-criterion pre-registration.** At pooled-n high-statistical-power low-R² regression designs, a significance criterion (CI excludes zero) and a magnitude criterion (|β × IQR| exceeds operational threshold) can return divergent classifications on operationally small effects. SQ8 surfaced this explicitly: classifier fired `goyens_consistent_bias_detected`, magnitude fired `tight_null`, both reported without override. Pattern for any future regression-style sub-question: pre-register both criteria, expect potential disagreement, decide which is load-bearing for the umbrella question (operational-magnitude is load-bearing for change-monitoring use cases). Document the disagreement when it occurs as a methodology observation rather than resolving by override.

**Power-confirmation reading of significant-but-tiny regression effects.** When a regression detects a statistically significant effect that is 25× below the operational-significance threshold, the Bayesian-inverse reading is that the test had power to find a small effect if one existed and that is what it found. This strengthens, rather than undermines, an operational null established by other designs. SQ8's −0.0018 NDVI per IQR AOD is read as power-confirmation of SQ3/SQ4/SQ4B's operational null, not as Goyens transfer. Frame this way when significance and magnitude criteria disagree at high n with low R².

**The diagnosis is often the finding.** Qiddiya 28.1% retention at SQ3 was a direct downstream consequence of SQ2's construction-substrate finding. SQ4B Arm B's coverage failure was a structural cadence mismatch (S2A+B vs L8+L9). SQ5's retention failure was Riyadh's UVAI seasonality. SQ8's AERONET halt was the absence of operational stations within 500km. In each case, the diagnosis carries forward as a finding (or as methodology context for the next sub-question). Pattern: when a stop rule fires, look upstream — the cause may already be a documented finding from a previous SQ, or it may be the new finding the halt is delivering.

**Pair-level bootstrap for paired difference designs.** Bootstrap on **pairs** (not scenes) is correct when neighbors can be reused across pairings — pair-level resampling handles the dependence at inference time. Standard at SQ3, SQ4, SQ4B. Carries forward to any future paired sub-question.

**Two-layer findings hold up better than one-layer findings.** SQ2 (V4 detects atmospheric optical thickness) plus SQ3 (that thickness does not propagate to NDVI bias on Sen2Cor L2A) plus SQ4 (the null is not Sen2Cor-specific) plus SQ4B (the null is not NIR-band-shift-driven) plus SQ8 (the null holds at high reanalysis-AOD via regression with quantified upper bound) is a five-layer answer to the umbrella question. Each layer rules out a candidate explanation and tightens the scope claim. Frame as a multi-layer chain in piece B prose, not as a sequence of independent findings.

**The smallest-n AOI is often the cleanest atmospheric prior.** Diriyah has the lowest V4 fire rate (11.8%), the smallest paired set (n=8 across SQ3/SQ4/SQ4B), and the cleanest Goyens-regime test cell (Q4∧¬V4 = 12 from SQ5 R5 contingency). The AOI most worth measuring is the AOI we can measure least precisely from satellite-only paired designs. SQ8B (KAUST coastal generalization) and any future ground-truth campaign should anchor at Diriyah.

**Self-caught bugs validate the verification loop.** SQ3's `scene_date` vs `acquisition_date` typo failed loudly with `KeyError`, never reached output. Generalizes: design diagnostics that *fail loudly* on the first wrong assumption rather than silently producing plausible-looking output. Sanity tests at SQ4/SQ4B/SQ8 (same date queried twice must produce identical output) catch corruption in the same shape.

**CLAUDE.md infrastructure descriptions can drift from scripts.** Scripts are source of truth for infrastructure; this doc's "What works right now" section needs verification when describing data sources, not assumption. Drift caught at SQ8 (VIIRS Deep Blue AOD listed as available, no cached CSV exists). Drift caught at SQ8 R1 (AERONET Solar_Village date listed as Jan 2013; actual last data 2015-10-12). Updates land at end-of-session ritual.

**Credential hygiene.** Sentinel Hub OAuth credentials, GEE project name, and any API tokens stay in `.env` only. `.env` is gitignored. `.private/context.md` for SARsatX-specific framing also gitignored. Permissions config `.claude/settings.local.json` deny rules block `cat .env*` even in bypass mode.

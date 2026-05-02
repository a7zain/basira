# CLAUDE.md

**Project:** Basira (بصيرة) — Saudi satellite change monitoring
**Last updated:** 2026-05-02 (post-SQ3-ship, conditional null at moderate loadings)
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

## Current state (as of 2026-05-02)

**Project shape.** Basira's Phase 1 deliverable is a portfolio-with-research-engine. The cinematic homepage at root `index.html` stays as-is for now; new research pages live at `/research/<slug>/`. Live at https://a7zain.github.io/basira/.

**First two research pieces, locked sequence B → A:**

### Research piece B (dust-honesty) — IN PROGRESS, SQ3 conditional null landed

Question: how does Sen2Cor's known underestimation of aerosols over deserts (Goyens 2024) translate into NDVI bias for change monitoring over Riyadh, and how often does it matter? Sources: Sentinel-2 L2A (subject), TROPOMI UVAI (validation, all three AOIs from GEE COPERNICUS/S5P/OFFL/L3_AER_AI), HLS NDVI (cross-check). Method: faithful port of Lolli 2024 DBB index, recalibrate for AP. 7 sub-questions (SQ1–SQ7) plus committed SQ8 (KAUST AERONET validation). Lives at `research/dust-honesty/`.

**Sub-question status:**

- **SQ1, SQ1B (original), SQ1D (faithful Lolli port + reference selection + visually-blind relabel + faithful compute + sensitivity)** — DONE, see prior session logs (2026-04-28, 2026-04-29) for detail.

- **Scene manifest defense against GEE catalog drift** — DONE 2026-04-30 morning. `sq1d_scene_manifest.csv` locks system:index per (aoi, month_slot) for the 30-scene SQ1D set; renderers read manifest first, deterministic-pick is fallback only with WARNING log. Date-based fetch + `assert_manifest_match(system_index)` precondition is the locked pattern (single-image system:index clips drift at tile-mosaic boundaries).

- **SQ1C (calibration-set expansion via UVAI-anchored positives, SZA-aware seasonal balance)** — DONE 2026-05-01 (researcher confirmation complete). Selection produced 15 candidates per AOI (45 total). S2 L2A matching at ±3d / ≤20% cloud landed 45/45 same-day matches. Render produced 43 real thumbnails + 2 KSP skip-panels caught by `array_has_data` guard. Manifest-locked at selection time via `sq1c_scene_manifest.csv`.

  AI pre-labeling against the SQ1D Pass 5 rubric was completed 2026-04-30 evening (preliminary). **Researcher confirmation pass completed 2026-05-01:** all 43 rows confirmed, 12 overrides total (27.9% disagreement rate). Per-AOI: KSP 11/13 agree (84.6%), Qiddiya 10/15 agree (66.7%), Diriyah 10/15 agree (66.7%). Override direction is AOI-dependent — Qiddiya/KSP softened toward clean (construction-substrate AOIs where AI over-flagged haze), Diriyah hardened toward heavy_dust (3 added heavy_dust scenes; AI under-flagged real dust). 6 cold-protocol rows (bias_exposed during AI pre-labeling) labeled blind: 4/6 agreed with AI, 2/6 disagreed in directions consistent with the AOI-level pattern — cold-protocol audit did NOT detect bias-direction beyond the broader AOI pattern.

- **SQ1D Part B re-run with bug-fixed reducer** — DONE 2026-04-30 evening. The `n_valid > n_total` count drift in the original primary CSV (root cause: bestEffort scale drift between separate `reduceRegion` calls) is now fixed. Single-image, single-reducer (sum + count), no bestEffort, identical native scale. `sq1d_dbb_faithful.csv` regenerated. Max abs delta vs old buggy CSV: 0.0165. Self-reference unit test still passes: Diriyah 2020-04-25 vs 2020-04-25 ref → DBB = 0 exactly.

- **SQ1B re-re-run on confirmed labels (combined 73-scene calibration set)** — DONE 2026-05-01 evening. Stop rule unchanged (CI half-width < 0.020 AND AUC > 0.75). Cloud-labeled rows excluded.

  | variant | n_pos prelim → conf | AUC prelim → conf | t_youden conf | CI_hw conf | ships prelim → conf |
  |---|---:|---:|---:|---:|---|
  | V1 (heavy_dust vs clean, all) | 2 → 5 | 0.924 → 0.626 | +0.034 | 0.109 | ✗ → ✗ |
  | V2 (any-non-clean vs clean, all) | 23 → 19 | 0.711 → 0.578 | +0.034 | 0.027 | ✗ → ✗ |
  | V3 (KSP-only any-non-clean vs clean) | 11 → 9 | 0.934 → 0.837 | +0.053 | 0.000 | ✓ → ✓ |
  | V4 (KSP+Diriyah any-non-clean vs clean) | 17 → 16 | 0.924 → 0.853 | +0.034 | 0.012 | ✓ → ✓ |

  **Headline (post-confirmation, non-preliminary): V3 (KSP-only) and V4 (KSP+Diriyah, the most defensible scope) both ship at AUC 0.837 / 0.853, CI 0.000 / 0.012. V4 is the lead calibration result. V1 collapses on n_pos=5 — this is a structural finding that the Lolli DBB index is not a univariate heavy_dust detector at Riyadh-region atmospheric loadings. V2 fails again — fourth independent line of evidence for Qiddiya bidirectional construction-substrate contamination. Every AUC dropped from preliminary to confirmed; AI pre-labeling produced cleaner class separation than reality, and that gap is itself a methodology finding for piece B.** Outputs: `sq1b_rerun_v2_confirmed_threshold_results.csv`, `sq1b_rerun_v2_confirmed_threshold_spec.md`, `sq1b_rerun_v2_confirmed_roc_curves.png`, `sq1b_rerun_v2_confirmed_bootstrap_thresholds.png`, `sq1bc_combined_calibration_confirmed.csv`. Findings note at `research/dust-honesty/docs/sq1b_confirmed_findings.md`.

- **SQ2 (apply calibrated DBB flag to operational 228-scene set)** — DONE 2026-05-01 (late evening). V4 (+0.034) and V3 KSP-only (+0.053) applied to 228 (aoi, year, month) operational scenes spanning 76 months × 3 AOIs (2020-01..2026-04). Manifest-locked at first run via `sq2_scene_manifest.csv`; calibration-overlap rows inherit locked system_indexes. Self-reference unit test passed at run start (DBB = 0.00e+00 exactly). 226/228 scenes usable (99.1%); 2 KSP scenes (2020-11, 2026-04) returned `no_usable_scene=True` due to SCL valid mask returning 0 AOI-resident pixels (granule-edge effect at the bbox of those orbit tracks). Manifest distribution: 30 cal_lock_sq1d + 27 cal_lock_sq1c + 171 gee_pick = 228.

  Headline V4 fire rates per AOI:

  | AOI | V4 fires / usable | rate | DBB mean | DBB range |
  |---|---:|---:|---:|---|
  | Diriyah Gate | 9 / 76 | **11.8%** | -0.052 | [-0.28, +0.07] |
  | King Salman Park | 24 / 74 | **32.4%** | +0.017 | [-0.23, +0.22] |
  | Qiddiya core | 57 / 76 | **75.0%** | +0.091 | [-0.16, +0.20] |

  V3 KSP-only at +0.053: 22/74 = 29.7%.

  **Headline reads:** Diriyah 11.8% is the cleanest operational fire rate — surface-stable AOI, all 9 fires concentrated Apr–Jul (0/0/0/2/2/3/2/0/0/0/0/0 by calendar month) matches independent shamal climatology (peak Mar–Aug, Apr–Jun maximum). KSP 32.4% sits at calibration mean. Qiddiya 75% is the **fifth** independent line of evidence for bidirectional construction-substrate contamination (SQ1D Pass 5 + Part B' sensitivity ρ=0.92 + V2 prelim AUC drop + V2 confirmed AUC drop + SQ2 baseline DBB +0.091 well above threshold). The DBB index reads accumulating construction substrate as scene-wide haze across B11/B12 against the fixed 2024-01-20 reference; the 75% rate quantifies that drift directly. Internal cross-validation: SQ1C cold-protocol blind labeling and SQ2 continuous DBB independently identified the 2022-05-10 Diriyah peak event without sharing decision-time inputs.

  Cloud-affected fraction: KSP 0/76, Qiddiya 0/76, Diriyah 1/76 (the 2026-04-14 scene at cloud_pct_aoi=80.56%, retained with `cloud_flag_present=True` rather than dropped). Operational availability bound for SQ3+: 226/228 = 99.1%.

  Cross-check vs `sq1bc_combined_calibration_confirmed.csv`: 57 unique (aoi, year, month) overlap slots, 55 pass / 2 fail (within tolerance 1e-4). Failures: KSP 2021-02 delta +0.0165, KSP 2026-02 delta -0.0039. Both stay V4-negative on each side — flag classifications stable; pixel values shifted ≤1.6%. Cause: GEE processing-baseline drift on the locked `system:index` (manifest locks scene identity, not pixel content). Listed in `sq2_cross_check_failures.csv` and surfaced in §5 of `sq2_findings.md` as the third instance of GEE drift in this project.

  Outputs: `sq2_apply_flag.py`, `sq2_plot_timeseries.py`, `sq2_summary_stats.py` (scripts); `sq2_scene_manifest.csv`, `sq2_dbb_operational.csv`, `sq2_cross_check_failures.csv`, `sq2_summary_stats.md`, `sq2_dbb_timeseries_<aoi>.png` × 3, `sq2_dbb_timeseries_combined.png` (data); `research/dust-honesty/docs/sq2_findings.md` (1–2 page narrative; §2 framing tightened + §6 cross-validation sentence added in `a6d4a12`). Commits: `ab00509`, `0dca7e4`, `65c23ea`, `a6d4a12`.

- **SQ3 (NDVI bias on V4-flagged vs unflagged scenes per AOI)** — DONE 2026-05-02. NDVI computed via fresh GEE pass on locked `sq2_scene_manifest.csv` (226/228 usable, same denominator as SQ2). Paired temporal-neighbor differencing, ±60-day window, V4-uniform headline, bootstrap 1000-resample on pairs. Stop rule fired mid-run at S1 (Qiddiya retention 28.1% < 30%), surfaced for scope decision; researcher accepted 28.1% with explicit caveat — the structural consequence of Qiddiya's 75% V4 fire rate, not a noise problem. Resumed cleanly to S2 + S3.

  | AOI | n_fired | n_paired | retention | mean Δ NDVI | 95% CI | halfwidth | signal_class |
  |---|---:|---:|---:|---:|---|---:|---|
  | King Salman Park | 24 | 14 | 58.3% | +0.0016 | [−0.0056, +0.0097] | 0.0076 | tight_null |
  | Qiddiya core | 57 | 16 | 28.1% | −0.0024 | [−0.0075, +0.0036] | 0.0055 | tight_null |
  | Diriyah Gate | 9 | 8 | 88.9% | −0.0002 | [−0.0220, +0.0224] | 0.0222 | wide_inconclusive |

  **Headline (conditional null, scope-bounded):** the pre-registered Goyens-consistent prediction (negative Δ NDVI on flagged scenes) is **not confirmed** at these AOIs under this design. KSP and Qiddiya land in tight nulls (CI halfwidths 0.0076 and 0.0055, mean |Δ| < 0.003) — two orders of magnitude below typical NDVI change-detection thresholds (~0.05+). Diriyah is wide-inconclusive on n alone (n_paired=8, halfwidth 0.022) — the cleanest atmospheric AOI has the smallest pair count, which is the SQ8 AERONET hook. The honest claim is conditional: *"On Sen2Cor L2A NDVI at Riyadh-region moderate atmospheric loadings, V4-flagged scenes do not exhibit a measurable bias relative to near-temporal unflagged neighbors at change-detection magnitude."* Two candidate explanations named in the findings note (TOA vs L2A loading regime; NDVI-as-ratio cancellation) — phrased as candidates, not confirmed mechanisms.

  SQ2-SQ3 chain is internally consistent: V4 detects atmospheric optical thickness (SQ2's Diriyah shamal alignment), but that thickness does not propagate to NDVI bias at change-detection magnitude (SQ3 null). Both findings are real; they describe different layers of the imaging chain — and that two-layer story is itself a piece B substance, not a defeat of the prior.

  Outputs: `sq3_compute_ndvi.py`, `sq3_pair_and_diff.py`, `sq3_plot_deltas.py`, `sq3_summary.py` (scripts under `research/dust-honesty/scripts/`); `sq3_ndvi_per_scene.csv` (228 rows, 226 with NDVI), `sq3_ndvi_bias.csv` (38 pair rows), `sq3_pairing_audit.csv` (3 AOI rows); `figures/sq3/` (per-AOI Δ histograms × 3 + forest plot + retention chart); `research/dust-honesty/docs/sq3_findings.md`. Commits: `c92b757`, `0e2e783`, `4e1ba7a`, `11faffe`.

- **SQ4–SQ7** — UNBLOCKED. SQ4 = HLS NDVI cross-check, positioned to test whether the SQ3 null is Sen2Cor-specific (different atmospheric correction chain — LaSRC vs Sen2Cor) or surface-driven. If LaSRC also nulls, the conditional null tightens into a cross-correction finding; if LaSRC shows the predicted bias, we've localized it to Sen2Cor. SQ4 is the next strategic-chat scoping target. SQ5–SQ7 ordering decided when SQ4 lands.

- **SQ8 (KAUST AERONET validation)** — committed for piece B before publishing. Now carries an extra hook from SQ3: Diriyah's wide_inconclusive (n=8) is the obvious target for ground-truth tightening. Defer until SQ4–SQ7 ship.

### Research piece A (churn, hardened) — QUEUED

Inherits B's dust-flag pipeline. Re-runs Phase 4 churn analysis with dust correction applied. Approximately 5 sessions after B.

### Cut from scope

- Vision 2030 progress audit — political risk vs target sector, deferred.
- MODIS as primary source — being decommissioned (Terra Dec 2025, Aqua Aug 2026). Replaced by VIIRS + TROPOMI.
- Bird migration / cross-domain — wrong fit for my positioning.

---

## Methodology footnote (binding for B writeups)

This must appear in any SQ1B / SQ1D / B-final writeup. Two paragraphs — keep both.

> "The 30-scene SQ1D calibration set was originally pre-labeled by an AI assistant (Claude) against a written rubric for atmospheric clarity (clean / light_haze / heavy_dust / cloud / mixed) and reviewed by the researcher with focus on low-confidence calls. Following the SQ1D Part A.5 finding that visual labels at construction-active AOIs were contaminated by construction substrate visually mimicking haze, the 24 scenes from construction-active AOIs (Qiddiya, King Salman Park) were re-rendered with date-only captions and re-labeled visually-blind (no UVAI, no prior label visible to the labeler) using the same rubric, augmented with an explicit construction-substrate exclusion rule: 'Construction substrate (bare beige/tan ground that is sharp-edged and stable across multiple dates) is a SURFACE feature, not atmospheric. Atmospheric features must be scene-wide veiling, not localized.' The researcher confirmed all 24 AI pre-labels without override. UVAI cross-check is a separate audit step, never an input to the label."

> "The SQ1C 43-scene calibration-set expansion was AI-pre-labeled by chat-Claude against the same rubric and construction-substrate exclusion rule as SQ1D Pass 5. Researcher confirmation completed 2026-05-01: 12 of 43 AI pre-labels were overridden (27.9% disagreement rate). Override direction was AOI-dependent — Qiddiya and KSP softened toward clean (AI over-flagged haze at construction-active AOIs); Diriyah hardened toward heavy_dust (AI under-flagged real dust at the desert-edge AOI). 6 of the 43 SQ1C scenes had partial UVAI value exposure to chat-Claude during pre-labeling (UVAI values for the top-3 candidates per AOI were surfaced in an intermediate session report before pre-labeling completed). These rows are flagged with `bias_exposed_during_ai_labeling=True` and were re-labeled by the researcher under a cold protocol with neither AI label nor UVAI visible. 4 of 6 cold-confirmed labels agreed with the AI pre-label; 2 disagreed in directions consistent with the AOI-level pattern. The cold-protocol audit did not detect a bias-direction beyond the broader AOI pattern. SQ1B re-re-run results derived from confirmed labels are non-preliminary; the 27.9% disagreement rate produced systematic AUC reductions vs preliminary across all four binary task variants (V1 0.924→0.626, V2 0.711→0.578, V3 0.934→0.837, V4 0.924→0.853), reflecting that AI pre-labeling produced cleaner class separation than reality."

---

## Flags before next session

- **SQ3 ships as a conditional null, not a Goyens-confirmation.** Lead headline: *"V4-flagged scenes do not exhibit measurable Sen2Cor L2A NDVI bias relative to near-temporal unflagged neighbors at moderate Riyadh-region atmospheric loadings, on the paired ±60-day design."* This is not "Sen2Cor is fine" and not "Goyens overstated." The Goyens result describes a TOA / extreme-AOD regime; L2A's Sen2Cor correction may absorb the bias at moderate loadings even if it fails at high loadings. NDVI-as-ratio (Red and NIR both perturbed) is the second candidate explanation. Both phrased as candidates in the findings note, not confirmed mechanisms.

- **SQ2-SQ3 internal consistency is a piece B substance finding.** Two layers of the imaging chain, both real: V4 detects atmospheric optical thickness (SQ2 Diriyah shamal alignment); that thickness does not propagate to NDVI bias at change-detection magnitude (SQ3 null). Frame as a two-layer answer, not a contradiction.

- **Diriyah n=8 / halfwidth 0.022 is the SQ8 hook.** The cleanest atmospheric AOI has the smallest pair count. Wider window costs surface-state fidelity; longer baseline costs construction-stability at the other AOIs. AERONET ground truth is the right path to tighten Diriyah specifically — and SQ8 was already committed before this finding.

- **Qiddiya 28.1% retention is itself a finding, not a flaw.** The unfired-neighbor pool is small and clustered because V4 fires on 75% of Qiddiya scenes. That's the SQ2 construction-substrate finding propagating to SQ3 by design — not a sampling artifact. Reported in §5 of the findings note as a structural consequence.

- **Diriyah 11.8% remains the lead operational fire rate for piece B.** Surface-stable AOI; all 9 fires concentrated Apr–Jul matching shamal climatology; peak event 2022-05-10 cross-validates with SQ1C cold-protocol heavy_dust labels for the same date.

- **Qiddiya 75% is a methodology finding, NOT a climatology finding.** DBB mean +0.091 (well above the +0.034 threshold) with fires distributed Feb–Nov and no shamal concentration. Fifth independent line of evidence for bidirectional construction-substrate contamination. Piece B prose must report Qiddiya's column with the methodology footnote, not the climatology framing.

- **KSP 32.4% is the secondary operational number.** DBB mean +0.017 sits at calibration center; V3 KSP-only at the tighter +0.053 threshold drops to 29.7% — the +0.019 threshold tightening costs ~2.7 percentage points. One sentence in piece B's operational table.

- **GEE baseline-reprocessing drift on locked system:index** is now mechanism #3 of GEE drift surfaced in this project (catalog backfill #1, bestEffort reducer counts #2, baseline-reprocessing #3). Two KSP cross-check rows shifted ≤1.6% in pixel value while keeping flag classifications stable. The robustness story (V4 absorbs baseline drift without flipping classifications) is a defensibility paragraph for piece B's discussion section.

- **V4 is the lead calibration scope, AUC 0.853, CI 0.012, threshold +0.034.** V3's CI=0.000 still needs the bootstrap-collapse disclosure when referenced.

- **V1 collapse is a piece-B finding, not a setback.** With n_pos=5, AUC dropped to 0.626 — the Lolli DBB index does not univariately discriminate visual heavy_dust from visual clean at Riyadh-region atmospheric loadings.

- **AOI-dependent AI bias direction is a real finding.** Qiddiya/KSP soften (AI over-flags at construction AOIs), Diriyah hardens (AI under-flags at desert-edge AOI). Methodology section material — texture that wouldn't surface from a smaller calibration set.

- **Qiddiya 2022-04-10 is publishable on its own.** Confirmed clean despite UVAI +2.07, surviving cold-protocol blind labeling. Direct demonstration that visual atmospheric clarity and TROPOMI UVAI can decouple over bright desert surfaces (Goyens 2024 underestimation pattern). Strong candidate for piece B introduction.

- **SQ4 is the next strategic-chat scoping target.** HLS NDVI cross-check, positioned to test whether SQ3's null is Sen2Cor-specific (LaSRC vs Sen2Cor) or surface-driven. If LaSRC also nulls, the SQ3 finding tightens into "the predicted bias is below detection across both major correction chains." If LaSRC shows the bias, the bias is localizable to Sen2Cor. Either outcome is publishable.

- **Naming rationalization owed before piece B prose.** `sq1d_*` / `sq1c_*` / `sq1b_rerun_v2_*` / `sq1b_rerun_v2_confirmed_*` / `sq2_*` / `sq3_*` are process-of-discovery names. End-state taxonomy needed before a fresh reader sees the data dir; suggested grouping: calibration-sets / DBB-compute / threshold-fits / operational / NDVI-bias. Cosmetic cleanup; can ride along inside any execution session.

- **CDSE OData spike still pending** for SQ8 KAUST AERONET (qa_value-aware masking, which the L3 OFFL product strips). No longer on the SQ3 critical path.

- **§7 SZA dependency formal investigation** — still open as discussion-section question. Two paths if elevated: (a) regress Diriyah residuals on `1/cos(SZA_test) − 1/cos(SZA_ref)` and report slope; (b) port Lolli to L2A SR to bypass TOA-path. Decision deferred; do not let this expand current scope.

- **KAUST AERONET validation chapter (committed for piece B).** KAUST Thuwal AERONET station added as SQ8 — external validation chapter using AERONET coarse-mode AOD as gold-standard. Solar Village (Riyadh) is dead since January 2013, so no AERONET ground truth exists for the exact Riyadh atmospheric column during the study window. KAUST surface differs from Riyadh (coastal, not bright desert), so this is also a generalization test. Hard commitment, not optional. Defer until SQ4–SQ7 ship.

---

## What NOT to do

- Do not re-litigate the TPM-track vs. EO-specialist framing. Decision made 2026-04-20.
- Do not expand Phase 1 scope. The three projects are the scope.
- Do not suggest paid imagery (Planet, Maxar) for Phase 1. Sentinel is the constraint, deliberately.
- Do not treat the longer-arc company vision as the active objective. North star, not map.
- Do not re-litigate the cinematic NYT-feature direction. Locked 2026-04-21.
- Do not re-litigate the portfolio-with-research-engine pivot. Locked 2026-04-27.
- Do not auto-label calibration scenes from UVAI as a shortcut. UVAI selects which months to pull; visual labels remain the calibration target. Conflating the two collapses SQ3 validation into circularity.
- Do not re-render test thumbnails with UVAI in caption. Visually-blind protocol established 2026-04-29. UVAI is post-labeling audit, never input.
- Do not surface candidate UVAI values in chat output before AI pre-labeling completes. Methodology contamination; locked 2026-04-30.
- **Do not reference preliminary V3/V4 numbers (AUC 0.93 / 0.92) externally.** Confirmed numbers are AUC 0.837 / 0.853. Use those.
- **Do not frame V1 collapse or V2 failure as setbacks.** They are structural findings.
- **Do not apply V3/V4 thresholds to AOIs not in the calibration set (KSP, KSP+Diriyah) without re-validating.** Qiddiya inclusion in SQ2 is reported with the construction-substrate methodology footnote, not as a clean dust climatology.
- **Do not frame the Qiddiya 75% rate as climatology.** It is a methodology limit on applying a fixed-reference DBB to a surface-evolving AOI.
- **Do not frame SQ3's conditional null as "Sen2Cor is fine" or "Goyens overstated."** It is a *scope-conditional* result: Sen2Cor L2A NDVI on V4-flagged scenes vs near-temporal unflagged neighbors does not exhibit the predicted bias at moderate Riyadh-region atmospheric loadings on the paired ±60-day design. The Goyens result describes a TOA / extreme-AOD regime; transfer is not assumed in either direction. Two candidate explanations (loading regime, NDVI-ratio cancellation) are named in the findings note as candidates only.
- **Do not switch a sub-question's design when its stop rule fires.** The "what if we did continuous regression instead" temptation is the move the stop rule is designed to catch. New questions become new sub-questions (SQ3B, SQ4, etc.); pre-registered designs ship or halt on their own terms.
- **Do not widen the SQ3 ±60-day pairing window post-hoc.** Surface-state fidelity is the reason for the window; trading it for retention reads as p-hacking. Diriyah's n-problem is an SQ8 hook, not a window-tuning problem.

---

## Active credentials and infrastructure

- Copernicus Dataspace: ahmadxgpx@gmail.com
- Sentinel Hub OAuth client: active (30K PU/month free tier; secondary post-GEE pivot)
- GEE project: `basira-494617` (Community Tier, 150 EECU/mo) — load-bearing for SQ1D, SQ1C, SQ2, SQ3, all UVAI all-months pipelines
- GitHub: `a7zain/basira` (repo renamed from `sar-change-detection`)
- Local path: `/Users/a7zain/basira`
- Conda env: `sarsat`
- Deployed dashboard: GitHub Pages at https://a7zain.github.io/basira/

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
- **Aerosol infrastructure (corrected provenance):** TROPOMI UVAI all three AOIs from GEE `COPERNICUS/S5P/OFFL/L3_AER_AI` band `absorbing_aerosol_index` (KSP 320 rows, Qiddiya 302 rows, Diriyah 300 rows). VIIRS Deep Blue AOD via GEE (project `basira-494617`).
- **SQ1D faithful-Lolli pipeline (DONE — both arms, bug-fixed reducer):**
  - Per-AOI 2/98 stretch with no-data filter, persisted to `sq1d_<aoi>_stretch.json`.
  - Date-only caption rendering for visually-blind labeling.
  - AI pre-label + researcher-review workflow with explicit construction-substrate rubric.
  - Canonical references config at `sq1d_references.json`.
  - 24 visually-blind relabels merged into `sq1d_ksp_relabel.csv` and `sq1d_qiddiya_relabel.csv`.
  - Faithful Lolli formula spec at `sq1d_lolli_formula.md`.
  - Faithful Lolli compute at `sq1d_lolli_faithful.py` (single-image single-reducer count handling).
  - 30-scene primary DBB at `sq1d_dbb_faithful.csv` (regenerated 2026-04-30 with bug-fixed reducer).
  - 24-scene sensitivity-alternate DBB at `sq1d_dbb_faithful_alt.csv`. Primary-vs-alternate Spearman ρ = 0.97 KSP / 0.92 Qiddiya.
- **Scene manifest pattern (DONE 2026-04-30):**
  - `sq1d_scene_manifest.csv` (30 rows), `sq1c_scene_manifest.csv` (43 rows), `sq2_scene_manifest.csv` (228 rows).
  - Test renderers read manifest first, deterministic-pick fallback with WARNING log.
  - Date-based fetch + `assert_manifest_match(system_index)` is the safe pattern.
- **SQ1C pipeline (DONE 2026-05-01 — confirmed labels):**
  - GEE TROPOMI UVAI source-check vs existing CSVs (n=30, ρ=1.0000) at `sq1d_uvai_source_check.py`.
  - Diriyah UVAI all-months search at `sq1d_diriyah_uvai_all_gee.py`.
  - Per-AOI negative-class month distribution + month-bin SZA-aware seasonal balance constraint.
  - Top-15 candidate selection per AOI at `sq1c_select_candidates.py`.
  - S2 L2A scene matching at `sq1c_match_s2_scenes.py`.
  - Manifest-locked candidate render at `sq1c_render_candidates.py`.
  - Per-AOI test montages at `sq1c_<aoi>_test_montage.png`.
  - Relabel CSVs at `sq1c_<aoi>_relabel.csv` with `final_label` (AI), `confirmed_label` (researcher), `review_protocol` (standard/cold), `reviewer_notes`, `confirmed_at`.
  - Confirmation tooling: `sq1c_label_review.py` (per-AOI walker), `sq1c_label_comparison.py` (audit + UVAI cross-check), `sq1b_rerun_v2_confirmed.py` (confirmed-label re-re-run).
  - Confirmation audit at `sq1c_confirmation_audit.csv` and `sq1c_confirmation_audit_report.txt`.
- **SQ1B pipelines:**
  - Original re-run on 30-scene primary: `sq1b_rerun.py`. Stop rule v1 (commit `3d3b511`).
  - Re-re-run on combined 73-scene preliminary: `sq1b_rerun_v2.py`. Outputs at `sq1b_rerun_v2_*`.
  - Re-re-run on combined 73-scene confirmed: `sq1b_rerun_v2_confirmed.py`. Outputs at `sq1b_rerun_v2_confirmed_*`. Combined dataset at `sq1bc_combined_calibration_confirmed.csv`.
  - Confirmed-vs-preliminary comparison table emitted in `sq1b_rerun_v2_confirmed_threshold_spec.md`.
- **SQ2 operational pipeline (DONE 2026-05-01 — late evening):**
  - V4 (+0.034) and V3 KSP-only (+0.053) thresholds applied to 228 (aoi, year, month) operational scenes via `sq2_apply_flag.py`.
  - Manifest-locked scene selection at `sq2_scene_manifest.csv` (30 cal_lock_sq1d + 27 cal_lock_sq1c + 171 gee_pick).
  - Self-reference unit test at run start (DBB = 0 exactly, asserted against ref scene).
  - AOI-local cloud handling via QA60 bits 10+11; `cloud_flag_present` column at cloud_pct_aoi > 30%.
  - Cross-check vs `sq1bc_combined_calibration_confirmed.csv` at 1e-4 tolerance; failures logged to `sq2_cross_check_failures.csv`.
  - Per-AOI + combined timeseries plots at `sq2_plot_timeseries.py`.
  - Summary stats + temporal pattern + monthly-distribution histogram at `sq2_summary_stats.py`.
  - Findings note (1–2 page narrative) at `research/dust-honesty/docs/sq2_findings.md`. §2 framing tightened + §6 cross-validation sentence added in commit `a6d4a12`.
- **SQ3 NDVI-bias pipeline (DONE 2026-05-02 — conditional null):**
  - Fresh GEE NDVI compute on locked SQ2 manifest at `sq3_compute_ndvi.py`. Single-image (B8−B4)/(B8+B4) at AOI mean, SCL valid mask reused from SQ2 cloud handling. Self-caught sanity_test column-name bug (manifest col is `acquisition_date`, not `scene_date`); fix landed before main loop.
  - Output: `sq3_ndvi_per_scene.csv` (228 rows, 226 with NDVI; 2 KSP misses match SQ2's `no_usable_scene=True` rows exactly — same granule-edge effect).
  - Pairing + bootstrap at `sq3_pair_and_diff.py`. ±60-day same-AOI nearest unflagged neighbor; deterministic earlier-date tie-break; 1000-resample bootstrap on pairs (handles neighbor reuse via pair-level resampling).
  - Outputs: `sq3_ndvi_bias.csv` (38 pair rows), `sq3_pairing_audit.csv` (3 AOI summary rows, signal_class column).
  - Plots at `sq3_plot_deltas.py`: per-AOI Δ histograms (3 PNGs), forest plot (1 PNG), retention bar chart (1 PNG with 70% reference line). Under `figures/sq3/`.
  - Findings note at `research/dust-honesty/docs/sq3_findings.md` (1–2 page narrative). §3 per-AOI table with conditional-null one-liners; §4 direction-vs-Goyens framing as scope-conditional, two candidate explanations as candidates only; §5 limitations (Qiddiya retention 28.1% as structural, Diriyah n=8 as SQ8 hook, ±60-day window trade-off); §6 cross-validation hooks to SQ4 (HLS / LaSRC) and SQ8 (AERONET), SQ2-SQ3 internal consistency named.
  - Stop-rule design proven in production: triggered at S1 on Qiddiya retention 28.1% < 30%, surfaced for scope decision rather than auto-widening window. Resumed cleanly to S2 + S3 after researcher accepted caveat.

---

## Working rhythm

- **This chat (Claude)**: strategy, planning, document drafting, review. No code execution here.
- **Claude Code**: all file operations, commits, code changes. Prompts from this chat are pasted into Claude Code.
- **Per-objective cleanup pass**: one cleanup at each objective boundary. Not two.
- **Per-session logs**: committed to `docs/sessions/YYYY-MM-DD.md` at session end. One day = one log even if multiple chats; combine in a single file with Part 1 / Part 2 / Part 3 sections.
- **End-of-session ritual**: at session end, Claude produces COMPLETE drop-in versions of `CLAUDE.md` and the dated `docs/sessions/YYYY-MM-DD.md` (full file replacements, not section edits). Ahmed overwrites the local files entirely, runs `git add -A && git commit && git push`, then clicks "Sync now" in the Claude Project to pull the latest from GitHub into the Project snapshot. Sync now is required because Projects don't auto-sync from GitHub — they're snapshots.
- **Claude Code prompts**: phrased as full sequences with verification at end. Single review point at end, not interleaved approvals. Only stop for destructive/irreversible operations (force push, mass delete, credential exposure, history rewrite).

---

## Operational guardrails (learned the hard way)

**Worktree drift.** Claude Code has previously created git worktrees under `.claude/worktrees/` and silently broken sessions multiple times. Every Claude Code prompt must include: *"Work directly on the main working tree. Do NOT create a git worktree under .claude/worktrees/. If you think you need one, stop and ask."*

**Verification discipline.** Claude Code has reported success on operations it hadn't completed multiple times. Always verify artifacts directly using `grep`, `ls -la`, `head`, `wc -l`, and `git status` as ground truth — never trust a success message alone.

**Force-add precedent.** Files under `research/dust-honesty/data/` are covered by a broad gitignore. Calibration data that must be reproducible is force-added per `442d7b0` precedent (`git add -f`).

**Self-reference unit tests.** When implementing a formula on a calibration set, design in a test where test-input == reference-input so the math reduces to a known answer (typically zero). Costs nothing; catches numerical artifacts and pairing bugs the moment the formula is implemented. Re-asserted at SQ2 run start: DBB = 0 exactly when KSP test = ref.

**Cross-check across runs.** Any time a scene has been computed in a prior pipeline, cross-check the new compute against the old at tight tolerance (1e-4 standard). Failures surface drift mechanisms; passing rows confirm value-stability. The SQ2 cross-check vs `sq1bc_combined_calibration_confirmed.csv` was the only reason GEE drift mechanism #3 surfaced.

**Single-reducer counts on GEE (drift mechanism #2).** `bestEffort=True` + multiple `reduceRegion` calls on the same image can return slightly different sample counts at scale boundaries (silent drift). Standard pattern: single image, single reducer combining `sum + count`, no `bestEffort`, identical scale across runs.

**Skip-with-marker over raise-loudly for batch operations.** A failed slot in a batch render either should raise loudly with full context (killing the batch) or render a visibly-blank panel with a labeled skip reason (preserving batch). The unacceptable middle ground is silent failure.

**GEE catalog backfill drift (drift mechanism #1).** GEE can backfill scenes with updated processing baselines that change which scene wins a deterministic-pick query. Defense pattern: lock `system:index` per (aoi, slot) in a sidecar manifest at first labeling; renderers read manifest first; deterministic-pick is fallback only with WARNING log. Date-based fetch + `assert_manifest_match(system_index)` is the safe pattern.

**GEE baseline-reprocessing drift on locked system:index (drift mechanism #3).** GEE retains the right to backfill the underlying L1C/L2A pixel content for a scene whose `system:index` is already locked in a manifest. The manifest pattern protects scene IDENTITY but NOT pixel CONTENT. Surfaced 2026-05-01 via SQ2 cross-check: 2 of 57 KSP overlap rows shifted ≤1.6% in pixel value while keeping V4 flag classifications stable. Mitigation: cross-check value-stability across runs at tight tolerance, surface failures honestly, and rely on threshold margin to absorb sub-classification-flip drift. Above ~5% pixel drift, classifications would flip and a frozen GEE asset export becomes the only protection — out of scope for piece B.

**CLAUDE.md infrastructure descriptions can drift from scripts.** Scripts are source of truth for infrastructure; this doc's "What works right now" section needs verification when describing data sources, not assumption.

**CDSE multi-day 503 pattern (post-upgrade residue).** Networking-layer upgrades at CDSE scale routinely leave SH-fronted endpoints flaky for several days while underlying catalog/object-storage stabilizes. Pre-flight `curl -s -o /dev/null -w "%{http_code}\n" https://sh.dataspace.copernicus.eu` before any agentic prompt that depends on CDSE.

**Methodology contamination via partial UVAI exposure in chat output.** Pattern locked: do not surface candidate UVAI values in chat output before labeling completes. Post-labeling cross-checks are fine; pre-labeling intermediate summaries that include UVAI values are not.

**AI pre-labeling produces optimistic class separation.** Confirmed across all four SQ1B variants 2026-05-01: V1 0.924→0.626, V2 0.711→0.578, V3 0.934→0.837, V4 0.924→0.853. Pattern-matchers push borderline scenes toward the nearest cluster centroid; real visual judgment is messier and that mess is signal. Researcher confirmation pass is the load-bearing methodology step, not a procedural appendix.

**AOI-dependent AI bias direction.** Construction-active AOIs (Qiddiya, KSP) → AI over-flags haze (substrate confusion). Desert-edge AOI (Diriyah) → AI under-flags real dust. This pattern won't surface from a smaller calibration set; the 43-scene SQ1C pass was load-bearing for finding it.

**Cold-protocol audits can return null results.** 4/6 cold-confirmed labels agreed with AI; 2/6 disagreed in directions consistent with the AOI-level pattern. The bias_exposure during pre-labeling did not produce a detectably different judgment pattern at this n. Negative results from contamination audits are still results — methodology footnote stays, but no separate finding to report.

**Long prompts to long work.** Single autonomous Claude Code prompt with recon-before-build, full multi-script execution, atomic commits, single review point at end — load-bearing protocol for any multi-step SQ. Confirmed working at SQ1C tooling build, SQ1C confirmation rerun, SQ2 operational, and SQ3 NDVI-bias. Interleaved approval gates burn momentum; recon-build-verify in one shot does not.

**Internal cross-validation between methods.** When two methods that didn't share decision-time inputs agree on the same finding, that's load-bearing for piece B's discussion section. SQ1C cold-protocol blind labeling and SQ2 continuous DBB independently identified the 2022-05-10 Diriyah peak event — name this kind of agreement explicitly when it surfaces; it doesn't surface often.

**Stop rules are scope-decision points, not failures.** SQ3's stop rule fired at Qiddiya 28.1% retention. The agent halted, surfaced the choice (widen window / drop AOI / change design / accept caveat) without picking, and waited for the researcher's call. That's the stop rule working *as designed*, not a problem to route around. Halting in the middle of the run is the cheapest possible scope review. Pattern: when designing a sub-question, write the stop rule as a multi-option scope decision rather than a binary fail/pass — the agent's job at threshold is to pause and surface, not to choose.

**The "different question" temptation when a stop rule fires.** When an analysis hits a stop-rule edge, the tempting move is to switch to a different design that bypasses the constraint (e.g. SQ3 paired-difference → continuous DBB-vs-NDVI regression). That switch is exactly what the stop rule is designed to catch: it conflates "we got a borderline retention" with "we should answer a different question." Pre-registered designs ship or halt on their own terms; new questions become new sub-questions (SQ3B, SQ4, etc.). Confirmed at SQ3: continuous-regression option offered, recommended-against, sub-question integrity preserved.

**Recon-before-build catches infra mismatches in 4 commands.** SQ3 prompt's R1–R4 recon block resolved NDVI-not-in-CSV, EECU estimate, column names, and denominator count before any new code was written. Saved a build pass that would have referenced `scene_date` (manifest col is `acquisition_date`) and assumed NDVI columns that didn't exist. Standard for any sub-question that touches an existing pipeline.

**Conditional nulls are findings, not setbacks.** SQ3's tight nulls at KSP and Qiddiya, with halfwidths 0.0076 and 0.0055 well below NDVI change-detection thresholds, are scope-bounded informative results. The honest framing names what the result *does* say (no measurable bias at this design at this loading regime on this correction chain) and what it *does not* say (Sen2Cor is universally fine; Goyens is wrong). The Goyens result describes a TOA / extreme-AOD regime; transfer to L2A at moderate loadings is not assumed in either direction. SQ4 (LaSRC cross-check) and SQ8 (AERONET ground truth) are the right ways to extend; window-widening or design-switching are not.

**Credential hygiene.** Sentinel Hub OAuth credentials, GEE project name, and any API tokens stay in `.env` only. `.env` is gitignored. `.private/context.md` for SARsatX-specific framing also gitignored.

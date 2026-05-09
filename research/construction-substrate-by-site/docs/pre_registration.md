# Piece A — Pre-registration

**Project:** Basira / construction-substrate-by-site
**Locked:** 2026-05-04
**Status:** Pre-registered. No execution before this document is committed.

## Umbrella question

Does substrate-aware L30+S30 fusion reduce false-positive change detections at active-construction Vision 2030 sites relative to S30-alone?

## Audience framing

Piece A is shaped for a Saudi space-sector hiring read, primary artifact is a technical methods memo (3–5 pages) for SARsatX-track audience. Three site-level research pieces (Qiddiya hero, KSP, Diriyah) are supporting assets. Execution discipline and clean communication are the load-bearing signals; methodological novelty is secondary.

## Scope conditional

Piece A has no external ground-truth label set for "real surface change" at Qiddiya. SA5's false-positive design uses piece B's V4 fire epochs + high-BSI flags as contamination labels — outputs of the basira research engine itself, not external truth. The umbrella question's answer is therefore conditional on that label framing: piece A can claim "the substrate-aware pipeline flags this fraction of V4+high-BSI scenes differently than S30-alone," not "this is the real surface change." Pre-registered now, not surfaced post-hoc.

## SA1 — Substrate spectral characterization

**Goal:** Build per-AOI bare-soil spectral signatures from cloud-free S30 + L30 scenes during identifiable bare-earth epochs. Output: BSI baseline per AOI.

**Method:** Bare Soil Index, BSI = ((SWIR + Red) − (NIR + Blue)) / ((SWIR + Red) + (NIR + Blue)). Compute per-scene BSI on S30 and L30 separately for each AOI. Identify bare-earth epochs from piece B's DBB-operational window (pre-construction or between phases) using BSI > AOI-specific 75th percentile as the bare-epoch flag.

**Pre-registered halt:** Minimum 5 cloud-free bare-epoch scenes per AOI, both S30 and L30. If any AOI has fewer than 5 in either sensor → halt SA1, document coverage gap as structural constraint, fall back to using piece B's full DBB-operational window as proxy bare epoch. SA1 receipts ship under `data/halts/sa1_coverage/` if halt fires.

**Output deliverable:** `data/sa1_bsi_baseline/{aoi}_bsi_per_scene.csv`, one row per scene with BSI value + cloud fraction + bare-epoch flag.

## SA2 — Construction-phase timeline

**Goal:** Map each AOI into construction phases (bare earthworks, active fill/grading, partial vegetation, landscaped) using BSI time series + piece B DBB fire rates. Establishes substrate-signal phase structure before any hypothesis testing.

**Method:** Phase boundaries defined by BSI quartile breaks computed across the full 76-month window per AOI. No visual inspection of imagery — quartile breaks are mechanical. Cross-reference phase transitions against DBB-operational fire rates from piece B SQ2 to confirm phase structure is real, not noise.

**Pre-registered halt:** If BSI variance across the 76-month window falls below threshold (var < 0.005) at any AOI → site is not phase-structured. Surface as finding (expected for Diriyah, informative if KSP). Site continues into SA3+ as control rather than test.

**Output deliverable:** `data/sa2_phase_timeline/{aoi}_phase_assignments.csv`, scene-date → phase label.

## SA3 — Substrate-NDVI confound test

**Goal:** Direct mechanism test. Does BSI predict NDVI residuals at Qiddiya independently of aerosol load?

**Method:** Regress NDVI residuals (per-AOI per-month climatology, same construction as piece B SQ8) against BSI, controlling for MERRA-2 DUEXTTAU. AOI fixed effects. HC3 robust standard errors. Pre-registered specification: `ndvi_residual ~ bsi + aod + aoi_fe`.

**Pre-registered hypotheses:**
- Substrate-primary (expected at Qiddiya): BSI coefficient β_bsi significant and positive; AOD coefficient β_aod near-zero (consistent with piece B null).
- Aerosol-primary (refutation direction): β_aod dominant, β_bsi near-zero.
- Equivalence (refutation direction): both coefficients of comparable magnitude.

**Pre-registered halt:** If per-AOI usable n < 20 after cloud-filtering (cloud fraction < 0.3 per scene) → halt, surface coverage deficit as structural finding. Defer per-AOI regression to pooled-only analysis.

**Pre-registered dual criterion (mirroring piece B SQ8):** Significance criterion (β_bsi CI excludes zero) and magnitude criterion (β_bsi × IQR(BSI) > 0.005, the operational change-detection threshold from piece B SQ8). Both pre-registered. Disagreement is a finding, not a failure.

**Output deliverable:** `data/sa3_bsi_ndvi_regression/regression_results.csv` + figure `figures/sa3_bsi_vs_ndvi_residual.png`.

## SA4 — L30 cross-sensor discriminability

**Goal:** Does L30 SWIR add discriminative power over S30 SWIR alone for separating construction substrate from real vegetation change?

**Method:** Paired design on S30+L30 co-acquisition dates (within ±1 day). Per-pair Δ(NDVI_S30) vs Δ(NDVI_L30). Stratify by BSI quartile. Bootstrap on pairs (not scenes), 1000 iterations.

**Pre-registered hypothesis:** If substrate dominates, S30 and L30 diverge in high-BSI quartiles (Q3/Q4). If real change dominates, they converge across all BSI quartiles.

**Pre-registered halt:** 50% L30 coverage floor — at least half of S30 scene dates need an L30 within ±1 day, computed per AOI. If coverage falls below 50% at any AOI → cadence mismatch halt-with-receipt (SQ4B shape from piece B). L30 coverage probe ships as committed receipt under `data/halts/sa4_coverage/`.

**Pre-scoped fallback (SA4C):** If SA4 halts in two or more AOIs, defer to native L30 pair construction (no S30 ±1-day requirement) for the AOI(s) with sufficient L30 density. SA4C is pre-scoped not because it will run, but so the fallback exists in advance — piece B taught this lesson at SQ4B → SQ4C cost. SA4C does not auto-run; it requires its own pre-registration before execution if SA4 halts.

**Output deliverable:** `data/sa4_s30_l30_paired/divergence_by_bsi_quartile.csv` + figure `figures/sa4_s30_vs_l30_quartile.png`.

## SA5 — False-positive reduction (operational test)

**Goal:** Build two change maps over the 76-month window at Qiddiya. Compare false-positive rate using piece B V4-fire epochs + high-BSI scenes as known-contamination anchors.

**Method:**
- Pipeline A (baseline): S30-alone NDVI delta, change flag = |Δ(NDVI)| > operational threshold (0.05 from piece B operational definition).
- Pipeline B (substrate-aware fusion): S30 NDVI delta + BSI phase mask. Change flag fires only if |Δ(NDVI)| > 0.05 AND BSI is not in active-substrate-phase quartile (Q4 from SA2).
- Reference labels: scenes flagged V4-fire (piece B SQ2 output) AND high-BSI (Q4 from SA2) are known-contamination anchors. False positive = pipeline flags real change at known-contamination anchor scene.

**Pre-registered hypothesis:** Pipeline B reduces false-positive rate at anchor scenes by ≥ 30% relative to Pipeline A at Qiddiya. <30% reduction is a null result and must ship as such.

**Pre-registered halt:** V4-anchor cell count < 15 at Qiddiya → insufficient anchor density. Defer to SA5B with expanded window (or the alternate framing: drop the false-positive design entirely and report only SA3+SA4 mechanism findings). SA5B requires its own pre-registration before execution.

**Output deliverable:** `data/sa5_false_positive/comparison_at_qiddiya.csv` + figure `figures/sa5_pipeline_comparison.png`.

## SA6 — Generalization at KSP and Diriyah

**Goal:** Anchor the substrate-finding generalization claim at the other two AOIs.

**Method:** Run SA1 + SA3 at KSP and Diriyah using identical specifications.

**Pre-registered expectations:**
- Qiddiya BSI-NDVI correlation: > 0.4 (test region).
- KSP: 0.2–0.5.
- Diriyah: < 0.2.

**Pre-registered surprises (must be reported if they fire):**
- Diriyah BSI-NDVI correlation > 0.4 → unexpected substrate finding at the cleanest atmospheric prior. Surface as primary finding, not aside.
- KSP correlation either > 0.5 or < 0.2 → site doesn't fit the gradient hypothesis. Surface as scope-specific finding.

**Pre-registered halt:** L30 coverage at KSP or Diriyah < 40% → site-specific cadence gap, surface as structural finding. SA6 ships SA1+SA3 results without SA4 cross-sensor for halted sites.

**Output deliverable:** `data/sa6_generalization/{ksp,diriyah}_bsi_ndvi.csv` + figure `figures/sa6_three_aoi_comparison.png`.

## Stop-rule philosophy (carried from piece B)

When a stop rule fires, the cheapest possible scope review is the one happening mid-run. The temptation in each case will be to switch to a different design that bypasses the constraint — a temptation that conflates "this measurement got borderline retention" with "we should answer a different question." Pre-registration catches that. New questions become new sub-questions (SA4C, SA5B); the original ships or halts on its own terms.

Halts ride into piece A as findings, not as appendix material. The `data/halts/` directory pattern from piece B carries forward.

## Time budget

Estimate: 6–10 weeks. Piece B took four months from SQ2 to ship; piece A has piece B's infrastructure (climatology, V4 outputs, AOD time series) but introduces new data (L30, BSI computation) and one new design (SA5 operational test). Net: faster than piece B but not 4–6 weeks.

Hard cap: 10 weeks for SA1 through SA6 execution + 4 weeks for prose draft + structural review + ship. If we blow through, halt and re-scope; do not silently extend.

## Out of scope

- SQ8B (KAUST coastal generalization) remains piece-B deferred. Not a piece A sub-question.
- SAR-optical fusion (the dust-robust monitoring jewel from the longer roadmap) is post-piece-A.
- Substrate composition by mineralogy (alluvium vs fill vs mixed) is piece-A-future, not piece A V1.
- Multi-city expansion remains parked on `wip/phase5-multicity`. Not a piece A sub-question.

## Locked. Execute SA1 first.

## Amendments

- Amendment 01 (locked 2026-05-09): SA2 halt substitution. SA4/SA5 redirect "Q4 from SA2" to "bare_epoch_flag from SA1". See `amendment_01_sa2_halt_substitution.md`.

# SQ1B re-run on faithful Lolli DBB — threshold tuning spec & results

**Inputs:** `research/dust-honesty/data/sq1d_dbb_faithful.csv` (Part B primary, 30 rows) and `sq1d_dbb_faithful_alt.csv` (Part B' alternate references, 24 rows).
**Output table:** `sq1b_threshold_results.csv`.
**Figures:** `sq1b_roc_curves.png`, `sq1b_bootstrap_thresholds.png`.
**Companion:** `sq1d_lolli_formula.md` (formula spec). `SQ1B_RESULTS.md` (predecessor on inspired-not-faithful values, commit `3d3b511`).

---

## 1. Stop rule (reused verbatim)

The stop rule comes from `SQ1B_RESULTS.md` (commit `3d3b511`):

> "abort if the bootstrap 95% CI half-width exceeds ±0.02 DBB units"
> "Only after CI half-width < 0.02 and AUC > 0.75: ship a threshold and write `is_dust_flagged`."

Reused without modification:

| Component | Threshold | Direction |
|---|---:|---|
| Bootstrap 95% CI half-width on Youden threshold | < **0.02** DBB units | precision |
| AUC of ROC | > **0.75** | discrimination |

Both conditions must hold. The same numerics applied to the original SQ1B run (CI half-width 0.026, AUC 0.55 / 0.51 → STOP), so this is a like-for-like comparison.

---

## 2. Method

For each binary task variant:
- Drop `cloud`-labeled rows (cloud is a different physical phenomenon, not aerosol load).
- ROC curve over a fine threshold sweep: 1000 thresholds linearly spanning the observed DBB range with ±0.1% pad.
- AUC via trapezoidal integration of TPR vs FPR.
- Youden-optimal threshold = `argmax(TPR − FPR)`. Tie-break: midmost threshold among tied indices.
- Bootstrap: 2000 iterations, seed 42, sample with replacement from the labeled set, recompute Youden threshold each iteration. Iterations where the bootstrap sample is single-class are skipped (counted in `notes`).
- 95% CI = (2.5, 97.5) percentiles of bootstrap thresholds.
- `ships` = `(CI half-width < 0.02) AND (AUC > 0.75)`.

**Caveat:** for variants with `n_pos < 5`, bootstrap is structurally unstable (many resamples will exclude the few positives entirely) and the CI is dominated by the degeneracy floor rather than true sampling variability. We run anyway and flag honestly in `notes`.

## 3. Variants

Cloud row dropped from all variants. `Qiddiya` is excluded from V4 because of the SQ1D Part A.5 finding that visual atmospheric labels there are contaminated by construction substrate visually mimicking haze — see `sq1d_lolli_formula.md` and CLAUDE.md.

| Variant | Scope | Positive class | n_pos | n_neg |
|---|---|---|---:|---:|
| V1 | all AOIs | heavy_dust vs clean | 1 | 23 |
| V2 | all AOIs | light_haze ∪ heavy_dust vs clean | 6 | 23 |
| V3 | KSP only | light_haze ∪ heavy_dust vs clean | 4 | 7 |
| V4 | KSP + Diriyah | light_haze ∪ heavy_dust vs clean | 4 | 12 |

V1 mirrors the conservative mapping of the original SQ1B for apples-to-apples comparison with `3d3b511`; n_pos collapsed from 2 → 1 because the relabel reclassified one of the original heavy_dust scenes (Qiddiya 2020-09 in the original mapping) as light_haze.

V2 mirrors the aggressive mapping. V3 isolates the construction-evolving AOI where the relabel yielded the cleanest signal monotonicity. V4 expands V3 with the surface-stable AOI but excludes the contaminated one.

## 4. Per-variant results (primary references)

### V1 — heavy_dust vs clean, all AOIs (1 vs 23)
AUC = 1.000, threshold = +0.1753, 95% CI = [+0.121, +0.175], CI half-width = 0.027. **STOP** — CI fails (single positive separates trivially but bootstrap collapses; 757/2000 iterations degenerate). The structural floor of an n_pos=1 task.

### V2 — any-non-clean vs clean, all AOIs (6 vs 23)
AUC = 0.688, threshold = +0.0477, 95% CI = [−0.064, +0.175], CI half-width = 0.120. **STOP** — both criteria fail. AUC near chance is driven by Qiddiya: the 11 clean Qiddiya scenes have a higher DBB median (+0.109) than the 2 light_haze Qiddiya scenes (+0.100), inverting the expected ordering and dragging discrimination down.

### V3 — KSP-only any-non-clean vs clean (4 vs 7)
AUC = 0.839, threshold = +0.0558, 95% CI = [−0.064, +0.056], CI half-width = 0.060. **STOP** — AUC passes; CI fails (n_pos=4 unstable; 9/2000 iters degenerate). KSP shows the expected monotone clean → light_haze → heavy_dust ordering, but the sample is too small to pin the threshold to ±0.02 precision.

### V4 — KSP + Diriyah any-non-clean vs clean (4 vs 12)
AUC = 0.823, threshold = +0.0274, 95% CI = [−0.064, +0.027], CI half-width = 0.046. **STOP** — AUC passes; CI fails. Adding Diriyah's 5 clean scenes preserves AUC, lowers the threshold (Diriyah cleans pull the negative-class distribution down because of the §7 SZA seasonal bias), and tightens CI from V3's 0.060 → 0.046, but still 2.3× over budget.

## 5. Sensitivity check (alternate references)

By the stop-rule selection rule (largest passing variant; if none pass, highest-AUC variant), the chosen variant is **V1** (AUC = 1.000). V1 was re-run on `sq1d_dbb_faithful_alt.csv` filtered to its positive class (heavy_dust) and clean negatives.

Diriyah has no alternate reference, so V1_alt operates on KSP + Qiddiya only (1 heavy_dust positive, 18 cleans — same scenes as V1_primary minus the 5 Diriyah cleans).

| Side | n_pos | n_neg | AUC | t_youden | CI half-width | ships |
|---|---:|---:|---:|---:|---:|---|
| V1 primary | 1 | 23 | 1.000 | +0.1753 | 0.0272 | False |
| V1 alternate | 1 | 18 | 1.000 | +0.2420 | 0.0320 | False |

Threshold delta = +0.0667 (alternate is uniformly higher because the alternate references at Qiddiya and KSP are atmospherically cleaner — UVAI −1.166 / +0.336 vs primary +0.310 / −0.067 — making test scenes look more positive in DBB). **Stop-rule outcomes agree** (both STOP, both on the CI condition). The high AUC is preserved across reference choice; the absolute threshold shifts as expected from the Part B' Spearman rank-correlation finding (ρ = 0.97 KSP / 0.92 Qiddiya — ordering stable). This is consistent with V1's discrimination being a structural separability finding (heavy_dust does sit above all cleans), not an artifact of reference choice.

## 6. Recommendation

**No threshold ships from this re-run.** All four variants STOP on the bootstrap CI condition, three of them despite passing AUC. The blocker is sample size, not signal — V3 and V4 show AUC > 0.82 on the faithful values (vs 0.55 on the inspired-not-faithful values from the original SQ1B), confirming that the formula port did the work it was meant to. What is missing is positives.

**Path forward — calibration-set expansion via SQ1C-style UVAI-anchored positives.** Use TROPOMI UVAI as an instrument-anchored selector for high-aerosol days, then pull S2 scenes from each AOI on those days, label them with the same visually-blind protocol (post-render, date-only caption, construction-substrate exclusion rule per the methodology footnote). Target **n_pos ≥ 10 per AOI** for V3-scope and V4-scope so the bootstrap CI floor drops below 0.02. UVAI is appropriate here because Part A.5 already showed that purely visual labels at construction-active AOIs are unreliable in both directions; a UVAI prior tightens the heavy-dust class boundary without contaminating the visual rubric. Document this expansion as a new sub-question (call it SQ1C) so the methodology footnote can cite it cleanly. Until that lands, **none of V1–V4 thresholds should be propagated to SQ2–SQ7** as production dust flags. The faithful-DBB *value* per scene is fine to use as a continuous covariate; only the binarized flag is gated.

If the field-expansion route is rejected, the second-best option is to ship V4's threshold (+0.027) under a clearly-labeled "preliminary, n=4 positives, CI ±0.046" caveat. This is a research-piece-discussion result, not a production flag. Recommend against it for SQ2–SQ7 because the downstream NDVI-bias analysis is sensitive to false-positive dust days; a 0.046 CI on the threshold translates to ~25–40% swing in flagged-day count over our 6-year window.

## 7. Why V4 exists alongside V2 — Qiddiya label contamination

V2 includes Qiddiya, where the SQ1D Part A.5 visually-blind relabel revealed that 4/13 calibration scenes had their original haze labels overturned. Qiddiya's clean DBB median (+0.109) is *higher* than its light_haze DBB median (+0.100) — an inversion that reflects the difficulty of distinguishing atmospheric haze from sharp-edged construction substrate even with the explicit exclusion rule. V2's AUC drop (0.688) vs V3/V4 (0.82–0.84) is almost entirely Qiddiya's contribution.

V4 keeps the same task framing as V2 (any-non-clean vs clean) but restricts to AOIs where the visual labels are trustworthy: KSP (where the relabel's monotonicity is preserved) and Diriyah (surface-stable, no construction substrate). V4 is the most defensible variant for ship-no-ship purposes; it stops only on sample size.

## 8. Sensitivity check: what we learned

V1's near-trivial separability (one heavy_dust scene, no overlap with cleans) is preserved across reference choice — the +0.21 KSP heavy_dust DBB on primary becomes +0.26 on alternate, but all clean scenes still sit below it. The alternate-mode threshold shift (+0.067) is larger than the CI half-width on either side, so the choice of reference scene measurably moves the threshold line, but does not reverse the classification of any scene at the Youden point. This is the expected behaviour from Part B''s Spearman finding (ranking stable, absolute level shifts) — and means the *form* of any future shipped threshold will be reference-anchored: SQ1C should use the primary reference set throughout for consistency.

## 9. Stop-rule status table

| Variant | n_pos | n_neg | AUC | CI hw | AUC > 0.75 | CI < 0.02 | ships |
|---|---:|---:|---:|---:|:-:|:-:|:-:|
| V1 | 1 | 23 | 1.000 | 0.027 | ✓ | ✗ | **stop** |
| V2 | 6 | 23 | 0.688 | 0.120 | ✗ | ✗ | **stop** |
| V3 | 4 | 7 | 0.839 | 0.060 | ✓ | ✗ | **stop** |
| V4 | 4 | 12 | 0.823 | 0.046 | ✓ | ✗ | **stop** |
| V1_alt | 1 | 18 | 1.000 | 0.032 | ✓ | ✗ | **stop** |

**Verdict:** none of V1–V4 cleared. SQ2–SQ7 proceed without a binarized dust flag. Continuous DBB covariate is usable. Calibration-set expansion (SQ1C) is the unblocking task.

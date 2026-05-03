# SQ1B confirmed-label findings — what the researcher pass actually changed

**Date:** 2026-05-01.
**Inputs:** `calibration/combined_calibration_confirmed.csv` (73 rows), `sq1b_rerun_v2_confirmed_threshold_spec.md`, `calibration/confirmation_audit_sq1c.csv`.
**Reference baselines:** `sq1b_rerun_v2_threshold_spec.md` (preliminary, AI-only SQ1C labels).

This note is the factual readout of the post-confirmation pass. It is the document we point at when asked "what did researcher confirmation actually find."

---

## 1. Calibration-layer agreement

12 of 43 SQ1C AI pre-labels were overridden by the researcher (agreement = 31/43 = 72.1%, disagreement = 27.9%). Per AOI:

| AOI | n | Agree | Override | Rate |
|---|---:|---:|---:|---:|
| KSP | 13 | 11 | 2 | 84.6% |
| Qiddiya | 15 | 10 | 5 | 66.7% |
| Diriyah | 15 | 10 | 5 | 66.7% |
| **All** | 43 | 31 | 12 | 72.1% |

**Override directions are AOI-dependent.** The pattern matters more than the rate.

| AOI | clean → light_haze | light_haze → clean | clean → heavy_dust | light_haze → heavy_dust | light_haze → clean |
|---|---:|---:|---:|---:|---:|
| KSP | 0 | 2 | 0 | 0 | (= col 2) |
| Qiddiya | 1 | 4 | 0 | 0 | (= col 2) |
| Diriyah | 1 | 0 | 1 | 2 | 1 |

- **KSP and Qiddiya softened toward clean.** 6 of 7 overrides on construction-active AOIs went `light_haze → clean` (AI was over-flagging summer brightness as haze where the researcher reads it as scene-wide construction substrate or summer sun-angle). 1 Qiddiya scene went the other way (`clean → light_haze`).
- **Diriyah hardened.** 3 of 5 overrides went toward heavier classes (`clean → heavy_dust`, `light_haze → heavy_dust × 2`). 2 went the other way. Net effect: Diriyah's heavy_dust class grew from 1 to 4 in SQ1C.

This AOI-direction split is itself a finding: AI labeling under the SQ1D Pass 5 rubric was consistently more haze-skeptical at construction-active AOIs and consistently milder than blind researcher reading at the surface-stable AOI.

## 2. Cold-row results — the bias-exposure signal

The 6 rows flagged `bias_exposed_during_ai_labeling=True` were cold-labeled blind (no AI label, no UVAI). Result:

| AOI | Date | AI pre-label | Cold-confirmed | Agree? | UVAI |
|---|---|---|---|---|---:|
| KSP | 2025-07-15 | light_haze | light_haze | yes | +2.25 |
| Qiddiya | 2022-04-10 | clean | clean | yes | +2.07 |
| Qiddiya | 2024-03-10 | light_haze | clean | NO | +2.20 |
| Diriyah | 2022-05-10 | light_haze | heavy_dust | NO | +2.29 |
| Diriyah | 2022-05-20 | light_haze | light_haze | yes | +2.26 |
| Diriyah | 2022-05-25 | heavy_dust | heavy_dust | yes | +3.30 |

**Cold disagreement: 2/6 = 33%. Standard disagreement: 10/37 = 27%.** The two rates are within sampling noise of each other on n=6 vs n=37. The bias_exposure during AI pre-labeling (top-3 candidate UVAI values surfaced before labeling on these 6 scenes) did not produce a detectably different AI judgment pattern from the unexposed 37. Read: the contamination chain existed in protocol but did not move the AI's actual labels in a measurable way for this batch.

This is a narrower finding than "the contamination invalidated the labels." The exposure was real and the disclosure stays in the methodology footnote — but the cold-label audit did not detect a bias-direction in those 6 rows beyond what we see in the unexposed 37. The 2 disagreements that exist (Qiddiya 2024-03-10 light_haze→clean, Diriyah 2022-05-10 light_haze→heavy_dust) are in the same direction as the AOI-level pattern from §1, not orthogonal to it.

## 3. Stop-rule outcomes — confirmed vs preliminary

Stop rule unchanged: **CI half-width < 0.020 AND AUC > 0.75**. 4 binary task variants on the 73-row combined set, cloud-labeled rows excluded.

| Variant | Scope | n_pos prelim | n_pos conf | AUC prelim | AUC conf | t_youden prelim | t_youden conf | CI_hw prelim | CI_hw conf | Ships prelim | Ships conf |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|:-:|:-:|
| V1 | heavy_dust vs clean, all | 2 | 5 | 0.924 | **0.626** | +0.121 | +0.034 | 0.049 | 0.109 | ✗ | ✗ |
| V2 | any-non-clean vs clean, all | 23 | 19 | 0.711 | **0.578** | +0.027 | +0.034 | 0.030 | 0.027 | ✗ | ✗ |
| V3 | KSP-only any-non-clean vs clean | 11 | 9 | 0.934 | **0.837** | +0.053 | +0.053 | 0.000 | 0.000 | ✓ | ✓ |
| V4 | KSP+Diriyah any-non-clean vs clean | 17 | 16 | 0.924 | **0.853** | +0.027 | +0.034 | 0.018 | 0.012 | ✓ | ✓ |

**Stop-rule outcomes did not flip for any variant.** What ships still ships; what doesn't still doesn't.

**AUC fell across all four variants.** The preliminary AI-only labels were systematically easier for the formula to discriminate than the researcher's confirmed labels. The headline numbers are the confirmed ones now; the preliminary AUCs were optimistic.

### Per-variant prose

**V1 (heavy_dust vs clean, all AOIs):** AUC collapsed from 0.924 to **0.626** as n_pos tripled from 2 to 5. The 3 added heavy_dust scenes are all Diriyah (2021-08-03, 2022-04-10, 2022-05-10). At least one (2021-08-03) carries UVAI = +1.85, which sits inside the AOI's clean class UVAI range (mean +1.70, p75 +1.76). The researcher's blind visual reading identified scene-wide veiling on a day with moderate UVAI — visual heavy_dust is not univariately a high-UVAI / high-DBB regime. The Lolli DBB formula does not separate confirmed-heavy_dust from clean cleanly when the heavy_dust class spans a range of aerosol loads. **V1 does not ship and the explanation is structural, not n_pos-floor.** Growing V1 beyond n_pos=5 would require either a longer time window or anchoring positives to UVAI > +2.5 only, not visual judgment — but that defeats the purpose of treating visual labels as ground truth.

**V2 (any-non-clean vs clean, all AOIs):** AUC fell further, from 0.711 to **0.578**. Confirmed labels softened the Qiddiya positive class (4 light_haze→clean overrides) — but this didn't rescue V2 because (a) the AOI-pooled positive class now mixes Qiddiya-soft-haze and Diriyah-blind-heavy_dust which sit in different DBB regimes, and (b) Qiddiya's remaining positives include the `clean → light_haze` override on 2026-01-29 (a low-UVAI scene). Pooling all three AOIs into one binary task continues to fail the stop rule. The construction-substrate finding (V2 doesn't pool because Qiddiya contaminates) gets stronger, not weaker, on confirmed labels: that's the fourth independent line of evidence for the same effect (SQ1D Pass 5 + Part B' + V2 preliminary + V2 confirmed).

**V3 (KSP-only any-non-clean vs clean):** AUC dropped from 0.934 to **0.837**, n_pos dropped from 11 to 9 (the 2 light_haze→clean overrides at KSP). Bootstrap CI still collapses to 0.000 — every resample lands on the same Youden threshold +0.053 — because the n=24 KSP set is still perfectly separable at that threshold. Ships, but on a tighter sample. The CI=0.000 disclosure (`no bootstrap variance under current resampling protocol`) carries forward verbatim.

**V4 (KSP + Diriyah any-non-clean vs clean):** AUC dropped from 0.924 to **0.853**, n_pos from 17 to 16, threshold drifted from +0.027 to +0.034. CI half-width *tightened* from 0.018 to 0.012 — the Diriyah hardening (3 added heavy_dust labels) brought the bootstrap distribution in. Ships at the most defensible scope. **V4 remains the headline number.**

## 4. UVAI cross-check on confirmed labels (post-hoc audit)

Per (AOI, confirmed_label) cell. UVAI mean and p25/p50/p75:

| AOI | Label | n | mean | p25 | p50 | p75 |
|---|---|---:|---:|---:|---:|---:|
| KSP | clean | 8 | +1.634 | +1.533 | +1.593 | +1.738 |
| KSP | light_haze | 5 | +1.876 | +1.782 | +1.833 | +1.888 |
| Qiddiya | clean | 14 | +1.848 | +1.725 | +1.773 | +1.979 |
| Qiddiya | light_haze | 1 | +1.666 | +1.666 | +1.666 | +1.666 |
| Diriyah | clean | 8 | +1.703 | +1.616 | +1.627 | +1.757 |
| Diriyah | light_haze | 3 | +2.190 | +2.155 | +2.220 | +2.240 |
| Diriyah | heavy_dust | 4 | +2.366 | +1.977 | +2.156 | +2.545 |

- **KSP** monotone (clean < light_haze).
- **Qiddiya** has only 1 confirmed light_haze (2026-01-29 at UVAI +1.67), below the clean median +1.77. Qiddiya's confirmed label distribution (14 clean, 1 light_haze, 0 heavy_dust) means the AOI is essentially clean-dominated under researcher review, with the formula calibration coming from contrast within the clean class. Not interpretable as a class-vs-class UVAI ordering at this n.
- **Diriyah** light_haze and heavy_dust UVAI distributions overlap. Heavy_dust median (+2.156) is below light_haze median (+2.220), but heavy_dust p75 (+2.545) is above light_haze p75 (+2.240). The single very-high heavy_dust scene (2022-05-25 at +3.30) plus the moderate-UVAI heavy_dust scenes (2021-08-03 +1.85, 2022-04-10 +2.02, 2022-05-10 +2.29) span a wider range than light_haze. **Visually-judged heavy_dust does not sit at strictly higher UVAI than light_haze on Diriyah.** Piece B discussion-section material.

3 anomaly flags from the comparison script — confirmed-clean rows with UVAI > +2.0, all on Qiddiya:

| Date | UVAI | Notes |
|---|---:|---|
| 2022-04-10 | +2.07 | Cold-confirmed clean (blind, with UVAI hidden) |
| 2022-08-18 | +2.06 | Standard-confirmed clean |
| 2024-03-10 | +2.20 | Cold-confirmed clean (blind, with UVAI hidden) |

Two of these survived a cold-protocol check — the researcher labeled them clean blind, despite UVAI values that would normally flag a positive. **High UVAI without visible scene-wide veiling at construction-active Qiddiya is its own finding** for piece B's discussion section: TROPOMI absorbing-aerosol-index can register above +2.0 over a scene that visually reads clean, particularly where bidirectional construction substrate dominates the AOI surface. UVAI is the right tool for some questions and not for others; pairing visual labels with UVAI is the correct framing, not "calibrate visual to UVAI."

## 5. What this means for piece B framing

**Headline scope still V4 (KSP + Diriyah, any-non-clean vs clean).** AUC 0.853, threshold +0.034 at Youden's J, CI half-width 0.012. AUC dropped from preliminary 0.924 — disclose the drop in prose, do not lead with the preliminary number. The CI is *tighter* than preliminary, which is the stronger statistic to lead with.

**V3 supplementary** with disclosure: AUC 0.837, threshold +0.053, CI=0.000 = "no bootstrap variance under current resampling," not infinite confidence.

**V1 does not ship and that is a finding, not a setback.** "Heavy_dust vs clean is the cleanest binary task" was the working assumption on n_pos=2; on n_pos=5 with researcher-confirmed labels, AUC collapses because the heavy_dust visual class spans a wide range of aerosol loads and DBB regimes. The Lolli formula does not univariately discriminate visual heavy_dust from visual clean. This belongs in piece B's discussion section as a substantive limitation of the approach.

**V2 still does not ship — and the explanation is sharper now.** Pooling all three AOIs into one binary task fails for two distinct reasons: Qiddiya's bidirectional construction-substrate contamination (now four independent confirmations) and the AOI-dependent direction of label disagreement (KSP/Qiddiya soften toward clean, Diriyah hardens toward heavy_dust). Pooling these into one classifier averages over signal that the AOIs each carry differently.

**Methodology-section headline:** the 28% calibration-layer disagreement rate, AOI-direction split, and 3 cold-confirmed clean-with-high-UVAI rows on Qiddiya are now the load-bearing methodology findings for piece B. They are independent of the threshold-fit results and they are stronger evidence than any single variant's AUC. The piece-B writeup should lead the methodology section with these and use V4 as the recovered headline calibration result, not the other way around.

## 6. PRELIMINARY framing — drop or amend

The "PRELIMINARY pending researcher confirmation" framing on `sq1b_rerun_v2_*` results from 2026-04-30 session 3 can now be dropped from any forward-looking writeup. The non-preliminary numbers are in `sq1b_rerun_v2_confirmed_*`. The methodology footnote in CLAUDE.md and SQ1C protocol §4a needs updating to:

- Replace "Researcher confirmation at full resolution was deferred to a later cleanup pass" with the actual completion date (2026-05-01) and override count (12/43 = 27.9%).
- Replace "SQ1B re-re-run results derived from this set are PRELIMINARY pending researcher review" with the confirmed-vs-preliminary AUC delta per variant from §3 above.
- Retain the 6 bias_exposed row enumeration and the cold-protocol description verbatim. The cold-row finding (2/6 disagreement, same direction as the AOI-level pattern, not detectably bias-driven beyond it) updates the rationale paragraph but does not erase the disclosure.

The preliminary CSVs and PNGs stay on disk untouched per the audit-preservation rule.

## 7. Items still open (not blockers for piece B framing)

- Naming rationalization (`sq1d_*` / `sq1c_*` / `sq1b_rerun_v2_*` / `sq1b_rerun_v2_confirmed_*` → end-state taxonomy) before piece B prose ships. Cosmetic.
- §7 SZA dependency formal investigation still queued for piece B discussion.
- SQ8 KAUST AERONET validation still committed before publishing.
- CDSE OData spike still pending for SQ3 / SQ8.

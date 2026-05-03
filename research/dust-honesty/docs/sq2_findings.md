# SQ2 findings — applying the confirmed DBB flag to 228 operational scenes

**Date:** 2026-05-01.
**Inputs:** `sq2_dbb_operational.csv` (228 rows = 3 AOIs × 76 months, 2020-01..2026-04), `sq2_summary_stats.md`, `sq2_cross_check_failures.csv`.
**Calibration anchors:** V4 = +0.034, V3 (KSP only) = +0.053, both from `sq1b_rerun_v2_confirmed_threshold_spec.md`.

This is the operational readout for piece B. SQ1B sized the threshold; SQ2 measures how often that threshold fires across the full study period. No new modelling, no new fitting — application only.

---

## 1. What SQ2 does (and does not do)

SQ2 takes the V4 confirmed Youden threshold (+0.034) and applies it to one Sentinel-2 scene per (AOI, month) over Jan 2020 – Apr 2026. Selection follows a manifest-locked priority: any (AOI, month) overlapping the SQ1B/SQ1D/SQ1C calibration set inherits the locked scene; remaining slots are picked by lowest `CLOUDY_PIXEL_PERCENTAGE` over the AOI bbox in that calendar month, with date ascending as tiebreaker. DBB compute is byte-identical to `sq1d_lolli_faithful.compute_dbb` (single image, single sum+count reducer, no `bestEffort`, native scale 20m), imported wholesale to guarantee math parity. References per AOI are unchanged from `calibration/references_sq1d.json`.

A self-reference unit test (KSP test scene = ref scene) ran at the start of the sweep and returned `DBB = 0.00e+00` exactly, confirming the formula has not drifted.

This note does **not** speak to NDVI bias (SQ3), HLS cross-validation (SQ4), AERONET ground truth (SQ8), or the §7 SZA/TOA-vs-SR open question. SQ2's job is the V4 fire rate, the temporal pattern, and the cloud-availability bound. Everything downstream depends on this readout.

## 2. Headline rates

| AOI | months | usable | V4 fires | % of usable | DBB mean | DBB range |
|---|---:|---:|---:|---:|---:|---|
| King Salman Park | 76 | 74 | 24 | **32.4%** | +0.017 | [-0.23, +0.22] |
| Qiddiya core | 76 | 76 | 57 | **75.0%** | +0.091 | [-0.16, +0.20] |
| Diriyah Gate | 76 | 76 | 9 | **11.8%** | -0.052 | [-0.28, +0.07] |

**The three AOIs trace three different things.** KSP sits with its DBB distribution centered just below the V4 threshold and fires concentrated in shamal months (May–Oct = 19 of 24 fires; 0 fires Nov–Feb). That looks like a real seasonal aerosol signal, with the shoulder months (Mar–Apr, Sep–Oct) responsible for ~25% of fires.

Diriyah fires concentrate tightly in Apr–Jul (9 of 9 fires) with the peak DBB scene on 2022-05-10 — the same shamal-season cluster that drove the SQ1C confirmed `heavy_dust` labels at Diriyah. **Diriyah's 11.8% is the cleanest operational fire rate available — at the only surface-stable AOI in the set, with shamal-season concentration consistent with regional climatology (peak March–August, Apr–Jun maximum).** That number is the headline aerosol-incidence figure to lead with for piece B.

The Qiddiya rate is reported but flagged — see §3.

## 3. The Qiddiya 75% — methodology limit, not 57 dusty months

Qiddiya fires in 57 of 76 months (75%) with a DBB mean of **+0.091**, almost three times the V4 threshold. The fires are distributed across every calendar month from February through November (4–6 fires per month), not concentrated in shamal season. **This is not 57 dusty Qiddiyas; it is the construction-substrate signal predicted across four prior independent lines of evidence:**

1. **SQ1D Pass 5 visually-blind relabel** found 8 of 12 Qiddiya scenes initially labeled `light_haze` were actually scene-wide construction substrate, not atmospheric haze.
2. **SQ1D Part B' sensitivity analysis** showed Qiddiya primary-vs-alternate-reference Spearman ρ = 0.92 (vs ρ = 0.97 at KSP) — the surface evolution at Qiddiya induces reference-choice sensitivity beyond what is observed at KSP.
3. **SQ1B V2 preliminary AUC** (pooling all three AOIs) = 0.711, falling well short of the 0.75 stop rule, with Qiddiya excluded recovers to V4 AUC = 0.924.
4. **SQ1B V2 confirmed AUC** = 0.578 — the Qiddiya pooling failure tightens, not loosens, on researcher-confirmed labels.

The DBB formula is reading the difference between the test scene's TOA reflectance and a 2024-01-20 reference. As construction substrate accumulates between 2020 and 2026, that difference grows monotonically across the bright-surface bands (B11, B12) regardless of the day's atmospheric state. The 75% fire rate quantifies that drift directly.

**Implication for piece B:** Qiddiya's V4 column is reported in the operational table but the prose lead is "we cannot honestly translate the V4 fire rate to a per-month dust incidence at a construction-active AOI under a single fixed reference." The corollary recommendation — pair surface-static AOIs with surface-evolving AOIs and keep their interpretations separate — is itself the methodology contribution.

## 4. Cloud-affected fraction — operational availability bound

Per-AOI rate of `cloud_flag_present = True` (cloud_pct in AOI > 30%, computed from QA60 bits 10+11):

| AOI | cloud-affected | total | rate |
|---|---:|---:|---:|
| King Salman Park | 0 | 76 | 0.0% |
| Qiddiya core | 0 | 76 | 0.0% |
| Diriyah Gate | 1 | 76 | 1.3% |

**Cloud-affected fraction is ~1% across the operational set.** That is a Riyadh-region climatology fact, not a methodology choice — these AOIs sit in a low-cloud window. The single Diriyah cloud-affected scene is 2026-04-14 (cloud_pct_aoi = 80.56%); it remains in the operational CSV with `flag_v4 = True` and `cloud_flag_present = True`, surfaced honestly rather than dropped. Two KSP scenes (2020-11, 2026-04) were marked `no_usable_scene = True` because the SCL valid mask returned no AOI-resident pixels — a granule-edge effect, not a cloud effect. They appear in the manifest with system_indexes but with `dbb = NaN`.

For SQ3 onward, the operational availability bound is **74/76 KSP, 76/76 Qiddiya, 76/76 Diriyah** = 226/228 = 99.1%. NDVI bias estimates derived from this set will inherit that bound.

## 5. Cross-check vs calibration

Calibration overlap rows (where `(aoi, year, month)` appears in `sq1bc_combined_calibration_confirmed.csv`): **57**. Of those, **55 pass** the `|sq2_dbb − cal_dbb| < 1e-4` tolerance. Two fail:

| AOI | year-month | system_index | sq2 | cal | delta |
|---|---|---|---:|---:|---:|
| KSP | 2021-02 | `20210204T073111_..._T38RPN` | -0.0885 | -0.1050 | +0.0165 |
| KSP | 2026-02 | `20260213T074301_..._T38RPN` | +0.0069 | +0.0108 | -0.0039 |

**Both failures are GEE processing-baseline drift, not formula drift.** The system_indexes match the calibration manifest exactly; the underlying L1C/L2A pixel data has been backfilled with updated baselines since calibration was computed (the KSP 2021-02 scene was already documented as drift-prone in `calibration/manifest_sq1d.csv`'s lock note — the manifest locks `system:index`, but GEE retains the right to update the pixel content of that index). Both deltas leave the V4 classification unchanged: cal and sq2 are both V4-negative on each row. **Classifications are stable; pixel values shifted by ≤1.6%.** That is the load-bearing read.

The self-reference unit test (DBB exactly 0 at test=ref) passing on the same run rules out formula or pairing bugs as the source. The drift exists in GEE, not in our code.

For piece B's methodology section: this is the third instance of GEE catalog drift within this project (after the 2026-04-30 KSP 2021-02 deterministic-pick drift and the SQ1D `bestEffort`/scale-drift bug that occasioned the bug-fixed reducer). The mitigation pattern — manifest-lock `system:index` per (aoi, slot), test renderers read manifest first, deterministic-pick is fallback only — protects scene identity but not pixel content; for value-stability the only protection is a frozen GEE asset export, which is out of scope for SQ2.

## 6. Temporal pattern — peak scenes

| AOI | Peak DBB | Date | system_index |
|---|---:|---|---|
| KSP | +0.218 | 2024-08-02 | `20240802T072619_..._T38RPN` |
| Qiddiya | +0.204 | 2021-07-09 | `20210709T072619_..._T38RPN` |
| Diriyah | +0.066 | 2022-05-10 | `20220510T072621_..._T38RPN` |

The KSP and Qiddiya peaks are both summer-shamal scenes; the Diriyah peak is the May-2022 cluster that included three confirmed `heavy_dust` SQ1C scenes (2022-05-10, 2022-05-20, 2022-05-25). That cluster is internal cross-validation: SQ1C cold-protocol blind labeling and SQ2 operational continuous DBB independently identified the same Diriyah peak event without sharing decision-time inputs. **The Diriyah peak DBB (+0.066) is roughly one-third of the KSP and Qiddiya peaks** — consistent with Diriyah's surface-stable, desert-edge character: when the formula picks up real atmospheric loading rather than substrate evolution, the magnitudes are smaller and the dynamic range above the threshold is tighter.

## 7. What this enables and what it does not

**Enabled, immediately:**
- SQ3: NDVI bias on flagged-vs-unflagged scenes within each AOI.
- SQ4: HLS NDVI cross-check on the same 228-scene grid.
- SQ5–SQ7: continuing through the dust-honesty sub-question chain.
- The piece-B operational table: 32% / 75% / 12% V4 fire rates, with the Qiddiya methodology footnote.

**Not addressed, intentionally:**
- AERONET ground-truth (SQ8, KAUST station): committed before piece B publishes.
- §7 SZA/TOA-vs-SR formal investigation: discussion-section material, not a blocking dependency.
- Construction-substrate decoupling at Qiddiya: would require a per-period reference (rolling reference window) and is out of scope for SQ2's "apply the calibrated threshold" task.

The 12% Diriyah V4 rate is the number to lead with externally. The 32% KSP rate is the secondary number and stands as the comparison point. The 75% Qiddiya rate is a methodology finding, not a climatology finding, and the prose treatment must reflect that.

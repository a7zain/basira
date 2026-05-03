# SQ1B re-re-run — threshold spec on CONFIRMED labels

**Input:** `sq1bc_combined_calibration_confirmed.csv` (30 SQ1D + 43 SQ1C, primary refs, SQ1C labels = `confirmed_label` post-researcher-review).
**Stop rule:** CI half-width < 0.02 AND AUC > 0.75.
**Bootstrap:** 2000 iters, seed=42; ROC sweep 1000 thresholds.

**Status:** Non-preliminary IFF the 6 cold-protocol rows (`bias_exposed_during_ai_labeling=True`) and all 37 standard-protocol rows have been researcher-confirmed via `sq1c_label_review.py`. The bias_exposed flag remains True in the data even after cold-labeling — the cold protocol is the audit, not an erasure.

## Per-variant results (confirmed labels)

| variant | n_pos | n_neg | AUC | t_youden | CI [lo, hi] | CI hw | ships |
|---|---:|---:|---:|---:|---|---:|:-:|
| V1 | 5 | 53 | 0.6264 | +0.0344 | [-0.0106, +0.2070] | 0.1088 | ✗ |
| V2 | 19 | 53 | 0.5785 | +0.0344 | [-0.0037, +0.0512] | 0.0274 | ✗ |
| V3 | 9 | 15 | 0.8370 | +0.0529 | [+0.0529, +0.0529] | 0.0000 | ✓ |
| V4 | 16 | 28 | 0.8527 | +0.0344 | [+0.0274, +0.0512] | 0.0119 | ✓ |

## Confirmed vs preliminary (session 3) comparison

Preliminary source: `sq1b_rerun_v2_threshold_results.csv` (AI-only labels for SQ1C).

| variant | n_pos prelim | n_pos conf | AUC prelim | AUC conf | t_youden prelim | t_youden conf | CI hw prelim | CI hw conf | ships prelim | ships conf | changed? |
|---|---:|---:|---:|---:|---:|---:|---:|---:|:-:|:-:|:-:|
| V1 | 2 | 5 | 0.9235 | 0.6264 | +0.1209 | +0.0344 | 0.0490 | 0.1088 | ✗ | ✗ | **no** |
| V2 | 23 | 19 | 0.7107 | 0.5785 | +0.0274 | +0.0344 | 0.0302 | 0.0274 | ✗ | ✗ | **no** |
| V3 | 11 | 9 | 0.9336 | 0.8370 | +0.0529 | +0.0529 | 0.0000 | 0.0000 | ✓ | ✓ | **no** |
| V4 | 17 | 16 | 0.9237 | 0.8527 | +0.0274 | +0.0344 | 0.0176 | 0.0119 | ✓ | ✓ | **no** |

**Stop-rule changes** are the load-bearing diff. Any 'yes' in the `changed?` column needs prose explanation in the methodology footnote update.

## Variant scopes

- V1: heavy_dust vs clean, all AOIs.
- V2: any-non-clean vs clean, all AOIs (HEADLINE attempt).
- V3: KSP-only any-non-clean vs clean.
- V4: KSP + Diriyah any-non-clean vs clean (Qiddiya excluded for construction-substrate label contamination — V2 failure on this scope is the third independent line of evidence for that effect).

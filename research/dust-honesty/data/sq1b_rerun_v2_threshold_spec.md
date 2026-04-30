# SQ1B re-re-run — threshold spec on combined 73-scene set

**Input:** `sq1bc_combined_calibration.csv` (30 SQ1D + 43 SQ1C, primary references).
**Stop rule:** CI half-width < 0.02 AND AUC > 0.75.
**Bootstrap:** 2000 iters, seed=42; ROC sweep 1000 thresholds.

**Status:** PRELIMINARY. SQ1C labels are AI-only (researcher confirmation
deferred per 2026-04-30 session 3 decision); 6 SQ1C rows had partial UVAI
exposure during AI pre-labeling and are flagged via
`bias_exposed_during_ai_labeling=True` in the source CSVs. Do not propagate
results to external communication before researcher review.

## Per-variant results

| variant | n_pos | n_neg | AUC | t_youden | CI [lo, hi] | CI half-width | ships |
|---|---:|---:|---:|---:|---|---:|:-:|
| V1 | 2 | 49 | 0.9235 | +0.1209 | [+0.1090, +0.2070] | 0.0490 | ✗ |
| V2 | 23 | 49 | 0.7107 | +0.0274 | [+0.0185, +0.0789] | 0.0302 | ✗ |
| V3 | 11 | 13 | 0.9336 | +0.0529 | [+0.0529, +0.0529] | 0.0000 | ✓ |
| V4 | 17 | 27 | 0.9237 | +0.0274 | [+0.0245, +0.0596] | 0.0176 | ✓ |

## Variant scopes

- V1: heavy_dust vs clean, all AOIs.
- V2: any-non-clean vs clean, all AOIs (HEADLINE).
- V3: KSP-only any-non-clean vs clean.
- V4: KSP + Diriyah any-non-clean vs clean (Qiddiya excluded).

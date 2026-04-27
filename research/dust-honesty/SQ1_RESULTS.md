# SQ1 — Port Lolli 2024 DBB index, sample 30 scenes

**Status:** Implementation complete, threshold tuning awaiting manual labels.
**Date:** 2026-04-27
**Reference:** Lolli et al. 2024, *Atmosphere* 15(6):672 — "Characterizing
Dust and Biomass Burning Events from Sentinel-2 Imagery."

## Implementation notes

The DBB composite index is implemented in
[`scripts/dbb_index.py`](scripts/dbb_index.py) as a normalized difference
between the visible-band mean (B2/B3/B4) and the SWIR-band mean (B11/B12):

```
DBB = (mean(B2,B3,B4) - mean(B11,B12)) / (mean(B2,B3,B4) + mean(B11,B12) + 1e-6)
```

This follows the structure described in the SQ1 brief — visible bands
amplify aerosol scattering, SWIR bands look through to surface, normalized
to damp terrain. **The exact formulation in Lolli 2024 has not been
verified against the published paper** (paper not available in this
session). The implementation should be cross-checked against Lolli's
section 3 methodology before any quantitative claim is published. The
*structure* of the index — visible-vs-SWIR contrast, normalized — is
robust enough to test against manual labels in this session; calibration
of the exact constants is downstream.

Inputs are Sentinel-2 L2A surface reflectance from the existing Phase 1
corpus. The Phase 1 download pipeline (`src/phase1_download.py`) writes
FLOAT32 tifs already in [0, 1] reflectance — no /10000 scaling step is
needed. Confirmed by inspecting `data/phase1/qiddiya_core/2022-05.tif`
(min 0.0, max 1.27, mean 0.36). Bands 1–6 in each tif map to
B02 / B03 / B04 / B08 / B11 / B12.

## Sampling rationale

The Phase 1 corpus is 76 months × 3 AOIs = 228 scenes. SQ1 samples 30,
stratified across the dust calendar:

- **Peak dust season (Mar–May), n ≥ 5:** drawn first.
- **Low dust season (Dec–Feb), n ≥ 5:** drawn second.
- **Remainder (n = 20):** drawn uniformly across the rest.

Random seed `20260427` for reproducibility. After draw the sample
contains 8 peak-season and 10 low-season scenes, exceeding the quotas.
Sample list: [`data/sq1_sample.csv`](data/sq1_sample.csv) (gitignored).

## DBB value distribution

Across the 30 sampled scenes, scene-mean DBB values are:

- **mean:** −0.255
- **std:** 0.022
- **range:** −0.315 to −0.219

All values are negative because Riyadh's bright desert surface has
higher SWIR than visible reflectance year-round; what matters for dust
detection is the *relative* shift toward less-negative values when
aerosol load increases. The peak-season scenes (e.g. 2022-04 KSP at
−0.226, 2022-06 KSP at −0.219) sit at the upper edge of the
distribution; deep-winter scenes (e.g. 2020-01 Qiddiya at −0.315) sit
at the lower edge. This is the expected qualitative signal.

Histogram: [`figures/sq1_dbb_histogram.png`](figures/sq1_dbb_histogram.png).
Per-scene values: [`data/sq1_dbb_values.csv`](data/sq1_dbb_values.csv).

## Open

- **Threshold tuning awaits manual labels (Ahmed step).** The thumbnail
  grid [`figures/sq1_thumbnails.png`](figures/sq1_thumbnails.png) shows
  all 30 scenes as RGB. Ahmed fills `label` for each row in
  [`data/sq1_manual_labels.csv`](data/sq1_manual_labels.csv) with one of
  `clean | light_haze | heavy_dust | cloud | mixed`. Threshold tuning
  then happens in [`notebooks/sq1_calibration.ipynb`](notebooks/sq1_calibration.ipynb).
- **Lolli 2024 formulation verification.** Confirm the exact
  normalization in section 3 of the paper before SQ2.

## Next steps

1. Ahmed: fill `data/sq1_manual_labels.csv` from the thumbnail grid.
2. Tune threshold(s) in `sq1_calibration.ipynb` — maximize agreement
   between DBB-derived flag and manual label. Report agreement rate.
3. SQ2 onward: apply the calibrated flag to the full 228-scene corpus
   via `scripts/apply_flag.py`, then quantify NDVI-bias-conditional-on-dust.

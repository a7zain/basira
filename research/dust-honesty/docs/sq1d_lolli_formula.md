# SQ1D Part B — Faithful Lolli 2024 DBB Formula Spec

**Reference:** Lolli, Alparone, Arienzo, Garzelli (2024). *Characterizing Dust and Biomass Burning Events from Sentinel-2 Imagery.* Atmosphere 15, 672. DOI: 10.3390/atmos15060672.

**Purpose:** lock the exact formula and every implementation choice before writing the GEE port. This is the methodology footnote for SQ1D Part B output.

---

## 1. The DBB equation (Lolli 2024 Eq. 1, p. 13)

For a pixel `(i,j)`:

```
              1     ρ_k^TOA(i,j) − ρ̄_k^TOA(i,j)
DBB(i,j) = ─── ∑    ─────────────────────────────
              5  k              ρ̄_k(i,j)

                                k ∈ {2, 3, 4, 11, 12}
```

Where, **per the paper's prose immediately following Eq. 1:**

- `ρ_k^TOA(i,j)` — TOA reflectance of the **test image** in band `k`, sourced from the **L1C Sentinel-2 A/B product**.
- `ρ̄_k^TOA(i,j)` — TOA reflectance from a **reference acquisition** at the same location under clear atmospheric conditions (paper criterion: combined coarse + fine mode AOD < 0.07), also from **L1C**.
- `ρ̄_k(i,j)` — the normalizer; the band-`k` value of the **L2A (surface reflectance) product of the reference image**.

Both terms in the numerator are TOA reflectances (L1C). The denominator is surface reflectance (L2A) of the reference scene only. This matches the 2026-04-28 audit note that SQ1's `dbb_index.py` was inspired-not-faithful: it used a single visible-vs-SWIR ratio on L2A inputs, which is a different physical quantity.

## 2. Bands

Paper Eq. 1 fixes `k ∈ {2, 3, 4, 11, 12}`:
- **B2** (490 nm, blue, 10 m)
- **B3** (560 nm, green, 10 m)
- **B4** (665 nm, red, 10 m)
- **B11** (1610 nm, SWIR, 20 m)
- **B12** (2190 nm, SWIR, 20 m)

NIR and red-edge bands are deliberately excluded because of seasonal vegetation variability (§2.4.1).

The paper computes the index pixelwise at 10 m or 20 m resolution depending on whether SWIR is upsampled to 10 m or RGB is downsampled to 20 m (§2.4.2, last sentence). For our scene-mean output, the choice is numerically near-invariant.

## 3. Aggregation rule (per-scene scalar)

§2.4.2 last paragraph and §3 Table 2:

> "the proposed pixel index can be averaged across the scene, better on non-water pixels … Water pixels can be identified by thresholding the surface reflectance of B12 provided by the L2A product (ρ12 < 1%)."

Per-scene scalar = **spatial mean of `DBB(i,j)` over land pixels in the AOI**.

## 4. Required products (per side)

Per the formula prose:

| Term | Image | Product | Note |
|---|---|---|---|
| numerator: `ρ_k^TOA` (test) | test scene | **S2 L1C TOA** | Bands B2, B3, B4, B11, B12 |
| numerator: `ρ̄_k^TOA` (reference) | reference scene | **S2 L1C TOA** | Same bands |
| denominator: `ρ̄_k` (reference) | reference scene | **S2 L2A surface reflectance** | Same bands; also B12 used for water mask |

This matches the 2026-04-28 audit conclusion: "L1C TOA for one side and L2A reference reflectance for the other" — but precisely, **both numerator terms are L1C; only the denominator is L2A**, and the L2A is for the reference, not the test.

## 5. Preprocessing in the paper

What Lolli specifies explicitly:

- **Reference selection criterion:** clear-sky AERONET-confirmed AOD < 0.07 (§2.3 for each test site). Paper uses one fixed reference date per location.
- **Reflectance scaling:** L1C and L2A reflectance values in `[0, 1]` (§2.1). On Sentinel-2, the raw integer values are divided by 10 000 and (for processing baseline 04.00+, post-2022-01-25) additionally offset-corrected by −1000 before division. GEE's `COPERNICUS/S2_HARMONIZED` collection harmonizes the offset, so dividing by 10 000 yields `[0,1]` reflectance for both pre- and post-baseline scenes.
- **Resampling:** SWIR upsampled to 10 m, **or** RGB downsampled to 20 m. Bicubic resampling mentioned in §2.3 ("with the lower-resolution bands bicubically resampled at 10 m GSD").
- **Water mask:** `ρ12 (L2A surface reflectance of reference) < 0.01`.
- **Vegetation note:** paper notes B3/B4 may suffer over heavily vegetated areas; no formal vegetation mask is applied — only acknowledged as a limitation (§3, §4).

What Lolli does NOT specify:

- No formal cloud mask is described in the formula. The paper relies on operator-selected near-cloud-free dates.
- No explicit time-window rule for "test scene" beyond "one acquisition on date X".
- No no-data handling rule beyond the implicit water-pixel exclusion.

## 6. Choices we must make (named, with rationale)

These are gaps in the paper that affect implementation. Documented here so the methodology is auditable.

### Choice 1 — Test scene selection per (calendar-month, sub_aoi)

The paper uses one fixed test date. Our calibration set indexes scenes by `YYYY-MM` (monthly composite slot from Phase 1). We need to map each `(YYYY-MM, sub_aoi)` pair to one specific S2 scene.

**Rule:** for each `(YYYY-MM, sub_aoi)`, query `COPERNICUS/S2_HARMONIZED` filtered to that calendar month and the AOI bbox; pick the scene with the **lowest `CLOUDY_PIXEL_PERCENTAGE`** over the AOI (system property). Tie-break by earlier date. Record the chosen `system:index` in the output.

Rationale: matches Phase 1's monthly-slot semantics; the lowest-cloud rule mirrors how the test-scene thumbnails were rendered for the visually-blind relabel and what those visual labels actually describe.

### Choice 2 — Reference scenes

Use the **PRIMARY** references from `sq1d_references.json` (Phase B' will repeat with sensitivity alternates next session):

| AOI | Primary ref date |
|---|---|
| qiddiya_core | 2024-01-20 |
| king_salman_park | 2023-10-27 |
| diriyah_gate | 2020-04-25 |

For the reference, select the S2 scene **on that exact date**, lowest cloud cover if multiple tiles overlap.

Rationale: the references are already date-locked in `sq1d_references.json` per the 2026-04-28/29 selection rule (cleanest UVAI from a date with surface-state representative of test scenes). The "AOD < 0.07" original criterion is replaced by our UVAI-based selection rule because no AERONET ground truth exists at any of the three Riyadh AOIs — this substitution is documented in CLAUDE.md and the SQ8 plan.

### Choice 3 — Resolution

Compute everything at **20 m**. SWIR (B11, B12) is native 20 m; RGB (B2, B3, B4) is reprojected from 10 m to 20 m by GEE's default mean reduction in `reduceResolution` (or by sampling at 20 m). Scene-mean output is near-invariant to the choice.

Rationale: avoids upsampling SWIR (introducing synthetic detail) and is the simpler, faster default.

### Choice 4 — Cloud + invalid-pixel mask

For both test and reference scenes, build a "valid pixel" mask from the L2A SCL (Scene Classification Layer) band: a pixel is **valid** iff SCL ∈ {4 (vegetation), 5 (not-vegetated), 6 (water), 7 (unclassified), 11 (snow)}. SCL classes excluded: 0 (no_data), 1 (saturated/defective), 2 (dark_area), 3 (cloud_shadow), 8 (cloud_med_prob), 9 (cloud_high_prob), 10 (thin_cirrus).

Spatial-mean DBB is computed over the **AND** of `valid_test ∩ valid_ref ∩ not_water` masks, where `not_water` = `(ρ̄_12 ≥ 0.01)`.

Rationale: paper selects clear scenes manually; on a 30-scene calibration set we need a programmatic equivalent. SCL-based masking is the GEE-standard approach for Sentinel-2 and lets contaminated pixels (clouds, shadows, defective) be excluded without discarding the entire scene.

### Choice 5 — L1C and L2A pairing

For each (test or reference) date+tile, fetch the matching **L1C** scene (`COPERNICUS/S2_HARMONIZED`) and its corresponding **L2A** scene (`COPERNICUS/S2_SR_HARMONIZED`) by matching `system:index` prefix (granule ID). If a date has L1C but not L2A available in GEE, log it and skip — the formula needs both for the reference (L1C in numerator, L2A in denominator). For the test scene only L1C is required, but L2A is needed for the test SCL mask.

Rationale: GEE's `S2_HARMONIZED` (L1C) and `S2_SR_HARMONIZED` (L2A) have aligned granule IDs after Mar 2017 over our AOIs; mismatch is rare but possible for early scenes. Skip-and-log avoids silent data loss.

### Choice 6 — Reflectance scale

Divide all S2 reflectance bands by **10 000** to get `[0, 1]` reflectance. Both `S2_HARMONIZED` and `S2_SR_HARMONIZED` already harmonize the post-2022 +1000 DN offset, so division by 10 000 alone is correct.

### Choice 7 — Numerical no-data on denominator

If the L2A reference reflectance for any pixel is `≤ 0` in any of the 5 bands (no-data, sensor saturation), exclude that pixel from the spatial mean. Avoids divide-by-zero / divide-by-tiny.

## 7. Expected sign convention (sanity-check anchor)

From paper §2.4.2 last paragraph:

- **Dust** (Saharan-style) increases TOA reflectance in B2-B4 and B11-B12 → **DBB > 0**.
- **Biomass burning aerosol (BBA)** decreases TOA reflectance in those bands → **DBB < 0**.
- **Clear** ≈ DBB ≈ 0.

For our Riyadh AOIs (bright desert substrate, no biomass burning regime, dust-dominated atmosphere), the expectation is `DBB(heavy_dust) > DBB(light_haze) > DBB(clean)`, with clean scenes near zero (relative to the locked reference). Bright-desert reflectance behaviour vs. Lolli's Mediterranean-urban substrate is exactly what SQ1B/SQ8 are meant to test — this is why we recalibrate on AP rather than borrowing thresholds from the paper.

## 8. What this spec does NOT cover

- The threshold tuning that turns scene-mean DBB into a clean/light_haze/heavy_dust flag — that is SQ1B (re-run after Part B).
- Sensitivity analysis using alternate references — Part B' (next session).
- AERONET validation at KAUST — SQ8 (deferred until SQ1B re-run, SQ2–SQ7 ship).

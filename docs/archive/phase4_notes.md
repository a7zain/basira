# Phase 4 — Technical Notes

Reference document for Phase 4 (monthly temporal resolution). All numbers
are from actual outputs in the repo, not estimates.

---

## 1. Catalog Dry-Run

Script: `src/phase4_catalog.py`

- **Total scenes:** 950 Sentinel-2 L2A over Riyadh AOI (24.55–24.85°N, 46.55–46.95°E)
- **Period queried:** 2020-01-01 to 2026-04-07
- **Months covered:** 76 (Jan 2020 – Apr 2026)
- **Cloud cover distribution:**
  - <10%: 700 (74%)
  - 10–30%: 95 (10%)
  - 30–60%: 59 (6%)
  - >60%: 96 (10%)
- **Months with zero usable scenes (<30%):** None. Every month has clear imagery.
- **Best scene per month:** 0.0% cloud in 74 of 76 months. Exceptions:
  Dec 2021 (0.1%), Apr 2026 (14.7%).

Outputs: `outputs/phase4_catalog.csv`, `outputs/phase4_catalog_summary.txt`

---

## 2. Download Pipeline

Script: `src/phase4_download.py`

- **Scenes downloaded:** 76 (one per month, lowest cloud cover)
- **Bands:** B02 (blue), B03 (green), B04 (red), B08 (NIR)
- **Resolution:** 20 m
- **CRS:** EPSG:32638 (UTM Zone 38N)
- **Image size:** 2002 × 1687 pixels
- **Format:** GeoTIFF, float32, DEFLATE compression
- **PU per request:** 17.18
- **Total PU consumed:** 1,305.5 (4.4% of 30,000/month free tier)
- **PU safety ceiling in script:** 5,000
- **Output:** `data/processed/monthly/YYYY_MM.tif`

Manifest: `outputs/phase4_download_manifest.csv` (77 lines incl. header)

---

## 3. Partial-Coverage Scenes

10 of 76 scenes have a diagonal nodata strip from Sentinel-2 swath geometry.
These come from relative orbit R006; full-coverage scenes come from R049.
Identifiable by file size (18–22 MB vs. 40–43 MB for full scenes).

| Month   | File size |
|---------|-----------|
| 2020_04 | 18.2 MB   |
| 2020_06 | 19.0 MB   |
| 2020_07 | 18.5 MB   |
| 2021_03 | 19.6 MB   |
| 2021_09 | 18.4 MB   |
| 2021_12 | 19.4 MB   |
| 2022_07 | 21.6 MB   |
| 2023_11 | 20.1 MB   |
| 2024_01 | 19.3 MB   |
| 2026_04 | 19.3 MB   |

---

## 4. Common Valid Mask

Script: `src/phase4_valid_mask.py`

**Method:** Per-pixel temporal-coverage threshold. For each pixel, count
how many of the 76 scenes have valid data (all 4 bands nonzero). A pixel
is marked valid if count >= 80% × 76 = 61 scenes.

**Why not strict AND?** The strict AND (valid in ALL scenes) yielded only
42.9% valid — the 10 partial-coverage scenes collectively wiped out the
western half of the AOI.

**Actual results:**
- Valid pixels: 3,351,258 / 3,377,374 (99.2%)
- Valid area: 1,340.5 km²

Outputs: `outputs/phase4_valid_mask.tif`, `outputs/phase4_pixel_coverage.tif`,
corresponding PNGs.

---

## 5. Regions of Interest

Script: `src/phase4_rois.py`

| ROI | Lat range | Lon range | Rationale |
|-----|-----------|-----------|-----------|
| wadi_hanifa | 24.62–24.78°N | 46.58–46.65°E | NW-SE wadi corridor, known greening/rehabilitation area |
| king_salman_park | 24.80–24.85°N | 46.55–46.62°E | Royal Arts Complex / King Salman Park construction zone |
| northern_expansion | 24.80–24.85°N | 46.65–46.75°E | New suburban grading north of central Riyadh |
| central_urban | 24.66–24.71°N | 46.68–46.74°E | Established dense urban core (control baseline) |

Outputs: `outputs/phase4_rois.geojson`, `outputs/phase4_rois_pixel.json`,
`outputs/phase4_rois_overlay.png`

---

## 6. NDVI Time Series

Script: `src/phase4_ndvi_timeseries.py`

**Per-ROI NDVI statistics (from CSV, 305 rows):**

| ROI | Valid months | Dropped | Mean NDVI | Min | Max |
|-----|-------------|---------|-----------|-----|-----|
| wadi_hanifa | 66 | 10 | 0.0939 | 0.0760 | 0.1108 |
| king_salman_park | 66 | 10 | 0.0641 | 0.0455 | 0.0793 |
| northern_expansion | 66 | 10 | 0.0701 | 0.0537 | 0.0826 |
| central_urban | 67 | 9 | 0.0780 | 0.0598 | 0.2035 |

Dropped months are those where valid pixel count < 500 (MIN_VALID_PIXELS
threshold), which aligns with the 10 partial-coverage scenes.

**Deseasonalization:** Per-calendar-month climatology computed (mean NDVI for
each Jan, Feb, ..., Dec across all years), then anomaly = value − climatology.

**Trend slopes (NDVI units per year):**

| ROI | Raw slope | Deseasonalized slope | Interpretation |
|-----|-----------|---------------------|----------------|
| wadi_hanifa | −0.00121 | −0.00104 | STABLE |
| king_salman_park | −0.00107 | −0.00094 | STABLE |
| northern_expansion | −0.00102 | −0.00090 | STABLE |
| central_urban | −0.00219 | −0.00222 | BROWNING |

All trends are weakly negative. Central urban is the steepest, likely
influenced by the 2022_07 anomaly (see below).

Outputs: `outputs/phase4_ndvi_timeseries.csv`, `outputs/phase4_ndvi_timeseries.png`,
`outputs/phase4_ndvi_anomaly.png`

---

## 7. Greening Map

Script: `src/phase4_green_map.py`

**Method:** Per-pixel vegetation persistence — fraction of months where
NDVI > 0.20. Computed separately for 2020 (12 scenes) and 2025 (12 scenes).

**Classification thresholds:**
- `stable_green` (class 1): persistence > 0.6 in both years
- `new_green` (class 2): persistence < 0.2 in 2020 AND > 0.6 in 2025
- `lost_green` (class 3): persistence > 0.6 in 2020 AND < 0.2 in 2025

**AOI-wide results:**

| Class | Pixels | Area (km²) |
|-------|--------|-----------|
| Stable green | 86,469 | 34.59 |
| New green | 23,643 | 9.46 |
| Lost green | 23,180 | 9.27 |
| **New/Lost ratio** | | **1.02** |

**Per-ROI results:**

| ROI | Stable (km²) | New (km²) | Lost (km²) | New/Lost |
|-----|-------------|-----------|------------|----------|
| wadi_hanifa | 8.519 | 1.600 | 1.977 | 0.81 |
| king_salman_park | 0.280 | 0.222 | 0.058 | 3.82 |
| northern_expansion | 1.589 | 0.602 | 0.279 | 2.15 |
| central_urban | 1.586 | 0.184 | 0.486 | 0.38 |

King Salman Park shows the strongest new/lost ratio (3.82), consistent with
active construction and landscaping. Northern expansion also net positive (2.15).
Wadi Hanifa and central urban are net negative, though the absolute areas are
small.

Output: `outputs/phase4_green_map.tif`, `outputs/phase4_green_map.png`

---

## 8. Known Issues

**2022_07 Central Urban NDVI spike.** Status: **investigated, not yet resolved.**

The 2022-07 scene is a partial-coverage scene (21.6 MB). Central Urban has
947 valid pixels for this month (above the 500 MIN_VALID_PIXELS threshold),
so it is NOT filtered. The mean NDVI is 0.2035 vs. the ROI's overall mean of
0.0780, with a deseasonalized anomaly of +0.1064.

The anomaly check script (`src/phase4_anomaly_check.py`) flagged this and
saved a cropped quicklook at `outputs/phase4_anomalies/central_urban_2022_07.png`.
Possible causes: biased pixel sample from partial coverage, radiometric
artifact, or genuine but unrepresentative vegetation patch. Options for next
session: lower the pixel threshold, apply per-scene outlier rejection, or
manually exclude this month.

**Decision (2026-04-08 followup):** Parked until Phase 4.5. This spike only
affects the Central Urban ROI time-series mean and linear trend; it does NOT
affect the pixel-level greening map headline numbers (which compare 2020 vs
2025 persistence, not individual monthly means). The correct fix when we
revisit is a relative-coverage threshold — drop a ROI-month if its
valid_pixel_count < 0.5 × median valid_pixel_count for that ROI — rather
than raising the absolute 500-pixel minimum, which would be fragile across
ROIs of different sizes.

---

## 9. Web-Ready Exports

Script: `src/phase4_export_web.py`

Files staged in `webapp/data/phase4/`:

| File | Size | Description |
|------|------|-------------|
| green_map.png | 213 KB | Transparent RGBA overlay, WGS84 |
| green_map_bounds.json | 111 B | Bounding box for L.imageOverlay |
| latest_rgb.png | 8.2 MB | Most recent full-coverage RGB, WGS84 |
| latest_rgb_bounds.json | 111 B | Bounding box |
| ndvi_timeseries.json | 17.8 KB | Per-ROI time series, NaN skipped |
| rois.geojson | 2.7 KB | ROI polygons (WGS84) |

Wired into the web app as of Phase 4.5a (commit `d9f83d3`).

### Phase 4.5a Integration (April 13, 2026)

Three overlays added to `webapp/index.html`:

1. **Greening map** (`green_map.png`) — `L.imageOverlay` on custom pane
   `greenPane` (z-index 450). Toggleable via layer control.
2. **ROI polygons** (`rois.geojson`) — `L.geoJSON` on custom pane `roiPane`
   (z-index 460). Styled outlines with click popups showing ROI name and stats.
3. **Sentinel-2 latest RGB** (`latest_rgb.png`) — `L.imageOverlay` on custom
   pane `rgbPane` (z-index 440). Toggleable basemap context layer.

Custom panes ensure correct z-ordering (RGB < greening < ROIs < popups).
A legend control (bottom-right) shows color keys for stable/new/lost green
and ROI outlines.

---

## 11. Phase 4.5c — Cell Breakdowns + Visible Grid

### Desert Mask Applied to Stats (not just overlay)

Prior to Phase 4.5c, `src/prepare_webapp_data.py` applied the desert mask only
to the change overlay PNG — suppressing false-positive change pixels in the
visual output. But `grid_index.json` stats were computed from the **raw**
classification without the mask, producing inflated `change_pct` values.

**Fix:** For each grid cell, pixels flagged as desert AND classified as changed
are suppressed (treated as stable) for the masked stats. The denominator stays
constant (all valid pixels). This is a numerator-only correction.

**AOI-wide result:**
- `change_pct` (unmasked): **42.6%**
- `change_pct_masked` (desert-masked): **17.8%**
- Drop: **-24.8 percentage points**

The inflated raw number was the primary cause of tester feedback that "the
percentage of change seems overcalculated."

### New grid_index.json Schema

Each of the 56 cells (7 rows x 8 cols, no cells skipped) now includes:

```json
{
  "id": "3_4",
  "row": 3, "col": 4,
  "lat": 24.712, "lng": 46.734,
  "valid_pixels": 65536,
  "change_breakdown": {
    "new_construction": 12.3,
    "land_clearing": 28.7,
    "vegetation_change": 5.1,
    "stable": 53.9
  },
  "vegetation_breakdown": {
    "stable_green": 3.2,
    "new_green": 1.1,
    "lost_green": 0.8,
    "other": 94.9
  },
  "class": 3,
  "label": "Land clearing",
  "change_pct": 46.1,
  "change_pct_masked": 21.3
}
```

- `change_breakdown`: from `outputs/optical_change_2020_2026.tif` (classes 0-3)
- `vegetation_breakdown`: from `outputs/phase4_green_map.tif` (classes 0-3),
  indexed by direct row/col (same 1687x2002 shape, no reprojection needed)
- All percentages are of valid pixels (nodata=255 excluded)
- Legacy fields (`class`, `label`, `change_pct`) retained for backward compatibility

### Grid Layer Architecture

Leaflet pane z-ordering (updated for Phase 4.5c):

```
optical (default)  <  greenPane (440)  <  roiPane (445)  <  gridPane (446)  <  changePane (450)
```

- **gridPane (z-index 446):** Contains 56 `L.rectangle` instances in an
  `L.layerGroup`. Sits above ROI polygons so grid clicks take priority.
- **Fill opacity ramp:** `change_pct_masked` 0%->0 opacity, 5%->0.10,
  linear to 50%+->0.30 (capped). Color: `#ff8800` (orange).
- **Stroke:** weight 1, `#ff8800`, opacity 0.4. Hover: weight 2, opacity 0.8.
- **Toggle:** Grid layer is added/removed by the "Show Changes" button
  alongside the existing change overlay PNG.

Click on a rectangle fires `buildCellPopup(cell)`, which generates the
breakdown popup HTML. `L.DomEvent.stopPropagation` prevents the click from
reaching the ROI layer below.

### ROI Cross-Reference

Each cell popup checks if the cell centroid falls inside any ROI polygon using
a ray-casting point-in-polygon algorithm (library-free, implemented in JS).
If so, the popup footer shows "Part of ROI: {name}".

Handles both Polygon and MultiPolygon GeoJSON geometries.

### Known Label Limitation

The K-means "Land clearing" class (from `outputs/optical_change_2020_2026.tif`)
is assigned heuristically based on spectral change direction. It conflates:
- Genuine demolition / land clearing
- Seasonal vegetation loss
- Illumination / shadow differences between acquisition dates
- Construction-site staging and grading

This is why the desert mask was necessary (sandy areas classified as "land
clearing" due to speckle). Real change-type attribution would require:
- Monthly time-series classification (track change trajectory, not just
  start vs. end)
- Higher spatial resolution (10m or better)
- Multi-source validation (SAR + optical fusion)

Planned for Phase 5+. For now, the label should be changed to "Surface change
/ clearing" to avoid implying certainty about the change mechanism.

---

## 13. Phase 4.6 — Before/After Slider (commit c6118b1)

Added `leaflet-side-by-side@2.2.0` to `webapp/dashboard.html`. Left pane shows
the 2020 Sentinel-2 RGB, right pane shows 2026. Both rendered as `L.imageOverlay`
on custom panes (`sbsLeftPane` z-401, `sbsRightPane` z-402) so the slider divider
renders correctly above the basemap. A dedicated "Before/After" toggle button
shows/hides the comparison; the toggle disables the normal basemap and swaps in
the two timed overlays.

---

## 14. Phase 4.7 — Pixel-Level Time-Series Classification (commit deb983c)

Script: `src/phase4_pixel_classify.py` + `src/phase4_export_pixel_classes.py`

K-Means (k=5) on 5 per-pixel temporal features extracted from the 76-month NDVI
cube: mean, linear slope, seasonal amplitude (annual std), first-half mean
(months 1–38), second-half mean (months 39–76). Processing chunked at 200 rows
to avoid loading the full ~970 MB float32 cube. Runtime ~156 s. Output:
`outputs/phase4_pixel_classes.tif` (uint8, 0=nodata, 1–5=clusters).

Cluster interpretation: 63% stable desert, 18% sparse/suburban green, 15%
stable built-up, 2.7% established vegetation, 0.9% vegetation loss. Desert
cluster (class 2) exported as fully transparent in the PNG overlay. Wired into
`webapp/dashboard.html` as a toggleable layer on `pixelClassPane` (z-442).

---

## 15. Phase 4.8 — NDVI Anomaly Detection (commit 1254155)

Script: `src/phase4_compute_anomalies.py`

Monthly climatology computed per calendar month (Jan–Dec) across all years.
Anomaly = value − climatology; z-score = anomaly / std. Months with |z| > 2
flagged as anomalies. Results augmented into `webapp/data/phase4/ndvi_timeseries.json`
(`anomaly_zscore`, `is_anomaly`, `anomaly_direction` fields added).

Results: 9 anomalies total (wadi_hanifa 3, king_salman_park 3, northern_expansion 1,
central_urban 2). April 2022 appears as a co-occurring negative anomaly in 3 of 4
ROIs — independent signal of a regional event. Web app shows anomaly months as
red/blue dots on ROI time-series charts.

---

## 16. Phase 4.9 — Active Hotspots (commit 8683ceb)

Script: `src/phase4_compute_hotspots.py`

Composite hotspot score per cell: 50% veg_loss_score + 40% change_score + 10%
anomaly_overlap. Top 10 cells ranked. Point-in-polygon check (ray-casting) flags
ROI overlap. Also outputs `cell_veg_loss.json` (all 56 cells). Web app gains a
collapsible hotspot panel (bottom-left) with ranked rows; clicking a row flies to
the cell and opens its popup. Hotspot cell borders rendered on `hotspotPane` (z-444).

---

## 17. Phase 4.10 — Confidence Layer + Hotspot Drill-In (commit 9f222dc)

Script: `src/phase4_export_coverage.py`

Maps per-pixel scene-count raster (`outputs/phase4_pixel_coverage.tif`) to a grey
haze RGBA overlay. Thresholds: ≥60 transparent, 50–59 light, 40–49 medium, 30–39
heavy, <30 near-opaque. Only 0.7% of AOI falls below the 60-scene threshold
(bimodal distribution: most pixels at 66–67 or 76). Output: `coverage_mask.png` (51 KB).

Hotspot drill-in button added to each cell popup: clicking "Show pixel evolution"
loads the pixel-class thumbnail for that cell and computes a veg-loss stat inline.
`pixelClassLayer` hoisted from `const` inside `init()` to module-level `let` to
allow access from the popup event handler.

---

## 18. Phase 4.11 — Hotspot Time Attribution (commit 2187fb8)

Script: `src/phase4_cell_timeseries.py` (hotspot mode)

For each of the top-10 hotspot cells: windowed rasterio read of the 76-month
NDVI cube, masked to valid pixels, mean per month. Onset detection: baseline from
first 18 months, threshold = baseline − 1σ, sustained ≥2 consecutive months.
`est_onset`, `delta_ndvi`, `baseline_ndvi` fields appended to `hotspots.json`.
6 of 10 hotspots show April 2022 onset — consistent with the ROI anomaly signal.
Runtime ~27 s for 10 cells using windowed reads.

---

## 19. Phase 4.12 — Per-Cell NDVI Time Series Chart (commit a602cbe)

Script: `src/phase4_cell_timeseries.py --all` (56-cell mode)

Extended the hotspot-mode script to process all 56 grid cells. Output:
`webapp/data/phase4/cell_timeseries.json` (270 KB, 56 cells × ~76 months each).
Each cell popup now renders a Chart.js time-series chart (date-fns adapter) when
opened. An `activeCellChart` module-level variable tracks the Chart.js instance
and destroys it on `popupclose` to prevent canvas reuse errors. Onset annotation
drawn as a vertical dashed line where `est_onset` is available.

---

## 20. Phase 4.13 — Landing Page (commit 0e90c16)

`webapp/index.html` (old dashboard) renamed to `webapp/dashboard.html` via
`git mv` to preserve history. New `webapp/index.html` is a pure HTML+CSS
dark-theme landing page: hero section with Sentinel-2 background at 0.15 opacity,
Arabic "بصيرة" label, "Basira" gradient wordmark, three capability cards
(classification, hotspots, onset), CTA button to `dashboard.html`. No JavaScript.

---

## 21. Phase 4.14 — Auto-Generated PDF Report (commit b8a9442)

Script: `src/generate_report_pdf.py`

Two-part output. Part A: matplotlib hero map — `latest_rgb.png` basemap with
correct geographic extent, red cell rectangles for top-10 hotspots (numbered
labels for top 5), dashed yellow/orange ROI outlines, dark theme. Saved at 300
DPI to `outputs/report_hero_map.png`. Part B: reportlab one-page A4 PDF —
header, hero map image, 4-column stat bar (10 hotspots / 9 anomalies / 3.35M
pixels / 76 months), top-5 hotspot table (score highlighted in red), April 2022
event callout box, methodology paragraph, footer. Runtime 3.6 s; PDF ~14 MB
(embedded 300-DPI image). Both outputs gitignored as regenerable artifacts.

---

## 12. Phase 5 Considerations

- **Disk savings:** uint16 with scale factor 10000 instead of float32 → ~50% reduction
- **Cloud masking:** Riyadh is trivial (desert). Jeddah/Mecca have real clouds — need SCL-based masking or multi-scene compositing
- **PU budget:** ~1,306 PU/city × 5 cities = ~6,530 PU/month (22% of free tier)
- **Pipeline:** Parameterize AOI via config file rather than hardcoded RIYADH_BBOX

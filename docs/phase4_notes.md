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

## 12. Phase 5 Considerations

- **Disk savings:** uint16 with scale factor 10000 instead of float32 → ~50% reduction
- **Cloud masking:** Riyadh is trivial (desert). Jeddah/Mecca have real clouds — need SCL-based masking or multi-scene compositing
- **PU budget:** ~1,306 PU/city × 5 cities = ~6,530 PU/month (22% of free tier)
- **Pipeline:** Parameterize AOI via config file rather than hardcoded RIYADH_BBOX

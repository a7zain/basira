# Basira Cleanup Audit — 2026-04-20

Read-only inventory. No files have been moved, deleted, or modified. All tags
below are *candidates* for Ahmed to review before Pass 2.

---

## 1. Repository overview

- **Files tracked by git:** 215
- **On-disk size (includes untracked/ignored):** ~11 GB
  - `data/raw/` 6.3 GB (Sentinel-1 raw — gitignored)
  - `data/processed/` 3.9 GB (gitignored)
  - `data/optical/` 29 MB (gitignored)
  - `outputs/` 215 MB
- **Tracked files by extension:** 112 jpg, 35 png, 29 py, 14 json, 7 md, 4 html,
  4 csv, 2 yml, 2 txt, 2 geojson, 1 pdf, 1 ipynb, 1 .gitignore, 1 .env.example

### Largest 10 tracked files
| Size (KB) | File |
|---|---|
| 30,256 | outputs/10_optical_timeline.png |
| 9,604  | outputs/optical_2026.png |
| 9,480  | outputs/optical_2023.png |
| 9,348  | outputs/phase4_green_map.png |
| 9,112  | outputs/optical_2020.png |
| 8,712  | webapp/data/optical_2026.png |
| 8,660  | webapp/data/optical_2023.png |
| 8,504  | webapp/data/optical_2020.png |
| 8,360  | webapp/data/phase4/latest_rgb.png |
| 7,692  | outputs/phase4_rois_overlay.png |

**Files >5 MB tracked in git:** 11 files (all listed above plus
`outputs/phase4_quicklook_grid.png` at 5.8 MB). None exceed 10 MB except
`outputs/10_optical_timeline.png` at ~30 MB — flag for review.

---

## 2. Source code — `src/` (33 Python files, + root notebooks)

| File | Last commit | Purpose | Tag |
|---|---|---|---|
| src/change_detect.py | 2026-04-04 | SAR log-ratio change detection (v1) | UNCERTAIN — likely superseded by `_v2` |
| src/change_detect_v2.py | 2026-04-04 | SAR log-ratio change map (v2) | ACTIVE — referenced by README pipeline |
| src/city_config.py | untracked | Phase 5 city-config loader | ACTIVE (new, not yet committed) |
| src/classify.py | 2026-04-04 | K-means ML classification on SAR stack | UNCERTAIN — Phase 2/3 SAR flow |
| src/download_optical.py | 2026-04-07 | Sentinel-2 3-timepoint downloader | UNCERTAIN — superseded by `phase4_download.py`? |
| src/generate_pdf.py | 2026-04-04 | One-page technical summary PDF (v1) | ORPHAN candidate — superseded by `generate_report_pdf.py` |
| src/generate_report_pdf.py | 2026-04-16 | Phase 4.14 Basira analytical report PDF | ACTIVE |
| src/map_interactive.py | 2026-04-04 | Folium interactive map (early) | UNCERTAIN — Leaflet webapp is current UI |
| src/optical_change.py | 2026-04-04 | Multi-temporal optical change detection | UNCERTAIN — Phase 3 flow |
| src/phase4_anomaly_check.py | 2026-04-08 | Anomaly diagnostic helper | UNCERTAIN — one-off diagnostic? |
| src/phase4_catalog.py | 2026-04-07 | Sentinel Hub Catalog dry-run | ACTIVE |
| src/phase4_cell_timeseries.py | 2026-04-16 | Phase 4.11/4.12 cell NDVI + onset | ACTIVE |
| src/phase4_compute_anomalies.py | 2026-04-15 | Phase 4.8 NDVI anomalies | ACTIVE |
| src/phase4_compute_hotspots.py | 2026-04-16 | Phase 4.9 hotspot scoring | ACTIVE |
| src/phase4_download.py | 2026-04-07 | Monthly S2 downloader | ACTIVE |
| src/phase4_export_coverage.py | 2026-04-16 | Phase 4.10 coverage PNG export | ACTIVE |
| src/phase4_export_pixel_classes.py | 2026-04-15 | Phase 4.7 pixel-class PNG export | ACTIVE |
| src/phase4_export_web.py | 2026-04-08 | Generic web-ready export | ACTIVE |
| src/phase4_green_map.py | 2026-04-08 | Pixel greening map (2020 vs 2025) | ACTIVE |
| src/phase4_ndvi.py | 2026-04-08 | NDVI raster computation | ACTIVE |
| src/phase4_ndvi_timeseries.py | 2026-04-08 | Per-ROI NDVI time series | ACTIVE |
| src/phase4_pixel_classify.py | 2026-04-15 | Phase 4.7 pixel time-series K-means | ACTIVE |
| src/phase4_quicklook.py | 2026-04-08 | Year×month thumbnail grid | ACTIVE |
| src/phase4_rois.py | 2026-04-08 | ROI polygon definitions | ACTIVE |
| src/phase4_valid_mask.py | 2026-04-08 | Common valid mask (80% coverage) | ACTIVE |
| src/phase5_download_annual.py | untracked | Phase 5 annual S2 download (city-agnostic) | ACTIVE (new) |
| src/phase5_green_map_annual.py | untracked | Phase 5 annual green map | ACTIVE (new) |
| src/phase5_ndvi_annual.py | untracked | Phase 5 annual NDVI | ACTIVE (new) |
| src/prepare_webapp_data.py | 2026-04-13 | GeoTIFF → web PNG converter | UNCERTAIN — may be replaced by phase4_export_* |
| src/preprocess.py | 2026-04-04 | SAR preprocessing (v1) | UNCERTAIN — likely superseded by `_v2` |
| src/preprocess_v2.py | 2026-04-04 | SAR preprocessing (v2) | UNCERTAIN — used by SAR pipeline per README |
| src/utils.py | 2026-04-04 | Shared constants, speckle filter, AOI | ACTIVE |
| src/validate.py | 2026-04-04 | Validation site finder | UNCERTAIN — Phase 2 artifact |

**Root-level files:**
- `01_preprocessing.ipynb` (617 b) + `.ipynb_checkpoints/01_preprocessing-checkpoint.ipynb` — ORPHAN candidate; nearly empty notebook, checkpoints dir should be gitignored (already is).
- `project_dashboard.html` (26 KB, 2026-04-13) — UNCERTAIN; not in `webapp/` tree, unclear if linked anywhere.
- `index.html` (root, 204 b) — just a redirect to `webapp/`. ACTIVE.

---

## 3. Webapp — `webapp/`

Grep of `index.html` + `dashboard.html` for data-file references:

**Referenced (keep):**
- `data/bounds.json`, `data/change_overlay.png`, `data/cities.json`,
  `data/grid_index.json`, `data/optical_2020.png`, `data/optical_2026.png`,
  `data/thumbs/{2020,2026}_*.jpg`
- `data/phase4/riyadh/latest_rgb.png` (landing page hero)
- `data/phase4/${CITY}/`: `ndvi_timeseries.json`, `green_map.png`,
  `green_map_bounds.json`, `rois.geojson`, `latest_rgb.png`,
  `latest_rgb_bounds.json`, `pixel_classes.png`, `pixel_classes_bounds.json`,
  `coverage_mask.png`, `coverage_mask_bounds.json`, `cell_veg_loss.json`,
  `cell_timeseries.json`, `hotspots.json`

**Orphan candidates (not referenced by HTML — needs Ahmed review, may be loaded dynamically or generated for backup):**
- `webapp/data/phase4/ndvi_timeseries_pre_anomaly.json` — backup file, source code confirms it's only written by `phase4_compute_anomalies.py`
- `webapp/data/phase4/hotspot_cell_timeseries.json` — written by `phase4_cell_timeseries.py`, not fetched by dashboard
- `webapp/data/phase4/` also contains top-level copies of files that now live under `phase4/riyadh/` (e.g. `green_map.png`, `rois.geojson`, `cell_timeseries.json`, etc.). These appear to predate the per-city split introduced in the Phase 5 refactor. UNCERTAIN — may be kept for backward-compat; needs Ahmed review.
- `webapp/data/optical_2023.png` — tracked but not referenced in either HTML (2020 + 2026 are used).

**Regenerable-looking large files:**
- `webapp/data/optical_{2020,2023,2026}.png` (8.5 MB each) and
  `webapp/data/phase4/latest_rgb.png` (8.4 MB) — generated from Sentinel-2 by
  export scripts.

**Jeddah subdir** (`webapp/data/phase4/jeddah/`): untracked so far; populated by
the new Phase 5 scripts.

---

## 4. Documentation — root + `docs/`

| File | Size | Last commit | Tag |
|---|---|---|---|
| README.md | 9.2 KB | 2026-04-04 | **NEEDS REWRITE** — titled "SAR Change Detection — Riyadh Urban Development (2022–2024)"; still frames the project as SAR/Phase 1–3, no mention of Basira, Phase 4+, web app, Vision 2030 megaprojects, or the TPM/SARsatX direction |
| CLAUDE.md | 4.6 KB | 2026-04-16 | CURRENT |
| basira_master_plan.md | 7.1 KB | 2026-04-13 | CURRENT (but predates the TPM/megaprojects pivot — may need a light update) |
| docs/phase4_notes.md | 18 KB | 2026-04-16 | CURRENT — running phase-4 log |
| docs/sessions/2026-04-08.md | 8.9 KB | 2026-04-08 | HISTORICAL |
| docs/sessions/2026-04-13.md | 9.2 KB | 2026-04-13 | HISTORICAL |
| docs/sessions/2026-04-16.md | 2.4 KB | 2026-04-16 | HISTORICAL |

---

## 5. Data and outputs

**`data/` (gitignored subtrees):**
- `data/raw/` 6.3 GB — source Sentinel-1 scenes, not regenerable without redownload
- `data/processed/` 3.9 GB — intermediate rasters, regenerable from `data/raw/`
- `data/optical/` 29 MB — Sentinel-2 cache, regenerable via API

**`outputs/` (215 MB total, mostly tracked):**

Tracked files >1 MB in `outputs/` (all PNG, regenerable from pipeline):
- 10_optical_timeline.png 30 MB ⚠️ >10 MB threshold
- optical_{2020,2023,2026}.png ~9 MB each
- phase4_green_map.png 9 MB
- phase4_rois_overlay.png 7.7 MB
- phase4_quicklook_grid.png 5.8 MB
- phase4_first_vs_last.png 4.6 MB
- 03_change_detection.png 3.8 MB
- 02_riyadh_crop.png 2.8 MB
- 01_full_overview.png 2.7 MB

**Regenerable vs source:** all tracked PNGs under `outputs/` are produced by
scripts in `src/` (quicklooks, map exports, timeline renders). The only
non-regenerable source data (raw S-1/S-2 imagery) lives under `data/` and is
already gitignored.

**Untracked but present on disk:**
- `outputs/*.tif` (6 files: change_continuous, change_map, ml_classification,
  optical_change_2020_2026, phase4_green_map, phase4_pixel_classes,
  phase4_pixel_coverage, phase4_valid_mask) — gitignored via `outputs/*.tif`
- `outputs/riyadh_change_map.html` — gitignored via `outputs/*.html`
- `outputs/basira_report.pdf` — gitignored explicitly
- `outputs/report_hero_map.png` — gitignored explicitly
- `outputs/phase4_anomalies/` (28 KB) — small diagnostic PNG

**Tracked PDFs:** `outputs/technical_summary.pdf` (only tracked PDF). The newer
`outputs/basira_report.pdf` is correctly gitignored. UNCERTAIN whether
`technical_summary.pdf` is still linked from anywhere — needs Ahmed review.

---

## 6. .gitignore review

Current `.gitignore` entries (deduped):
```
__pycache__/  .claude/  .DS_Store  .eggs/  .env  .env.save  .env*
.idea/  .ipynb_checkpoints/  .virtual_documents/  .vscode/
*.egg  *.egg-info/  *.log  *.pyc  *.pyo  *.swo  *.swp
data/optical/  data/processed/  data/raw/
outputs/*.html  outputs/*.tif
outputs/basira_report.pdf  outputs/report_hero_map.png
Thumbs.db
```

**Checks against tracked files** (nothing leaking through):
- No `.tif`, `.DS_Store`, `.env`, `__pycache__`, `.pyc` files tracked. ✅
- `outputs/technical_summary.pdf` is the only tracked PDF and is not covered by
  current rules. Suggest broadening to `outputs/*.pdf` after confirming nothing
  still depends on it.

**Suggested additions (no action taken):**
- `outputs/*.pdf` (generalize from the two explicit names)
- `outputs/phase4_anomalies/` (diagnostic output)
- `.ipynb_checkpoints/` is already covered, but an empty committed directory
  still exists — noted as ORPHAN in §2.

---

## 7. Summary recommendations

- **ORPHAN candidates in `src/`:** 1 clear (`generate_pdf.py`, superseded by
  `generate_report_pdf.py`) + 10 UNCERTAIN legacy SAR/Phase 1–3 scripts
  (`change_detect.py`, `preprocess.py`, `classify.py`, `validate.py`,
  `map_interactive.py`, `optical_change.py`, `download_optical.py`,
  `phase4_anomaly_check.py`, `prepare_webapp_data.py`, and the `_v2` split on
  `change_detect`/`preprocess`). All flagged for Ahmed review — none deleted.
- **STALE docs:** 0. One `NEEDS REWRITE`: `README.md` still describes the
  SAR-only Phase 1–3 project and predates the Basira / Vision-2030 pivot.
- **Files >10 MB in git:** 1 — `outputs/10_optical_timeline.png` (~30 MB).
- **Surprising finds:**
  1. The webapp has two parallel data layouts under `webapp/data/phase4/` —
     top-level (old, Riyadh-only) and `phase4/<city>/` (new, post-Phase 5).
     Duplication of ~15 files; cleanup will need to confirm no cached user
     bookmarks / deploys still hit the top-level paths.
  2. `outputs/10_optical_timeline.png` alone is ~14% of all tracked bytes. If
     it's regenerable, consider gitignoring the whole `outputs/*.png` family
     and keeping a small README asset set elsewhere.
  3. `project_dashboard.html` lives at the repo root and is 26 KB, but the
     live dashboard is `webapp/dashboard.html`. Likely an older standalone copy.
  4. Phase 5 scripts (`src/phase5_*.py`, `src/city_config.py`, `cities/*.yaml`,
     `webapp/data/cities.json`, `webapp/data/phase4/jeddah/`) are all
     **untracked** — in-progress work that's not yet committed.

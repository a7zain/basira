# Basira (بصيرة)

**Saudi satellite change monitoring — a technical prototype**

Basira means *insight* in Arabic. This repository is an active prototype: 
Sentinel-1 SAR and Sentinel-2 optical imagery processed into change 
detection, vegetation time series, and an interactive web dashboard 
covering Riyadh, Saudi Arabia.

The project is in an active pivot toward Vision 2030 megaproject 
monitoring. See `basira_master_plan.md` for the current direction.

**Live dashboard:** https://a7zain.github.io/sar-change-detection/
**Status:** Active. Focused scope.

---

## What this project does today

- Processes **76 monthly Sentinel-2 scenes** (Jan 2020 – Apr 2026) over 
  Riyadh at 20m resolution
- Runs a **Sentinel-1 SAR change detection pipeline** — GCP correction, 
  Lee speckle filter, log-ratio change detection, K-means classification
- Computes **per-pixel NDVI time series** with anomaly detection and 
  hotspot ranking
- Renders a **Leaflet-based interactive dashboard** with greening maps, 
  before/after sliders, per-cell charts, and auto-generated PDF reports
- Is deployed live via **GitHub Pages** — no backend, all static

## What it's becoming

A scoped technical deliverable focused on three Vision 2030 megaprojects:

- **Qiddiya** — hero demo, dense construction activity
- **King Salman Park** — vegetation establishment and landscape change
- **Diriyah Gate** — heritage-adjacent, subtler change patterns

With a **SAR-optical fusion** approach for dust-robust monitoring, and 
a technical memo documenting the approach, decisions, and limitations.

---

## Repository structure
src/                    Active pipeline scripts
src/archive/            Superseded scripts (preserved with git history)
webapp/                 Leaflet dashboard, deployed to GitHub Pages
docs/                   Active documentation
docs/archive/           Historical phase notes and session logs
data/                   Raw and processed satellite imagery (gitignored)
outputs/                Generated artifacts (gitignored)
cities/                 City configuration files (multi-city work, parked)

Historical work is preserved under `docs/archive/` and on the 
`wip/phase5-multicity` branch.

## How to reproduce

Requires Python 3.11+, a Copernicus Dataspace account, and a Sentinel 
Hub OAuth client (both free tier).

```bash
conda create -n sarsat python=3.11
conda activate sarsat
pip install -r requirements.txt
cp .env.example .env   # populate with your credentials
```

The core pipeline entry points:

- `src/preprocess_v2.py` — Sentinel-1 SAR preprocessing
- `src/change_detect_v2.py` — SAR log-ratio change detection
- `src/phase4_download.py` — Sentinel-2 monthly time series
- `src/phase4_green_map.py` — greening persistence map
- `src/phase4_compute_hotspots.py` — hotspot ranking
- `src/generate_report_pdf.py` — auto-generated technical report

The dashboard (`webapp/dashboard.html`) is a static Leaflet app; open 
it locally or view the deployed version.

## Technical approach

The current pipeline uses Sentinel-1 SAR (C-band, VV polarization) and 
Sentinel-2 optical (L2A, cloud-masked) as complementary sensors. 
Sentinel-1 provides weather-independent change detection; Sentinel-2 
provides spectral information for vegetation and surface classification.

**Change detection** is computed as a log-ratio of pre- and post-event 
SAR backscatter, thresholded and classified via K-means (k=5).

**Vegetation analytics** use NDVI time series with monthly climatology 
for anomaly detection (|z| > 2), composite scoring for hotspot 
ranking, and temporal K-means for pixel-level classification.

**Validation** is qualitative against Google Maps imagery and against 
cross-sensor agreement between SAR-detected and optical-detected change 
(current agreement: ~58%, indicating independent evidence of real 
change rather than sensor artifacts).

Full technical documentation is in the project memo (in preparation — 
will be linked here when complete).

## Limitations

- Current scope is Riyadh; multi-city work is parked
- 20m resolution (Sentinel-2 Level-2A)
- 10 of 76 monthly scenes have partial coverage (diagonal nodata strips)
- SAR change detection is relative, not radiometrically calibrated to 
  sigma-naught
- K-means classification labels are descriptive, not semantic — real 
  attribution (construction vs. demolition vs. natural change) requires 
  monthly time-series classification, which is future work
- Dust events degrade optical returns; SAR-optical fusion to address 
  this is in active development

## About

Built by Ahmed Zainaddin — electrical engineer with upstream satellite 
systems background (KACST, SHAMS qualification model, mission analysis, 
communications systems), deliberately building downstream capability in 
earth observation and machine learning.

The name Basira (بصيرة) means insight — chosen to reflect the project's 
intent: making satellite data legible and useful, not just technically 
processed.

---

**Current focus:** Phase 1 deliverable targeting the three flagship 
Vision 2030 projects named above. See `basira_master_plan.md`.


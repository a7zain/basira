# CLAUDE.md — Basira Project Memory

Persistent memory for the Basira project. Read at session start, updated at
session end. Keep lean — only what must persist.

---

## Project snapshot

**Name:** Basira (بصيرة) — "insight" in Arabic
**Type:** Satellite-based change monitoring platform for Saudi Arabia
**Stage:** Phase 4.14 complete (full analytical pipeline + landing page + PDF report)
**Repo:** github.com/a7zain/sar-change-detection
**Local path:** /Users/a7zain/sar-change-detection
**Conda env:** sarsat (`/opt/anaconda3/envs/sarsat/bin/python`)

---

> **Claude Code guardrail:** Every Claude Code prompt must start with "Work
> directly on the main working tree. Do NOT create a git worktree under
> `.claude/worktrees/`." Worktree drift silently broke sessions on April 8
> and April 13.

> **Git status guardrail:** After every Claude Code step, run `git status` to
> confirm what's actually staged. Two sessions have shipped "done" messages
> while changes sat uncommitted on disk.

---

## Current state (as of April 16, 2026)

### What works
- SAR pipeline: Sentinel-1 download → GCP correction → UTM → Lee filter →
  log-ratio change detection → K-means (k=5)
- Sentinel-2 optical: 3 time points (2020/2023/2026) + **76 monthly scenes**
  (Jan 2020 – Apr 2026) at 20m, 4 bands (B02/B03/B04/B08), UTM 38N
- Per-pixel NDVI time series, common valid mask (80% threshold), 4 ROIs
- Pixel-level greening map (NDVI > 0.2 persistence, 2020 vs 2025)
- Web-ready exports in webapp/data/phase4/ (green map, RGB, time series JSON)
- Interactive Leaflet web app deployed via GitHub Pages
- **Web-visible greening map:** Phase 4 greening overlay, ROI polygons with
  popups, and Sentinel-2 RGB basemap live in the web app (Phase 4.5a, commit
  `d9f83d3`)
- **Phase 4.5c visible grid + breakdowns:** 56-cell clickable grid layer
  (gridPane, z-index 446) with per-cell change/vegetation breakdowns,
  desert-masked stats (AOI: 42.6% raw -> 17.8% masked), ROI cross-reference
  via ray-casting PIP, wired to "Show Changes" toggle
- **Phase 4.6:** before/after slider (2020 vs 2026, leaflet-side-by-side)
- **Phase 4.7:** pixel-level time-series classification (K-means k=5 on
  5 temporal features, 76-month NDVI trajectories, 5 clusters)
- **Phase 4.8:** NDVI anomaly detection (z-score on monthly climatology,
  9 anomalies across 4 ROIs, April 2022 regional signal)
- **Phase 4.9:** active hotspots (composite scoring, top 10, collapsible
  panel with fly-to + popup trigger)
- **Phase 4.10:** confidence layer (coverage mask) + hotspot drill-in
  (show pixel evolution per cell with veg-loss stat)
- **Phase 4.11:** hotspot time attribution (per-cell onset estimation,
  6/10 hotspots onset April 2022)
- **Phase 4.12:** per-cell NDVI time series chart in every cell popup
- **Phase 4.13:** landing page (webapp/index.html, dashboard moved to
  webapp/dashboard.html)
- **Phase 4.14:** auto-generated PDF report (src/generate_report_pdf.py)

### Known limitations
- 10 of 76 monthly scenes have partial coverage (diagonal nodata strip)
- 20m resolution (Sentinel Hub free tier)
- Only Riyadh covered
- No radiometric calibration to sigma-naught (relative change only)
- K-means "Land clearing" label is a heuristic for surface darkening /
  vegetation loss / disturbance — not all detected pixels are genuine
  demolition. Real attribution requires monthly time-series classification
  (Phase 5+).

### Open questions
- 2022_07 Central Urban NDVI spike: partial-coverage artifact now filtered
  (< 500 px threshold), but root cause not confirmed radiometrically

---

## Architecture decisions

| Decision | Why |
|----------|-----|
| Sentinel-1 + Sentinel-2 (free Copernicus) | Free, global, well-documented |
| Sentinel Hub Process API for optical | Pre-processed L2A, cloud masking |
| K-means for ML classification | Simple, interpretable, validated |
| Static web app (Leaflet + GitHub Pages) | Zero backend cost |
| 80% coverage threshold for valid mask | Balances coverage vs strictness |
| 500-pixel minimum for ROI stats | Prevents partial-scene artifacts |
| Landing page + dashboard split | Clean separation of marketing and product; landing is static HTML, dashboard is the app |

---

## Active credentials

- Copernicus Dataspace: `ahmadxgpx@gmail.com`
- Sentinel Hub OAuth: stored in `.env` (gitignored)
- GitHub repo: `a7zain/sar-change-detection`

---

## Immediate priorities

1. Awaiting tester responses on updated prototype
2. UI polish pass: hotspot panel, legend stack, mobile layout
3. Decision: deeper Riyadh features vs second AOI (after tester input)

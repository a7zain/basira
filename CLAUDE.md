# CLAUDE.md — Basira Project Memory

Persistent memory for the Basira project. Read at session start, updated at
session end. Keep lean — only what must persist.

---

## Project snapshot

**Name:** Basira (بصيرة) — "insight" in Arabic
**Type:** Satellite-based change monitoring platform for Saudi Arabia
**Stage:** Phase 4 complete (monthly temporal resolution); Phase 4.5 next
**Repo:** github.com/a7zain/sar-change-detection
**Local path:** /Users/a7zain/sar-change-detection
**Conda env:** sarsat (`/opt/anaconda3/envs/sarsat/bin/python`)

---

## Current state (as of April 8, 2026)

### What works
- SAR pipeline: Sentinel-1 download → GCP correction → UTM → Lee filter →
  log-ratio change detection → K-means (k=5)
- Sentinel-2 optical: 3 time points (2020/2023/2026) + **76 monthly scenes**
  (Jan 2020 – Apr 2026) at 20m, 4 bands (B02/B03/B04/B08), UTM 38N
- Per-pixel NDVI time series, common valid mask (80% threshold), 4 ROIs
- Pixel-level greening map (NDVI > 0.2 persistence, 2020 vs 2025)
- Web-ready exports in webapp/data/phase4/ (green map, RGB, time series JSON)
- Interactive Leaflet web app deployed via GitHub Pages

### Known limitations
- 10 of 76 monthly scenes have partial coverage (diagonal nodata strip)
- 20m resolution (Sentinel Hub free tier)
- Only Riyadh covered
- Web app not yet wired to Phase 4 outputs
- No radiometric calibration to sigma-naught (relative change only)

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

---

## Active credentials

- Copernicus Dataspace: `ahmadxgpx@gmail.com`
- Sentinel Hub OAuth: stored in `.env` (gitignored)
- GitHub repo: `a7zain/sar-change-detection`

---

## Immediate priorities

1. **Phase 4.5:** Wire Phase 4 outputs into Leaflet web app
2. **Phase 5:** Multi-city expansion (Jeddah, Mecca, NEOM, Dammam)
3. Show prototype to 3 non-engineers, capture feedback
4. SpaceUp Competition 2026 application status
5. MSc applications (GMU/Edinburgh/Glasgow)
6. SARsatX outreach

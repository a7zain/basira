# CLAUDE.md — Basira Project Memory

This file is the persistent memory for the Basira project. It is updated at the
end of each session and read at the start of every new chat. Keep it lean — only
what must persist.

---

## Project snapshot

**Name:** Basira (بصيرة) — "insight" in Arabic  
**Type:** Satellite-based change monitoring platform for Saudi Arabia  
**Stage:** Riyadh prototype complete; Phase 4 (monthly temporal resolution) is next  
**Repo:** github.com/a7zain/sar-change-detection  
**Local path:** /Users/a7zain/sar-change-detection  
**Conda env:** sarsat  

---

## Current state (as of April 4, 2026)

### What works
- Full SAR pipeline: Sentinel-1 download → GCP correction → UTM reprojection →
  Lee speckle filter → log-ratio change detection → K-means classification (k=5)
- Sentinel-2 optical pipeline: Sentinel Hub API download → cloud-free mosaics for
  2020/2023/2026 → optical change detection (k=4) → cross-sensor validation (58.4%)
- Interactive web app: Leaflet.js, timeline slider (2020/2023/2026), satellite
  basemap toggle, change overlay with click popups
- Validation: Top-10 change clusters cross-referenced against Google Maps;
  King Salman Park, northern expansion zones, infrastructure all confirmed
- GitHub Actions deploys webapp/ to GitHub Pages on push to main

### Known limitations
- 30% nodata strip in SAR scenes (geometric edge, masked but visible in some outputs)
- 20m resolution for optical (Sentinel Hub free tier, single-request limit)
- Only 3 time points so far (2020, 2023, 2026)
- No NDVI yet (only RGB optical, no NIR band requested)
- No radiometric calibration to sigma-naught (relative change only)
- No terrain correction (acceptable — Riyadh is flat)
- Only Riyadh covered

---

## Architecture decisions

| Decision | Why |
|----------|-----|
| Sentinel-1 + Sentinel-2 (free Copernicus) | Free, global, well-documented |
| Sentinel Hub Process API for optical | Pre-processed L2A, cloud masking, mosaicking |
| Direct GCP-based reprojection (not SNAP) | Works in pure Python, no GUI dependency |
| K-means for ML classification | Simple, interpretable, validated against optical |
| Static web app (Leaflet + GitHub Pages) | Zero backend cost for prototype |
| Application layer focus (not data infra) | Differentiation from UP42/SARsatX |

---

## Product positioning

- **Free tier:** Public access, annual snapshots, all Saudi cities (eventually)
- **Pro tier:** Monthly updates, higher resolution, custom AOI, alerts, exports
- **Enterprise:** API, custom ML, historical archive, GIS integration
- **Research:** Academic pricing, full data export, historical (back to Landsat)

Inspired by SARsatX/UP42 but focused on the **application layer for non-technical
users**. They sell raw data and APIs; Basira sells the finished product.

---

## How Ahmed and Claude work together

- **This chat** = strategy, brainstorming, planning, code review
- **Claude Code** = all execution (file editing, running scripts, debugging)
- **Claude gives Ahmed exact prompts to paste into Claude Code**, not descriptions
- **Honest, direct feedback** — push back, don't just agree
- **Action over deliberation** — speed matters, course corrections are fine
- **Match Ahmed's level** — analogies/visuals first, then go deeper

---

## Active credentials

- Copernicus Dataspace: `ahmadxgpx@gmail.com`
- Sentinel Hub OAuth client created (saved locally)
- GitHub repo: `a7zain/sar-change-detection`

---

## Immediate priorities (April 2026)

1. Show Riyadh prototype to 3 non-engineers, capture feedback
2. Phase 4: Monthly temporal resolution pipeline for Riyadh
3. Check SpaceUp Competition 2026 application status
4. GMU/Edinburgh/Glasgow MSc applications
5. Outreach to SARsatX

---

## Session log

### April 4, 2026
- Built complete Riyadh prototype from scratch in one day
- Fixed critical SAR coregistration bug (wrong slice2)
- Added Sentinel-2 optical layer with 3 time points
- Built interactive Leaflet web app with timeline + change overlay
- Deployed to GitHub Pages
- Created project dashboard HTML and master plan markdown
- Defined product vision: Basira as company launch product
- Decision: stay broad but go deep on what works; don't over-build before
  validating with real users

# Basira (بصيرة) — Master Plan
**Last updated:** April 13, 2026  
**Author:** Ahmed Zainaddin  

---

## What is Basira?

A Saudi Arabia-wide satellite change monitoring platform. It lets anyone — from a
government planner to a curious citizen — see how the land has changed over time.
New construction, vegetation growth, land clearing, infrastructure — all detected
automatically using satellite data and machine learning.

It starts as software. It becomes a company.

---

## Why this matters

1. **The market is real.** Saudi geospatial analytics = $1.68B in 2026, growing at 10.6%.
   Vision 2030 is spending SAR 1.285 trillion on development programs. Every mega-project
   needs monitoring. PIF launched Neo Space Group + UP42 marketplace in 2025.

2. **The gap is real.** UP42/SARsatX operate at the data/infrastructure layer. Nobody is
   building the consumer-grade application layer — the "Google Maps of change" — for
   Saudi Arabia. That's where Basira sits.

3. **The timing is right.** Free Sentinel data, cloud APIs, ML tools — the technical barriers
   have never been lower. SpaceUp Competition offers contractual opportunities. Saudi Space
   Agency is actively looking for private sector participation.

---

## What we've built (Riyadh Prototype)

| Component | Status | Notes |
|-----------|--------|-------|
| SAR preprocessing pipeline | ✅ Done | GCP correction, UTM reprojection, Lee filter |
| SAR change detection (2022→2024) | ✅ Done | Log-ratio, 3dB threshold, validated |
| ML classification (K-means, k=5) | ✅ Done | 5 classes, nodata masked, silhouette 0.319 |
| Sentinel-2 optical download | ✅ Done | 2020, 2023, 2026 via Sentinel Hub API |
| Optical change detection | ✅ Done | K-means k=4, cross-sensor validation 58.4% |
| Google Maps validation | ✅ Done | King Salman Park, northern expansion confirmed |
| Interactive web app | ✅ Done | Leaflet.js, timeline, change overlay, popups. Phase 4.5a (greening map, ROIs, RGB basemap) shipped April 13 |
| GitHub repo | ✅ Done | a7zain/sar-change-detection |
| Professional deliverables | ✅ Done | README, technical PDF, dashboard HTML |

---

## Product Architecture

```
FREE TIER (Public)                    PRO TIER (Paid)                 ENTERPRISE TIER
─────────────────                    ────────────────                ────────────────
Annual change maps                   Monthly updates                 API access
All Saudi cities                     Higher resolution (10m)         Custom AOI monitoring
Basic change categories              Detailed classification         Alert notifications
Web access                           Export reports (PDF)             Historical archive (2015+)
                                     Custom area monitoring          Custom ML models
                                     Mobile app                      GIS integration
                                                                     Research/academic data
```

## Platform

- **Web app** — primary interface, works everywhere
- **Mobile** (iOS/Android) — for field use, site visits, quick checks
- **API** — for developers and enterprises integrating into their own systems
- **Language** — English first, Arabic next

---

## Roadmap

### Phase 4: Monthly Temporal Resolution (COMPLETE)
- [x] Automate Sentinel-2 download for every month, Jan 2020 to present
- [ ] ML cloud masking for clean monthly composites
- [x] Time-series change analysis: when did each pixel change?
- [x] NDVI vegetation index using NIR band
- [x] Web integration: greening map, ROI popups, RGB basemap (Phase 4.5a, April 13)
- **Goal:** Riyadh has a complete monthly change history

### Phase 5: Multi-City Expansion
- Config-driven architecture (city_config.yaml)
- Add: Jeddah, Dammam, NEOM, Mecca, Medina
- Batch processing pipeline
- Shared ML models with transfer learning
- **Goal:** All major Saudi cities covered

### Phase 6: Advanced ML
- Deep learning segmentation (U-Net / SegFormer)
- Training data from validated Riyadh results
- Categories: residential, commercial, roads, utilities, parks, demolition, agriculture
- Confidence scores per pixel
- Automated report generation
- **Goal:** Classification accuracy that enterprises trust

### Phase 7: Multi-Sensor Fusion
- Add Landsat (30m, 40+ year archive for historical research)
- Explore Planet (3m daily), Capella/ICEYE (commercial SAR)
- Weather, population, economic data layers
- ML fusion model optimizing per change type
- **Goal:** Best possible change detection from all available sources

### Phase 8: Production Platform
- Full-stack web application (React + FastAPI + PostgreSQL/PostGIS)
- User accounts, dashboards, saved locations
- 10m tile serving on zoom (progressive detail)
- Monthly automated updates
- Mobile app (React Native or Flutter)
- Export reports, alert system
- Cloud deployment (AWS/Azure)
- **Goal:** Production-grade product that paying customers use daily

### Phase 9: Commercialization
- Pricing model finalized
- API documentation
- Enterprise dashboard with custom branding
- Government contracts pipeline
- SpaceUp Competition / Saudi Space Agency engagement
- **Goal:** Revenue

---

## Beyond the software (company vision)

Basira the software is the entry point. The company can expand into:

- **Upstream:** Satellite systems, new remote sensors, CubeSat programs
- **Downstream research:** Academic partnerships, environmental monitoring, migration
  patterns, 3D city modeling, drone integration
- **Adjacent markets:** UAE, Qatar, broader GCC, Africa
- **Internet/connectivity:** Leveraging space infrastructure expertise
- **Defense/security:** Monitoring, surveillance, border change detection

The software proves the team can execute. Everything else follows from credibility.

---

## Key accounts and credentials

| Service | Account | Notes |
|---------|---------|-------|
| Copernicus Dataspace | ahmadxgpx@gmail.com | Download SAR + search catalog |
| Sentinel Hub (CDSE) | OAuth client created | 30K processing units/month free |
| GitHub | a7zain | Repo: sar-change-detection |

---

## Workflow

| Tool | Use for |
|------|---------|
| Claude Chat | Strategy, brainstorming, planning, analysis |
| Claude Code | All code execution, debugging, file editing |
| GitHub | Version control, deployment |
| Notion | Daily tracking, learning log |
| The project dashboard HTML | Living roadmap, updated regularly |

---

## Honest priorities (next 30 days)

1. **Show the prototype to 3 non-engineers.** Get feedback. Write it down.
2. **Phase 4: Monthly pipeline for Riyadh.** Makes the product genuinely useful.
3. **Check SpaceUp Competition 2026.** Apply if open. Basira fits their tracks.
4. **Continue GMU/Edinburgh/Glasgow applications.** MSc in Remote Sensing + a
   working product = extremely strong position.
5. **Talk to SARsatX.** Even informally. They're the closest to what you're building.

---

*"An action is always better than inaction — even if we have to redo everything."*

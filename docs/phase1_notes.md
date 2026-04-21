# Phase 1 — Site Skeleton Notes

**Session date:** 2026-04-21  
**What was built:** HTML/CSS/JS skeleton for the Basira cinematic site.

---

## What's in place

- `index.html` at repo root — single file, all CSS and JS inline, no framework
- Google Fonts linked (Playfair Display + Inter, no self-hosting)
- `assets/timelapses/` — copies of the three GIFs and preview PNGs from `outputs/phase1/`
- All 8 chapters from `docs/site_spec.md` scaffolded:
  - **Ch 0** — full-viewport black, Qiddiya GIF letterboxed 16:9, title + tagline fade at 3s/5s, down-arrow
  - **Ch 1** — off-white, large serif text, spec template prose verbatim marked `[DRAFT]`
  - **Ch 2–4** — Qiddiya / King Salman Park / Diriyah Gate, each with timelapse wrap, before/after placeholder, prose stubs, chart placeholder, tech-note
  - **Ch 5** — methodology placeholder, two styled exit-ramp links
  - **Ch 6** — about placeholder
  - **Ch 7** — footer with mark, year, links, "Built with…" line

## Interactions wired

- `IntersectionObserver` autoplay on scroll-into-view (threshold 0.3), pause on scroll-out
- Click any timelapse to user-pause / resume; scroll-out always pauses
- GIF/static swap strategy: `<img src>` toggled between `.gif` (playing) and `_preview.png` (paused) — restarts GIF from frame 0, acceptable for skeleton pass; MP4 `<video>` swap is a later session
- `prefers-reduced-motion`: fades disabled (CSS), autoplay disabled (JS), static preview shown

## What's placeholder / not yet done

| Item | Status |
|---|---|
| All prose in Ch 1–6 | `[DRAFT]` — Ahmed writes |
| Before/after sliders | Static image + label, `// TODO` comment — next session |
| Charts (Ch 2–4) | Empty `div` with correct aspect-ratio, caption stub |
| Tech-note figures (Ch 5) | Not yet — two figure placeholders for later |
| Methodology prose | `[DRAFT]` — ~500 words needed |
| Memo PDF link | `href="#"` — file not yet written |
| Email + LinkedIn links | `href=""` placeholder — Ahmed fills in |
| MP4 timelapses | GIFs used — MP4 render + `<video>` swap is a later session |
| Repo rename | Not done — Ahmed does this on GitHub directly |
| GitHub Pages config | Untouched |

---

## Wide-context backdrop imagery (2026-04-21)

**Script:** `src/phase1_backdrops.py` (standalone, do not modify phase1_download.py)

**What it does:** Downloads a single cloud-free RGB (B02/B03/B04) composite per AOI at 20 m
resolution, using a bbox ~3× the tight KML polygon in each dimension, centred on the polygon
centroid.  Mosaicking: leastCC.  Date range: 2024-01-01–2024-12-31.  Output: JPEG quality=85,
percentile-stretched for visual quality.

**Outputs (assets/backdrops/):**

| File | Size | Px dims | Est. PU |
|---|---|---|---|
| `king_salman_park_context.jpg` | 358 KB | 802 × 841 | 2.57 |
| `qiddiya_core_context.jpg`     | 149 KB | 829 × 455 | 1.44 |
| `diriyah_gate_context.jpg`     |  76 KB | 530 × 312 | 0.63 |

**Total estimated PU:** 4.64

**Note — Diriyah file size below 200 KB target:** Diriyah's tight polygon is small (roughly
3.5 km × 2 km before expansion), so the 3× bbox is only ~12 km × 6 km → 530×312 px image.
Desert terrain compresses heavily at JPEG 85 → 76 KB.  If you want a physically larger context
image for Diriyah, re-run with `EXPAND_FACTOR = 2.0` in the script (→ 5× bbox, costs ~1.5 PU).
For a blurred backdrop this size may be perfectly adequate.

---

## Next session priorities

1. Before/after sliders — lightweight JS, no library (Ch 2–4)
2. Real timelapse render as MP4 at 1920×1080 for Ch 0 hero and per-AOI
3. Ahmed's prose first drafts (Chs 1–4 are the bottleneck)
4. Methodology text (Ch 5)
5. Wire backdrop JPEGs into index.html as blurred bg behind each AOI chapter

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

---

## Backdrop integration + scroll fades (2026-04-22)

**What changed in index.html:**

- **Backdrop system**: `.backdrop` div (position absolute, fills parent, `filter: blur(24px) brightness(0.55) saturate(0.9)`, `transform: scale(1.08)` to prevent blur edge reveal)
- **Chapter 0**: backdrop inside `.ch0-frame`; `qiddiya_core_context.jpg` replaces the solid black; `.ch0-gif` given `position: relative; z-index: 1`
- **Chapters 2–4**: each gets `.chapter--project` class with `overflow: hidden`; backdrop div; `.content` wrapper (`position: relative; z-index: 1; padding: 10vh 8vw`); each uses its own AOI backdrop
- **Text cascade for dark chapters**: `.chapter--project` cascades `var(--ch-text)` (warm cream) and `var(--ch-muted)` for legibility over the dark backdrop; chart borders, tech-note, coords all adjusted
- **Timelapse box-shadow**: `0 20px 60px rgba(0,0,0,0.4)` — "placed" feel on backdrop
- **Scroll-linked scale/fade**: second `IntersectionObserver` (threshold 0.4) adds `.is-visible` class once per timelapse wrap; CSS transitions from `opacity:0 scale(1.04)` → `opacity:1 scale(1.0)` over 800ms ease-out
- **Mobile**: backdrop blur reduced to 12px at ≤768px (lighter GPU load)
- **prefers-reduced-motion**: timelapse wraps start at `opacity:1 scale(1.0)` with no transition; backdrop stays static (no animation was planned)

**spec amended**: imagery section, motion section (scroll-linked bullet), parked decisions (video scrubbing rejection).

---

---

## Per-GIF blurred context via CSS masking (2026-04-22)

**Replaced** the viewport-wide chapter backdrop system (session 5) with a tighter per-timelapse treatment:

**Approach:** Each timelapse lives in a `.timelapse-frame` div whose `aspect-ratio` is set inline to the GIF's native pixel dimensions (1110/598, 1086/1106, 1065/615). Inside that frame: a `.timelapse-backdrop` img (Sentinel-2 context JPEG, `blur(18px) brightness(0.6)`, `object-fit: cover`, scaled 1.06× to clip blur fringe) and a `.timelapse-gif` img (the GIF or static placeholder, `object-fit: cover`, clipped by `mask-image`).

**Masks (`assets/masks/`):** Three white-inside/black-outside PNG masks at GIF native dimensions, generated from the KML polygon coordinates using the same `polygon_pixel_coords()` logic as the timelapse script. Verified 98.9–99.3% alignment with GIF data pixels.

**Preview PNG dimension mismatch resolved:** Preview PNGs have different dimensions than GIFs (e.g. Qiddiya: preview 1419×836, GIF 1110×598). Fixed by locking `.timelapse-frame` to GIF aspect-ratio via `aspect-ratio` inline style; both images use `object-fit: cover`, so the preview PNG fills the fixed frame without layout shift. The mask at `mask-size: 100% 100%` always covers the element correctly.

**What changed structurally:**
- Removed: `.chapter--project` class, viewport-wide `.backdrop` divs, `.content` wrapper, `--ch-text`/`--ch-muted` CSS vars, dark-text cascade for project chapters
- Chapters 2–4 return to `background: var(--bg)` (#FAF8F3) with standard `padding: 10vh 8vw`
- JS `setPlaying()` updated: queries `.timelapse-gif` not generic `img`
- Ch 0 hero backdrop unchanged (sits inside `.ch0-frame`, not viewport-wide)

**Spec amended:** imagery bullet and surface discipline section updated to reflect per-GIF masking and AI imagery prohibition.

---

## Fix: preview PNG alignment and object-fit (2026-04-22)

Preview PNGs regenerated at exact GIF dimensions by extracting frame 0 from each GIF
(`gif.seek(0); gif.convert('RGB').save(...)`). Previous preview PNGs were ~30–45% larger
in each dimension with different aspect ratios, causing `object-fit: cover` to crop the
polygon and break mask alignment. Sizes now: 1110×598 / 1086×1106 / 1065×615 — matching
GIFs and masks exactly.

Removed `object-fit: cover` from `.timelapse-gif`: since frame and image now share the
same aspect ratio, no fit adjustment is needed and the mask aligns pixel-accurately.
`.timelapse-backdrop` retains `object-fit: cover` (context JPEG has different dims).

---

## Next session priorities

1. Before/after sliders — lightweight JS, no library (Ch 2–4)
2. Real timelapse render as MP4 at 1920×1080 for Ch 0 hero and per-AOI
3. Ahmed's prose first drafts (Chs 1–4 are the bottleneck)
4. Methodology text (Ch 5)

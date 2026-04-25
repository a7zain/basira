# Basira — Site Specification (v1)

**Last updated:** 2026-04-25
**Status:** Locked. Any change to the visual direction or page structure is a deliberate decision, not a drift.

---

## Direction

Cinematic long-form, single-page scroll with full-viewport chapters. Reference points: New York Times interactive features ("Snow Fall," "What Three Years of Drought Look Like"), Apollo tribute sites, long-form visual journalism. Not SaaS landing pages. Not data dashboards.

This direction is a binding constraint. Every future decision passes through: "does this belong in a New York Times feature?" If no, it doesn't go on the surface. Phase 4 analytics, filter panels, metrics grids, toggle widgets — these remain in the repo, in the memo, and in the methodology chapter, but not on the main scroll.

## Reader model

One primary reader: a Saudi space-sector CTO evaluating a TPM-track candidate. First pass 60-90 seconds on a laptop at ~1440×900. May return for 10 minutes if hooked. Must survive being forwarded, including to mobile. Must also survive being forwarded without context.

## Tech

Static HTML/CSS/JS. No framework. Single `index.html` file. Deployed via GitHub Pages. Repo renamed from `sar-change-detection` to `basira`, URL `a7zain.github.io/basira`.

---

## Visual language

### Typography

- Display: **Playfair Display** (Google Fonts) for project names and the site title.
- Body/UI: **Inter** (Google Fonts) for everything else.
- Body copy minimum 20px, never 18px. Line-height 1.7-1.8 for body, 1.2 for headlines.

### Color

- Background: warm off-white, #FAF8F3 or similar. Not pure white.
- Text: dark charcoal, #1A1A1A. Not pure black.
- Accent: single sand/ochre tone, around #B87333. Used sparingly — links, the Arabic mark, section numbers. Never for buttons or metric callouts.
- No gradients, shadows, glassmorphism, or decorative effects.

### Motion

- Slow. Fades 400-800ms, ease-out.
- `prefers-reduced-motion` respected: autoplaying video has static fallback, animations degrade to fades.
- No parallax. No scroll-jacking — a scroll gesture always moves the page.
- Subtle scroll-linked scale/fade on chapter-in for project chapters: 1.04→1.0 scale, 0→1 opacity, 800ms ease-out, once per page load. Disabled under prefers-reduced-motion.

### Imagery

- Satellite data is the hero visual. No stock photography. No generative AI imagery of any kind — not for backdrops, not for illustrations, not for placeholder content.
- Each timelapse sits in a fixed-aspect-ratio frame (GIF native pixel dimensions). Behind it: a blurred Sentinel-2 RGB composite of the same region (blur 18px, brightness 60%), sized to fill the frame. The GIF is clipped to its polygon by a CSS mask-image (white-inside/black-outside PNG at GIF dims), so black letterbox pixels become transparent and the blurred backdrop shows through. Chapters 2–4 are on off-white (#FAF8F3); the backdrop is per-timelapse only, not viewport-wide.

---

## Page structure

Single HTML file, eight scroll-chaptered sections. Each chapter is `min-height: 100vh` to own the viewport on entry.

### Chapter 0 — Opening

Full viewport, black background. Qiddiya timelapse plays silently, centered, letterboxed to 16:9, looping. First ~3 seconds: pure visual, no overlay.

Then fade in over the video, bottom-third:

> **Basira** بصيرة
> *Insight, from above.*

After ~2 more seconds, a small monochrome down-arrow fades in at bottom center.

Note: Chapter 0 is the only chapter using the black-letterbox framing. Chapters 2-4 use the §Imagery composition.

### Chapter 1 — The premise

Off-white background, centered large text. Three short paragraphs in first person, Ahmed's voice. Template:

> I'm an electrical engineer. I spent time at KACST on a satellite called SHAMS, learning how these instruments are built.
>
> This project is the other side of that coin — not the satellite, but what you can see with one. Three Vision 2030 projects, watched from Sentinel-2 every month from 2020 through today.
>
> Here's what they've shown me.

No images, no chrome. Text breathes. Optional small section number ("I.") in the corner.

### Chapter 2 — Qiddiya

Timelapse autoplayed on scroll-into-view via IntersectionObserver, framed per §Imagery — native AOI dimensions, polygon-masked over a per-region blurred Sentinel-2 backdrop. Top-left, small and elegant:

> *Chapter II*
> **Qiddiya**
> *24.59°N, 46.33°E*

Timelapse plays one loop (~19s at 4fps). Below, a before/after slider: January 2020 vs April 2026, slim UI, small year labels in the corners of each half.

Below that, two paragraphs in Ahmed's voice — what changed, what he noticed, what surprised him.

Below that, one small chart (e.g., built area over time). Minimal axis labels, no gridlines, desaturated. The chart supports the prose, it is not the main event.

Below, one italic line in lighter text — a technical honesty note. Example:

> *Note: March 2022 had persistent dust cover; that month's frame is cloudier than its neighbors. This is why Basira's next step is SAR-optical fusion.*

This italic line is load-bearing. It signals technical seriousness without breaking tone.

### Chapter 3 — King Salman Park

Same structure as Chapter 2. The story is greening, not construction. The chart is an NDVI time series, not built-area. Prose reflects the different character.

### Chapter 4 — Diriyah Gate

Same structure. Heritage-adjacent, subtler change. The italic note can lean into Diriyah's cloud frequency (real number, computed once the data is fully in).

### Chapter 5 — How this was made

The methodology chapter. Where the TPM-signal substance lives.

Off-white background. Prose, ~500-600 words, not a bullet list. Covers:

- Why Sentinel-2, why 10m
- Why not Maxar / Planet (deliberate scoping)
- What SAR-optical fusion does, why it matters in this region
- What Basira deliberately does *not* do, and why (scoping discipline as evidence)
- What I'd build next

Two supporting figures allowed — e.g., optical-vs-SAR side-by-side for a cloudy month. Technical without breaking tone.

Ends with two prominent links:

> **Read the full technical memo (PDF) →**
> **See the source code on GitHub →**

22px, accent color, generous bottom margin. These are exit ramps for the depth-seeking reader.

### Chapter 6 — About the builder

Short. One paragraph.

> I'm Ahmed Zainaddin. I'm based in Dammam. My background is in satellite hardware; my current interest is in what you can build with the data those satellites return. Basira is one answer to that question.
>
> You can reach me at [email], or find me on [LinkedIn].

Optional small photo — if used, authentic not stylized.

### Chapter 7 — Footer

Minimal.

- Basira بصيرة (project mark, small)
- Year
- Links: GitHub, technical memo PDF, email, LinkedIn
- One muted line: "Built with Sentinel-1, Sentinel-2, Python, and Leaflet. No backend." (A final subtle technical signal.)

---

## Interaction details

### Scroll

- Smooth scroll, but never scroll-jacked. Reader always drives.
- Timelapses autoplay on scroll-into-view (IntersectionObserver), pause on scroll-out.

### Timelapse player

- Click to pause / resume.
- Hover reveals a subtle progress bar at the bottom, scrubbable.
- No chrome buttons. Just the video.
- `muted` always.

### Before/after slider

- Horizontal divider with small arrow-handles.
- Drag to reveal.
- Small year labels in the corners of each half. No floating big labels.
- On scroll-into-view: loads at 50%, plays a 1.5s slow auto-sweep to demonstrate it's interactive, then hands control over.

### Mobile

- Single column already.
- Timelapses scale to width, keep 16:9.
- Body type stays large — readability over compactness.
- Before/after slider becomes tap-to-toggle (drag is unreliable on touch).
- Chapter 1's large text uses viewport-based sizing with a minimum to avoid a text-wall on phone.

---

## Content inventory

Writing Ahmed needs to do. This is the biggest hidden cost in the cinematic direction.

| Section | Word count | Tone |
|---|---|---|
| Chapter 0 — title + subtitle | ~6 | Terse, poetic |
| Chapter 1 — premise | ~80 | First-person, restrained |
| Chapter 2 — Qiddiya prose | ~120 | Observational, first-person |
| Chapter 3 — KSP prose | ~120 | Observational, first-person |
| Chapter 4 — Diriyah prose | ~120 | Observational, first-person |
| Chapter 5 — methodology | ~500-600 | Technical but plain |
| Chapter 6 — about | ~60 | Personal, direct |
| Technical memo PDF | ~1500-2000 | Technical, professional |

Total ~2500-3200 words of original writing. ~1-2 days of focused effort, iterated.

**Voice requirement:** the prose is the humanity. If it reads as AI-polished, the aesthetic collapses. Ahmed writes the messy first draft; Claude edits for brevity and rhythm; Claude never invents voice (no fabricated "I felt" or "I noticed" unless Ahmed said something like it).

---

## Build sequence

Rough order once data is fully downloaded:

1. Final timelapse renders — hero MP4 1920×1080 letterboxed, 4fps, per AOI.
2. Domain + repo rename — `a7zain.github.io/basira`.
3. HTML/CSS skeleton with placeholder content.
4. Before/after sliders — lightweight JS, no library.
5. Scroll-linked timelapse players — IntersectionObserver.
6. Methodology chapter — substantial writing + two figures.
7. Per-project prose — written while looking at the timelapses.
8. Technical memo PDF — in parallel with all the above.

Estimate: 5-7 focused sessions. Within the Phase 1 4-6 week window.

---

## Parked decisions

### Scroll-linked vs autoplay-on-view timelapse playback

v1 uses autoplay on scroll-into-view. Scroll-linked (where scroll position controls video time) is more NYT-cinematic but more fragile on mobile. If autoplay feels insufficient after seeing it live, we upgrade to scroll-linked as a Phase 1.5 polish.

### Section numbering ("Chapter II" etc.)

Kept in the spec. Drop if execution makes it feel pretentious rather than editorial.

### Chapter 6 as standalone vs folded into footer

Kept standalone for now. Might fold into the footer if it reads as ego rather than authorship.

### Scroll-linked video scrubbing (rejected for v1)

Considered in 2026-04-21 session. Rejected: fragile on mobile, would replace the autoplay-on-view behavior that already tested well, and can be added as Phase 1.5 polish if the softer scale/fade approach feels insufficient in the live review.

---

## Surface discipline — what stays off the main scroll

Non-exhaustive list of things that will not be added to the main cinematic scroll, regardless of how tempting:

- Generative AI imagery of any kind (backdrops, illustrations, placeholders) — all imagery is real satellite data or nothing
- Metric grids, KPI cards, dashboard widgets
- Filter panels, dropdowns, toggles
- Phase 4 analytics (hotspots, 56-cell grid, pixel classification, ML anomalies) — these live in the methodology chapter and memo only
- Multi-city framing, nationwide maps, "coming soon" teasers
- Vision 2030 / Saudi government logos
- Pricing, tiers, signup, newsletter
- "Live data" banners, update timestamps, version numbers
- Any CTA other than the two exit-ramp links at the end of Chapter 5

If a future session wants to add any of these, the default answer is no and the burden is on the argument for inclusion, not exclusion.

## Revision notes

- 2026-04-25 — resolved §Imagery vs §Chapters 2/3/4 contradiction in v1 in favor of §Imagery composition. Ch 0 unchanged.

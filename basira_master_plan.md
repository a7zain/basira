# Basira (بصيرة) — Direction

**Last updated:** 2026-04-20

---

## What this document is

An internal planning document. It describes what Basira is today, what the 
immediate objective is, and what the longer arc looks like. It is written 
for me, and for any future collaborator who needs to get oriented quickly.

This is not a marketing document. It does not oversell. It is meant to be 
honest about scope, limitations, and intent.

---

## What Basira is

Basira is a satellite-based change monitoring project focused on Saudi 
Arabia. Today, it is a working prototype: Sentinel-1 SAR and Sentinel-2 
optical imagery, processed into monthly change detection and vegetation 
time series, served through an interactive web dashboard deployed on 
GitHub Pages.

The project has been active since early 2026 and has progressed through 
four major phases of technical work — SAR preprocessing and change 
detection, ML classification, optical cross-validation, and monthly 
temporal resolution with per-pixel time-series analytics. The Riyadh AOI 
has 76 months of Sentinel-2 scenes from January 2020 to April 2026, with 
associated NDVI time-series, anomaly detection, hotspot ranking, and 
pixel-level classification.

The name Basira (بصيرة) means insight.

---

## Where it sits in my broader trajectory

I am an electrical engineer with upstream satellite systems experience — 
qualification-model build work on SHAMS at KACST, mission analysis 
documentation, communications systems focus. Basira is the deliberate 
downstream counterpart to that upstream foundation. The goal is to 
become credible at both ends of the space value chain: building the 
satellites and building the products that consume their data.

This positioning matters because the most interesting product-engineering 
roles in space sit at the upstream-downstream intersection, and very few 
people are building credibility on both sides simultaneously.

---

## Phase 1 — Immediate objective

**Ship a focused technical deliverable demonstrating end-to-end capability 
on Vision 2030 megaproject monitoring.**

This is a pivot from the earlier framing of Basira as a comprehensive 
nationwide change monitoring platform. The pivot is deliberate: a focused, 
polished, scoped deliverable is more valuable in the current moment than 
a broad, partial one. The broader product ambition is preserved in the 
longer arc below and is not abandoned — it is sequenced.

### Scope

Three Vision 2030 megaprojects as flagship demonstrations:

- **Qiddiya** — hero demo, dense construction activity
- **King Salman Park** — vegetation establishment and landscape transformation
- **Diriyah Gate** — mixed-use, heritage-adjacent, subtler change patterns

For each project, the deliverable includes:

- Monthly imagery time series (2020 to present, from Sentinel-2)
- SAR-optical fusion for robust detection through dust and partial cloud 
  cover
- A progress metric curve per project
- A project-focused view in the web dashboard

### Supporting deliverables

- A 3–5 page technical memo (PDF) describing approach, scoping decisions, 
  technical choices, limitations, and what I would build next
- A rewritten project README aligned to the current direction
- A cleaned GitHub repo with a readable history (completed April 2026)

### What Phase 1 is not

- Not a multi-city platform (multi-city work is parked on the 
  `wip/phase5-multicity` branch and will be re-evaluated after Phase 1)
- Not a commercial product pitch with pricing tiers
- Not a research paper on novel methodology
- Not a marketing site

Phase 1 is a scoped demonstration of end-to-end execution: from raw 
Sentinel data to a user-facing dashboard to a written technical 
communication. The full stack, done cleanly.

### What "done" looks like

Phase 1 is done when:

1. The three-project dashboard is live and the Qiddiya timelapse is 
   visually compelling
2. The technical memo exists as a PDF and reads well
3. The README on GitHub accurately represents the project
4. The deliverable has been shared with its intended first reader

Approximate timeline: 4–6 weeks from the cleanup completion date 
(2026-04-20). No hard external deadline.

---

## Architecture (revised 2026-04-27)

The Phase 1 deliverable is a **portfolio-with-research-engine**, not a single
cinematic site. Two-tier structure:

**Tier 1 — Cinematic homepage** (`/`)
The 8-chapter scroll site as originally locked in `docs/site_spec.md`. Acts as
table of contents and voice anchor. Each project chapter (Qiddiya, KSP,
Diriyah) gets an exit ramp to its corresponding research deep-dive.

**Tier 2 — Research deep-dives** (`/research/<slug>/`)
Long-form articles: ~1500-2000 words each, 4-6 figures, methodology + caveats
+ findings. Each is a standalone shareable URL. Reads like a paper, written
like long-form journalism. Pudding.cool / NYT Interactives / Reuters Graphics
as the reference aesthetic.

### Umbrella question

All research pieces sit under one umbrella:

> *"What can satellites honestly say about Saudi Arabia's transformation,
> and what are they missing?"*

The umbrella is binding. Future research pieces have to fit it or they
don't ship as part of Basira.

### Research pipeline

| Slug | Title | Status | Why |
|---|---|---|---|
| `dust-honesty` | How honest can satellites be about a country covered in dust? | In progress | Regional extension of Goyens 2024 with NDVI-bias dimension. Foundation for downstream pieces. |
| `riyadh-churn` | What did Riyadh actually do, 2020-2026? | Queued | Inherits dust-honesty's flag pipeline. Hardened Phase 4 finding. |
| (future) | TBD — irrigated vs natural greening, temporal resolution sufficiency, expansion frontier, long-baseline Landsat | Backlog | Each candidate evaluated against umbrella before scheduling. |

### What this changes vs original Phase 1 plan

- **Timeline:** 4-6 weeks → 4-6 months for first two research pieces.
- **Reader model:** 60-90s scan → 5-15 minute read.
- **Differentiator:** "I can play satellite data as video" → "I find findings
  others miss because I question the data itself."
- **LinkedIn:** Each research page is a shareable URL with a citable claim.
- **Reusability:** Future research pieces add to the umbrella without
  homepage redesign.

### What this does NOT change

- Upstream/downstream company vision: same.
- Saudi-first positioning: same, sharpened.
- Eventual commercialization story: same.
- Cinematic homepage as voice anchor: same — the prose just gets written
  later, after the research pieces exist.

---

## Design principles

A few principles that have emerged over the project so far and should 
continue to shape decisions:

**Surface area discipline.** Every feature added to the user-facing 
dashboard competes with every other feature for attention. Features that 
don't serve the current primary use case stay in the codebase but leave 
the surface. The Phase 4 analytics work (anomaly detection, hotspot 
scoring, 56-cell grid, confidence layer, pixel time-series classification) 
is technically strong but will not be on the Phase 1 dashboard surface — 
it lives behind an "Advanced" view at most.

**Scoping decisions are evidence.** What I chose to cut is as informative 
as what I chose to build. Phase 1 documentation explicitly records these 
decisions rather than presenting only the end state.

**Free data unless there's a specific reason otherwise.** Sentinel-1 and 
Sentinel-2 are the default. Paid imagery (Planet, Maxar) is not part of 
Phase 1. The constraint is part of the story: making Sentinel imagery 
look good is itself a signal.

**Honest limitations.** The memo and the README name real limitations 
explicitly. Overclaiming is a worse failure mode than underclaiming.

---

## Longer arc

Phase 1 is the near-term focus. The longer arc — preserved here to 
document intent, not to pursue until Phase 1 ships — remains Basira as a 
Saudi-focused satellite change monitoring product, with the potential to 
become the foundation of a company combining upstream (satellite 
building) and downstream (data analytics) capability.

The nearest adjacent directions, once Phase 1 has shipped and taught us 
what resonates, are likely one of: unauthorized construction detection 
for municipalities, afforestation verification for Saudi Green Initiative 
claims, or agricultural water compliance monitoring. Each of these is a 
vertical where satellite-scale monitoring is the appropriate primary 
tool, the customer is identifiable, and current market offerings are 
weak. The correct next vertical is not yet decided — Phase 1 shipping 
and the conversations it generates are the forcing function for that 
decision.

The broader company ambition — upstream satellite systems plus 
downstream analytics, Saudi-focused, eventually GCC and beyond — remains 
the north star. Phase 1 is the first legible artifact of that ambition.

---

## Active credentials and infrastructure

- Copernicus Dataspace: ahmadxgpx@gmail.com
- Sentinel Hub OAuth client: active (30K PU/month free tier)
- GitHub repo: a7zain/sar-change-detection
- Deployed dashboard: GitHub Pages
- Local conda environment: `sarsat`
- Local project path: `/Users/a7zain/sar-change-detection`

---

## Working rhythm

- This chat (Claude): strategy, planning, document drafting, review
- Claude Code: all code execution, file manipulation, commits
- GitHub: version control, deployment, canonical source of truth
- Per-objective cleanup pass at each objective boundary (one pass, 
  not two)
- Per-session logs in `docs/sessions/` capturing what happened and 
  what's next

The Phase 5 multi-city work is parked on `wip/phase5-multicity` for 
re-evaluation after Phase 1 ships.

# CLAUDE.md

**Project:** Basira (بصيرة) — Saudi satellite change monitoring
**Last updated:** 2026-04-28
**Purpose of this doc:** Minimum context needed to be immediately useful
in a fresh chat. Not a changelog.

> For employer-specific context on the current deliverable target, load
> `.private/context.md` at session start. That file is gitignored and
> contains the specific opportunity this work is shaped for.

---

## Who I am

Ahmed Zainaddin. Electrical engineer, based in Dammam, Saudi Arabia.
Early-career — still building, still choosing direction deliberately.

**Upstream background.** Hands-on satellite systems work at KACST
(King Abdulaziz City for Science and Technology). Qualification-model
build on SHAMS satellite. Mission analysis documentation for previous
satellite launches. Three weeks as a space systems engineer handling
communications-systems documentation. This is where my technical roots
are: hardware, systems integration, comms.

**Downstream direction.** Over the last eight months, deliberate
self-study in earth observation and machine learning. Basira is the
product of that effort — the intent was always to build something real
rather than just complete courses. I'm applying to KAUST Academy ML
Program and to MSc programs at GMU, Edinburgh, and Glasgow. The
deliberate trajectory is to become credible at both ends of the space
value chain — upstream satellite engineering and downstream data
products — because the most interesting roles in the Saudi space sector
sit at that intersection, and few people are building on both sides
simultaneously.

**How I work.** I move fast, I change course when evidence says I should,
and I prefer shipping over deliberating. I keep persistent notes across
sessions (this doc, session logs, master plan) because context-switching
between strategy chats and code execution burns more energy than most
people admit. I value direct pushback over polite agreement — if I'm
about to make a mistake, I'd rather hear that in the moment than
discover it later. When I say "do your recommendations" or "proceed," I
sometimes mean it and sometimes I'm fatigued; a fresh Claude is right to
flag when a decision is big enough that a real review is warranted.

**What I'm building toward.** Near term: a credible entry into the Saudi
space sector through a role that lets me work on both satellite systems
and EO products. Longer term: Basira (or its successor) as a product
company that produces value from satellite data, potentially expanding
into upstream capability. The company ambition is real but it's the
north star, not the current objective. Right now I'm focused on building
evidence that I can scope, execute, and communicate.

**Who's around me.** Mutual contacts at multiple Saudi space-sector
entities. Small sector, warm introductions matter, reputation compounds.
I am deliberate about not overpromising.

**Language.** English primary for technical work. Arabic native. The
project name Basira (بصيرة) means insight.

---

## Current objective

**Phase 1 deliverable: portfolio-with-research-engine — cinematic
homepage as table of contents, real research pages underneath.**

Three Vision 2030 megaproject chapters on the homepage (Qiddiya hero,
King Salman Park, Diriyah Gate), each linking to a research deep-dive
that answers one umbrella question with rigor:

> *"What can satellites honestly say about Saudi Arabia's transformation,
> and what are they missing?"*

This is shaped for a specific employment opportunity in the Saudi space
sector — a role that rewards breadth, scoping judgment, and clean
communication rather than deep methodological novelty. Framing of every
artifact should reflect that: execution story and upstream-downstream
narrative, not depth competition.

For the specific target, context, and timing of the outreach, see
`.private/context.md`.

Approximate timeline: 4–6 months for the first two research pieces
(revised from the original 4–6 week estimate when the architecture
pivoted on 2026-04-27).

Full strategic framing: see `basira_master_plan.md`.

---

## Current state (as of 2026-04-28, evening)

**Project shape.** Basira's Phase 1 deliverable is a portfolio-with-
research-engine. The cinematic homepage at root `index.html` stays as-is
for now; new research pages live at `/research/<slug>/`. Live at
https://a7zain.github.io/basira/.

**First two research pieces, locked sequence B → A:**

### Research piece B (dust-honesty) — IN PROGRESS, blocked

Question: how does Sen2Cor's known underestimation of aerosols over
deserts (Goyens 2024) translate into NDVI bias for change monitoring
over Riyadh, and how often does it matter? Sources: Sentinel-2 L2A
(subject), TROPOMI UVAI + VIIRS Deep Blue AOD (validation), HLS NDVI
(cross-check). Method: adapt Lolli 2024 DBB index, recalibrate for AP.
7 sub-questions (SQ1-SQ7). Lives at `research/dust-honesty/`.

**Sub-question status:**

- **SQ1 (port DBB index, sample 30 scenes)** — DONE. Commit `47ac3f9`.
  30 scenes pulled across 3 sub-AOIs (qiddiya_core, king_salman_park,
  diriyah_gate). DBB values uniformly negative (−0.315 to −0.219) over
  bright desert — relative shift, not sign change, is the dust signal.
  Lolli formulation flagged as inspired-not-faithful (paper PDF not
  verified — MDPI and ResearchGate both 403 to automated fetch).

- **SQ1 thumbnails** — iterated twice for usable labeling. v1 had
  black polygon-mask frame (commit `5bdb106`: bbox crop, drop polygon
  mask, largest interior rectangle per scene). v2 used global stretch
  that compressed within-AOI atmospheric variation (commit `91a7077`:
  per-AOI 2/98 percentile stretch). Final per-AOI stretches:
  - qiddiya_core:     R [0.279, 0.635], G [0.213, 0.520], B [0.136, 0.398]
  - king_salman_park: R [0.185, 0.637], G [0.147, 0.534], B [0.095, 0.410]
  - diriyah_gate:     R [0.070, 0.513], G [0.062, 0.454], B [0.031, 0.387]

- **SQ1 manual labels** — DONE via AI-pre-label + researcher-review
  workflow. Distribution: 23 clean / 4 light_haze / 2 heavy_dust / 1
  cloud / 0 mixed. Methodology: Claude pre-labeled against a written
  rubric, Ahmed reviewed and finalized against the full-resolution
  PNG. Force-added past `.gitignore` (data/ is broadly ignored; this
  CSV is calibration data and must be reproducible). Commits `9b73a75`,
  `442d7b0`.

- **SQ1B (threshold tuning with bootstrap CI)** — STOP RULE FIRED.
  Commit `3d3b511`. Bootstrap 95% CI half-width 0.026 vs threshold
  0.020. AUC 0.55 (conservative) / 0.51 (aggressive) — near chance.
  Driven by class imbalance: only 2 heavy_dust positives in 30-scene
  sample. No threshold shipped, `dbb_index.py` unchanged,
  `is_dust_flagged` not written. The stop rule worked as designed.

- **SQ1C (UVAI-anchored expansion of calibration set)** — BLOCKED.
  Strategy: pull TROPOMI monthly UVAI 2020-2026 for Riyadh, identify
  high-UVAI months, pull Sentinel-2 monthly mosaics for those months
  at all 3 sub-AOIs, generate thumbnails. Critical: UVAI selects WHICH
  months to pull but does NOT label scenes (would make SQ3 validation
  circular). Target: n_pos ≥ 12 in expanded set.
  Status: fetcher script `research/dust-honesty/scripts/fetch_uvai_monthly.py`
  written and uncommitted. **Did not run successfully** — Sentinel Hub /
  CDSE returned 503 across 30+ minutes (confirmed external outage,
  reproduced from cellular). Claude Code rate limit also hit, resets
  1:50pm Riyadh on 2026-04-28. Both blockers external.

- **SQ2-SQ7** — QUEUED behind SQ1B re-run on expanded calibration set.

### Research piece A (churn, hardened) — QUEUED

Inherits B's dust-flag pipeline. Re-runs Phase 4 churn analysis with
dust correction applied. Approximately 5 sessions after B.

### Cut from scope

- Vision 2030 progress audit — political risk vs target sector, deferred.
- MODIS as primary source — being decommissioned (Terra Dec 2025,
  Aqua Aug 2026). Replaced by VIIRS + TROPOMI.
- Bird migration / cross-domain — wrong fit for my positioning.

---

## Methodology footnote (binding for B writeups)

This must appear in any SQ1B / SQ1C / B-final writeup:

> "The 30-scene calibration set was pre-labeled by an AI assistant
> (Claude) against a written rubric for atmospheric clarity (clean /
> light_haze / heavy_dust / cloud / mixed), then reviewed and finalized
> by the researcher with focus on low-confidence calls."

---

## Flags before next session

- **CDSE outage check first.** Before re-running SQ1C, run:
  `curl -s -o /dev/null -w "%{http_code}\n" https://sh.dataspace.copernicus.eu`
  Expect 200 or 302. If 503, wait — don't burn Claude Code allowance.
- **Claude Code rate limit resets 1:50pm Riyadh on 2026-04-28.**
- **GEE project registered as `basira-494617`, Community Tier (150
  EECU/mo).** `GEE_PROJECT=basira-494617` saved to `.env`. Tested
  end-to-end (`ee.Number(1).add(1).getInfo()` → 2). VIIRS Deep Blue
  unblocked for SQ3.
- **Lolli 2024 PDF still not retrieved** — get it offline before any
  formulation-sensitive claim ships. Direction-of-signal sanity check
  passed in SQ1; not a session-blocker, but resolve before B-final.
- **TROPOMI via Sentinel Hub strips qa_value** — production needs raw
  netCDF via Copernicus CDSE OData. SQ3 concern, not yet.
- **Sentinel Hub PU consumption** — track via SH dashboard. Free tier
  is 30k/month; SQ1 + thumbnail re-renders consumed under 200 PU; SQ1C
  budget when it runs is ~200 PU more. Plenty of headroom.
- **Resume plan for SQ1C** when CDSE is up and CC allowance is back:
  the existing fetcher script in `research/dust-honesty/scripts/fetch_uvai_monthly.py`
  should work as-is. Run it standalone first (outside Claude Code) to
  confirm CDSE is reachable, THEN re-fire the SQ1C prompt for the
  rest of the pipeline.
- **Fallback if CDSE stays down**: pull TROPOMI directly from CDSE
  OData (raw netCDF). Heavier prompt, but bypasses Sentinel Hub
  entirely.

---

## What works right now

- **SAR pipeline** (`src/preprocess_v2.py`, `src/change_detect_v2.py`):
  Sentinel-1 download → GCP correction → UTM → Lee filter → log-ratio
  change detection → K-means (k=5)
- **Sentinel-2 monthly time series**: 76 scenes Jan 2020 – Apr 2026,
  Riyadh AOI, 20m, 4 bands (B02/B03/B04/B08), UTM 38N
- **NDVI analytics**: per-pixel time series, greening map, ROI time
  series, anomaly detection, hotspot ranking, pixel-level classification
- **Web dashboard**: Leaflet.js, deployed GitHub Pages, shows greening
  map, ROI polygons, before/after slider, hotspots, per-cell charts
- **Auto-generated PDF report**: `src/generate_report_pdf.py`
- **Phase 1 pipeline**: KML-based AOI registry, polygon-clipped
  Sentinel-2 downloader, RGB timelapse generator. Scripts:
  `src/phase1_aois.py`, `src/phase1_download.py`,
  `src/phase1_quicklook.py`, `src/phase1_timelapse.py`
- **Phase 1 data**: 76 months × 3 AOIs (qiddiya_core, king_salman_park,
  diriyah_gate), 10 m, 6 bands (B02/03/04/08/11/12), ~387 MB total
- **Phase 1 timelapses**: RGB GIFs per AOI, fixed cross-stack contrast,
  4 fps, polygon-outlined
- **Basira cinematic site** (`index.html`): 8-chapter skeleton, per-GIF
  blurred Sentinel-2 context via CSS mask-image (polygon masks at GIF
  dims), IntersectionObserver autoplay + scale/fade, off-white chapters
  2–4, prefers-reduced-motion support. Served locally at port 8888.
- **Wide-context backdrops** (`assets/backdrops/`): Sentinel-2 RGB
  composites per AOI, 2024 dry season, 20 m, leastCC, correct band
  order (R=B04, G=B03, B=B02). Script: `src/phase1_backdrops.py`
- **Polygon masks** (`assets/masks/`): white-inside/black-outside PNGs
  at GIF native dims (1110×598 / 1086×1106 / 1065×615), 98.9–99.3%
  polygon alignment verified
- **Aerosol spike infrastructure**: TROPOMI UVAI accessible via
  Sentinel Hub Process API on CDSE for any single date. VIIRS Deep
  Blue AOD now accessible via GEE (`basira-494617` project). Both
  validated end-to-end against the 2022-05-17 dust day vs 2022-12-15
  clear day pair (UVAI 2.89 vs 0.06, ~49× ratio).
- **Dust-honesty SQ1 pipeline**: DBB index implementation
  (Lolli-inspired-not-faithful), 30-scene sample with stratified
  seasonal coverage, per-AOI-stretched thumbnail rendering with
  largest-interior-rectangle bbox crop, AI-pre-label + researcher-review
  labeling workflow, bootstrap-CI threshold sweep with stop-rule.

## What's parked or incomplete

- Multi-city (Jeddah, etc.): on `wip/phase5-multicity` branch, not in
  Phase 1 scope.
- Before/after sliders: placeholder in HTML, JS not yet written.
- MP4 timelapses: GIFs used for now; MP4 render + `<video>` swap is next.
- All cinematic-site prose: `[DRAFT]` markers throughout Ch 1–6;
  Ahmed writes after research pages exist.
- SAR-optical fusion as a clean single product: not yet done.
- Technical memo: not yet written.
- README rewrite: pending Pass 3 of cleanup.
- Cosmetic cleanup: per-AOI stretch + bbox crop is now a real rendering
  convention. Worth applying to other figures across the project as a
  separate cleanup pass after B ships.

---

## Working rhythm

- **This chat (Claude)**: strategy, planning, document drafting, review.
  No code execution here.
- **Claude Code**: all file operations, commits, code changes. Prompts
  from this chat are pasted into Claude Code.
- **Per-objective cleanup pass**: one cleanup at each objective boundary.
  Not two (beginning and end are the same event).
- **Per-session logs**: committed to `docs/sessions/YYYY-MM-DD.md` at
  session end.
- **End-of-session ritual (revised 2026-04-28)**: at session end, Claude
  produces COMPLETE drop-in versions of `CLAUDE.md` and the dated
  `docs/sessions/YYYY-MM-DD.md` (full file replacements, not section
  edits). Ahmed overwrites the local files entirely, runs
  `git add -A && git commit && git push`, then clicks "Sync now" in the
  Claude Project to pull the latest from GitHub into the Project
  snapshot. Sync now is required because Projects don't auto-sync from
  GitHub — they're snapshots.

---

## Operational guardrails (learned the hard way)

**Worktree drift.** Claude Code has previously created git worktrees
under `.claude/worktrees/` and silently broken sessions multiple times.
Every Claude Code prompt must include: *"Work directly on the main
working tree. Do NOT create a git worktree under `.claude/worktrees/`.
If you think you need one, stop and ask."*

**Post-edit verification.** After any Claude Code report of "N
insertions" or "file edited," verify with `git status` and `find . -name
<file> -not -path '*/.git/*'` before trusting the edit. This caught
two "shipped but not actually committed" states. The 2026-04-28 SQ1C
session also showed Claude Code reporting "completed (exit code 0)"
when no output files were written — always verify on disk, not from
the report.

**Atomic commits.** Each cleanup, refactor, or feature goes in its own
commit with an accurate message. No mixed commits. If a multi-part
operation is needed, split it into numbered passes (e.g. Pass 2A, 2B,
2C, 2D) and verify between each.

**Token budget awareness.** Claude Code reading full file contents of
every script when it only needs filenames and metadata is a budget waste.
Prompts should explicitly constrain depth of reading where possible.

**Autonomous execution preferred.** Claude Code prompts skip "show me
each diff" / "wait for my approval" gates. Phrase prompts as: full
sequence, verify with git log/status at end, report results. Single
review point at end, not interleaved. Only stop for genuinely
destructive or irreversible cases (force push, mass delete, credential
exposure, history rewrite) or for explicit stop-rule clauses written
into the prompt itself.

**External-blocker triage.** When a Claude Code task hangs for >5
minutes with no visible progress, check three things in order:
(1) the local file system for partial output, (2) the upstream service
status (e.g. CDSE), (3) the Claude Code rate limit / allowance. The
2026-04-28 SQ1C run lost ~30 minutes to a CDSE 503 outage that I first
misdiagnosed as a script issue. External blockers are not script bugs.

---

## Active credentials and paths

- Copernicus Dataspace: ahmadxgpx@gmail.com
- Sentinel Hub OAuth: stored in `.env` (gitignored)
- Earth Engine project: `basira-494617`, Community Tier, stored as
  `GEE_PROJECT=basira-494617` in `.env`
- GitHub: `a7zain/basira` (repo renamed from `sar-change-detection`)
- Local path: `/Users/a7zain/basira`
- Conda env: `sarsat`

---

## Open questions and things to decide

- Chart design per project chapter (Qiddiya = built area, KSP = NDVI,
  Diriyah = TBD — probably vegetation/built blend). Defer until research
  pages and cinematic-site exit ramps are wired together.
- SAR-optical fusion design spec: to be drafted before Phase 1 build
  begins. Held for now pending research-piece completion.
- Outreach message framing: draft closer to send date, not now.
- If SQ1C-with-expanded-calibration still doesn't yield a stable
  threshold: reconsider DBB formulation (verify Lolli first, consider
  pixel-level vs scene-mean DBB, evaluate alternative indices).

---

## What NOT to do

- Do not re-litigate the TPM-track vs. EO-specialist framing. That
  decision was made 2026-04-20 after an explicit reframe conversation.
  The deliverable is shaped for breadth and execution, not for
  methodological depth competition.
- Do not expand Phase 1 scope. The three projects are the scope.
  Additional projects, additional cities, additional analytics — all
  post-Phase 1.
- Do not suggest paid imagery (Planet, Maxar) for Phase 1. Sentinel is
  the constraint, deliberately.
- Do not treat the longer-arc company vision as the active objective.
  It's the north star, not the map.
- Do not re-litigate the cinematic NYT-feature direction. Locked
  2026-04-21 after explicit pushback discussion. All surface-level
  additions pass through: "does this belong in a New York Times feature?"
- Do not re-litigate the portfolio-with-research-engine pivot. Locked
  2026-04-27. Research pages add to the homepage's umbrella; they don't
  replace it.
- Do not auto-label calibration scenes from UVAI as a shortcut. UVAI
  selects which months to pull; visual labels remain the calibration
  target. Conflating the two collapses SQ3 validation into circularity.

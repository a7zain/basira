# CLAUDE.md

**Project:** Basira (بصيرة) — Saudi satellite change monitoring
**Last updated:** 2026-04-21
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

**Phase 1 deliverable: scoped technical demonstration of end-to-end 
capability on Vision 2030 megaproject monitoring.**

Three projects — Qiddiya (hero), King Salman Park, Diriyah Gate. 
Deliverable includes a live dashboard, a 3–5 page technical memo PDF, 
a rewritten README, and targeted outreach.

This is shaped for a specific employment opportunity in the Saudi space 
sector — a role that rewards breadth, scoping judgment, and clean 
communication rather than deep methodological novelty. Framing of every 
artifact should reflect that: execution story and upstream-downstream 
narrative, not depth competition.

For the specific target, context, and timing of the outreach, see 
`.private/context.md`.

Approximate timeline: 4–6 weeks from 2026-04-20.

Full strategic framing: see `basira_master_plan.md`.

---

## Current repo state

- On `main`: Phase 1 data-acquisition session complete 2026-04-21 (latest commit `14fda9e`, five Phase 1 commits stacked on the 2026-04-20 cleanup ending `d0457bb`)
- Phase 1 data fully downloaded (2026-04-21): 228 Sentinel-2 scenes across three AOIs, polygon-clipped to KML geometry
- Phase 5 multi-city work parked on `wip/phase5-multicity` (commit `8ea085b`)
- Superseded scripts archived under `src/archive/` with `git mv` history preserved
- Historical docs under `docs/archive/`
- `outputs/*.png` and `outputs/*.pdf` now gitignored; `outputs/phase1/` and `data/phase1/*/*.tif` also gitignored (regenerable)

## What works right now

- **SAR pipeline** (`src/preprocess_v2.py`, `src/change_detect_v2.py`): 
  Sentinel-1 download → GCP correction → UTM → Lee filter → log-ratio 
  change detection → K-means (k=5)
- **Sentinel-2 monthly time series**: 76 scenes Jan 2020 – Apr 2026, 
  Riyadh AOI, 20m, 4 bands (B02/B03/B04/B08), UTM 38N
- **NDVI analytics**: per-pixel time series, greening map, ROI time series, 
  anomaly detection, hotspot ranking, pixel-level classification
- **Web dashboard**: Leaflet.js, deployed GitHub Pages, shows greening 
  map, ROI polygons, before/after slider, hotspots, per-cell charts
- **Auto-generated PDF report**: `src/generate_report_pdf.py`
- **Phase 1 pipeline**: KML-based AOI registry, polygon-clipped Sentinel-2
  downloader, RGB timelapse generator. Scripts: `src/phase1_aois.py`,
  `src/phase1_download.py`, `src/phase1_quicklook.py`, `src/phase1_timelapse.py`
- **Phase 1 data**: 76 months × 3 AOIs (qiddiya_core, king_salman_park,
  diriyah_gate), 10 m, 6 bands (B02/03/04/08/11/12), ~387 MB total
- **Phase 1 timelapses**: RGB GIFs per AOI, fixed cross-stack contrast,
  4 fps, polygon-outlined

## What's parked or incomplete

- Multi-city (Jeddah, etc.): on `wip/phase5-multicity` branch, not in 
  Phase 1 scope
- Site build not yet started. Cinematic site spec locked in
  `docs/site_spec.md` (v1, 2026-04-21). Build sequence: repo rename →
  HTML skeleton → sliders → scroll players → prose → memo PDF.
- SAR-optical fusion as a clean single product: not yet done (Phase 1 
  technical work)
- Technical memo: not yet written
- README rewrite: pending Pass 3 of cleanup

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
- **End-of-session file handoff**: Claude (chat) drafts any repo-bound 
  files — session logs, specs, notes — as text in chat, not as 
  downloadable files. Ahmed copies the text and pastes it into a 
  single Claude Code prompt that creates the file at the correct path, 
  commits with a meaningful message, and pushes. No browser downloads, 
  no GitHub web UI uploads. Text flows chat → Claude Code → repo.

---

## Operational guardrails (learned the hard way)

**Worktree drift.** Claude Code has previously created git worktrees 
under `.claude/worktrees/` and silently broken sessions three times 
(April 8, April 13, and one during the Phase 4 rush). Every Claude Code 
prompt must include: *"Work directly on the main working tree. Do NOT 
create a git worktree under `.claude/worktrees/`. If you think you need 
one, stop and ask."*

**Post-edit verification.** After any Claude Code report of "N insertions" 
or "file edited," verify with `git status` and `find . -name <file> -not 
-path '*/.git/*'` before trusting the edit. This caught two "shipped but 
not actually committed" states.

**Atomic commits.** Each cleanup, refactor, or feature goes in its own 
commit with an accurate message. No mixed commits. If a multi-part 
operation is needed, split it into numbered passes (e.g. Pass 2A, 2B, 
2C, 2D) and verify between each.

**Token budget awareness.** Claude Code reading full file contents of 
every script when it only needs filenames and metadata is a budget waste. 
Prompts should explicitly constrain depth of reading where possible.

**File handoff discipline.** Do not use chat's file-download or file-
presentation tools for repo-bound files. Any content that belongs in 
the repo (session logs, specs, notes, docs) is drafted as text in chat, 
copied by Ahmed, and committed via Claude Code in a single prompt. 
Using GitHub's web UI to upload files (as happened 2026-04-21) fragments 
history with generic "Add files via upload" commits that duplicate 
atomic work already staged locally. If Ahmed is unclear where a file 
goes, Claude provides the exact target path in the Claude Code prompt.

---

## Active credentials and paths

- Copernicus Dataspace: ahmadxgpx@gmail.com
- Sentinel Hub OAuth: stored in `.env` (gitignored)
- GitHub: `a7zain/sar-change-detection`
- Local path: `/Users/a7zain/sar-change-detection`
- Conda env: `sarsat`

---

## Open questions and things to decide

- Chart design per project chapter (Qiddiya = built area, KSP = NDVI,
  Diriyah = TBD — probably vegetation/built blend). Defer until site
  skeleton exists.
- SAR-optical fusion design spec: to be drafted before Phase 1 build 
  begins. Held for now pending cleanup completion.
- Outreach message framing: draft closer to send date, not now.

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

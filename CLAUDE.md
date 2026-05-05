# Basira — Working Context for Claude

## Purpose

Working context for all Claude sessions on Basira. Lives in repo root, not shipped to readers. Read at session start, update at session end.

## Current State (as of 2026-05-05 mid-session)

**Project:** Basira (بصيرة) — Saudi satellite change monitoring. Phase 1 deliverable is a portfolio-with-research-engine: cinematic homepage as table of contents (Qiddiya hero, KSP, Diriyah Gate), each linking to a real research deep-dive that answers one umbrella question with rigor. Live at https://a7zain.github.io/basira/. Repo: `a7zain/basira`. Shaped for a specific Saudi space-sector opportunity (TPM-track read). Specifics in `.private/context.md` (gitignored).

**Piece B (dust-honesty):** SHIPPED. V1 prose at commit `8c83854` (structural-review pass complete, 6 edits applied, 4760 words, 8 sections). Headline: NDVI bias from Sen2Cor aerosol underestimation is sub-operational at Riyadh (−0.002 NDVI per IQR AOD, 95% CI lower bound −0.003). Side-finding: six independent lines of evidence that Qiddiya is contaminated by construction substrate, not aerosol.

**Piece A (construction-substrate-by-site):** Pre-registration LOCKED at commit `afcf80c`. Six sub-questions (SA1–SA6) with halt conditions, dual criterion at SA3, pre-scoped fallbacks (SA4C, SA5B). Path: `research/construction-substrate-by-site/docs/pre_registration.md`.

**Active work:** SA1 parked. Compute script committed at `26c7cdd` (`research/construction-substrate-by-site/scripts/sa1_compute_bsi.py`), 1-month batches with timeouts and retries, 456 batches total, ETA ~3.5h at full speed. Earth Engine soft-throttle hit during execution; resume requires waiting for the sliding 24h quota window to reset. Resume command in `research/construction-substrate-by-site/scripts/sa1_run_log.md`. Outputs (per-AOI CSVs, SA1_summary.md) will be produced by the resume run.

**SA1 execution findings (locked, surface in piece A methods prose):**
- All three AOIs (Qiddiya, KSP, Diriyah) sit in MGRS tile 38RPN. Single-tile coverage means cross-AOI scene cadence is identical by construction.
- HLS `filterBounds` is broken on Earth Engine for the HLS catalog. Workaround: filter by `ee.Filter.stringContains('system:index', '38RPN')`. Methods note for any future HLS-on-GEE work.
- B8A locked as S30 NIR (855–875nm) for cross-sensor overlap with L30 OLI Band 5 (845–885nm). Documented in script docstring + SA1_summary.md when the resume run lands.

**SA3 implementation spec:** Locked at `research/construction-substrate-by-site/docs/sa3_implementation.md`. Reuses piece B NDVI residuals + AOD tables directly. S30-only. Pooled-with-FE headline + per-AOI heterogeneity check, both pre-registered.

**Multi-city expansion** parked on `wip/phase5-multicity`. Not active; deferred post-piece-A.

## Piece A Umbrella Question (Locked)

Does substrate-aware L30+S30 fusion reduce false-positive change detections at active-construction Vision 2030 sites relative to S30-alone?

Audience: TPM-track Saudi space-sector hire. Primary deliverable: technical methods memo (3–5 pages, SARsatX read). Three site-level research pieces (Qiddiya hero, KSP, Diriyah) as supporting assets. Time budget: 6–10 weeks SA1–SA6 + 4 weeks prose. Hard cap, halt and re-scope if blown.

Scope conditional pre-registered: piece A has no external ground-truth label set. SA5 uses piece B V4-fire + high-BSI as contamination labels. Answer is conditional on that framing — claim "pipeline flags differently," not "this is real change."

## Key Decisions (Locked, Not to Be Relitigated)

- Cinematic over dashboard; single-page scroll; Qiddiya hero
- AI-generated imagery prohibited (every pixel real satellite data)
- No toggles on main scroll; methodology chapter multi-mode figure carries that weight
- Phase 4 analytics hidden not deleted
- B8A locked for S30 NIR in BSI (cross-sensor matching)
- Stop-rule philosophy carries from piece B: halts ride into prose as findings, not appendix
- Fallback sub-questions (SA4C, SA5B) pre-scoped but require own pre-registration before execution
- Out of scope for piece A: SQ8B (KAUST coastal), SAR-optical fusion, substrate composition by mineralogy, multi-city

## How I Work (Session Protocol)

**Division of labor:** This chat = strategy, scoping, pushback, exact Claude Code prompts. Claude Code = all execution.

**Claude Code prompt rules (mandatory):**
1. Open with: *"Work directly on the main working tree. Do NOT create a git worktree under `.claude/worktrees/`. If you think you need one, stop and ask."*
2. No "show me each diff" gates. Autonomous end-to-end. Stop only for destructive/irreversible cases.
3. Verify with `git status` + `git log --oneline -10` at end. Single review point.

**Pacing:** Default is continue. Keep prompts compact, less back-and-forth. Flag genuine concerns (time cap, scope risk, real fork) but do not pause-and-check at natural junctures.

**End-of-session ritual:** Full file replacements for `CLAUDE.md` + dated `docs/sessions/YYYY-MM-DD.md`. Ahmed overwrites local, commits, pushes, clicks "Sync now" in Project.

**Push state note:** HTTPS pushes from Claude Code session blocked on credentials. Ahmed runs `git push origin main` from his shell after Claude Code commits land locally.

## Worktree Hygiene Warning

Claude Code has historically created silent worktrees and reported success while editing off-main. Guardrail in every prompt. Post-commit verification: `git status`, `git log --oneline -10`, `find . -name <file> -not -path '*/.git/*'` before trusting any "committed" report.

## Tools & Resources

**Satellite data:**
- Sentinel Hub (Copernicus Dataspace): `ahmadxgpx@gmail.com`, OAuth in `.env`
- Google Earth Engine: project `basira-494617` (HLS S30/L30, MERRA-2, CAMS, TROPOMI)

**Processing:**
- Python, rasterio, `sarsat` conda environment (`/opt/anaconda3/envs/sarsat/bin/python`)
- Piece B engine: `research/dust-honesty/scripts/` (61 .py files, full pre-reg + findings chain)
- Piece A engine: `research/construction-substrate-by-site/` (initialized; SA1 in progress)

**Site & deployment:**
- Static HTML/CSS/JS, Leaflet.js, Chart.js 4.4.1
- Live at `a7zain.github.io/basira` (GitHub Pages auto-deploy from main)

**Key repo files:**
- `CLAUDE.md` (this file)
- `basira_master_plan.md`
- `site_spec.md`
- `research/dust-honesty/piece_b.md` (V1 shipped)
- `research/construction-substrate-by-site/docs/pre_registration.md` (locked)
- `docs/sessions/YYYY-MM-DD.md`
- `.private/context.md` (gitignored)

## Recent Commit Trail

- `26c7cdd` piece A SA1: compute script committed, EE quota throttle parked execution
- `afcf80c` piece A: pre-registration locked (SA1–SA6)
- `8c83854` piece B: structural-review pass (6 edits, V1 ships)
- `e49df27` piece B: cosmetic docstring/comment sweep
- `560f8c3` piece B: V1 prose ships (post-structural-review) [superseded by 8c83854]
- `66af2f1` piece B: V1 prose draft (post-polish)
# Basira — Working Context for Claude

## Purpose

This file is the working context for all Claude sessions on the Basira project. It lives in the repo root and is not shipped to readers; it's the session-to-session calibration artifact. Read it at the start of any session. Update it at the end with the current state and the next active work.

## Current State (as of 2026-05-04 end-of-session)

**Project:** Basira (بصيرة) — Saudi satellite change monitoring. Phase 1 deliverable is a portfolio-with-research-engine: cinematic homepage as table of contents (three Vision 2030 megaproject chapters — Qiddiya hero, King Salman Park, Diriyah Gate), each linking to a real research deep-dive that answers one umbrella question with rigor. Live at https://a7zain.github.io/basira/. Repo: `a7zain/basira`. Shaped for a specific Saudi space-sector opportunity (TPM-track read) — execution story over methodological novelty. Specifics in `.private/context.md` (gitignored).

**Piece B (dust-honesty) status:** V1 prose shipped 2026-05-04 at commit `e49df27`. Structural-review pass complete (5 flags applied, 175 docstring/comment cosmetic fixes, captions verified consistent). The piece is now publicly shippable at the research-engine level: four supporting figures (Figure 1–4), eight sections (§0–§7), 4956 words, full pre-registration + findings chain, methodology appendix complete.

**Active work post-piece-B:** Piece A (construction-substrate-by-site) scoped and ready to execute. The dust question answered piece B — "does aerosol corrupt NDVI at Riyadh?" No, not operationally. But piece B also surfaced six independent lines of evidence that Qiddiya is contaminated by construction substrate, not aerosol. Piece A is where that finding lives in detail: substrate-aware change detection at three Vision 2030 sites, substrate-phase-specific fingerprints, and a diagnostic protocol that generalizes to any active-construction site on Vision 2030. The umbrella question for piece A is: "Can a L30+S30 fusion detect substrate-induced contamination and isolate real surface change underneath?" Piece A will ship with a technical methods memo as the primary artifact for SARsatX read — the research site will be the supporting asset.

**Multi-city expansion** parked on `wip/phase5-multicity`. Not active; deferred post-piece-A.

## Key Decisions (Locked, Not to Be Relitigated)

- Cinematic over dashboard: homepage is single-page scroll, not multi-view selector
- Hero timelapse is Qiddiya (strongest story + construction-substrate finding)
- KSP at full polygon footprint, Diriyah at full polygon footprint
- AI-generated imagery explicitly prohibited (every pixel must be real satellite data)
- Phase 4 analytics hidden not deleted (parked in repo under non-public path for potential future activation)
- No toggles on main scroll; feature toggles redirected to methodology chapter multi-mode figure
- Scroll-linked video scrubbing parked as methodology-future decision

## How I Work (Session Protocol)

**Division of labor:** This chat (Claude) handles strategy, architecture, spec-enforcement, and exact Claude Code prompts. Claude Code (the executor) handles all implementation end-to-end.

**Claude Code prompt rules (mandatory):**
1. Every prompt opens with: *"Work directly on the main working tree. Do NOT create a git worktree under `.claude/worktrees/`. If you think you need one, stop and ask."*
2. Skip "show me each diff" / "wait for approval" gates. Autonomous end-to-end execution. Only stop for destructive/irreversible cases (force push, mass delete, credential exposure, history rewrite).
3. Phrase as: full sequence → verify with `git log`/`git status` at end → report results. Single review point at end.

**Basira end-of-session ritual (mandatory, every session):**
Produce complete drop-in file replacements (not section edits) for:
- `CLAUDE.md` (this file, full file)
- `docs/sessions/YYYY-MM-DD.md` (dated session log, full file)

Ahmed overwrites local files, commits, pushes, then clicks "Sync now" in Claude Project (Projects don't auto-sync from GitHub). Ahmed prefers overwriting complete files, not editing sections.

**Pacing:** Do not suggest stopping, pausing, or taking breaks between sections or at natural junctures. Default is continue until Ahmed says stop. Genuine concerns (time cap blown, scope risk, real fork in the road) can still be flagged — but default is keep going, not pause-and-check.

**Commits:** Atomic commits with accurate messages. Use `git mv` for file moves to preserve rename history. Run `git status` after every Claude Code step before trusting "done."

**Scope management:** Ahmed proposes scope expansions frequently. Claude pushes back directly, citing `site_spec.md`. Ahmed has consistently agreed when pushback is specific and grounded.

**Diagnostic discipline:** Three wrong hypotheses explored before ground-truth pixel stats revealed actual mask-alignment cause. Don't fix before diagnosing. Approach: check and verify, don't assume and trust.

## Worktree Hygiene Warning

Worktree drift is a silent killer. Claude Code has silently created git worktrees in the past (April 8: `relaxed-villani`/`determined-buck`, April 13: `heuristic-borg`, `epic-kalam`) and reported "committed and pushed" while edits landed off-main. The guardrail is in place (every Claude Code prompt leads with the worktree check). But the risk is real: **every Claude Code dispatch must verify working state with `git status` and `git log --oneline -5` before trusting any "committed" report.**

Post-commit verification pattern: After any Claude Code "N insertions" report, verify with `find . -name <file> -not -path '*/.git/*'` (expect one path) and `git status` (expect file modified, then committed) before trusting the edit landed.

## Tools & Resources

**Satellite data:**
- Sentinel Hub (Copernicus Dataspace): `ahmadxgpx@gmail.com`, OAuth credentials in `.env`
- Google Earth Engine: project `basira-494617` (HLS S30/L30, MERRA-2, CAMS, TROPOMI)

**Processing:**
- Python, rasterio, `sarsat` conda environment (`/opt/anaconda3/envs/sarsat/bin/python`)
- Key scripts: `src/phase1_download.py`, `src/phase1_backdrops.py`, `src/change_detect.py`, `src/preprocess.py`
- Research engine lives under `research/dust-honesty/scripts/` (61 .py files, fully documented with pre-registration + findings)

**Site & deployment:**
- Static HTML/CSS/JS, Leaflet.js, Chart.js 4.4.1
- Live at `a7zain.github.io/basira`
- GitHub Pages auto-deploys from main on any push

**Key repo files:**
- `CLAUDE.md` (this file)
- `basira_master_plan.md` (project arc, timelines, credential notes)
- `site_spec.md` (locked design decisions, scoping pushback anchor)
- `docs/sessions/YYYY-MM-DD.md` (dated session logs, full history)
- `docs/phase4_notes.md` (parked analytics, decision notes)
- `.private/context.md` (SARsatX-specific strategic context, gitignored)

**Hardware & identity:**
- MacBook Pro (primary): native shell, direct repo access, `ahmadxgpx@gmail.com` git identity
- Galaxy-A14 (secondary): Termux, requires `git config --global user.email/user.name` before commits
- Primary device is macOS; secondary is Android

**Learning track:**
- Coursera "Mathematics for Machine Learning and Data Science" specialization (registered, concurrent)
- Andrew Ng ML Specialization Course 1 (concurrent, given Ahmed's university math background)
- Book in use: *Why Machines Learn*
- All Notion updates Claude handles automatically; Ahmed does not read/edit Notion directly

## Notion Integration

Claude handles all Notion updates automatically. Main plan page ID: `316a819e-5d31-8125-9eba-d9e1a4d2e9c9`. Updates page ID: `316a819e-5d31-801c-9090-faef1e205537`. Log entries are short, first-person, written as if Ahmed is writing them. Insertion method: `insert_content_after` with `selection_with_ellipsis` targeting a unique string near end of content — reliable for appending log entries.

## Credential Hygiene

Sentinel Hub OAuth credentials have required multiple rotations due to exposure. Credentials live in `.env` only; **never commit `.env`** and **never paste credentials in chat**. `.env` is opened via `open -a TextEdit .env` (nano's Ctrl keys are intercepted by Terminal.app on macOS). Galaxy-A14 secondary device can access `.env` via termux but should never push credential-containing commits.

## Session Workflow Patterns

**Energy/state check-in:** At session start, explicit check-in on energy level and directions. Default is action-over-deliberation unless a genuine blocker surfaces.

**Session logs drafted by Claude:** Not by hand. Pasted from Claude at end-of-session, committed as full-file replacement via the ritual.

**Master plan updates:** Reserved for direction changes, not progress updates. Session logs are the granular record; master plan gets updated if scope, timeline, or strategic framing shifts.

**Cleanup passes:** Only at objective boundaries (after piece ships, after a phase closes, before a new major direction). Not between subsections. Default is momentum.

## How to Read This File

1. **At session start:** Read "Current State" first. That tells you where the work landed and what's active.
2. **Before sending Claude Code:** Refresh on "Claude Code prompt rules" — it's the checklist.
3. **For disagreement resolution:** "Spec is the pushback anchor" — if Ahmed proposes something that contradicts `site_spec.md`, cite the spec verbatim.
4. **For session planning:** "Pacing" section sets the default rhythm. "Session workflow patterns" surfaces what actually happens across sessions.

---

Last updated: 2026-05-04 end-of-session (piece B V1 prose ships, piece A scoped).

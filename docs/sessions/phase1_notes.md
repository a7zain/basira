# 2026-04-29 — SQ1D KSP relabel on tightened bbox; Qiddiya parallel relabel; reference lock-in

## Headline

Closed out SQ1D's reference-selection arm. Re-ran KSP UVAI search and rendering on the tightened 16.6 km² bbox, caught a methodology hole (UVAI in test caption would taint AI pre-label), expanded relabel scope to Qiddiya (construction-active AOI, same confound risk), AI-pre-labeled all 24 construction-active test scenes blind to UVAI and old labels, locked KSP reference at 2023-10-27, and consolidated all three AOI references into a canonical JSON config. 8 commits pushed; working tree clean.

## What happened

Came in pumped, fresh chat. The intro template I pasted was stale (still referenced "Riyadh prototype complete... next phase: monthly temporal resolution, then multi-city expansion" — pre-2026-04-20-pivot framing). Claude flagged that, surfaced current state from CLAUDE.md, asked for energy/state check-in, recommended commit/curate first then KSP re-run. Both confirmed.

### Pass 1 — Cleanup of 2026-04-28's uncommitted work (4 atomic commits)

The 2026-04-28 session ended with 8+ uncommitted SQ1D scripts and supporting data. Pass 1 organized them into atomic commits with `.gitignore` safety check up front and force-add precedent for `research/dust-honesty/data/` per `442d7b0`.

- `e95424a` — SQ1D reference selection + UVAI cross-check pipeline (9 scripts)
- `f779f66` — SQ1D KSP bbox verification thumbnails (2 PNGs)
- `cc19de1` — SQ1D Qiddiya reference candidates + UVAI cross-check (8 files)
- `8947617` — SQ1D KSP pre-bbox-tightening artifacts (will be superseded; preserved as research history so the bbox-change diff is readable in git log)

Smart catch from Claude Code: the bbox code change (`src/phase1_aois.py`, `data/phase1/aois/phase1.kml`) was already in `119db1b` from the prior session, so Commit B carries only the visual-verification PNGs and references the prior SHA in its body. Working tree had no diff for those files.

### Pass 2 — KSP UVAI all-months search + thumbnails on tightened bbox

Re-ran the SQ1D pipeline on the tightened 16.6 km² KSP bbox. Pulled 320 valid TROPOMI overpasses (2020-01 through 2026-03; 2026-04 had 0 cloud-free S2 scenes). UVAI mean range −1.44 to +3.85, median ~+0.79; 59 scenes with UVAI mean < 0.3.

Stratified KSP reference candidate pool: Pool A (top-3 by UVAI ascending across full window — early-clean atmosphere) + Pool B (top-3 from 2023-01 onward — recent-clean atmosphere). 6 candidates total, 2 of which were new dates added by the bbox change (2020-12-31, 2021-01-05).

Per-AOI 2/98 stretch on the new bbox: R [0.162, 0.470], G [0.156, 0.368], B [0.159, 0.300]. Materially shorter hi values than the old bbox (R hi 0.637→0.470). The shrinkage is real: removing the bright urban perimeter changed the radiometric calibration target. Worth a sentence in piece B's appendix.

Two anomalies caught by Claude Code:
1. **Stretch zero-floor bug.** First render produced lo=0.000 for all three channels because no-data padding pixels hit the 2nd percentile. Fixed by filtering `v > 0` before the percentile.
2. **11 KSP test scenes, not 10.** CLAUDE.md said "10 KSP test scenes." Source CSV (`sq1_manual_labels.csv`) has 11 KSP rows. Total split is 6 diriyah / 11 KSP / 13 qiddiya = 30. SQ1's stratification was by season, not equal-count per AOI. Updated in tonight's CLAUDE.md.

Commits this pass:
- `b131535` — UVAI all-months search + reference candidates (scripts + CSVs)
- `a5ea00a` — Candidate + test thumbnails, stretch JSON, relabel CSV (initial — UVAI in caption, will be superseded next pass)

Headline finding: **every "clean"-labeled KSP scene from 2021-07 onward had UVAI ≥ 1.16.** Visual labels at construction-active KSP fail because construction substrate visually mimics haze. Piece B's finding starting to write itself before any relabeling has happened.

### Pass 3 — Methodology catch and relabel scope expansion

Before doing AI pre-label on the new test montage, caught that the test thumbnails had UVAI in caption. That collapses the methodology footnote: if a reviewer asks "did the AI see the UVAI when labeling?" the only safe answer is "no." Otherwise SQ3 (which validates the threshold against UVAI) leaks back into SQ1's labels. Decision: re-render test montage with date-only caption. Cost is small, methodological tightness benefit is large.

While at it, raised the bigger question: Qiddiya is also construction-active. If KSP's visual labels are systematically wrong because construction substrate mimics haze, Qiddiya's 13 test scenes likely have the same problem. Relabeling only KSP would leave SQ1B's re-run with an asymmetric calibration set: 11 KSP (clean-relabeled) + 13 Qiddiya (contaminated visual labels) + 6 Diriyah (probably OK).

Decision: relabel KSP + Qiddiya in parallel. Diriyah is surface-stable, original labels stand.

### Pass 4 — Visually-blind relabel templates

Re-rendered KSP test (11 scenes, tightened bbox, stretch loaded from JSON) and Qiddiya test (13 scenes, unchanged bbox, SQ1-original stretch hardcoded then persisted to JSON for apples-to-apples comparison). Captions: date only. No UVAI, no old label, no AOI text.

Smart sequencing from Claude Code: ran the distribution-check step first (cheap, no GEE) to verify the 6/11/13 split before spending GEE budget on rendering. Saved a re-run cycle if the source data had been wrong. (It wasn't.)

Relabel CSV schema: `date, sub_aoi, old_label, ai_prelabel, ai_confidence, ai_reasoning, final_label`. Old label populated from `sq1_manual_labels.csv`; AI columns left blank for the labeling pass.

Commit: `e63b227` — visually-blind relabel templates for KSP + Qiddiya.

### Pass 5 — AI pre-label workflow

Ahmed uploaded both test montages plus the KSP candidate montage (with UVAI captions, correct as-is for reference selection — UVAI is INPUT to selection, not a label). Claude pre-labeled all 24 test scenes against the explicit rubric:

> **clean** — high scene contrast, sharp edges between bright/dark surfaces, no veiling.
> **light_haze** — reduced contrast, slight blue-shift, edges softer but still visible.
> **heavy_dust** — warm/yellow-orange cast across scene, edges muted or absent in patches, possible plume.
> **cloud** — bright white opaque coverage, sharp-edged, not yellow.
> **mixed** — combinations not cleanly fitting any single category.
>
> Construction substrate (bare beige/tan ground that is sharp-edged and stable across multiple dates) is a SURFACE feature, not atmospheric. Atmospheric features must be scene-wide veiling, not localized.

The construction-substrate exclusion is the load-bearing addition vs SQ1's original rubric. Names the failure mode that contaminated the original visual labels.

KSP pre-label distribution: 7 clean / 3 light_haze / 1 heavy_dust.
Qiddiya pre-label distribution: 11 clean / 2 light_haze / 0 heavy_dust.

Each row has `ai_confidence` (high/medium/low) and `ai_reasoning` (one sentence per scene).

KSP reference recommendation: **2023-10-27** (Pool B rank 1, UVAI −0.067), with **2024-12-05** as sensitivity alternate. Reasoning: Pool A scenes (2020-2021) show pre-demolition Riyadh Air Base — surface state matches only 1 of the 11 test scenes. Pool B candidates match the post-demolition surface that most test scenes show. Within Pool B, 2023-10-27 wins on UVAI (−0.067 vs +0.336) and sits midway through the construction evolution.

### Pass 6 — Researcher review

Ahmed reviewed both montages at full resolution and confirmed all 24 AI pre-labels without override. Confirmed KSP reference at 2023-10-27 (sensitivity alternate 2024-12-05) and acknowledged the 2025-11-27 candidate render silent failure as flag-only-not-fix this session.

The 2025-11-27 candidate failure is worth noting: bottom-right slot in `sq1d_ksp_ref_montage.png` is black with caption only. Claude Code reported the candidate render as successful; the silent failure was caught by visual review of the montage. Stop-on-fail guard didn't fire. Doesn't block (reference is locked at 2023-10-27 regardless), but worth fixing the guard before any future thumbnail batch run.

### Pass 7 — Merge and lock

Single commit `859450e`:
- 24 rows populated across both relabel CSVs (`final_label = ai_prelabel`).
- KSP reference locked at 2023-10-27.
- Canonical `sq1d_references.json` consolidating all 3 AOI references (Qiddiya, KSP, Diriyah).

Cross-check tolerance check (5 ppm tolerance vs CSVs):
- Qiddiya 2024-01-20 UVAI: JSON 0.310 vs CSV 0.3096, diff 0.0004 ✓
- KSP 2023-10-27 UVAI: JSON −0.067 vs CSV −0.0673, diff 0.0003 ✓
- Diriyah skipped — no all-months UVAI CSV exists yet (queued).

## Reference scenes locked (canonical: `sq1d_references.json`)

| AOI | Primary | UVAI | Sensitivity alternate |
|---|---|---|---|
| qiddiya_core | 2024-01-20 | +0.310 | 2021-01-10 (UVAI −1.166) |
| king_salman_park | 2023-10-27 | −0.067 | 2024-12-05 (UVAI +0.336) |
| diriyah_gate | 2020-04-25 | +0.082 | none (surface-stable) |

KSP rationale captured in JSON: Pool B rank 1; midway through KSP construction evolution; matches surface state of post-demolition test scenes (10 of 11). Pool A candidates (2020-2021) show pre-demolition Riyadh Air Base — surface state matches only 1 test scene.

## Findings captured for piece B

1. **Bidirectional label disagreement at construction-active AOIs (10/24 disagreements).** KSP under-flagged haze (2 → 4 non-clean); Qiddiya over-flagged haze (4 → 2 non-clean). Visual atmospheric labeling is unreliable in BOTH directions, depending on scene content. Discussion-section paragraph in piece B.

2. **"Every clean-labeled KSP scene from 2021-07 onward had UVAI ≥ 1.16."** Construction substrate at construction-active AOIs visually mimics haze, contaminating original visual labels. Methodology evolution: visually-blind labeling on cropped-to-AOI thumbnails, with explicit construction-substrate exclusion rule.

3. **Bbox change shifts radiometric calibration target.** KSP per-AOI stretch hi values shrunk markedly when the bbox tightened from 29.93 km² to 16.6 km² (R hi 0.637 → 0.470). The bbox change isn't just a scoping decision — it's a radiometric-calibration decision. Appendix-worthy.

## Decisions made (don't re-litigate)

- **KSP + Qiddiya parallel relabel** chosen over KSP-only. Methodological consistency for SQ1B re-run. Diriyah excluded — surface-stable AOI.
- **Visually-blind relabel protocol** locked. Date-only caption on test thumbnails. UVAI is post-labeling audit, never input. Methodology footnote updated in CLAUDE.md.
- **Construction-substrate exclusion rule** added to the rubric as the load-bearing addition vs SQ1's original rubric.
- **KSP reference at 2023-10-27** (Pool B rank 1, UVAI −0.067) locked; sensitivity alternate 2024-12-05 (UVAI +0.336).
- **Canonical references config at `sq1d_references.json`** consolidating all 3 AOIs. Downstream Part B compute reads from this single source.
- **Construction-active AOI relabels are final.** `final_label = ai_prelabel` for all 24 rows; researcher confirmed without override. SQ1B re-run uses these.

## What's next

1. **SQ1D Part B: implement Lolli's faithful formula on GEE.** Per-band TOA differential normalized by L2A reference reflectance, computed across all 30 calibration scenes against the 3 locked references. Non-trivial implementation; expect iteration cycles. Deserves its own session.
2. **Part B': sensitivity check.** Re-compute Part B with Qiddiya and KSP sensitivity-alternate references. Catches threshold sensitivity to surface evolution.
3. **SQ1B re-run** on faithful Lolli output across the relabeled 30-scene calibration set.
4. **Diriyah all-months UVAI CSV** — generate `sq1d_diriyah_uvai_all.csv` for audit completeness.
5. **Investigate 2025-11-27 KSP candidate render silent failure** — fix the stop-on-fail guard before any future thumbnail batch run.

## Commits this session

- `e95424a` SQ1D reference selection + UVAI cross-check pipeline (9 scripts)
- `f779f66` SQ1D KSP bbox verification thumbnails (2 PNGs)
- `cc19de1` SQ1D Qiddiya reference candidates + UVAI cross-check (8 files)
- `8947617` SQ1D KSP pre-bbox-tightening artifacts (will be superseded)
- `b131535` SQ1D KSP UVAI all-months search on tightened bbox
- `a5ea00a` SQ1D KSP candidate + test thumbnails, stretch JSON, relabel CSV (initial — superseded next pass)
- `e63b227` SQ1D visually-blind relabel templates for KSP + Qiddiya
- `859450e` SQ1D merge AI pre-labels and lock KSP reference at 2023-10-27

8 commits, all on origin/main, working tree clean.

## Files touched this session

- 4 cleanup commits (committed earlier-session artifacts)
- `research/dust-honesty/data/sq1d_ksp_uvai_all.csv` (regenerated on tightened bbox)
- `research/dust-honesty/data/sq1d_ksp_reference_candidates.csv` (new)
- `research/dust-honesty/data/sq1d_ksp_ref_thumbnails/*` (regenerated on tightened bbox)
- `research/dust-honesty/data/sq1d_ksp_test_thumbnails/*` (regenerated, date-only caption)
- `research/dust-honesty/data/sq1d_qiddiya_test_thumbnails/*` (new directory)
- `research/dust-honesty/data/sq1d_ksp_stretch.json` (new — per-AOI stretch on tightened bbox)
- `research/dust-honesty/data/sq1d_qiddiya_stretch.json` (new — SQ1-original stretch persisted)
- `research/dust-honesty/data/sq1d_ksp_relabel.csv` (rewritten in new schema, populated)
- `research/dust-honesty/data/sq1d_qiddiya_relabel.csv` (new, populated)
- `research/dust-honesty/data/sq1d_references.json` (new — canonical config)
- `research/dust-honesty/scripts/sq1d_ksp_test_blind.py` (new)
- `research/dust-honesty/scripts/sq1d_qiddiya_test_blind.py` (new)
- `research/dust-honesty/scripts/sq1d_relabel_templates.py` (new)

## Lessons reinforced

- **Stale intro templates miss pivots.** The intro pasted at session start was pre-2026-04-20-pivot framing. Reading CLAUDE.md and the master plan first surfaced the gap before any work happened. Worth normalizing into the workflow that the chat starts with the load and not the intro.
- **Methodology holes show up at the seam between pipeline steps.** UVAI in test caption was technically correct for review purposes but methodologically wrong for AI pre-label input. Caught at the right moment (before pre-labeling started). Cost of catching late would have been re-running the entire pre-label pass with disclosed methodology drift.
- **Cheap distribution-checks before expensive GEE renders.** Claude Code's instinct to run the count-verification step first saved an entire GEE budget cycle in case the source data was wrong.
- **Asymmetric calibration sets are silent failures.** If we'd relabeled only KSP, SQ1B would have run on 11 clean-relabeled + 13 contaminated + 6 OK rows. The threshold tuning would have been confounded by labels that were systematically wrong on Qiddiya. Catching this required pattern-matching across AOIs ("if construction-substrate confound applies at KSP it applies at Qiddiya too").
- **Force-add precedents earn their keep.** The `442d7b0` precedent for forcing past `research/dust-honesty/data/` gitignore meant every step today could write calibration data without arguing with `.gitignore`.
- **Visual review is part of verification.** The 2025-11-27 candidate render silent failure didn't trigger the stop-on-fail guard. Catching it required eyeballing the montage Ahmed uploaded to chat. "Verification discipline" includes looking at the images, not just trusting the success message.
- **2026-04-28 pre-bbox-tightening artifacts as research history.** Committing them deliberately (rather than orphaning) made today's bbox-change diff readable in git log: the same dates, with new bbox + new stretch, sitting next to the originals in commit `8947617`.

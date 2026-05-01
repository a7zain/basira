# SQ1C — Researcher confirmation pass protocol

**Status:** v0 (2026-05-01).
**Predecessor:** `sq1c_protocol.md` §4a (preliminary AI-only labels, 2026-04-30 session 3).
**Blocker this unblocks:** SQ1B re-re-run on confirmed labels (`sq1b_rerun_v2_confirmed.py`),
which removes the PRELIMINARY status from the V3/V4 ship results.

---

## 1. Purpose

The SQ1C 43-scene calibration-set expansion was AI-pre-labeled by chat-Claude
against the SQ1D Pass 5 rubric (clean / light_haze / heavy_dust / cloud / mixed
+ construction-substrate exclusion rule) on 2026-04-30 evening. Researcher
confirmation at full resolution was deferred to this pass.

The output of this pass is `confirmed_label` for every SQ1C row. Once it lands,
SQ1B re-re-run (V1–V4) is rerun on confirmed labels and the result ships as
non-preliminary if the stop rule still holds.

---

## 2. Two protocols: standard and cold

### Standard protocol (37 rows)

Rows where `bias_exposed_during_ai_labeling=False`. The AI pre-label is shown
to the researcher; pressing Enter accepts the AI pre-label as confirmed (the
common case). Override by typing a different choice.

### Cold protocol (6 rows — the bias-exposed set)

Rows where `bias_exposed_during_ai_labeling=True`. The AI pre-label is NOT
shown. The researcher labels the scene blind, against the same rubric, with
no anchor. This breaks the contamination chain: chat-Claude saw partial UVAI
information (top-3 candidate values per AOI) in an intermediate session report
before pre-labeling these 6 scenes. Cold-labeling produces a researcher-only
label that is independent of that contamination.

The 6 cold rows:

| AOI | Date |
|---|---|
| Qiddiya | 2022-04-10 |
| Qiddiya | 2024-03-10 |
| KSP | 2025-07-15 |
| Diriyah | 2022-05-10 |
| Diriyah | 2022-05-20 |
| Diriyah | 2022-05-25 |

`review_protocol` is recorded as `'standard'` or `'cold'` per row.

---

## 3. What the researcher sees (and does not see) at labeling time

**Visible per row:**
- AOI name + date + S2 system index + S2 cloud%
- Reviewer protocol (STANDARD or COLD)
- AI pre-label (STANDARD only)
- The thumbnail itself (opened in macOS Preview via `open -g`)

**Hidden at labeling time (regardless of protocol):**
- TROPOMI UVAI value
- The pre-existing `final_label` (which equals `ai_prelabel` from session 3)
- Any HLS/DBB/derived signal

This rule is locked in CLAUDE.md from 2026-04-30 ("Do not surface candidate
UVAI values in chat output before AI pre-labeling completes"). The same rule
applies to the researcher's confirmation pass: UVAI is the *selector* that
chose which months to pull and a *post-hoc audit* signal; it is never an
input to the visual label. Conflating the two collapses SQ3 validation into
circularity.

---

## 4. Tooling and autosave behavior

Entry point: `research/dust-honesty/scripts/sq1c_label_review.py`.

```
python sq1c_label_review.py --aoi qiddiya
python sq1c_label_review.py --aoi ksp
python sq1c_label_review.py --aoi diriyah
```

Single-keystroke prompts:
```
[c]lean / [l]ight_haze / [h]eavy_dust / [m]ixed / [cl]oud / [s]kip / [q]uit
```

- **Standard rows:** Enter accepts the AI pre-label as confirmed.
- **Cold rows:** no default; must type a choice explicitly.
- **`s`** leaves the row blank; `--resume` (default) skips it next run.
- **`q`** saves and exits cleanly.

Per-row autosave: every confirmation writes back to the CSV immediately, so
Ctrl+C / quit-mid-pass loses nothing. `--no-resume` re-prompts every row,
including ones already confirmed (use only if a redo of an entire AOI is
intended).

Optional reviewer notes are captured into `reviewer_notes` per row. Use them
liberally — disagreement reasoning, edge cases, scenes worth revisiting at
piece B writeup time.

---

## 5. Audit step (post-confirmation)

`research/dust-honesty/scripts/sq1c_label_comparison.py` is the audit
script. Run it AFTER all three AOIs are fully confirmed. It reports:

- AI–researcher agreement rate per AOI and overall.
- Disagreement table with UVAI, protocol, notes — for piece B prose.
- Cold-protocol-specific block: did cold-labeling agree with the AI
  pre-label for the 6 bias-exposed rows? This is the
  contamination-broke-or-not signal.
- UVAI sanity audit per (AOI, confirmed_label) cell — mean and quartiles.
  Flags anomalies (e.g. `clean` with UVAI > +2.0, `heavy_dust` with
  UVAI < +1.0) as piece B discussion-section candidates.

UVAI values are first surfaced HERE, never during labeling.

---

## 6. After confirmation: SQ1B re-re-run on confirmed labels

`research/dust-honesty/scripts/sq1b_rerun_v2_confirmed.py` reads
`confirmed_label` (instead of `final_label`) from the SQ1C rows; SQ1D rows
continue to use their existing labels (already researcher-confirmed in
SQ1D Pass 5). Outputs go to a parallel set of files prefixed
`sq1b_rerun_v2_confirmed_*` and `sq1bc_combined_calibration_confirmed.csv`,
so the preliminary results from session 3 are preserved untouched for
audit.

The threshold-spec markdown explicitly compares confirmed-vs-preliminary
AUC and threshold per variant V1–V4 and calls out any ship/no-ship change.

---

## 7. Methodology footnote update (post-confirmation)

Once confirmation lands, the binding methodology footnote in `CLAUDE.md`
and any piece B writeup is updated as follows:

- Replace the SQ1C paragraph's "Researcher confirmation at full resolution
  was deferred to a later cleanup pass" sentence with: "Researcher
  confirmation at full resolution was completed on YYYY-MM-DD; X of 43
  AI pre-labels were overridden."
- Replace "SQ1B re-re-run results derived from this set are PRELIMINARY
  pending researcher review" with the actual confirmed-vs-preliminary
  delta from `sq1b_rerun_v2_confirmed_threshold_spec.md`.
- Retain the bias-exposed disclosure verbatim (the 6 rows remain
  flagged in the data even after cold-labeling; the cold protocol
  is the audit, not an erasure).

Until that update happens, `sq1b_rerun_v2_*` (the session-3 preliminary
results) and `sq1b_rerun_v2_confirmed_*` (the post-confirmation results)
coexist on disk and the preliminary disclaimer stays in force.

---

## 8. References

- SQ1C selection + render protocol: `research/dust-honesty/docs/sq1c_protocol.md`
- SQ1D Pass 5 visually-blind protocol: see CLAUDE.md "Methodology footnote"
- 2026-04-30 contamination incident lesson: CLAUDE.md "Methodology
  contamination via partial UVAI exposure in chat output"
- Session 3 commits: `ee807ce`, `0c0ac6e`, `28ca483`, `1ecc49e`, `99f561e`

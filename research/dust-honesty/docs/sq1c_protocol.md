# SQ1C — Calibration-set expansion via UVAI-anchored positives

**Status:** v0 protocol design (2026-04-30). Pending execution.
**Predecessors:** SQ1D Part B (faithful Lolli compute, commit `76ca513`); SQ1B re-run (`2a019b1`).
**Blocker SQ1C unblocks:** SQ1B re-re-run with tighter bootstrap CI on the dust-flag threshold.

---

## 1. Purpose

Expand the calibration set so SQ1B's bootstrap CI on the Youden threshold drops below the **0.020 DBB-unit half-width** stop-rule budget. Current state is AUC = 0.82–0.84 on V3/V4 scopes (KSP-only and KSP+Diriyah) but CI half-width = 0.046–0.060 with `n_pos ≤ 4`. The blocker is positives, not signal.

Targets:
- **n_pos ≥ 10 per AOI** for V3 and V4 scopes, mixing `light_haze` + `heavy_dust`.
- Bias toward `heavy_dust` where TROPOMI UVAI permits — those are the high-information positives for the threshold fit.
- Keep the visually-blind labeling protocol identical to SQ1D Pass 4 to preserve label provenance for the methodology footnote.

**Scope:** all three AOIs (KSP + Qiddiya + Diriyah) ship in v0; Diriyah's UVAI was unblocked via GEE source per §9.

## 2. Selection rule (UVAI-anchored, SZA-aware)

### Step A — Load all-months UVAI

For each AOI load `research/dust-honesty/data/sq1d_<aoi>_uvai_all.csv`. All three AOIs use GEE `COPERNICUS/S5P/OFFL/L3_AER_AI` as the underlying source (KSP and Qiddiya through `sq1d_ksp_uvai_search.py` / `sq1d_qiddiya_uvai_search.py`, established before this protocol; Diriyah added 2026-04-30 via `sq1d_diriyah_uvai_all_gee.py` per the source-mixing decision in §9). The Diriyah CSV carries an extra `data_source="GEE_OFFL_L3"` column for disambiguation against any future re-pulls.

- KSP: `sq1d_ksp_uvai_all.csv` (320 rows, tightened bbox; commit `119db1b`).
- Qiddiya: `sq1d_qiddiya_uvai_all.csv` (302 rows).
- Diriyah: `sq1d_diriyah_uvai_all.csv` (rows TBA at pull-time; expected ~300–400 by analogy with the other two AOIs at the same bbox class).

### Step B — Negative-class month distribution

For each AOI, count the calendar-month bins of the existing `clean`-labeled scenes from the relabel CSVs (KSP/Qiddiya) or `sq1_manual_labels.csv` (Diriyah, never relabeled because it's surface-stable):

| AOI | Source | n_clean | Month distribution |
|---|---|---:|---|
| KSP | `sq1d_ksp_relabel.csv` (final_label='clean') | 7 | Jan: 3, Feb: 2, Jul: 1, Dec: 1 |
| Qiddiya | `sq1d_qiddiya_relabel.csv` (final_label='clean') | 11 | Jan: 1, Feb: 1, Mar: 3, Apr: 1, Jul: 2, Aug: 1, Sep: 1, Nov: 1 |
| Diriyah | `sq1_manual_labels.csv` (label='clean') | 5 | Feb: 1, Apr: 1, May: 1, Aug: 1, Dec: 1 |

KSP's negative class is concentrated in **Jan/Feb/Jul/Dec** (winter + one summer date). Qiddiya's spans **Jan–Apr + Jul–Sep + Nov** (broader). Diriyah's spans **Feb/Apr/May/Aug/Dec** (broader, lower count).

### Step C — Seasonal-balance constraint (the SZA defence)

Filter UVAI overpasses to **only calendar months with ≥1 clean scene** for that AOI. Months that have positives but no negatives are excluded.

Rationale: §7 of `sq1d_lolli_formula.md` documents the solar-zenith-angle confound — TOA reflectance differential isn't path-radiance-corrected, so a winter-only positive class against a summer-heavy negative class would teach a threshold to discriminate "season" not "aerosol load". The SQ1B re-run's V4 result (Diriyah cleans pulling negative DBB downward, threshold drifting to +0.027) is exactly that mechanism in miniature. Constraining positives to the same months as negatives is the cheapest defence; the principled alternative is in §3.

### Step D — Rank and select

Within the filtered set, rank by `uvai_mean` **descending**. Select the top **15 candidates per AOI**. The 50% over-target (15 selected for n_pos ≥ 10 floor) is attrition budget — some candidates will visually-label as `clean` despite high UVAI, and some thumbnails will fail rendering for cloud cover or S2-data-footprint gaps (the latter is exactly what `array_has_data` now catches loudly).

### Step E — S2 scene pull

For each selected UVAI date:
1. Query GEE `COPERNICUS/S2_SR_HARMONIZED` (L2A) on that exact date over the AOI bbox.
2. If exact-date match has `CLOUDY_PIXEL_PERCENTAGE > 30` over AOI, search ±3 days, pick the lowest-cloud match within the window.
3. If no scene within ±3 days passes the cloud filter, drop the candidate. Log the drop.
4. Record the (`uvai_date`, `s2_acquisition_date`, `day_offset`, `s2_system_index`, `cloud_pct`) tuple in `sq1c_<aoi>_positive_candidates.csv`.

### Step F — Write manifest entry

For each candidate scene actually pulled, append a row to `research/dust-honesty/data/sq1c_scene_manifest.csv` (same schema as `sq1d_scene_manifest.csv`) with `source='locked_at_selection'`. The manifest is the source of truth; SQ1C renderers read from it via the same lookup pattern as the SQ1D test renderers (`load_manifest_lookup()` →  `(system_index, acquisition_date)` →  date-based fetch with system:index assertion). This locks the (UVAI-anchored candidate ↔ S2 scene) tie at selection time so a future GEE catalog backfill cannot silently substitute a different scene under the same date+AOI query.

## 3. Operationalization decision (FLAGGED FOR REVIEW)

The seasonal-balance constraint in Step C is implemented as **calendar-month bin match** in v0. An alternative is **`1/cos(SZA)` bin match with bin width 0.1**, which directly maps to the path-radiance term in Lolli's TOA differential and is the principled choice. We choose the cheaper v0 because:

1. The negative-class month bins already span the seasons that matter (KSP's Jul positive is the only summer; Diriyah and Qiddiya have summer cleans too).
2. The SZA-bin alternative adds a SZA-computation dependency on every UVAI candidate — modest cost in PUs but real complexity in protocol audit.
3. Month-bin is interpretable in the methodology footnote without explaining `1/cos(SZA)` to a reader.

**Revisit only if:** SQ1B re-re-run on the SQ1C-expanded set still shows CI half-width or label-confound issues. If so, port the constraint to SZA-binning and re-pull the candidate set; cost is one extra session.

## 4. Visually-blind labeling protocol

Identical to SQ1D Pass 4 (committed in `859450e`). Locked.

### Stretch reuse

| AOI | Stretch source |
|---|---|
| KSP | `research/dust-honesty/data/sq1d_ksp_stretch.json` |
| Qiddiya | `research/dust-honesty/data/sq1d_qiddiya_stretch.json` |
| Diriyah | `research/dust-honesty/data/sq1d_diriyah_stretch.json` (new this commit; values lifted from CLAUDE.md provenance, not previously persisted) |

Per-AOI 2/98 stretches are reused verbatim. Do not recompute on the SQ1C candidate pool — that would shift the radiometric calibration target between the existing test set and the new positives, breaking visual comparability.

### Caption rule

Date only. No UVAI value. No old label. No AOI text. (UVAI is the *selector* for which months to pull; it is never visible to the labeler. This is what makes SQ8's UVAI cross-check non-circular.)

### Rubric (verbatim from SQ1D)

Five classes: `clean / light_haze / heavy_dust / cloud / mixed`, augmented with the construction-substrate exclusion rule:

> "Construction substrate (bare beige/tan ground that is sharp-edged and stable across multiple dates) is a SURFACE feature, not atmospheric. Atmospheric features must be scene-wide veiling, not localized."

### Workflow

1. AI assistant pre-labels each candidate thumbnail against the rubric; produces `ai_prelabel`, `ai_confidence` (high/medium/low), `ai_reasoning` (one sentence).
2. Researcher (Ahmed) reviews each pre-label at full resolution. Override → record both. Confirm → `final_label = ai_prelabel`.
3. UVAI cross-check is post-merge audit only, never input. Disagreement between UVAI rank and `final_label` is the *finding*, not a bug.

## 5. Diriyah handling

Diriyah is included in SQ1C v0 via GEE TROPOMI UVAI per §9. Original CDSE/Sentinel-Hub-sourced Diriyah UVAI deferred until CDSE recovers AND/OR the OData spike completes (raw netCDF with `qa_value` preserved); logged as deferred work, not blocking SQ1C.

Diriyah is the surface-stable AOI — the SZA seasonal bias from `sq1d_lolli_formula.md` §7 is most diagnostic there, so adding Diriyah positives is high-value even though Diriyah's existing negative-class size (5 cleans) limits its standalone discriminative power.

## 6. PU budget estimate

Per AOI:
- UVAI candidate-thumbnail batch: 15 scenes × 1 RGB rendering = ~15 GEE downloads. Each S2 RGB tile at 10 m over a ~16 km² bbox is ~1 PU on Sentinel Hub free tier; on GEE it counts toward EECU not PU. Estimate: **~15 PU equivalent on SH**, ~1 EECU on GEE.
- L2A pulls for the 15 candidates (`array_has_data` validation may force a few re-pulls within the ±3-day window): ~15–25 PU.

Total per AOI ≈ **30–40 PU** on SH side; ≈ **2 EECU** on GEE side.

Three AOIs (if Diriyah lands): ≈ **120 PU / 6 EECU**. Two AOIs (KSP + Qiddiya only, v0 ship): ≈ **80 PU / 4 EECU**. Both well under the SH 30 000 PU/month free tier and the GEE Community Tier 150 EECU/month.

Update this section with post-flight actuals after the candidate-thumbnail batch run.

## 7. Outputs

Per AOI:

| Path | Schema |
|---|---|
| `research/dust-honesty/data/sq1c_<aoi>_positive_candidates.csv` | `uvai_date,s2_acquisition_date,day_offset,s2_system_index,cloud_pct,uvai_mean,uvai_max,rank` |
| `research/dust-honesty/data/sq1c_<aoi>_test_thumbnails/<YYYY-MM-DD>.png` | one per surviving candidate |
| `research/dust-honesty/data/sq1c_<aoi>_relabel.csv` (post-labeling) | `date,sub_aoi,candidate_uvai,ai_prelabel,ai_confidence,ai_reasoning,final_label` |
| `research/dust-honesty/data/sq1c_scene_manifest.csv` | `aoi,month_slot,acquisition_date,system_index,cloudy_pixel_pct,processing_baseline,source,notes` — system:index lock per candidate, written at selection time (Step F), identical schema to `sq1d_scene_manifest.csv` |

The `_relabel.csv` schema mirrors `sq1d_<aoi>_relabel.csv` (commits `9b73a75`, `442d7b0`) so SQ1B re-re-run can union the two label sources without schema massaging.

## 8. Reproducibility note

GEE's catalog can backfill processing-baseline-updated scenes, causing the deterministic-pick logic (`filter cloud<5, sort by CLOUDY_PIXEL_PERCENTAGE asc, take first`) to silently change which scene is returned for a given `(aoi, month)` bucket. Verified empirically on **2026-04-30** with KSP `2021-02`: the original calibration-set render used `20210204T073111_..._T38RPN` (cloud=0.009, processing baseline 05.00), but today's catalog has `20210214T073011_..._T38RPN` ranking ahead at cloud=0.000 — the exact-zero suggests baseline reprocessing inserted a more-recent flag-recompute that won the tiebreak.

To prevent this from corrupting calibration sets that are already labeled, both SQ1D and SQ1C lock the `system:index ↔ (aoi, month_slot)` tie via sidecar manifests (`sq1d_scene_manifest.csv`, `sq1c_scene_manifest.csv`):

- Renderers read the manifest first; the deterministic pick is a fallback **only** when the manifest has no entry, and the renderer logs `[MANIFEST GAP]` in that case.
- The manifest path uses date-based fetch (`filterDate` + `mosaic` + `clip`) — byte-identical to the original committed renders — and asserts that the manifest's `system_index` is present in the catalog on the recorded `acquisition_date` before fetching. If GEE rolls a `system_index` out from under us in the future, this fails loud rather than rendering a different scene under the same filename.

**Net effect:** the calibration sets used in SQ1B / SQ1B re-re-run are exactly reproducible from `manifest + scripts` at any future date, regardless of GEE catalog evolution.

## 9. Data provenance for TROPOMI UVAI

The CDSE/Sentinel Hub HTTP 503 outage that ran from 2026-04-28 through 2026-04-30 (post-network-upgrade residual instability, not user-specific) initially looked like a Diriyah-only blocker — Diriyah's all-months UVAI was the one CSV not yet pulled. Investigating an alternate path surfaced a more important finding: CLAUDE.md describes TROPOMI UVAI as "accessible via Sentinel Hub Process API on CDSE," but the existing KSP and Qiddiya all-months CSVs were already running on GEE. The batch scripts `sq1d_ksp_uvai_search.py` and `sq1d_qiddiya_uvai_search.py` both use `ee.ImageCollection("COPERNICUS/S5P/OFFL/L3_AER_AI")` against the `absorbing_aerosol_index` band; the CDSE/SH framing in CLAUDE.md predates the all-months batch work and was never updated. The Diriyah pull was therefore brought into line with the existing pipeline rather than introducing a second source. **All three AOIs (KSP, Qiddiya, Diriyah) sit on GEE `COPERNICUS/S5P/OFFL/L3_AER_AI`. There is no source-mixing.** The CSVs carry a `data_source` column for future-proofing in case a re-pull lands in CDSE OData.

The 2026-04-30 session-2 source-check confirmed this empirically: 30 random KSP dates re-fetched from GEE under the SQ1C-spec reduction parameters (`bestEffort=False`, exact L3 native scale 1113.2 m) returned **Pearson r = 1.0000, Spearman ρ = 1.0000** against existing CSV values. Mean(existing − refetch) = +0.0024, stdev = 0.0081 — a residual consistent with `bestEffort` reducer-cell rounding. The scatter (`research/dust-honesty/data/sq1d_uvai_source_check.png`) lies on y = x. Pipeline reproducibility under the stricter SQ1C reduction params is bit-tight.

**Deferred, not blocking SQ1C.** OFFL L3 strips `qa_value`, which matters for SQ3's quantitative use and for SQ8's KAUST AERONET validation chapter — both need quality-flag-aware masking. The CDSE OData spike (raw netCDF, preserves `qa_value`) remains the right path for those downstream uses and is logged as a separate work item. SQ1C's positive-month selection is rank-based and within-AOI, so OFFL L3 is fit-for-purpose here.

## 10. Open questions / follow-ups

- Diriyah UVAI all-months pull (CDSE-dependent) — see §5. Closes the V4-scope gap.
- Whether to also re-render the existing 5 Diriyah cleans into the SQ1C thumbnail format for visual-comparability with the new Diriyah positives. Defer to the labeling-session decision; surface-stable AOI so the visual rubric should be unambiguous regardless.
- Whether to extend the `array_has_data` guard to count cloud-shadow / cirrus pixels too (currently flags only zero/NaN). The SCL-based cloud filter on S2 metadata catches scene-level cloud already; the pixel-level edge case is what SQ1C is most likely to expose. Watch for it during the labeling session, harden if it surfaces.

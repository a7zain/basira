# SQ1B — Verify Lolli, tune threshold with bootstrap CI

**Status:** Stop rule triggered. No threshold shipped. No flag function written.
**Date:** 2026-04-27 (continuation of SQ1)

## Lolli verification

The MDPI page (https://www.mdpi.com/2073-4433/15/6/672) and ResearchGate
mirror returned **HTTP 403** to automated requests this session, so the
PDF was not retrievable. Web-search snippets and the abstract confirm
the band selection (B2/B3/B4 visible, B11/B12 SWIR) and confirm the
phrase "normalization by the surface reflectance of the scene"
— but they do **not** disclose the exact denominator.

**Status of `dbb_index.py`:** *unverified.* The implementation
follows the standard normalized-difference structure
`(visible_mean − swir_mean) / (visible_mean + swir_mean + ε)`,
which is the natural reading of "normalized differential index" and is
consistent with the abstract. An alternative reading of "normalized by
surface reflectance" is to divide by SWIR alone (using SWIR as a
surface proxy because dust is partly transparent there). Until the PDF
is read directly the index should be treated as *Lolli-inspired* rather
than *Lolli-faithful*. Either denominator preserves the *direction* of
the dust signal (positive shifts on dust days), so the threshold-tuning
question below is well-posed regardless.

No change to `dbb_index.py` from SQ1. The 30 DBB values in
`data/sq1_dbb_values.csv` are unchanged.

## Calibration set

30 scenes drawn from the Phase 1 corpus (76 months × 3 AOIs), as
described in SQ1. Manual labels:

| label       | count |
|-------------|------:|
| clean       | 23    |
| light_haze  | 4     |
| heavy_dust  | 2     |
| cloud       | 1     |
| mixed       | 0     |

**Labeling methodology** (must be reported with any quantitative claim
downstream): scenes were *AI pre-labeled* by Claude against a written
rubric, then *reviewed and finalized by the researcher (Ahmed)* against
the full-resolution `sq1_thumbnails.png` on 2026-04-27. This is a
human-in-the-loop label set, not a blind expert label set. The
researcher's review is the authoritative pass; the AI pass is decision
support, not ground truth.

## Threshold sweep — both mappings

Decision rule: `dbb_mean > t  ⇒  flagged dust`. Best `t` maximizes
balanced accuracy (raw accuracy is uninformative under this class
imbalance). Bootstrap = 1000 resamples, 95% CI from 2.5 / 97.5
percentiles.

| mapping        | n+ | n− | best t   | 95% CI                 | half-width | sens | spec | bal-acc | F1   | AUC  |
|----------------|---:|---:|---------:|------------------------|-----------:|-----:|-----:|--------:|-----:|-----:|
| conservative   |  2 | 28 | −0.2278  | [−0.2798, −0.2278]     | **0.0260** | 0.50 | 0.93 | 0.714   | 0.40 | 0.554 |
| aggressive     |  6 | 24 | −0.2661  | [−0.2798, −0.2278]     | **0.0260** | 0.83 | 0.38 | 0.604   | 0.38 | 0.507 |

(Conservative mapping: clean / light_haze / cloud → 0; heavy_dust /
mixed → 1. Aggressive: clean / cloud → 0; light_haze / heavy_dust /
mixed → 1.)

Figures: `figures/sq1b_roc_{conservative,aggressive}.png`,
`figures/sq1b_confusion_{conservative,aggressive}.png`,
`figures/sq1b_threshold_bootstrap.png`.

## Decision — STOP RULE TRIGGERED

The brief sets a stop rule: **abort if the bootstrap 95% CI half-width
exceeds ±0.02 DBB units.** Both mappings come in at **0.026** — wider
than the rule. Two further signals reinforce this:

1. **AUC near chance.** Conservative AUC = 0.554, aggressive AUC =
   0.507. The DBB index in its current form is barely separating
   dust from clean over this 30-scene set.
2. **Top-of-distribution false positive.** The conservative best
   threshold puts the flag at the very top of the DBB distribution
   (only 3 scenes exceed it: 2 true heavy_dust + 1 clean false-positive).
   The threshold is essentially "the highest clean scene" — moving any
   one labeled scene by one rank changes the answer.

**No threshold is shipped. `dbb_index.py` is not updated.
`is_dust_flagged` is not written.**

## Confidence

**Low.** The dust signal exists in principle (TROPOMI UVAI ratio ~48×
in the spike) but the DBB index is not separating it cleanly at scene
mean over Riyadh sub-AOIs at this sample size. The threshold-tuning
exercise is statistically underpowered: 2 positives under the
conservative mapping, 6 under the aggressive — far below any sensible
threshold for binary classification with bootstrap uncertainty bounds.

## What would change the threshold

In rough order of likely impact:

1. **More dust-positive anchor scenes.** Add 5–10 known-dust scenes
   pulled from Sen5P UVAI peaks in the Riyadh window (May 2022 storm,
   any 2023–2024 events). Without more positives the bootstrap can't
   distinguish noise from signal. This is the cheapest move.
2. **Verify the exact Lolli denominator.** If Lolli normalizes by SWIR
   alone (or by another quantity), the index dynamic range and the
   threshold both shift. This is a one-PDF-read fix once the paper is
   accessible.
3. **Per-AOI thresholds, not a global one.** The three AOIs have
   different baseline albedos (visible in the per-AOI stretch ranges
   from the thumbnail-fix session). A single global threshold may be
   the wrong shape; per-AOI thresholds — or a z-scored DBB — could
   pull the dust scenes apart.
4. **Pixel-level instead of scene-mean DBB.** Scene means smear the
   dust signal over the whole AOI. A per-pixel flag thresholded then
   aggregated (e.g. "flag scene if >X% of pixels exceed t") could be
   more sensitive.
5. **Alternative label mappings.** The conservative/aggressive split
   was specified up front; with only 6 non-clean labels the data
   doesn't support finer mapping experiments yet.

## Caveats (must accompany any downstream use)

- 30-scene calibration is small; class imbalance is severe (2 positives
  conservative, 6 aggressive).
- AI-pre-labeled, researcher-reviewed labels — not blind expert labels.
- Calibrated against three Riyadh sub-AOIs (qiddiya_core,
  king_salman_park, diriyah_gate). Generalization to Riyadh-wide or
  other Saudi cities is not established.
- Lolli formulation unverified (PDF not accessible this session).

## Next steps (recommended order)

1. **Get more positives.** Pull Riyadh Sentinel-2 scenes from UVAI peak
   days in 2022–2024 and label them. Target n_pos ≥ 12 for a workable
   threshold.
2. **Read the Lolli PDF** offline and confirm denominator. Update
   `dbb_index.py` if it differs.
3. Re-run `sq1b_threshold.py` against the expanded label set.
4. Only after CI half-width < 0.02 and AUC > 0.75: ship a threshold
   and write `is_dust_flagged`.

# SQ5 — high-UVAI subset (HALT WITH RECEIPT; Goyens-regime → SQ8)

**Status:** HALTED 2026-05-02 at pre-registered 30% pair-retention floor in all three AOIs. Goyens-regime test inherits to SQ8 with regression design. Two findings survive the halt and ride into piece B substance.

## §1 Question, locked design, halt summary

Question: does the SQ3/SQ4/SQ4B conditional null hold at high atmospheric loadings, or does the predicted Goyens-consistent negative Δ NDVI emerge when atmospheric loading is in the per-AOI top quartile? Locked design: per-AOI top-quartile UVAI scenes (Q4) paired to nearest bottom-quartile (Q1) neighbor within ±60 days, same AOI; bootstrap on pairs (1000 resamples, seed 42); pre-registered direction negative if Goyens transfers; HARD HALT if pair retention <30% in any AOI.

The retention stop-rule fired in **all three AOIs** (KSP 0.0%, Qiddiya 11.1%, Diriyah 11.1%; floor 30%). Root cause is Riyadh's UVAI seasonality: Q1 (low UVAI) clusters in winter, Q4 (high UVAI) clusters in spring/summer; the two quartiles do not temporally interleave at the ±60-day pair-window scale. The paired temporal-neighbor design IS the right design for the question — it is mathematically incompatible with this site's UVAI seasonality. SQ5 ships as a halt-with-receipt; the Goyens-regime test is promoted to SQ8 (KAUST AERONET) with a regression-style design (sketched in §6, not scoped here).

## §2 Recon results (R1, R2, R5)

### R1 — UVAI distribution per AOI (PASSED, n=18 per quartile, well above n=12 floor)

Joined manifest + NDVI cache + UVAI: 221 candidate scenes (out of 228 manifest rows; 7 lost on shared TROPOMI gap dates 2023-06-24 and 2026-04-14).

| AOI | n | Q1 threshold | Q3 threshold | Q1 n | Q4 n | mean UVAI Q1 | mean UVAI Q4 | gap |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| King Salman Park | 73 | +0.774 | +1.618 | 18 | 18 | +0.088 | +1.907 | **+1.818** |
| Qiddiya core | 74 | +0.611 | +1.624 | 18 | 18 | −0.042 | +1.845 | **+1.887** |
| Diriyah Gate | 74 | +0.447 | +1.501 | 18 | 18 | −0.178 | +1.761 | **+1.939** |

UVAI gap of +1.8–1.9 between Q4 and Q1 is large — these are real loading-regime contrasts, not noise quartiles. Receipt: `sq5_uvai_labels.csv`.

### R2 — pair retention probe (HARD HALT, all three AOIs)

| AOI | n_q4 | n_q4 with Q1 neighbor ±60d | retention | floor | status |
|---|---:|---:|---:|---:|---|
| King Salman Park | 18 | **0** | **0.0%** | 30% | **HALT** |
| Qiddiya core | 18 | 2 | 11.1% | 30% | **HALT** |
| Diriyah Gate | 18 | 2 | 11.1% | 30% | **HALT** |

Receipt: `sq5_pair_retention_probe.csv`. Seasonal-stratification table in `sq5_seasonal_stratification.csv`; visual in `figures/sq5/sq5_seasonal_stratification.png`.

### R5 — UVAI × V4 contingency (PASSED, diagnostic only — feeds §4.2)

| AOI | Q4 ∧ V4 | Q4 ∧ ¬V4 | ¬Q4 ∧ V4 | ¬Q4 ∧ ¬V4 |
|---|---:|---:|---:|---:|
| King Salman Park | 10 | 8 | 13 | 42 |
| Qiddiya core | **16** | 2 | 40 | 16 |
| Diriyah Gate | 6 | **12** | 2 | 54 |

Confirms UVAI subsetting is NOT redundant with V4 subsetting. The two highlighted cells (Qiddiya 16/18 = 89% of Q4 fires V4; Diriyah Q4 ∧ ¬V4 = 12 scenes) are piece-B substance — see §4.2. Receipt: `sq5_uvai_v4_contingency.csv`.

### R3, R4 (collected during recon)

- **R3**: primary EECU = 0; existing `sq3_ndvi_per_scene.csv` covers all SQ5 candidate dates (226/228 with NDVI). VIIRS Deep Blue AOD has no cached CSV in `research/dust-honesty/data/`; CLAUDE.md infrastructure description says it's available via GEE but the cached file is absent — **CLAUDE.md infrastructure-description drift, parity with the project's documented "infrastructure descriptions can drift from scripts" guardrail**. The VIIRS sensitivity arm was out of scope for this halt-with-receipt ship; the GEE call belongs in SQ8 scoping where absolute-AOD calibration matters.
- **R4**: Per-AOI UVAI CSVs do NOT carry an `aoi` column — AOI is implicit from filename (`sq1d_<aoi>_uvai_all.csv`). Diriyah's CSV additionally has a `data_source` column (GEE_OFFL_L3 marker). `sq5_uvai_subset.py` injects AOI on load from a filename map. Documented in code and in this note per the same drift guardrail.

## §3 Why the halt fired

Riyadh's UVAI seasonality clusters Q1 (low) in winter (Nov–Feb dominate) and Q4 (high) in spring/summer (Mar–Aug dominate). KSP's Q1 set has 0 scenes in Mar–Aug; KSP's Q4 set has 0 scenes in Nov–Feb. The two distributions are temporally disjoint at the ±60-day pair-window scale. Qiddiya and Diriyah have a small number of shoulder-season Q1 scenes (one each in Mar, Apr, May) that pair with adjacent Q4 neighbors — explaining their 2/18 retention. The seasonal-stratification figure is the visual diagnostic.

The paired temporal-neighbor design is the correct design for the SQ3-style question of "does atmospheric thickness propagate to NDVI bias *holding surface state approximately constant*." That design assumes the two contrast classes can co-occur in the same season; UVAI extremes at this site cannot. The constraint is structural to the dataset, not a sample-size problem fixable by widening the window or relabeling quartiles.

## §4 Two findings that survive the halt

### §4.1 — Seasonal stratification of UVAI at Riyadh is itself a methodology finding

Paired temporal-neighbor designs cannot probe high-AOD vs low-AOD contrasts at Riyadh because high-AOD scenes and low-AOD scenes live in different seasons. This generalizes beyond SQ5: any future within-Sentinel-2 paired design that tries to anchor on UVAI extremes at moderate-aridity Saudi sites will hit the same constraint. The methodological implication for the field is that per-scene absolute-AOD regression — the SQ8 design — is the right approach for high-vs-low AOD contrasts at this loading regime. Paired designs work only for V4-fired-vs-unfired (SQ3) where both flagged and unflagged scenes can occur in the same season because V4 fires on a continuous index and is not seasonally exclusive. This is a design-selection finding, not a data-quality finding.

### §4.2 — UVAI × V4 contingency is piece B substance independent of SQ5's halt

- **Diriyah Q4 ∧ ¬V4 = 12 scenes.** High atmospheric loading at the surface-stable AOI without V4 firing. This is the cleanest possible Goyens-regime test cell at this site — atmospheric thickness present, surface stable, V4 didn't trigger. SQ8 anchors AERONET ground truth here.
- **Qiddiya Q4 ∧ V4 = 16/18 = 89% of Q4.** Almost every high-UVAI Qiddiya scene fires V4. This is a **sixth independent line of evidence for the construction-substrate finding** at Qiddiya. Existing five lines surfaced in SQ1D Pass 5 + SQ1D Part B' sensitivity ρ=0.92 + V2 prelim AUC drop + V2 confirmed AUC drop + SQ2 baseline DBB +0.091. SQ5's contribution is a structural correlation: V4 over-fires at Qiddiya in ways that correlate with high UVAI background, even though the root cause is surface (substrate accumulation), not atmospheric. The atmospheric and substrate signals are entangled at Qiddiya in a way that would require a substrate-controlled DBB calibration to disentangle.
- **KSP Q4 evenly split** between V4-fired (10) and not (8). Consistent with KSP being the moderate-substrate AOI between Diriyah-stable and Qiddiya-changing.

## §5 Limitations of the halt-with-receipt finding itself

a) The halt is **design-specific**. A different design (regression on continuous UVAI, independent pair construction, hierarchical model) might still probe the high-AOD question at this site — SQ8 is one such design.
b) The seasonal-stratification finding is **conditional on UVAI as the AOD proxy**. A different AOD source (VIIRS Deep Blue, AERONET) might show a different seasonal distribution, though Riyadh's shamal climatology suggests the same pattern would hold for any column-aerosol metric.
c) **Per-AOI quartile thresholds are not comparable across AOIs in absolute UVAI units** — Diriyah's Q4 floor (+1.501) is below KSP's (+1.618) and Qiddiya's (+1.624). The per-AOI design controls for surface but not for absolute loading; would have been an SQ5 limitation regardless of halt.

## §6 Cross-validation hooks

a) **SQ8 (KAUST AERONET) — INHERITS THE GOYENS-REGIME QUESTION.** Two-sentence design sketch (do NOT scope further here): SQ8 will regress per-scene NDVI residual (relative to seasonal climatology or a paired neighbor) on per-scene AERONET absolute AOD, using a regression-style design rather than paired-quartile design; the Diriyah Q4 ∧ ¬V4 = 12 cell from SQ5 R5 contingency is the pre-identified anchor cell for AERONET co-location.

b) **SQ4C (native L30 pair construction) — DEFERRED, parity with SQ4B's deferral note.** Cross-correction-chain robustness at high-AOD subset is a possible SQ4C extension, but only after SQ8 establishes whether high-AOD bias exists at all on Sen2Cor.

c) **Original-SQ5 (seasonal modulation) and SQ6 (per-AOI bias regression) — DEFERRED to post-piece-B.** These elaborate the existing finding chain rather than extend it; piece B prose will surface whether they're needed for the headline.

d) **Internal consistency: SQ2 / SQ3 / SQ4 / SQ4B / SQ5 chain — the loading-regime ladder.**
   - **SQ2** detects atmospheric optical thickness via DBB (V4 fires at moderate loadings, AOI-dependent fire rates).
   - **SQ3** measures Δ NDVI on V4-flagged vs near-temporal unflagged Sen2Cor B8 pairs at moderate loadings — tight nulls at KSP and Qiddiya, wide-inconclusive at Diriyah n=8.
   - **SQ4** confirms the SQ3 null under HLS LaSRC B8A — rules out Sen2Cor-specific absorption.
   - **SQ4B Arm A** confirms the SQ3/SQ4 null under HLS LaSRC B8 broad NIR — rules out narrow-vs-broad NIR band selection. Three measured cells per AOI agree at change-detection magnitude.
   - **SQ5** halts: high-AOD subset cannot be probed by paired temporal-neighbor design at this site because UVAI is seasonally stratified. Goyens-regime test inherits to SQ8.

The piece-B mechanism story remains: **at moderate Riyadh-region atmospheric loadings, V4-flagged scenes do not exhibit a measurable bias relative to near-temporal unflagged neighbors at change-detection magnitude across two correction chains and two NIR bands.** The high-AOD extension to that claim cannot be answered by the current pair-and-diff design — that's the SQ5 contribution. SQ8 is the right anchor for the high-AOD question and for Diriyah's underpowered cell.

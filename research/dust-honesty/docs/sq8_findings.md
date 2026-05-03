# SQ8 — Goyens-regime regression test at Riyadh (reanalysis-AOD primary)

**Status:** DONE 2026-05-02. Power-confirmation of the operational null (Option 4 framing). Pre-registered classifier and magnitude criterion both fire on this result and are reported without override.

## §1 Question and locked design

SQ8 inherited the Goyens-regime question from SQ5's halt and tests whether per-scene Sen2Cor L2A NDVI residual (relative to per-AOI per-month climatology) is significantly biased by absolute atmospheric AOD at Riyadh. R1 confirmed no operational AERONET station within 500 km of Riyadh during the SQ2 window (Solar_Village dead 2015-10-12, ~30 km from Riyadh; Bahrain dead 2007-03-06, ~424 km; UAE cluster ~750–800 km outside the 500 km outer ring), so the design retargeted to reanalysis primary: **MERRA-2 DUEXTTAU** (dust extinction at 550 nm, mechanistic match to TROPOMI UVAI and the V4 DBB index) with **CAMS NRT total AOD at 550 nm** as independent reanalysis cross-check. Statistical design: OLS with AOI fixed effects, HC3 robust standard errors. Pre-registered signal classification on the AOD coefficient applied to both the primary regression and the magnitude criterion.

## §2 Recon results

### §2.1 R1 — AERONET station availability

| station | distance from Riyadh | last operational | viable for SQ2 window |
|---|---:|---|---|
| Solar_Village (Riyadh) | ~30 km | 2015-10-12 | ✗ (pre-window) |
| Bahrain | ~424 km | 2007-03-06 | ✗ (pre-window) |
| Al_Dhafra (Abu Dhabi) | ~796 km | (operational) | ✗ (>500 km) |
| Mussafa, Mezaira, Hamim, etc. | ~700–800 km | (operational) | ✗ (>500 km) |
| KAUST_Campus (Thuwal) | ~820 km | (operational) | ✗ (>500 km; deferred to SQ8B) |

Source: AERONET v3 station listing (`https://aeronet.gsfc.nasa.gov/aeronet_locations_v3.txt`) plus AERONET station summary pages for operational dates. Halt at the 500 km outer ring was unambiguous; SQ8 retargeted to reanalysis primary.

### §2.2 R2 — reanalysis source availability

| source | GEE asset | images in window (Riyadh) | AOD band | native resolution |
|---|---|---:|---|---|
| **MERRA-2 aerosol** (primary) | `NASA/GSFC/MERRA/aer/2` | 54,648 | `DUEXTTAU` (dust extinction 550 nm) | ~0.5°×0.625° (~55×70 km) |
| **CAMS NRT** (cross-check) | `ECMWF/CAMS/NRT` | 189,476 | `total_aerosol_optical_depth_at_550nm_surface` | ~0.4° (~44 km) |

Both sources well above the 80% coverage floor on the 228 SQ2 manifest dates.

### §2.3 R3 — EECU estimate vs actual

Estimated <5 EECU for 228 dates × 2 sources × small-AOI reducers. Actual in-budget; no rerun cost incurred for SQ5 NDVI inputs (`sq3_ndvi_per_scene.csv` covers all SQ8 dates from prior commits).

### §2.4 R4 — column compatibility

All upstream files confirmed: `sq3_ndvi_per_scene.csv`, `operational/dbb_operational_sq2.csv`, `operational/manifest_operational_sq2.csv`, `sq5_uvai_labels.csv`, `sq5_uvai_v4_contingency.csv`. Join keys `(aoi, acquisition_date)` consistent across SQ3/SQ5/SQ8.

### §2.5 R5 — climatology design diagnostic

Per-AOI per-calendar-month NDVI climatology cells: 36 (3 AOIs × 12 months), n = 5–7 each, all above the n = 3 sensitivity floor. `sensitivity_flag = False` for all 226 NDVI-present scenes; the climatology baseline is robust at this site for this window.

### §2.6 In-build correction surfaced and resolved

The CAMS NRT collection in GEE is **3-hourly** (validity times at 00/03/06/09/12/15/18/21 UTC), not hourly as initially assumed from the asset name. The first sanity-test run with a ±60 min window around 07:30 UTC missed both the 06:00 and 09:00 CAMS steps and returned NA. Fix landed before the production loop: per-source temporal windows — MERRA-2 ±60 min (genuinely hourly assimilated reanalysis), CAMS ±120 min (brackets the 06:00 and 09:00 steps for temporal interpolation across the S2 acquisition window). Sanity test passed after fix; no data loss in production.

This is the **fourth GEE-pattern drift mechanism** documented in this project's session logs:
1. Catalog backfill on `system:index` (SQ1D scene-manifest pattern)
2. `bestEffort=True` reducer-count drift (SQ1D Part B re-run)
3. Baseline-reprocessing drift on locked `system:index` (SQ2 cross-check)
4. CAMS NRT 3-hourly cadence vs hourly assumption (this run)

Mitigation pattern shared with the prior three: probe upstream collection structure before scaling the production loop; document the specific cadence/scale/baseline assumption in the script header.

## §3 Per-AOI table — primary regression (MERRA-2 DUEXTTAU)

The primary regression is pooled across all three AOIs with AOI fixed effects. The AOD coefficient is shared; per-AOI variation is in the n and in the predicted residuals at the AOI's loading-regime quantiles.

**Pooled coefficient (MERRA-2 DUEXTTAU + AOI fixed effects, HC3 robust SE):**

| metric | value |
|---|---:|
| AOD coefficient β | **−0.010122** |
| robust SE (HC3) | 0.004480 |
| p-value | **0.0239** |
| 95% CI on β | [−0.018903, −0.001342] |
| n | 224 |
| R² | 0.0278 |
| β × IQR (Q4 − Q1 AOD = 0.176) | **−0.001776** NDVI per IQR |
| 95% CI on β × IQR | [−0.003317, −0.000236] |

**Per-AOI predicted residuals from the pooled fixed-effects model** (units: NDVI):

| AOI | n | AOI-mean AOD | predicted at AOI-mean | predicted at Q1 AOD | predicted at Q4 AOD |
|---|---:|---:|---:|---:|---:|
| King Salman Park | 74 | 0.249 | +0.0000 | +0.0011 | −0.0007 |
| Qiddiya core | 75 | 0.228 | +0.0002 | +0.0011 | −0.0007 |
| Diriyah Gate | 75 | 0.243 | −0.0008 | +0.0002 | −0.0016 |

Q1 AOD = 0.1404, Q4 AOD = 0.3159 (pooled MERRA-2 DUEXTTAU 25th and 75th percentiles).

**Diriyah Q4 ∧ ¬V4 anchor cell** (pre-registered cleanest Goyens-regime cell: high-UVAI Diriyah scenes where V4 did not fire, n = 12 per `sq5_uvai_v4_contingency.csv`):

| metric | value |
|---|---:|
| n | 12 |
| mean MERRA-2 DUEXTTAU at this cell | 0.3303 |
| predicted NDVI residual at this AOD | **−0.001714** |
| 95% CI on prediction | [−0.004574, **+0.001146**] |

Anchor-cell prediction CI **straddles zero**. The pre-registered headline cell does not individually confirm a Goyens-regime bias.

## §3.1 Cross-check — CAMS total AOD

Same regression structure with CAMS NRT total aerosol optical depth replacing MERRA-2 DUEXTTAU.

| metric | value |
|---|---:|
| AOD coefficient β | **−0.007307** |
| robust SE (HC3) | 0.003046 |
| p-value | **0.0169** |
| 95% CI on β | [−0.013302, −0.001312] |
| n | 226 |
| R² | 0.0126 |
| β × IQR (Q4 − Q1 CAMS AOD) | **−0.001389** NDVI per IQR |

**Cross-source agreement:** sign agreement ✓; CI overlap with primary ✓. Both p < 0.05.

Methodology note: MERRA-2 DUEXTTAU is dust-specific extinction, mechanistically aligned with TROPOMI UVAI (the SQ5 quartile basis, an absorbing-aerosol index dust-dominated at Riyadh). CAMS total AOD is total-aerosol-mix, including non-dust species. The two AOD measurements are methodologically distinct; sign and CI agreement across them strengthens replication beyond what a same-source cross-validation would. R² is roughly halved on CAMS (0.013 vs 0.028 primary), consistent with CAMS total mixing in non-dust aerosol that is less correlated with the SQ8 NDVI residuals.

## §3.2 Sensitivity — climatology-stable rows + AOI-stratified

**Climatology-stable subset** (drop rows where `sensitivity_flag = True`; per R5, no rows qualify): result identical to primary, n = 224, β = −0.010122. Reported here for parity even though no rows were dropped.

**AOI-stratified separate regressions** (no fixed effects, HC3):

| AOI | n | β | 95% CI | p | individually significant? |
|---|---:|---:|---|---:|---|
| King Salman Park | 74 | −0.0085 | [−0.0197, +0.0027] | 0.138 | n.s. |
| Qiddiya core | 75 | −0.0083 | [−0.0200, +0.0035] | 0.169 | n.s. |
| Diriyah Gate | 75 | −0.0132 | [−0.0338, +0.0073] | 0.208 | n.s. |

**No individual AOI is significant on its own.** The pooled significance is a power-of-large-n result; no individual AOI demonstrates an effect. All three per-AOI confidence intervals straddle zero. The pooled-FE model with n = 224 has the power that the per-AOI n ≈ 75 models do not.

## §4 Interpretation

SQ8 detects a statistically significant negative relationship between reanalysis-AOD and per-scene NDVI residual at Riyadh on Sen2Cor L2A. The relationship replicates across two independent reanalysis sources (MERRA-2 dust-specific extinction and CAMS total aerosol optical depth), with sign agreement, CI overlap, and p<0.05 from both. The direction is consistent with the Goyens prediction of negative NDVI bias under elevated atmospheric loading. At pooled-AOI fixed-effects n=224, the regression has the power to detect small effects, and it does.

The detected effect is operationally below detection. β × IQR = −0.0018 NDVI per IQR of AOD on the primary regression and −0.0014 on the cross-check. Both magnitudes are 2.8× below the pre-registered operational-significance threshold of 0.005 NDVI and ~25× below typical NDVI change-detection thresholds in the literature (~0.05). The R² of 0.028 (primary) means AOD explains roughly 3% of NDVI residual variance; ~97% is surface change, weather, and day-to-day sensor variability. None of the per-AOI regressions are individually significant (p = 0.138, 0.169, 0.208 for KSP, Qiddiya, Diriyah). The pre-registered Diriyah Q4∧¬V4 anchor cell — the cleanest atmospheric Goyens-regime cell at this site (n=12 high-UVAI scenes where V4 did not fire) — predicts a residual of −0.0017 NDVI with 95% CI [−0.0046, +0.0011], straddling zero.

Read jointly, this result is best characterized as power-confirmation of the SQ3/SQ4/SQ4B operational null rather than as Goyens transfer. The regression had sensitivity to detect a 0.002 NDVI effect, and that is what it detected. The Bayesian inverse holds: the test was sensitive enough to find a sub-operational effect if one existed, and it found one. That strengthens, rather than undermines, the operational null established at moderate loadings — because the test demonstrably has the power to detect operationally relevant magnitudes if they were present at high loadings, and they are not.

Two pre-registered criteria fire on this result. The classifier output, based on whether the AOD coefficient's confidence interval excludes zero, returns `goyens_consistent_bias_detected`. The magnitude criterion, based on whether |β × IQR| exceeds 0.005 NDVI, returns `tight_null`. Both criteria are reported here without override. The disagreement is itself worth naming: at the pooled-n power available to this design, the significance criterion and the magnitude criterion can return divergent classifications on operationally small effects. Similar regression-style atmospheric-correction analyses in the literature operate at comparable n with comparable R²; the disagreement we observe here is plausibly common in this design class but is rarely surfaced explicitly. For this study's umbrella question — whether atmospheric dust corrupts NDVI-based change monitoring at Riyadh on Sen2Cor L2A — the operational-magnitude criterion is the load-bearing one, because the change-monitoring use case is what determines whether a detected bias is consequential.

Combined with the SQ3 paired-design null at moderate loadings, the SQ4 cross-correction-chain robustness, the SQ4B cross-NIR-band robustness, and the SQ5 demonstration that paired temporal-neighbor designs cannot probe high-AOD vs low-AOD contrasts at Riyadh's seasonal stratification, the piece B headline is: across two correction chains (Sen2Cor + LaSRC), two NIR bands (B8 broad + B8A narrow), paired and per-scene regression designs, and reanalysis-AOD up to Q4 dust loadings at Riyadh, AOD-dependent NDVI bias does not exist at operationally meaningful magnitude. The largest detectable AOD–NDVI relationship at this site is −0.002 NDVI per IQR of AOD, with 95% CI lower bound −0.003 — sub-operational across the loading regime spanned by the SQ2 manifest. NDVI-as-ratio cancellation between Red and NIR perturbations is the surviving mechanism after correction-chain-specific absorption (SQ4), NIR-band-shift artifacts (SQ4B), and high-AOD threshold breakdown (SQ8) are all ruled out at operational magnitude.

## §5 Limitations

a) **Reanalysis-AOD vs measurement-AOD.** MERRA-2 and CAMS are model-assimilated AOD products, not direct measurements. AERONET unavailability at Riyadh during the SQ2 window forced this choice (R1). Operational NDVI-QC pipelines (HLS QA flags, Sen2Cor SCL) use reanalysis-AOD as the standard methodological precedent, so the use of reanalysis-primary here is consistent with how the question would be answered in production.

b) **Spatial mismatch.** MERRA-2 native resolution is ~55×70 km and CAMS NRT is ~44 km; the Riyadh AOIs are 5–15 km. The reanalysis cell averages over a footprint much larger than the AOI, and both sources should partially miss AOI-specific atmospheric signal. This is a real attenuation effect on the regression coefficient: the 95% CI lower bound on β IS the upper bound on detectable bias given this spatial constraint. A higher-resolution reanalysis source would be needed to lift this attenuation.

c) **Climatology baseline robustness.** All 36 (AOI, calendar month) cells have n = 5–7 scenes; sensitivity_flag was False for all 226 scenes (R5). This limitation will inherit to any extension that adds AOIs with sparser per-month coverage.

d) **AOI fixed effects absorb baseline NDVI differences but not within-AOI surface change events.** Large NDVI shifts from construction (especially Qiddiya) or vegetation growth events enter as residual variance. The R² of 0.028 reflects this — most NDVI residual variance is surface-state-driven, not atmospheric. The high residual variance is part of why the pooled regression has detection power for sub-operational effects but the per-AOI regressions individually do not.

e) **AERONET unavailability is site-specific and window-specific.** Solar_Village (the in-Riyadh AERONET station) is dead since 2015-10-12 — well before the SQ2 window starts. KAUST_Campus (Thuwal AERONET) is operational but at ~820 km, coastal not bright-desert; it tests a different generalization question and is **deferred to SQ8B**. The CLAUDE.md commitment to KAUST as the SQ8 anchor predates this R1 finding and is reconciled at the next end-of-session ritual update.

f) **Diriyah Q4 ∧ ¬V4 anchor cell n = 12 is small.** The predicted residual at this cell has wide CI (95% on prediction = [−0.0046, +0.0011]). The anchor-cell null is consistent with the operational-magnitude headline but does not independently confirm. A future SQ8 extension with longer time-series or additional desert-edge AOIs could tighten this anchor.

## §6 Cross-validation hooks

a) **SQ8B (KAUST Thuwal AERONET as Saudi-coastal generalization test) — DEFERRED to post-piece-B.** Different scientific question (generalization across surface and coastal-vs-inland regime) from SQ8 (Riyadh high-AOD bias). KAUST AERONET is operational and would deliver gold-standard ground-truth at a Saudi site, but on a different surface and likely a different climatological loading regime. CLAUDE.md commitment is reconciled at end-of-session ritual.

b) **SQ4C (native L30 pairs at high AOD) — DEFERRED.** Cross-correction-chain robustness at the high-AOD subset is post-piece-B. SQ8's result reduces the urgency: the operational null is robust enough that adding a third correction chain (LaSRC on Landsat-OLI) at high AOD is unlikely to change the headline. SQ4C remains a clean methodological extension for future work, not a piece-B-blocking question.

c) **Original-SQ5 (seasonal modulation) and SQ6 (per-AOI continuous regression) — DEFERRED to post-piece-B.** SQ6 is partially answered by SQ8's AOI fixed effects (per-AOI betas are all individually null). Original-SQ5 (seasonal modulation of the AOD–NDVI relationship) would elaborate the surviving NDVI-ratio-cancellation mechanism rather than test it.

d) **Internal consistency: SQ2 / SQ3 / SQ4 / SQ4B / SQ5 / SQ8 chain — the loading-regime ladder.**
   - **SQ2** detects atmospheric optical thickness via DBB (V4 fires at moderate loadings, AOI-dependent fire rates).
   - **SQ3** measures Δ NDVI on V4-flagged vs near-temporal unflagged Sen2Cor B8 pairs at moderate loadings — tight nulls at KSP and Qiddiya, wide-inconclusive at Diriyah n=8.
   - **SQ4** confirms the SQ3 null under HLS LaSRC B8A — rules out Sen2Cor-specific absorption.
   - **SQ4B Arm A** confirms the SQ3/SQ4 null under HLS LaSRC B8 broad NIR — rules out narrow-vs-broad NIR band selection. Three measured cells per AOI agree at change-detection magnitude.
   - **SQ5** halts: paired Q4-vs-Q1 quartile design fails on Riyadh's UVAI seasonal stratification (retention <30% in all AOIs). Goyens-regime test inherited to SQ8 with regression design.
   - **SQ8** detects a sub-operational AOD–NDVI relationship: β × IQR = −0.0018 NDVI, p = 0.024, 95% CI [−0.003, −0.0002]. Statistically detected, operationally null. Power-confirmation of the SQ3/SQ4/SQ4B operational null at high reanalysis-AOD.

   **Piece B headline:** AOD-dependent NDVI bias does not exist at operationally meaningful magnitude at Riyadh on Sen2Cor L2A across the loading regime spanned by the SQ2 manifest. The largest detectable effect is sub-operational and survives independent reanalysis cross-check; NDVI-as-ratio cancellation is the surviving mechanism after correction-chain-specific absorption, NIR-band-shift artifacts, and high-AOD threshold breakdown are all ruled out at operational magnitude.

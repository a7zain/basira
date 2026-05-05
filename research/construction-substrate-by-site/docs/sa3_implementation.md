# SA3 — Implementation Spec (Addendum to Pre-registration)

**Status:** Locked 2026-05-05. Addendum to pre_registration.md §SA3.
**Purpose:** Resolve implementation details left at one-line resolution in the pre-reg, before execution. Locked now while piece B context is fresh.

## Inputs (all reused from piece B — no recomputation)

1. **NDVI residuals** — piece B's per-AOI per-month climatology table. Source: piece B output under `research/dust-honesty/data/`. SA3 takes `ndvi_residual` as the dependent variable, no recomputation. Rationale: piece B's null finding (β_aod ≈ 0) is a load-bearing input to SA3's interpretation. Recomputing the residual with a different spec would introduce spec-confound rather than substrate signal.

2. **BSI** — from SA1 output `data/sa1_bsi_baseline/{aoi}_bsi_per_scene.csv`. Filter to `sensor == "S30"` only. L30 dropped from SA3.

3. **MERRA-2 AOD (DUEXTTAU)** — piece B's AOD table under `research/dust-honesty/data/`. SA3 takes `aod_duexttau` directly, no refetch.

## Sensor scope: S30-only

SA3 uses S30 scenes only. L30 BSI rows from SA1 are dropped before regression. Cross-sensor questions belong to SA4 by design.

Rationale: piece B's NDVI residual was constructed on S30. Mixing L30 BSI against S30 NDVI residual at the same date introduces a sensor-mismatch confound that has nothing to do with substrate. SA3 is the mechanism test; clean single-sensor data protects the causal interpretation.

## Join keys

Three-table inner join on `(aoi, scene_date)`: SA1 S30 BSI ⨝ piece B NDVI residual ⨝ piece B AOD. Inner join. Missing in any source = scene drops out of regression. No imputation. Date matching: exact. NDVI and BSI are computed on the same scene, so dates match by construction. AOD is daily MERRA-2; exact date match.

## Cloud filter

Per pre-reg: `cloud_fraction < 0.3` for SA3. Note: SA1 already filters at `< 0.1`, so the SA3 filter is inherited at `< 0.1` in practice. Documented as inherited, not relaxed.

## Specifications (both pre-registered)

### Headline: pooled with AOI fixed effects
ndvi_residual ~ bsi + aod_duexttau + C(aoi)

HC3 robust standard errors. One β_bsi, one CI, one significance test. Reports as primary result.

### Heterogeneity check: per-AOI

Three regressions, one per AOI, each `ndvi_residual ~ bsi + aod_duexttau` filtered to that AOI. HC3 robust standard errors. Three β_bsi values, three CIs. Reports as heterogeneity check.

**Pre-registered interpretation rule:** If pooled β_bsi fires significant + magnitude criterion but per-AOI shows the effect is concentrated at Qiddiya — this is the expected pattern under the substrate hypothesis, not a contradiction. Substrate-primary predicts Qiddiya-loaded heterogeneity by design. If pooled fires but per-AOI shows the effect at KSP or Diriyah (not Qiddiya) — substantive surprise, primary finding. If pooled fires uniformly across all three — substrate signal more general than predicted, primary finding.

## Dual criterion (per pre-reg, applied to pooled regression)

- **Significance:** β_bsi 95% CI excludes zero.
- **Magnitude:** β_bsi × IQR(BSI) > 0.005 (operational change-detection threshold from piece B SQ8). IQR(BSI) computed per regression: pooled IQR for pooled spec, per-AOI IQR for per-AOI specs.
- Both must hold. Disagreement = finding, not failure.

## Halt rules (per pre-reg)

- Per-AOI usable n < 20 after join → halt the per-AOI regression for that site. Pooled-only result ships. Halt receipt under `data/halts/sa3_coverage/{aoi}.md`.
- All-AOI usable n < 60 (pooled) → halt SA3 entirely. Surface coverage deficit as structural finding.

## Outputs

- `data/sa3_bsi_ndvi_regression/regression_results.csv` — one row per spec (pooled + 3 per-AOI). Columns: spec, n, beta_bsi, beta_bsi_ci_lo, beta_bsi_ci_hi, beta_bsi_pvalue, beta_aod, beta_aod_ci_lo, beta_aod_ci_hi, beta_aod_pvalue, magnitude_check (beta_bsi × IQR), magnitude_passes (bool).
- `data/sa3_bsi_ndvi_regression/sa3_results.md` — narrative summary: headline result, heterogeneity result, dual criterion outcome, halt status if any.
- `figures/sa3_bsi_vs_ndvi_residual.png` — scatter of NDVI residual vs BSI, colored by AOI, regression lines per AOI + pooled.

## What's NOT in SA3

Cross-sensor S30 vs L30 questions → SA4. Operational false-positive reduction → SA5. Generalization claim → SA6. BSI phase structure / quartile interpretation → SA2. SA3 is one regression. The umbrella question's mechanism test, scoped tight.

# SQ8 — high-AOD regression: summary stats

Goyens-regime test inherited from SQ5 halt. Per-scene NDVI residual (relative to per-AOI per-month climatology) regressed on reanalysis AOD with AOI fixed effects, HC3 robust SEs.

AERONET unavailable: no station within 500 km of Riyadh during the SQ2 window (Solar_Village dead 2015-10-12, Bahrain dead 2007-03-06, UAE cluster ~750–800 km outside 500 km outer ring). Reanalysis primary: MERRA-2 DUEXTTAU (dust extinction at 550 nm). Cross-check: CAMS NRT total AOD at 550 nm.

## Coverage

- SQ2 manifest dates: 228
- MERRA-2 DUEXTTAU coverage: 225/228 = 98.7%
- CAMS total AOD coverage: 228/228 = 100.0%
- Joined rows with NDVI + MERRA-2: 224
- Joined rows with NDVI + CAMS: 226

## Pooled MERRA-2 DUEXTTAU distribution

- Q1 (25th pct) = 0.1404
- Mean         = 0.2399
- Q4 (75th pct) = 0.3159
- IQR (Q4 − Q1) = 0.1755

## Primary regression (MERRA-2 DUEXTTAU + AOI fixed effects, HC3)

| metric | value |
|---|---:|
| AOD coefficient β | -0.010122 |
| Robust SE (HC3) | 0.004480 |
| p-value | 0.0239 |
| 95% CI on β | [-0.018903, -0.001342] |
| n | 224 |
| R² | 0.0278 |
| β × IQR (predicted Δ NDVI Q1→Q4) | -0.001776 NDVI units |
| 95% CI on β × IQR | [-0.003317, -0.000236] |

## Cross-check (CAMS total AOD + AOI fixed effects, HC3)

| metric | value |
|---|---:|
| AOD coefficient β | -0.007307 |
| Robust SE (HC3) | 0.003059 |
| p-value | 0.0169 |
| 95% CI on β | [-0.013302, -0.001312] |
| n | 226 |
| R² | 0.0126 |
| β × IQR (predicted Δ NDVI Q1→Q4) | -0.001389 NDVI units |

**Cross-source agreement**: sign agreement ✓; CI overlap with primary ✓.

**MERRA-2 vs CAMS Spearman ρ on shared dates** = 0.664.

## Per-AOI sensitivity regressions (separate OLS, no fixed effects, HC3)

| AOI | n | β | 95% CI | p | individual sig? |
|---|---:|---:|---|---:|---|
| King Salman Park | 74 | -0.0085 | [-0.0197, +0.0027] | 0.138 | n.s. |
| Qiddiya core | 75 | -0.0083 | [-0.0200, +0.0035] | 0.169 | n.s. |
| Diriyah Gate | 75 | -0.0132 | [-0.0338, +0.0073] | 0.208 | n.s. |

**No individual AOI is significant on its own. The pooled signal arises from n=224 power of the fixed-effects model.**

## Diriyah pre-registered Goyens-regime anchor cell

Cell: Diriyah ∧ UVAI Q4 ∧ ¬V4-fired.

- n = 12 scenes
- mean MERRA-2 DUEXTTAU at this cell = 0.3303
- model prediction at this AOD = -0.001714 NDVI
- 95% CI on prediction = [-0.004574, +0.001146]

**Anchor-cell prediction CI includes zero — pre-registered headline-anchor cell does not individually confirm a Goyens-regime bias.**

## Signal classification

Per the SQ8 prompt's Option 4 framing decision: the pre-registered classifier output and the magnitude criterion BOTH fire on this result. Both are reported here as a methodology finding rather than reconciled by override; the framing prose is deferred to `sq8_findings.md` drafted in a later session.

| criterion | rule | this run | classification |
|---|---|---|---|
| Pre-registered classifier | 95% CI on β excludes zero AND β < 0 | CI [-0.0189, -0.0013] excludes 0; β = -0.0101 | `goyens_consistent_bias_detected` |
| Pre-registered magnitude | &#124;β × IQR&#124; < 0.005 NDVI → tight_null | &#124;-0.0018&#124; = 0.0018 < 0.005 | `tight_null` |

Classifier sq8_signal_class.csv preserves the canonical pre-registered classifier output: `goyens_consistent_bias_detected`. The dual-criterion observation is the headline of the figures and this summary table; framing prose is OUT OF SCOPE for this commit cycle.

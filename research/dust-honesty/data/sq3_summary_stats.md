# SQ3 summary stats

Inputs: `sq3_ndvi_bias.csv`, `sq3_pairing_audit.csv`. All bootstrap CIs use 1000 resamples of pairs with replacement, seed=42.

## Per-AOI table

| AOI | n_fired | n_paired | retention% | mean Δ NDVI | 95% CI | CI halfwidth | signal_class |
|---|---:|---:|---:|---:|---|---:|---|
| King Salman Park | 24 | 14 | 58.3 | +0.0016 | [-0.0056, +0.0097] | 0.0076 | tight_null |
| Qiddiya core | 57 | 16 | 28.1 | -0.0024 | [-0.0075, +0.0036] | 0.0055 | tight_null |
| Diriyah Gate | 9 | 8 | 88.9 | -0.0002 | [-0.0220, +0.0224] | 0.0222 | wide_inconclusive |

## Per-pair Δ distribution (sample percentiles)

| AOI | n | min | p25 | median | p75 | max |
|---|---:|---:|---:|---:|---:|---:|
| King Salman Park | 14 | -0.0192 | -0.0091 | -0.0013 | +0.0086 | +0.0302 |
| Qiddiya core | 16 | -0.0185 | -0.0126 | +0.0002 | +0.0055 | +0.0225 |
| Diriyah Gate | 8 | -0.0484 | -0.0184 | +0.0005 | +0.0145 | +0.0600 |

## dt_days distribution per AOI

| AOI | n_paired | min |Δt| | median |Δt| | max |Δt| |
|---|---:|---:|---:|---:|
| King Salman Park | 14 | 5 | 35.0 | 55 |
| Qiddiya core | 16 | 20 | 40.0 | 60 |
| Diriyah Gate | 8 | 15 | 36.0 | 55 |


# SQ4 — HLS vs Sen2Cor Δ NDVI: per-AOI summary

Pairs from SQ3 (n=38). HLS NDVI computed at AOI mean, native 30 m, 
Fmask bits 1-4 masked (cloud, adj, shadow, snow). NIR band: HLS B8A 
(narrow ~865 nm); Red: HLS B4 ~665 nm. SQ3 Sen2Cor used B8 broad 
NIR ~833 nm — see §5 of sq4_findings.md for the band-shift caveat.

diff_of_diffs = Δ NDVI (HLS LaSRC) − Δ NDVI (S2 Sen2Cor)  per pair.
Bootstrap: 1000 resamples on pairs (seed 42).

| AOI | n_kept / n_sq3 | mean diff | 95% CI | halfwidth | signal_class |
|---|---:|---:|---|---:|---|
| King Salman Park | 14/14 | -0.0062 | [-0.0136, +0.0006] | 0.0071 | `tight_null` |
| Qiddiya core | 15/16 | -0.0021 | [-0.0069, +0.0026] | 0.0047 | `tight_null` |
| Diriyah Gate | 8/8 | -0.0009 | [-0.0141, +0.0134] | 0.0138 | `wide_inconclusive` |

Per-AOI scope-conditional reads:
- **King Salman Park**: tight null. HLS LaSRC and Sen2Cor agree on Δ NDVI to within halfwidth 0.0071. The SQ3 conditional null is not Sen2Cor-specific at this AOI.
- **Qiddiya core**: tight null. HLS LaSRC and Sen2Cor agree on Δ NDVI to within halfwidth 0.0047. The SQ3 conditional null is not Sen2Cor-specific at this AOI.
- **Diriyah Gate**: wide-inconclusive on n alone (n=8). CI halfwidth 0.0138 is above the 0.01 tight-null threshold — same SQ8 AERONET hook as SQ3.

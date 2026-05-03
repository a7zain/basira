# SQ4B Arm A — B8 broad-NIR sensitivity on HLS S30

Pairs from SQ3 (n=38). Arm A reruns SQ4's compute pipeline on
HLS S30 v2.0 with broad NIR (B8 ~833nm) instead of narrow NIR
(B8A ~865nm) used in SQ4. Same correction chain (LaSRC), same
AOI mean / native 30m / single-image single-reducer / mosaic()
across MGRS tiles. Fmask bits 1–4 masked. Bootstrap 1000 on
pairs (seed 42).

Pair retention: 37/38 = 97.4% (1 dropped, parity with SQ4 single-loss).

## §3 Arm A per-AOI signal classification

| AOI | n_kept / n_sq3 | mean diff | 95% CI | halfwidth | signal_class |
|---|---:|---:|---|---:|---|
| King Salman Park | 14/14 | -0.0027 | [-0.0055, +0.0002] | 0.0028 | `tight_null` |
| Qiddiya core | 15/16 | +0.0012 | [-0.0010, +0.0034] | 0.0022 | `tight_null` |
| Diriyah Gate | 8/8 | -0.0009 | [-0.0156, +0.0137] | 0.0146 | `wide_inconclusive` |

## §3.1 Two-by-two summary (correction chain × NIR band)

Cells: raw mean Δ NDVI per pair (paired V4-fired minus
unflagged neighbor), bootstrap halfwidth on the same
pair set used for that cell.

| AOI | chain | NIR | n | mean Δ NDVI | halfwidth | scope |
|---|---|---|---:|---:|---:|---|
| King Salman Park | Sen2Cor | B8 (broad ~833nm) | 14 | +0.0016 | 0.0076 | yes (from SQ3) |
| King Salman Park | Sen2Cor | B8A (narrow ~865nm) | — | — | — | no (S2 L2A delivers B8 as primary NIR; B8A is supplementary, not exercised in SQ3) |
| King Salman Park | LaSRC (HLS S30) | B8 (broad ~833nm) | 14 | -0.0011 | 0.0063 | yes (this run, SQ4B Arm A) |
| King Salman Park | LaSRC (HLS S30) | B8A (narrow ~865nm) | 14 | -0.0046 | 0.0032 | yes (from SQ4) |
| Qiddiya core | Sen2Cor | B8 (broad ~833nm) | 16 | -0.0024 | 0.0055 | yes (from SQ3) |
| Qiddiya core | Sen2Cor | B8A (narrow ~865nm) | — | — | — | no (S2 L2A delivers B8 as primary NIR; B8A is supplementary, not exercised in SQ3) |
| Qiddiya core | LaSRC (HLS S30) | B8 (broad ~833nm) | 15 | -0.0005 | 0.0042 | yes (this run, SQ4B Arm A) |
| Qiddiya core | LaSRC (HLS S30) | B8A (narrow ~865nm) | 15 | -0.0038 | 0.0021 | yes (from SQ4) |
| Diriyah Gate | Sen2Cor | B8 (broad ~833nm) | 8 | -0.0002 | 0.0222 | yes (from SQ3) |
| Diriyah Gate | Sen2Cor | B8A (narrow ~865nm) | — | — | — | no (S2 L2A delivers B8 as primary NIR; B8A is supplementary, not exercised in SQ3) |
| Diriyah Gate | LaSRC (HLS S30) | B8 (broad ~833nm) | 8 | -0.0011 | 0.0092 | yes (this run, SQ4B Arm A) |
| Diriyah Gate | LaSRC (HLS S30) | B8A (narrow ~865nm) | 8 | -0.0011 | 0.0095 | yes (from SQ4) |

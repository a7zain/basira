# SQ4 — HLS NDVI cross-check on V4-flagged pairs

**Status:** DONE (2026-05-02). Cross-correction tight null at the two AOIs with adequate n.

## §1 Question and locked design

Question: is the SQ3 conditional null Sen2Cor-specific, or does the same V4-flagged-vs-neighbor difference structure hold under a different atmospheric correction chain? SQ4 reuses SQ3's 38 pre-registered pairs (V4-fired scene paired to nearest unflagged neighbor in the same AOI within ±60 days) and recomputes Δ NDVI under HLS S30 v2.0 (LaSRC atmospheric correction, NASA HLS User Guide v2). Statistic: per-pair `diff_of_diffs = Δ NDVI(HLS LaSRC) − Δ NDVI(S2 Sen2Cor)`, bootstrapped on pairs (1000 resamples, seed 42), per-AOI 95% CI. Locked design decisions: HLSS30 v2.0 only (L30 deferred to SQ4B); SQ3 pairs reused unmodified; HLS computed at AOI mean, native 30 m; NIR = `B8A`, Red = `B4`; single-image single-reducer pattern matching SQ2/SQ3.

## §2 Recon results (R1–R4)

| check | result |
|---|---|
| **R1** HLS S30 coverage on 65 unique (AOI, pair-date) tuples (±1 d window) | KSP 24/24, Qiddiya 27/27, Diriyah 14/14 — **100%** all AOIs |
| **R2** EECU estimate | <5 EECU (65 tuples × 3 ops × tiny AOIs at 30 m) — well under 30 EECU floor |
| **R3** Column compatibility | SQ3 column is `delta_ndvi`; aliased as `delta_sen2cor` in SQ4 outputs |
| **R4** Fmask present | Confirmed (8-bit packed). Reject mask: bits 1–4 (cloud, adj, shadow, snow). Cirrus and water bits NOT masked (cirrus over bright desert is a known HLS Fmask false-positive case; AOIs are inland) |

GEE band naming caveat surfaced at R4: HLSS30 v002 in GEE uses `B4`/`B8`/`B8A` (not `B04`/`B08`/`B8A`). Documented in script header.

## §3 Per-AOI table

| AOI | n_kept / n_sq3 | mean diff | 95% CI | halfwidth | signal_class |
|---|---:|---:|---|---:|---|
| King Salman Park | 14/14 | −0.0062 | [−0.0136, +0.0006] | 0.0071 | `tight_null` |
| Qiddiya core | 15/16 | −0.0021 | [−0.0069, +0.0026] | 0.0047 | `tight_null` |
| Diriyah Gate | 8/8 | −0.0009 | [−0.0141, +0.0134] | 0.0138 | `wide_inconclusive` |

Pair retention 37/38 (97.4%). One pair lost: Qiddiya `2020-04-25 → 2020-03-01` — the fired-side HLS scene was fully Fmask-rejected (real fully-clouded scene; n=14 mosaicked tiles, all rejected). Pair was dropped honestly, not retried.

Per-AOI scope-conditional reads:
- **KSP**: tight null. HLS LaSRC and Sen2Cor agree on Δ NDVI to within halfwidth 0.0071 — about an order of magnitude below NDVI change-detection thresholds (~0.05+). The SQ3 conditional null is not Sen2Cor-specific at this AOI.
- **Qiddiya**: tight null. Halfwidth 0.0047. Even tighter cross-correction agreement than KSP, despite Qiddiya's V4 fires being construction-substrate-driven (SQ2 finding) rather than atmospheric.
- **Diriyah**: wide-inconclusive on n alone (n=8). Halfwidth 0.0138 sits above the 0.01 tight-null threshold — same SQ8 AERONET hook as SQ3, now reinforced.

Both tight-null means are slightly negative (KSP −0.0062, Qiddiya −0.0021): directionally consistent across AOIs but each CI includes zero and the magnitudes are well below change-detection magnitude. Reported as an observation, not a finding.

## §4 Interpretation

The pre-registered SQ4 finding is that **at the two AOIs with adequate n (KSP, Qiddiya), the SQ3 conditional null survives the LaSRC cross-check at tight-null magnitude.** The V4-flagged-vs-neighbor Δ NDVI does not differ between Sen2Cor (S2 L2A) and LaSRC (HLS S30) at change-detection magnitude on the paired ±60-day design. This rules out the "Sen2Cor specifically absorbs the bias at moderate loadings" interpretation as the sole explanation for SQ3's null. The two candidate explanations named in `sq3_findings.md` reduce to one:

1. ~~Sen2Cor L2A specifically absorbs the predicted bias at moderate loadings while a different correction chain would expose it.~~ — **not supported** (LaSRC behaves the same way).
2. **NDVI-ratio cancellation**: Red and NIR are both perturbed by aerosol scattering in the same direction, so the ratio (B8A − B4) / (B8A + B4) attenuates the signal regardless of correction chain. Surviving candidate.

The honest claim now extends one layer: *"On both Sen2Cor L2A NDVI and HLS LaSRC NDVI at Riyadh-region moderate atmospheric loadings, V4-flagged scenes do not exhibit a measurable bias relative to near-temporal unflagged neighbors at change-detection magnitude. The cross-correction agreement makes correction-chain-specific absorption an unlikely sole mechanism."*

This does NOT say:
- Sen2Cor and LaSRC are universally fine. Both share the surviving NDVI-ratio cancellation hypothesis; neither has been independently anchored to AERONET ground truth at the study AOIs in this work.
- Goyens 2024 is wrong. The Goyens TOA-reflectance / extreme-AOD regime is not the regime tested here; transfer is not assumed in either direction.

The Diriyah wide-inconclusive (n=8) does not rule out a hidden LaSRC-specific bias at the desert-edge AOI; it only says the current SQ4 design lacks the power to detect one. SQ8 (AERONET at KAUST) remains the right anchor.

## §5 Limitations

1. **Band-center shift in NIR.** SQ3 used Sen2Cor `B8` (broad NIR, ~833 nm). SQ4 uses HLS `B8A` (narrow NIR, ~865 nm) per NASA HLS User Guide v2 NDVI convention. The two NIR bands respond slightly differently to vegetation and to aerosol scattering; the offset mostly cancels in pair differencing (both fired and neighbor are computed with the same band on each chain) but does not fully cancel because aerosol absorption differs between the two NIR centers. Reported `diff_of_diffs` is therefore not a pure correction-chain difference — it absorbs ~30 nm of NIR center shift. A `B8`-on-HLS reanalysis would isolate the correction-chain effect more cleanly; deferred to SQ4B.
2. **Cloud-mask algorithm differs.** HLS Fmask (Lasrc-derived) vs Sen2Cor SCL classify clouds via different algorithms. Bright desert is a known HLS Fmask false-positive surface. One Qiddiya scene (2020-04-25) was fully Fmask-rejected on HLS but had a usable Sen2Cor NDVI in SQ3. Different valid-pixel pools for the same date.
3. **Native grid differs.** HLS S30 at 30 m vs Sen2Cor L2A at 20 m. AOI-mean reduction at native scale partially absorbs the resolution difference, but the pixel-set membership is not identical. No HLS-to-S2 resampling was performed — locked decision.
4. **Multi-scene mosaic policy.** 39 of 65 dates required mosaicking 2+ HLS tiles to cover the AOI (Riyadh AOIs sit at the corner of MGRS tiles T38R/T39R). The mosaic blends band values across overlapping tiles in regions where the AOI bbox crosses a tile seam. Same-day acquisitions are co-acquired so blending is small in practice; documented in script header. The first-attempt `coll.first()` would have lost 39 dates to sliver-coverage tiles — caught and fixed before commit.
5. **Sample size per AOI is small.** n_kept ranges from 8 (Diriyah) to 15 (Qiddiya). The bootstrap CIs are pair-level, but small-n bootstraps under-cover at the tails. The tight-null finding is robust for KSP and Qiddiya within the design's resolution; Diriyah remains explicitly underpowered.

## §6 Cross-validation hooks

- **SQ4B (HLS L30 = Landsat 8/9 OLI surface reflectance).** Given SQ4-S30 supports the SQ3 null, L30 would add a third correction chain (LaSRC again on Landsat-OLI bands) covering the same V4-fired dates. If L30 also nulls, the cross-correction story tightens to "the predicted bias is below detection across all three major correction chains tested." If L30 disagrees with both S30 and Sen2Cor, that's a sensor-rather-than-chain finding. Either is publishable. Promoted from "if SQ4 supports it" → "supported, schedule SQ4B."
- **SQ8 (AERONET at KAUST Thuwal).** Already committed for piece B. Now reinforced by SQ4: the slight negative directional bias common to KSP and Qiddiya in `diff_of_diffs` (means −0.0062, −0.0021) is consistent with a small NDVI-ratio attenuation that AERONET ground truth could distinguish from "true zero." Diriyah's n=8 wide-inconclusive remains the primary AERONET target.
- **Internal consistency check.** Qiddiya's tight-null at halfwidth 0.0047 (the tightest of the three) is itself notable: even at the construction-substrate AOI with V4's 75% fire rate, the cross-correction Δ NDVI signal is suppressed. This is consistent with the SQ2 finding that V4 fires at Qiddiya are surface-driven not atmospheric — both chains see the same surface, so neither correction chain has a chance to disagree about an atmospheric perturbation that isn't there.

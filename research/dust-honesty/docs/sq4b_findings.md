# SQ4B — NIR-band sensitivity (Arm A only); Arm B deferred to SQ4C

**Status:** DONE (2026-05-02). Arm A: tight nulls at the two AOIs with adequate n. Arm B (L30 cross-check) deferred to SQ4C — pre-registered 50% L30 coverage floor failed at +/-1d in two of three AOIs.

## §1 Question and locked design

Question: does the SQ3/SQ4 conditional null hold under broad-vs-narrow NIR selection on the same correction chain (HLS S30, LaSRC)? Arm A reruns the SQ4 pipeline on the SQ3 pair set with broad NIR (`B8` ~833 nm, the same NIR center used by Sen2Cor in SQ3) instead of narrow NIR (`B8A` ~865 nm, used in SQ4). Statistic: per-pair `arm_a_diff = Δ NDVI(LaSRC B8) − Δ NDVI(Sen2Cor B8)`, bootstrapped on pairs (1000 resamples, seed 42), per-AOI 95% CI. Locked design decisions: HLSS30 v2.0 only; SQ3 pairs reused unmodified; AOI mean / native 30 m / single-image single-reducer / `coll.mosaic()` across MGRS tiles / Fmask bits 1–4 masked. Arm B (L30 cross-check) was pre-registered for SQ4B and is **deferred to SQ4C** — see §2 for the recon-driven rationale.

## §2 Recon results (R1–R4)

| check | result |
|---|---|
| **R1** L30 coverage on 65 unique (AOI, pair-date) tuples (±1 d) | KSP **54.2%** (13/24), Qiddiya **33.3%** (9/27), Diriyah **42.9%** (6/14). Total 28/65 = **43.1%**. Pre-registered 50% floor failed in 2 of 3 AOIs. |
| **R2** EECU estimate (Arm A, 65 tuples × 3 ops × tiny AOIs at 30 m) | <5 EECU; well under 30 floor. |
| **R3** Column compatibility | SQ3 col `delta_ndvi` aliased to `delta_sen2cor`; join keys `(aoi, fired_date, neighbor_date)` unchanged from SQ4. |
| **R4** Band naming | S30 exposes `B4, B8, B8A, Fmask`. L30 exposes `B4, B5, Fmask` (no B8/B8A — OLI has fewer bands). All confirmed in `sq4b_l30_coverage_probe.csv` recon run. |

**Why R1 failed structurally.** SQ3 pairs are anchored on Sentinel-2 acquisition dates. S2A+B combined cadence over Riyadh is ~5 d; Landsat 8+9 combined cadence is ~8 d. Probability of a Landsat overpass within ±1 d of any given S2 date is ~3/8 = 37.5% as a baseline, modulated by orbit-track geometry per AOI. KSP at 54.2% sits above the baseline; Qiddiya 33.3% and Diriyah 42.9% are about at the baseline. **This is cadence-mismatch baked into pairing OLI dates against MSI dates, not a data quality issue.** The two design changes that would route around it — switching to native L30 dates, or widening the pair window — were both explicitly disallowed in the SQ4B prompt. The pre-registered stop-rule fired as designed; halt-and-surface was the correct response.

**SQ4C deferral (the L30 question, redone with discipline).** Promoted from "if SQ4 supports it" to its own pre-registered design: build pairs on Landsat overpass dates (V4-fired Landsat scene paired to nearest unflagged Landsat neighbor in the same AOI within ±k days), then match Sen2Cor scenes to those Landsat dates via ±k-day matching for the diff_of_diffs reference. Out of scope for the current pass.

**In-build corrections (parity with SQ4 mosaic note).** None new. SQ4's `coll.mosaic()` pattern (locked after SQ4 caught `coll.first()` silently dropping MGRS sliver tiles) was carried forward unchanged. Self-reference unit test passed at run start (`B8 NDVI = +0.070713` twice on KSP 2021-05-05). Same single Qiddiya 2020-04-25 fully-clouded scene wiped out as in SQ4 (1 dropped pair).

## §3 Per-AOI table — Arm A signal classification

| AOI | n_kept / n_sq3 | mean diff | 95% CI | halfwidth | signal_class |
|---|---:|---:|---|---:|---|
| King Salman Park | 14/14 | −0.0027 | [−0.0055, +0.0002] | 0.0028 | `tight_null` |
| Qiddiya core | 15/16 | +0.0012 | [−0.0010, +0.0034] | 0.0022 | `tight_null` |
| Diriyah Gate | 8/8 | −0.0009 | [−0.0156, +0.0137] | 0.0146 | `wide_inconclusive` |

**Spearman cross-check (diagnostic).** Per-scene B8 vs B8A NDVI on shared (aoi, date) rows: ρ = **0.868** on n = 64. Below the 0.95 flag threshold — meaningful per-scene divergence between broad and narrow NIR at the absolute NDVI level. Within-AOI, B8 is systematically lower than B8A by ~0.02–0.03 NDVI units (KSP B8 ≈ 0.06, B8A ≈ 0.09; Qiddiya B8 ≈ 0.07, B8A ≈ 0.09; Diriyah B8 ≈ 0.12, B8A ≈ 0.14). The diff_of_diffs design absorbs this additive offset because both sides of each pair are computed with the same band on the same chain — the per-scene divergence does not propagate to a per-pair Δ difference. This is itself a finding: at the absolute-NDVI level, broad and narrow NIR are not interchangeable, but the SQ3-style change-detection design is insensitive to this band shift.

## §3.1 Two-by-two summary (correction chain × NIR band)

Cells: raw mean Δ NDVI per pair (paired V4-fired minus unflagged neighbor), bootstrap halfwidth on the same pair set used for that cell.

| AOI | chain | NIR | n | mean Δ NDVI | halfwidth | scope |
|---|---|---|---:|---:|---:|---|
| King Salman Park | Sen2Cor | B8 (broad ~833nm) | 14 | +0.0016 | 0.0076 | yes (from SQ3) |
| King Salman Park | Sen2Cor | B8A (narrow ~865nm) | — | — | — | no (S2 L2A delivers B8 as primary NIR; B8A supplementary, not exercised in SQ3) |
| King Salman Park | LaSRC (HLS S30) | B8 (broad ~833nm) | 14 | −0.0011 | 0.0066 | yes (this run, SQ4B Arm A) |
| King Salman Park | LaSRC (HLS S30) | B8A (narrow ~865nm) | 14 | −0.0046 | 0.0099 | yes (from SQ4) |
| Qiddiya core | Sen2Cor | B8 (broad ~833nm) | 16 | −0.0024 | 0.0055 | yes (from SQ3) |
| Qiddiya core | Sen2Cor | B8A (narrow ~865nm) | — | — | — | no (as above) |
| Qiddiya core | LaSRC (HLS S30) | B8 (broad ~833nm) | 15 | −0.0001 | 0.0062 | yes (this run, SQ4B Arm A) |
| Qiddiya core | LaSRC (HLS S30) | B8A (narrow ~865nm) | 15 | −0.0035 | 0.0084 | yes (from SQ4) |
| Diriyah Gate | Sen2Cor | B8 (broad ~833nm) | 8 | −0.0002 | 0.0222 | yes (from SQ3) |
| Diriyah Gate | Sen2Cor | B8A (narrow ~865nm) | — | — | — | no (as above) |
| Diriyah Gate | LaSRC (HLS S30) | B8 (broad ~833nm) | 8 | −0.0014 | 0.0228 | yes (this run, SQ4B Arm A) |
| Diriyah Gate | LaSRC (HLS S30) | B8A (narrow ~865nm) | 8 | −0.0011 | 0.0226 | yes (from SQ4) |

Across the three filled cells per AOI (Sen2Cor B8 / LaSRC B8 / LaSRC B8A), all means sit within ±0.005 NDVI of zero at KSP and Qiddiya, and within ±0.002 at Diriyah. KSP and Qiddiya halfwidths are all <0.01. Diriyah halfwidths are all ~0.022 — same n=8 issue across the board.

## §4 Interpretation

The pre-registered Arm A finding is that **at the two AOIs with adequate n (KSP, Qiddiya), the SQ3/SQ4 null is robust to NIR band selection within HLS S30 LaSRC.** The piece B claim narrows to:

> *"On Sen2Cor L2A NDVI (B8 broad NIR) and on HLS S30 LaSRC NDVI (both B8 broad and B8A narrow NIR) at Riyadh-region moderate atmospheric loadings, V4-flagged scenes do not exhibit a measurable bias relative to near-temporal unflagged neighbors at change-detection magnitude."*

The candidate-explanation list updated through SQ4B:
1. ~~Sen2Cor L2A specifically absorbs the bias.~~ — ruled out by SQ4 (LaSRC also nulls on B8A).
2. ~~Narrow-vs-broad NIR band selection accounts for the null on LaSRC.~~ — **ruled out by SQ4B Arm A** (LaSRC B8 broad also nulls; arm_a_diff halfwidths 0.0022–0.0028 at adequate-n AOIs).
3. **NDVI-as-ratio cancellation between Red and NIR perturbations.** — surviving candidate.

Surviving candidate is now load-bearing for the piece B mechanism story. The aerosol perturbation produces correlated Red and NIR shifts; the NDVI ratio (NIR − Red) / (NIR + Red) is mathematically less sensitive to that correlated shift than either band alone. Two correction chains and two NIR bands all behave the same way because none of them break the Red/NIR correlation.

What this still does NOT say:
- **Sen2Cor and LaSRC are universally fine.** They share the surviving NDVI-ratio cancellation; neither has been independently anchored to AERONET ground truth at the study AOIs in this work.
- **Goyens 2024 is wrong.** The Goyens TOA-reflectance / extreme-AOD regime is not the regime tested here.
- **Diriyah has no LaSRC-specific bias.** n=8 lacks the power; SQ8 (KAUST AERONET) remains the right anchor.
- **Arm B (L30 cross-check) is unanswered** — deferred to SQ4C with native L30 pair construction.

The directional pattern across cells is worth one observation: at KSP, the LaSRC-B8A mean (−0.0046) sits slightly more negative than LaSRC-B8 (−0.0011) and Sen2Cor-B8 (+0.0016). At Qiddiya, the same ordering holds (LaSRC-B8A −0.0035 < LaSRC-B8 −0.0001 < Sen2Cor-B8 −0.0024). The narrow NIR band tracks slightly more negative than broad NIR on the LaSRC chain — consistent with B8A being more sensitive to vegetation-water interactions (red-edge proximity) and showing a small atmospheric-suppression on V4-fired scenes. None of these differences exceed their CIs; reported as an observation, not a finding.

## §5 Limitations

1. **HLS QA differs from Sen2Cor QA.** HLS Fmask (LaSRC-derived) vs Sen2Cor SCL classify clouds via different algorithms. Bright desert is a known HLS Fmask false-positive surface. Same single-pair loss as SQ4 (Qiddiya 2020-04-25, fully Fmask-rejected).
2. **Native-grid coverage.** HLS S30 at 30 m vs S2 native 20 m for B8. AOI-mean reduction at native scale partially absorbs the resolution difference, but the pixel-set membership is not identical. Locked decision; no resampling.
3. **Sample size at Diriyah (n_kept = 8).** Carries forward the SQ8 AERONET hook.
4. **Three-chain framing was pre-registered but cannot be delivered in SQ4B.** Arm B (L30) requires its own pair design (SQ4C); see §6.
5. **NIR band offsets within HLS S30.** B8 (broad ~833 nm, ~100 nm bandwidth) vs B8A (narrow ~865 nm, ~20 nm bandwidth) are not identical bandpasses. The diff_of_diffs design absorbs additive offsets but not multiplicative or non-linear sensor differences. The Spearman ρ = 0.868 between B8 and B8A on shared dates demonstrates that the per-scene NDVI is sensitive to band choice; the fact that the per-pair Δ is not is a property of the differencing design, not the bands.
6. **Bootstrap small-n undercoverage.** Pair counts are 8–15 per AOI; tail coverage of bootstrap CIs at small n is known to be optimistic. The tight-null finding holds at KSP and Qiddiya within the design's resolution; Diriyah remains explicitly underpowered.

## §6 Cross-validation hooks

- **SQ4C (HLS L30 native pair construction) — DEFERRED, pre-registered.** Build pairs on Landsat overpass dates: V4-fired Landsat scene paired to nearest unflagged Landsat neighbor in the same AOI within ±k days, then match Sen2Cor scenes to those Landsat dates via ±k-day matching for the diff_of_diffs reference. Sketches the design; do NOT scope further until piece B's Arm-A-only ship lands.
- **SQ8 (KAUST AERONET) — anchor at Diriyah.** The wide-inconclusive AOI remains the load-bearing ground-truth target for piece B. Reinforced by SQ4B: the cross-chain cross-band agreement at KSP and Qiddiya makes ground-truth at Diriyah the only path to distinguish "true zero" from "small bias both chains and both NIRs share."
- **Internal consistency: SQ2 / SQ3 / SQ4 / SQ4B chain.** Four layers, each adding something the prior could not see.
  - **SQ2** detects atmospheric optical thickness via DBB (V4 flag fires at 11.8% Diriyah / 32.4% KSP / 75% Qiddiya — Diriyah aligns with shamal climatology, Qiddiya is construction-substrate not climatology).
  - **SQ3** measures Δ NDVI on V4-flagged vs near-temporal unflagged Sen2Cor B8 pairs and finds tight nulls (KSP halfwidth 0.0076, Qiddiya 0.0055) — the V4-detected atmospheric thickness does not propagate to NDVI bias at change-detection magnitude under Sen2Cor.
  - **SQ4** confirms the SQ3 null under HLS LaSRC B8A — rules out Sen2Cor-specific absorption; reduces candidate explanations from two to one.
  - **SQ4B Arm A** confirms the SQ3/SQ4 null under HLS LaSRC B8 broad NIR — rules out narrow-vs-broad NIR band selection as the surviving correction-chain-internal candidate. Three measured cells per AOI agree at change-detection magnitude.

  Two layers of the imaging chain remain consistent: atmospheric thickness (SQ2) is real; its propagation to NDVI is below detection at this design across two correction chains and two NIR bands (SQ3/SQ4/SQ4B). The piece B mechanism story now has one surviving candidate (NDVI-ratio cancellation) and one outstanding ground-truth anchor (SQ8 at Diriyah).

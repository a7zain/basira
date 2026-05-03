# SQ3 findings — NDVI bias on V4-flagged vs unflagged scenes

**Date:** 2026-05-02.
**Inputs:** `operational/dbb_operational_sq2.csv` (228 rows; 226 usable), `sq3_ndvi_per_scene.csv` (NDVI mean per scene on the same manifest), `sq3_ndvi_bias.csv`, `sq3_pairing_audit.csv`.
**Calibration anchor:** V4 = +0.034 (KSP+Diriyah scope, applied uniformly to all three AOIs).

## 1. Question

On the 226-usable-scene operational set, do Sen2Cor-derived NDVIs differ between V4-flagged and V4-unflagged scenes per AOI, at a magnitude that matters for change detection? Direction-agnostic — we report whichever sign shows up. The Goyens 2024 prediction (residual aerosol → low NDVI bias on flagged scenes) is the prior, but the analysis design does not assume it.

## 2. Method

**NDVI compute.** Per scene, NDVI = (B8 − B4) / (B8 + B4) from Sen2Cor L2A SR, masked to SCL ∈ {4, 5, 6, 7, 11} (veg / not-veg / water / unclassified / snow) AND B12 ≥ 0.01 (not water — same convention as the SQ1D faithful-Lolli mask). Spatial mean over the AOI bbox at 20 m native scale, single mean reducer + single sum+count valid-pixel reducer, no `bestEffort`. Manifest-locked to `operational/manifest_operational_sq2.csv` so every NDVI scene matches the DBB scene byte-for-byte on `system:index`.

**Pairing.** For each V4-fired scene at (AOI, date) with valid NDVI, find the temporally-nearest scene in the same AOI with `flag_v4=False`, `cloud_flag_present=False`, `no_usable_scene=False`, NDVI present, and |Δt| ≤ 60 days. Tie-break on equidistant neighbors: earlier date wins (deterministic). Unflagged neighbors may be reused across pairings; the bootstrap resamples PAIRS (not scenes), so within-AOI dependence is handled at inference time.

**Bootstrap.** 1000 resamples of pairs with replacement (seed = 42). 95% CI from 2.5 / 97.5 percentiles of the resampled means. ci_halfwidth = (ci_hi − ci_lo) / 2.

**Decision rule.** signal_negative if 95% CI excludes 0 and mean Δ < 0; signal_positive if CI excludes 0 and mean Δ > 0; tight_null if CI includes 0 and halfwidth < 0.01; else wide_inconclusive.

**Decision: V4 uniform across all three AOIs in the headline.** V3-KSP-only (+0.053) is a sensitivity consideration in §4, not the lead figure (same scope decision SQ2 settled on).

**Operational denominator:** 226 / 228 scenes usable (KSP 74, Qiddiya 76, Diriyah 76; two KSP scenes `no_usable_scene=True` from SCL granule-edge effects).

## 3. Results

| AOI | n_fired | n_paired | retention | mean Δ NDVI | 95% CI | halfwidth | signal_class |
|---|---:|---:|---:|---:|---|---:|---|
| King Salman Park | 24 | 14 | 58.3% | +0.0016 | [-0.0056, +0.0097] | 0.0076 | **tight_null** |
| Qiddiya core | 57 | 16 | 28.1% | -0.0024 | [-0.0075, +0.0036] | 0.0055 | **tight_null** |
| Diriyah Gate | 9 | 8 | 88.9% | -0.0002 | [-0.0220, +0.0224] | 0.0222 | **wide_inconclusive** |

**Per-AOI plain language:**

- **KSP**: tight null (95% CI [-0.0056, +0.0097], halfwidth 0.0076, n_paired=14, retention 58%). No measurable Sen2Cor NDVI bias on V4-flagged scenes at this AOI under this design.
- **Qiddiya**: tight null (95% CI [-0.0075, +0.0036], halfwidth 0.0055, n_paired=16, retention 28.1% — see §5). Direction consistent with Goyens prior but magnitude an order of magnitude below noise floor.
- **Diriyah**: wide inconclusive (95% CI [-0.0220, +0.0224], n_paired=8, retention 89%). Sample too small to call a sign — flag for SQ8 AERONET follow-up.

## 4. Direction discussion — observed sign vs Goyens prior

**The pre-registered prediction (Goyens-consistent negative Δ NDVI on flagged scenes) is not confirmed at these AOIs under this design.** The result is a *conditional null*: Sen2Cor L2A NDVI on V4-flagged scenes vs near-temporal unflagged neighbors does not exhibit the Goyens-predicted bias at moderate Riyadh-region atmospheric loadings, on the paired 60-day-window design. This is not a claim that Sen2Cor is correcting perfectly; it is not a claim that Goyens overstated the effect. The honest claim is scope-conditional — a null at moderate loadings, on this design, at these AOIs, with Sen2Cor L2A as the source.

Two reasons the Goyens prior may not transfer cleanly to the SQ3 setting (candidate explanations, not confirmed mechanisms):

- **Loading regime.** Goyens 2024 characterizes a TOA / extreme-AOD regime where Sen2Cor's underestimate is largest. At the moderate atmospheric loadings sampled by the V4 fires here (mean DBB +0.017 at KSP, -0.052 at Diriyah), Sen2Cor's L2A correction may absorb the bias even if it fails at higher loadings. The null may sharpen into a signal at AERONET-confirmed extreme-loading events; SQ8 is the right place to check that.
- **NDVI is a ratio.** Red and NIR are both perturbed by residual aerosol scattering. Partial cancellation in the (B8 − B4) / (B8 + B4) ratio attenuates whatever bias survives Sen2Cor's correction. This is a structural feature of the index, not an SQ3-specific limitation, and is consistent with the literature observation that NDVI is more robust to atmospheric noise than single-band reflectance.

## 5. Limitations

**(a) Qiddiya retention 28.1% is structural, not noise.** The unfired neighbor pool is small (19 unflagged scenes across 76 months) because SQ2 found that V4 fires on 75% of Qiddiya scenes — a direct consequence of construction-substrate contamination of the DBB index against the fixed 2024-01-20 reference. The pool is also clustered, so most fired Qiddiya months have no V4=0 anchor inside ±60 days. This does not invalidate the 16 pairs that did form — those pairs still produce a tight CI ([-0.0075, +0.0036], halfwidth 0.0055) — but it does mean Qiddiya's null is supported by a thinner sample than KSP's null, and the conclusion should be read with that asymmetry in mind.

**(b) Diriyah n_paired=8 yields a wide CI** (halfwidth 0.0222, an order of magnitude wider than KSP or Qiddiya). The AOI with the cleanest atmospheric prior — surface-stable desert edge, shamal-aligned fires, peak event 2022-05-10 cross-validated by SQ1C cold-protocol labels — is also the AOI with the smallest pair count. Tighter Diriyah CIs are the obvious SQ8 AERONET deliverable.

**(c) Pairing design is direction-agnostic** and the bootstrap on pairs handles neighbor reuse, but the 60-day window is a compromise between atmospheric specificity (shorter is better) and surface-state continuity (longer admits more pairs). A wider window was rejected to preserve atmospheric specificity at Qiddiya, where surface drift dominates beyond two months.

## 6. Cross-validation hooks

- **SQ4 (HLS NDVI) is positioned to test whether the null is Sen2Cor-specific.** HLS uses LaSRC for atmospheric correction (different chain from Sen2Cor); if HLS-NDVI on the same V4-fired scenes shows the Goyens-predicted negative bias and Sen2Cor-NDVI does not, the null collapses to a Sen2Cor-correction story. If both NDVIs agree on the null, it is a surface-driven result and Sen2Cor is exonerated for this loading regime.
- **SQ8 (KAUST AERONET) is positioned to add ground-truth atmospheric comparisons** that can tighten Diriyah CIs and decouple `small bias` from `small sample`. Solar Village (Riyadh) is dead since 2013, so KAUST Thuwal is the closest AERONET station; its different surface (coastal vs bright desert) is itself a generalization test for the SQ3 framework.
- **The SQ2-SQ3 chain is internally consistent.** V4 detects atmospheric optical thickness — confirmed by SQ2's Diriyah shamal-season alignment and the 2022-05-10 peak-event agreement with SQ1C cold-protocol labels — but that thickness does not propagate to NDVI bias at change-detection magnitude on Sen2Cor L2A SR. Both findings are real; they describe different layers of the imaging chain. SQ3's null does not invalidate SQ2's fire-rate readout; it bounds the downstream consequence for NDVI-based change monitoring.

---

_Footnote on what this note does not claim._ SQ3 measures Sen2Cor L2A NDVI on V4-flagged scenes against Sen2Cor L2A NDVI on unflagged temporal-neighbor scenes — not against a model-independent atmospheric reference. SQ4 (HLS / LaSRC) and SQ8 (KAUST AERONET) are the downstream chapters that cross the model-independence boundary.


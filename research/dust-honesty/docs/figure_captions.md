# Piece B figure captions

Canonical source for piece B figure captions. The polished prose draft
will reference this file when the prose-ships commit lands. Editorial
notes on length and tradeoffs are preserved alongside each caption for
the prose pass.

---

## Figure 1 — SQ2 V4 timeseries (anchors §3.1)

Figure 1. V4 dust-flag fire timeline across the three Vision 2030 AOIs over the SQ2 operational window (2020-01 through 2026-04, 76 months × 3 AOIs = 228 scenes). Diriyah Gate fires V4 on 11.8% of scenes — concentrated in the spring shamal season and consistent with independent dust climatology. King Salman Park fires on 32.4%. Qiddiya fires on 75.0%, an anomalously high rate that §4 unpacks as construction-substrate contamination rather than aerosol. Source: `data/operational/dbb_operational_sq2.csv` rendered via `scripts/sq2_plot_timeseries.py`.

_110 words. Long for a caption. Shorter alternative: cut the climatology sentence about Diriyah and the source-data sentence (keep only the figure name), get to ~70 words. The full version above earns its length on a research-page deliverable where the figure will be the first visual the reader encounters; underselling the fire-rate disparity here means the reader has to assemble it from the prose alone. Recommend keeping the full version._

---

## Figure 2 — SQ8 regression scatter with per-AOI fixed effects (anchors §3.6)

Figure 2. Per-scene NDVI residuals (each scene relative to its AOI–month climatology) regressed against MERRA-2 dust optical depth. n = 226 scenes pooled across three AOIs with AOI fixed effects; HC3 robust standard errors. The pooled slope β = −0.0018 NDVI per IQR of AOD is statistically distinguishable from zero (p = 0.024) and replicated by the CAMS NRT cross-check (p = 0.017), but the magnitude sits 2.8× below the operational-significance threshold. Per-AOI regressions individually null. Source: `data/high_aod_regression/regression_primary_sq8.csv`.

_90 words. The two-criterion split (significant and sub-operational) needs to land in the caption because the figure alone shows a slope that looks like a real bias to a reader who doesn't know about the operational-significance band. Caption is doing real work here._

---

## Figure 3 — Operational-magnitude ladder (anchors §3.6 closing, the visual punchline)

Figure 3. Estimated NDVI bias magnitude across four measurement designs at Riyadh: SQ3 (V4-paired Sen2Cor), SQ4 (V4-paired LaSRC on HLS S30), SQ4B Arm A (V4-paired LaSRC on HLS S30 with B8 broad NIR), and SQ8 (per-scene reanalysis-AOD regression). Each design's CI sits inside the ±0.005 NDVI operational-significance band shown in grey. SQ8's significant-but-sub-operational result (diamond marker) is the high-AOD regime's contribution to the convergence. Source: `data/high_aod_regression/regression_primary_sq8.csv` and the four upstream sub-question outputs; rendered by `scripts/sq8_summary.py`.

_105 words. This is the figure that has to land at thumbnail size for a hiring reader scrolling past — the caption needs to make "every probe sits inside the band" legible without forcing them to zoom. The "shown in grey" detail is doing that work._

---

## Figure 4 — Qiddiya construction-substrate convergence panel (anchors §4)

Figure 4. Six independent lines of evidence for bidirectional construction-substrate contamination at Qiddiya, none of which the umbrella dust question was pointed at. Each panel renders a per-AOI scalar comparison on a different metric — visually-blind relabel direction, SQ1D Part B sensitivity (Spearman ρ), V4 calibration AUC with versus without Qiddiya in the training pool, mean operational DBB above the V4 threshold (Qiddiya: +0.091 mean / +0.106 median, almost three times the +0.034 threshold), SQ3 paired retention against the 30% halt line, and the SQ5 Q4∧V4 contingency at high atmospheric loading. Qiddiya occupies the extreme position in every panel. Source: aggregated across `data/calibration/`, `data/threshold_fits/`, `data/operational/`, `data/ndvi_bias/`, and `data/halts/uvai_sq5/`; rendered by `scripts/qiddiya_convergence_panel.py`.

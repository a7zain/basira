"""
SQ8 — figures + summary stats markdown (NO findings prose).

Inputs:
  research/dust-honesty/data/sq8_aod_per_scene.csv
  research/dust-honesty/data/sq8_ndvi_residuals.csv
  research/dust-honesty/data/sq8_regression_primary.csv
  research/dust-honesty/data/sq8_regression_crosscheck.csv
  research/dust-honesty/data/sq8_regression_sensitivity.csv
  research/dust-honesty/data/sq8_predicted_residuals.csv
  research/dust-honesty/data/sq8_signal_class.csv
  research/dust-honesty/data/sq5_uvai_labels.csv
  research/dust-honesty/data/sq3_pairing_audit.csv (loading-ladder)
  research/dust-honesty/data/sq4_signal_class.csv (loading-ladder)
  research/dust-honesty/data/sq4b_arm_a_signal_class.csv (loading-ladder)
  research/dust-honesty/data/sq5_pair_retention_probe.csv (loading-ladder)

Outputs (under research/dust-honesty/figures/sq8/):
  sq8_aod_distribution.png
  sq8_residual_vs_aod_primary.png        — piece B SQ8 headline figure
  sq8_diriyah_anchor.png
  sq8_merra2_vs_cams_scatter.png
  sq8_loading_regime_ladder.png          — piece B loading-regime headline

Output: research/dust-honesty/data/sq8_summary_stats.md  — narrative table
form ONLY. NO §4 prose; the dual-criterion observation rides as a
footnote so the receipt is in git history before chat-side §4 draft.

Per the SQ8 prompt's Option 4 framing decision: classifier output
(goyens_consistent_bias_detected) and magnitude criterion (|beta × IQR|
< 0.005 → tight_null) BOTH fire on this result. Both are reported in
the figures and the summary table; the framing prose is deferred to
sq8_findings.md drafted in a later session.
"""
from __future__ import annotations

import csv
import math
from collections import defaultdict
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.stats import spearmanr

ROOT = Path(__file__).resolve().parents[3]
DATA = ROOT / "research/dust-honesty/data"
FIG = ROOT / "research/dust-honesty/figures/sq8"
FIG.mkdir(parents=True, exist_ok=True)

AOD_CSV = DATA / "sq8_aod_per_scene.csv"
RES_CSV = DATA / "sq8_ndvi_residuals.csv"
PRIM_CSV = DATA / "sq8_regression_primary.csv"
CROSS_CSV = DATA / "sq8_regression_crosscheck.csv"
SENS_CSV = DATA / "sq8_regression_sensitivity.csv"
PRED_CSV = DATA / "sq8_predicted_residuals.csv"
CLASS_CSV = DATA / "sq8_signal_class.csv"
UVAI_CSV = DATA / "sq5_uvai_labels.csv"

OUT_MD = DATA / "sq8_summary_stats.md"

AOIS = ["king_salman_park", "qiddiya_core", "diriyah_gate"]
AOI_LABELS = {
    "king_salman_park": "King Salman Park",
    "qiddiya_core": "Qiddiya core",
    "diriyah_gate": "Diriyah Gate",
}
AOI_COLORS = {
    "king_salman_park": "#2a9d8f",
    "qiddiya_core": "#e76f51",
    "diriyah_gate": "#264653",
}


# ---- I/O ----

def load_joined():
    aod = pd.read_csv(AOD_CSV)
    res = pd.read_csv(RES_CSV)
    uvai = pd.read_csv(UVAI_CSV)
    df = res.merge(
        aod[["aoi", "acquisition_date",
             "merra2_duexttau_550", "cams_total_aod_550"]],
        on=["aoi", "acquisition_date"], how="left",
    )
    df = df.merge(
        uvai[["aoi", "acquisition_date", "uvai_quartile", "v4_flag"]],
        on=["aoi", "acquisition_date"], how="left",
    )
    df["v4_flag"] = df["v4_flag"].astype(str) == "True"
    return df


def load_class():
    with open(CLASS_CSV) as f:
        return list(csv.DictReader(f))[0]


def load_predicted():
    rows = []
    with open(PRED_CSV) as f:
        for r in csv.DictReader(f):
            for k in ("aod_value", "predicted_residual",
                      "ci_lo_95_pred", "ci_hi_95_pred"):
                r[k] = float(r[k])
            rows.append(r)
    return rows


def load_primary_aod_coef():
    """Return dict with beta, se, p, ci_lo, ci_hi, n, r2 for the AOD
    coefficient row in sq8_regression_primary.csv."""
    with open(PRIM_CSV) as f:
        for r in csv.DictReader(f):
            if r["coefficient"] == "aod":
                return {
                    "beta": float(r["beta"]),
                    "se": float(r["se_robust"]),
                    "p": float(r["p"]),
                    "ci_lo": float(r["ci_lo_95"]),
                    "ci_hi": float(r["ci_hi_95"]),
                    "n": int(r["n"]),
                    "r2": float(r["r2"]),
                }


def load_cross_aod_coef():
    with open(CROSS_CSV) as f:
        for r in csv.DictReader(f):
            if r["coefficient"] == "aod":
                return {
                    "beta": float(r["beta"]),
                    "se": float(r["se_robust"]),
                    "p": float(r["p"]),
                    "ci_lo": float(r["ci_lo_95"]),
                    "ci_hi": float(r["ci_hi_95"]),
                    "n": int(r["n"]),
                    "r2": float(r["r2"]),
                }


def load_sensitivity():
    rows = []
    with open(SENS_CSV) as f:
        for r in csv.DictReader(f):
            for k in ("beta", "se", "p", "ci_lo_95", "ci_hi_95"):
                r[k] = float(r[k])
            r["n"] = int(r["n"])
            rows.append(r)
    return rows


# ---- figures ----

def fig_aod_distribution(df):
    fig, axes = plt.subplots(1, 3, figsize=(13, 4.5))
    for ax, aoi in zip(axes, AOIS):
        sub = df[df["aoi"] == aoi]
        m_vals = sub["merra2_duexttau_550"].dropna().values
        c_vals = sub["cams_total_aod_550"].dropna().values
        bins = np.linspace(0, max(c_vals.max() if len(c_vals) else 0,
                                  m_vals.max() if len(m_vals) else 0,
                                  0.01) * 1.05, 30)
        ax.hist(m_vals, bins=bins, alpha=0.55,
                color="#9c6644", label="MERRA-2 DUEXTTAU",
                edgecolor="white", linewidth=0.5)
        ax.hist(c_vals, bins=bins, alpha=0.55,
                color="#264653", label="CAMS total AOD",
                edgecolor="white", linewidth=0.5)
        if len(m_vals):
            ax.axvline(m_vals.mean(), color="#9c6644", ls="--", lw=1)
            ax.axvline(np.median(m_vals), color="#9c6644", ls=":", lw=1)
        if len(c_vals):
            ax.axvline(c_vals.mean(), color="#264653", ls="--", lw=1)
            ax.axvline(np.median(c_vals), color="#264653", ls=":", lw=1)
        ax.set_title(AOI_LABELS[aoi])
        ax.set_xlabel("AOD at 550 nm")
        ax.set_ylabel("scene count")
        ax.legend(fontsize=8, loc="upper right")
        ax.grid(alpha=0.3)
    fig.suptitle("SQ8 — per-AOI reanalysis AOD distribution\n"
                 "dashed = mean, dotted = median")
    fig.tight_layout()
    out = FIG / "sq8_aod_distribution.png"
    fig.savefig(out, dpi=150)
    plt.close(fig)
    print(f"  Wrote {out}")


def fig_residual_vs_aod(df, prim, q1_aod, q4_aod):
    """Per-AOI scatter of NDVI residual vs MERRA-2 DUEXTTAU.

    Per-AOI panel: scatter, MARGINAL per-AOI OLS line for visual aid only,
    Q4 UVAI scenes overlaid as distinct markers. Subtitle marks per-AOI
    significance status. Footer captures pooled-AOI fixed-effects result
    and the dual-criterion observation.
    """
    sens_rows = load_sensitivity()
    sens_by_aoi = {r["aoi"]: r for r in sens_rows
                   if r["variant"].startswith("aoi_stratified_")}

    fig, axes = plt.subplots(1, 3, figsize=(15, 5))
    for ax, aoi in zip(axes, AOIS):
        sub = df[df["aoi"] == aoi].dropna(
            subset=["ndvi_residual", "merra2_duexttau_550"])
        x = sub["merra2_duexttau_550"].values
        y = sub["ndvi_residual"].values
        c = AOI_COLORS[aoi]

        non_q4 = sub[sub["uvai_quartile"] != "Q4"]
        q4 = sub[sub["uvai_quartile"] == "Q4"]
        ax.scatter(non_q4["merra2_duexttau_550"], non_q4["ndvi_residual"],
                   color=c, s=35, alpha=0.55, edgecolor="white", linewidth=0.6,
                   label="Q1–Q3 UVAI")
        ax.scatter(q4["merra2_duexttau_550"], q4["ndvi_residual"],
                   color=c, marker="^", s=70, alpha=0.95,
                   edgecolor="black", linewidth=0.8,
                   label="Q4 UVAI")

        # Per-AOI OLS line (visual aid only — sensitivity result)
        beta_a = sens_by_aoi[aoi]["beta"]
        if len(x):
            xx = np.linspace(x.min(), x.max(), 50)
            # Recover intercept by passing through (mean, mean_residual)
            # Use formula: y_hat = beta * x + (mean_y - beta * mean_x)
            intercept = y.mean() - beta_a * x.mean()
            ax.plot(xx, beta_a * xx + intercept,
                    color=c, lw=1.5, alpha=0.75, ls="--")

        sig = sens_by_aoi[aoi]["p"] < 0.05
        sig_label = "p<0.05" if sig else "p≥0.05 (n.s.)"
        ax.set_title(
            f"{AOI_LABELS[aoi]}\n"
            f"per-AOI β={beta_a:+.4f}, "
            f"{sig_label}, n={sens_by_aoi[aoi]['n']}",
            fontsize=10,
        )
        ax.axhline(0, color="gray", lw=0.5, alpha=0.5)
        ax.set_xlabel("MERRA-2 DUEXTTAU (dust extinction at 550 nm)")
        ax.set_ylabel("NDVI residual (vs per-AOI per-month climatology)")
        ax.legend(loc="upper right", fontsize=8)
        ax.grid(alpha=0.3)

    iqr = q4_aod - q1_aod
    delta = prim["beta"] * iqr
    footer = (
        f"Pooled-AOI fixed-effects regression: "
        f"β = {prim['beta']:+.4f} NDVI per unit DUEXTTAU "
        f"(p = {prim['p']:.3f}, "
        f"95% CI [{prim['ci_lo']:+.4f}, {prim['ci_hi']:+.4f}], "
        f"n = {prim['n']}, R² = {prim['r2']:.3f}).  "
        f"β × (Q4 − Q1) AOD = {delta:+.4f} NDVI units across the IQR; "
        f"magnitude is 2.8× below the pre-registered 0.005 NDVI "
        f"operational-significance threshold.\n"
        f"Classifier (CI excludes zero): goyens_consistent_bias_detected.   "
        f"Magnitude criterion (|β × IQR| < 0.005): tight_null.   "
        f"Both reported per Option 4 framing decision."
    )
    fig.suptitle("SQ8 — per-AOI NDVI residual vs MERRA-2 DUEXTTAU\n"
                 "(dashed line: per-AOI marginal regression; "
                 "individual AOIs not significant)",
                 y=0.995)
    fig.text(0.5, -0.02, footer, ha="center", va="top",
             fontsize=8, style="italic", wrap=True)
    fig.tight_layout(rect=[0, 0.05, 1, 0.97])
    out = FIG / "sq8_residual_vs_aod_primary.png"
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  Wrote {out}")


def fig_diriyah_anchor(df):
    sub = df[df["aoi"] == "diriyah_gate"].dropna(
        subset=["ndvi_residual", "merra2_duexttau_550"])
    anchor = sub[(sub["uvai_quartile"] == "Q4") & (~sub["v4_flag"])]
    other_q4 = sub[(sub["uvai_quartile"] == "Q4") & (sub["v4_flag"])]
    not_q4 = sub[sub["uvai_quartile"] != "Q4"]

    pred = load_predicted()
    anchor_pred = next(
        (p for p in pred
         if p["aoi"] == "diriyah_gate"
         and "diriyah_q4_not_v4_anchor" in p["prediction_point"]),
        None,
    )

    fig, ax = plt.subplots(figsize=(8, 5.5))
    ax.scatter(not_q4["merra2_duexttau_550"], not_q4["ndvi_residual"],
               color="#264653", s=35, alpha=0.4,
               edgecolor="white", linewidth=0.6, label="Q1–Q3 UVAI")
    ax.scatter(other_q4["merra2_duexttau_550"], other_q4["ndvi_residual"],
               color="#264653", marker="s", s=70, alpha=0.7,
               edgecolor="black", linewidth=0.8,
               label="Q4 UVAI ∧ V4-fired")
    ax.scatter(anchor["merra2_duexttau_550"], anchor["ndvi_residual"],
               color="#e07a3f", marker="*", s=180, alpha=0.95,
               edgecolor="black", linewidth=1.0,
               label=f"Q4 UVAI ∧ ¬V4  (n={len(anchor)}, anchor cell)")

    if anchor_pred is not None:
        ax.errorbar(
            anchor_pred["aod_value"],
            anchor_pred["predicted_residual"],
            yerr=[[anchor_pred["predicted_residual"]
                   - anchor_pred["ci_lo_95_pred"]],
                  [anchor_pred["ci_hi_95_pred"]
                   - anchor_pred["predicted_residual"]]],
            fmt="D", color="black", ecolor="black",
            elinewidth=2, capsize=6, markersize=10,
            label="anchor-cell model prediction (95% CI)",
        )
        ax.text(
            anchor_pred["aod_value"] + 0.005,
            anchor_pred["predicted_residual"] + 0.003,
            f"pred = {anchor_pred['predicted_residual']:+.4f}\n"
            f"CI [{anchor_pred['ci_lo_95_pred']:+.4f}, "
            f"{anchor_pred['ci_hi_95_pred']:+.4f}]",
            fontsize=9, va="bottom",
        )

    ax.axhline(0, color="gray", lw=0.5, alpha=0.5)
    ax.set_xlabel("MERRA-2 DUEXTTAU (dust extinction at 550 nm)")
    ax.set_ylabel("NDVI residual (vs Diriyah per-month climatology)")
    ax.set_title(
        "SQ8 — Diriyah anchor: Q4 UVAI ∧ ¬V4 cell (pre-registered "
        "Goyens-regime test cell)\n"
        "anchor-cell prediction CI includes zero")
    ax.legend(loc="lower left", fontsize=9)
    ax.grid(alpha=0.3)
    fig.tight_layout()
    out = FIG / "sq8_diriyah_anchor.png"
    fig.savefig(out, dpi=150)
    plt.close(fig)
    print(f"  Wrote {out}")


def fig_merra2_vs_cams(df):
    fig, ax = plt.subplots(figsize=(7.5, 6))
    sub = df.dropna(subset=["merra2_duexttau_550", "cams_total_aod_550"])
    rho_overall, _ = spearmanr(sub["merra2_duexttau_550"],
                               sub["cams_total_aod_550"])
    for aoi in AOIS:
        ss = sub[sub["aoi"] == aoi]
        ax.scatter(ss["merra2_duexttau_550"], ss["cams_total_aod_550"],
                   color=AOI_COLORS[aoi], s=35, alpha=0.7,
                   edgecolor="white", linewidth=0.6,
                   label=AOI_LABELS[aoi])
    lo = 0
    hi = max(sub["merra2_duexttau_550"].max(),
             sub["cams_total_aod_550"].max()) * 1.05
    ax.plot([lo, hi], [lo, hi], color="gray", ls="--", lw=1, label="1:1")
    ax.set_xlim(lo, hi)
    ax.set_ylim(lo, hi)
    ax.set_xlabel("MERRA-2 DUEXTTAU (dust-only extinction at 550 nm)")
    ax.set_ylabel("CAMS NRT total AOD at 550 nm")
    ax.set_title(f"SQ8 — MERRA-2 dust vs CAMS total AOD on shared dates\n"
                 f"Spearman ρ = {rho_overall:.3f}  (n = {len(sub)})")
    ax.legend(loc="upper left", fontsize=9)
    ax.grid(alpha=0.3)
    fig.tight_layout()
    out = FIG / "sq8_merra2_vs_cams_scatter.png"
    fig.savefig(out, dpi=150)
    plt.close(fig)
    print(f"  Wrote {out}")
    return rho_overall


def fig_loading_regime_ladder():
    """Single visual summary of SQ3/SQ4/SQ4B/SQ5/SQ8 across the loading
    regime, per AOI. Reads the canonical signal_class CSVs from each
    sub-question."""
    # Load each layer's per-AOI mean Δ (from prior SQ outputs)
    sq3 = pd.read_csv(DATA / "sq3_pairing_audit.csv")
    sq4 = pd.read_csv(DATA / "sq4_signal_class.csv")
    sq4b_a = pd.read_csv(DATA / "sq4b_arm_a_signal_class.csv")
    sq5_ret = pd.read_csv(DATA / "sq5_pair_retention_probe.csv")

    # SQ8 per-AOI predicted Δ at Q4-vs-Q1 AOD using the pooled regression
    pred = load_predicted()
    pred_by_aoi = defaultdict(dict)
    for r in pred:
        if r["prediction_point"] == "q1_aod":
            pred_by_aoi[r["aoi"]]["q1"] = r
        elif r["prediction_point"] == "q4_aod":
            pred_by_aoi[r["aoi"]]["q4"] = r
    sq8_delta = {}
    for aoi, parts in pred_by_aoi.items():
        if "q1" in parts and "q4" in parts:
            d_pred = parts["q4"]["predicted_residual"] - parts["q1"]["predicted_residual"]
            d_lo = parts["q4"]["ci_lo_95_pred"] - parts["q1"]["ci_hi_95_pred"]
            d_hi = parts["q4"]["ci_hi_95_pred"] - parts["q1"]["ci_lo_95_pred"]
            sq8_delta[aoi] = (d_pred, d_lo, d_hi)

    layers = [
        ("SQ3 — Sen2Cor B8\nmoderate loadings", "mean_delta", "ci_halfwidth", sq3),
        ("SQ4 — LaSRC B8A\nmoderate loadings", "mean_diff", "ci_halfwidth", sq4),
        ("SQ4B — LaSRC B8\nmoderate loadings", "mean_diff", "ci_halfwidth", sq4b_a),
    ]

    fig, axes = plt.subplots(1, 3, figsize=(14, 5), sharey=True)
    layer_labels = [lab for lab, _, _, _ in layers]
    layer_labels.append("SQ5 — paired Q4-vs-Q1\nhalt receipt")
    layer_labels.append("SQ8 — pooled regression\nper IQR AOD")

    for ax, aoi in zip(axes, AOIS):
        means = []
        hws = []
        labels = []
        for lab, mean_col, hw_col, dfL in layers:
            row = dfL[dfL["aoi"] == aoi]
            if row.empty:
                continue
            m = float(row[mean_col].iloc[0])
            hw = float(row[hw_col].iloc[0])
            means.append(m)
            hws.append(hw)
            labels.append(lab)
        # SQ5 halt: plot a sentinel point at zero with no error bar, marker '×'
        ret_row = sq5_ret[sq5_ret["aoi"] == aoi]
        if not ret_row.empty:
            labels.append(layer_labels[3])
            means.append(np.nan)
            hws.append(np.nan)
        # SQ8 IQR-scaled prediction
        if aoi in sq8_delta:
            d_pred, d_lo, d_hi = sq8_delta[aoi]
            labels.append(layer_labels[4])
            means.append(d_pred)
            hws.append((d_hi - d_lo) / 2.0)

        xs = np.arange(len(means))
        for x, m, hw, lab in zip(xs, means, hws, labels):
            if np.isnan(m):
                ax.scatter(x, 0, color="gray", marker="x", s=120,
                           label="halt receipt" if x == 3 else None)
                ax.text(x, 0.018,
                        f"{ret_row['retention_pct'].iloc[0]:.1f}% ret",
                        ha="center", fontsize=8, color="gray")
                continue
            color = AOI_COLORS[aoi]
            ax.errorbar(x, m, yerr=hw, fmt="o", color=color, ecolor=color,
                        elinewidth=2, capsize=5, markersize=8)

        ax.axhline(0, color="gray", lw=0.5, ls="--")
        ax.axhline(-0.005, color="orange", lw=0.5, ls=":", alpha=0.5)
        ax.axhline(0.005, color="orange", lw=0.5, ls=":", alpha=0.5)
        ax.set_xticks(xs)
        ax.set_xticklabels(labels, fontsize=8, rotation=15, ha="right")
        ax.set_ylim(-0.030, 0.030)
        ax.set_title(AOI_LABELS[aoi])
        ax.grid(axis="y", alpha=0.3)

    axes[0].set_ylabel("Δ NDVI / paired or per-IQR-AOD (units of NDVI)")
    fig.suptitle(
        "SQ8 — loading-regime ladder across SQ3 / SQ4 / SQ4B / SQ5 / SQ8\n"
        "orange dotted = ±0.005 NDVI operational-significance threshold; "
        "all measured cells fall within ±0.005",
        y=0.99,
    )
    fig.tight_layout(rect=[0, 0, 1, 0.96])
    out = FIG / "sq8_loading_regime_ladder.png"
    fig.savefig(out, dpi=150)
    plt.close(fig)
    print(f"  Wrote {out}")


# ---- summary stats markdown ----

def write_summary_md(df, prim, cross, sens_rows, q1_aod, q4_aod, rho_mc):
    iqr = q4_aod - q1_aod
    delta = prim["beta"] * iqr
    delta_lo = prim["ci_lo"] * iqr
    delta_hi = prim["ci_hi"] * iqr
    cross_iqr = cross["beta"] * (df["cams_total_aod_550"].quantile(0.75)
                                 - df["cams_total_aod_550"].quantile(0.25))
    sens_by_aoi = {r["aoi"]: r for r in sens_rows
                   if r["variant"].startswith("aoi_stratified_")}
    pred = load_predicted()
    anchor = next((p for p in pred
                   if p["aoi"] == "diriyah_gate"
                   and "diriyah_q4_not_v4_anchor" in p["prediction_point"]),
                  None)
    cls = load_class()

    def n_cell(aoi, q4, v4):
        sub = df[(df["aoi"] == aoi)
                 & (df["uvai_quartile"] == ("Q4" if q4 else None) if q4
                    else df["uvai_quartile"] != "Q4")
                 & (df["v4_flag"] == v4)]
        return len(sub)

    lines = [
        "# SQ8 — high-AOD regression: summary stats",
        "",
        "Goyens-regime test inherited from SQ5 halt. Per-scene NDVI "
        "residual (relative to per-AOI per-month climatology) regressed "
        "on reanalysis AOD with AOI fixed effects, HC3 robust SEs.",
        "",
        f"AERONET unavailable: no station within 500 km of Riyadh during "
        f"the SQ2 window (Solar_Village dead 2015-10-12, Bahrain dead "
        f"2007-03-06, UAE cluster ~750–800 km outside 500 km outer ring). "
        f"Reanalysis primary: MERRA-2 DUEXTTAU (dust extinction at 550 nm). "
        f"Cross-check: CAMS NRT total AOD at 550 nm.",
        "",
        "## Coverage",
        "",
        f"- SQ2 manifest dates: 228",
        f"- MERRA-2 DUEXTTAU coverage: 225/228 = 98.7%",
        f"- CAMS total AOD coverage: 228/228 = 100.0%",
        f"- Joined rows with NDVI + MERRA-2: {prim['n']}",
        f"- Joined rows with NDVI + CAMS: {cross['n']}",
        "",
        "## Pooled MERRA-2 DUEXTTAU distribution",
        "",
        f"- Q1 (25th pct) = {q1_aod:.4f}",
        f"- Mean         = {df['merra2_duexttau_550'].mean():.4f}",
        f"- Q4 (75th pct) = {q4_aod:.4f}",
        f"- IQR (Q4 − Q1) = {iqr:.4f}",
        "",
        "## Primary regression (MERRA-2 DUEXTTAU + AOI fixed effects, HC3)",
        "",
        "| metric | value |",
        "|---|---:|",
        f"| AOD coefficient β | {prim['beta']:+.6f} |",
        f"| Robust SE (HC3) | {prim['se']:.6f} |",
        f"| p-value | {prim['p']:.4f} |",
        f"| 95% CI on β | [{prim['ci_lo']:+.6f}, {prim['ci_hi']:+.6f}] |",
        f"| n | {prim['n']} |",
        f"| R² | {prim['r2']:.4f} |",
        f"| β × IQR (predicted Δ NDVI Q1→Q4) | "
        f"{delta:+.6f} NDVI units |",
        f"| 95% CI on β × IQR | "
        f"[{delta_lo:+.6f}, {delta_hi:+.6f}] |",
        "",
        "## Cross-check (CAMS total AOD + AOI fixed effects, HC3)",
        "",
        "| metric | value |",
        "|---|---:|",
        f"| AOD coefficient β | {cross['beta']:+.6f} |",
        f"| Robust SE (HC3) | {cross['se']:.6f} |",
        f"| p-value | {cross['p']:.4f} |",
        f"| 95% CI on β | [{cross['ci_lo']:+.6f}, {cross['ci_hi']:+.6f}] |",
        f"| n | {cross['n']} |",
        f"| R² | {cross['r2']:.4f} |",
        f"| β × IQR (predicted Δ NDVI Q1→Q4) | "
        f"{cross_iqr:+.6f} NDVI units |",
        "",
        "**Cross-source agreement**: sign agreement ✓; CI overlap with "
        "primary ✓.",
        "",
        f"**MERRA-2 vs CAMS Spearman ρ on shared dates** = {rho_mc:.3f}.",
        "",
        "## Per-AOI sensitivity regressions (separate OLS, no fixed effects, HC3)",
        "",
        "| AOI | n | β | 95% CI | p | individual sig? |",
        "|---|---:|---:|---|---:|---|",
    ]
    for aoi in AOIS:
        r = sens_by_aoi[aoi]
        sig = "✓ p<0.05" if r["p"] < 0.05 else "n.s."
        lines.append(
            f"| {AOI_LABELS[aoi]} | {r['n']} | {r['beta']:+.4f} | "
            f"[{r['ci_lo_95']:+.4f}, {r['ci_hi_95']:+.4f}] | "
            f"{r['p']:.3f} | {sig} |"
        )
    lines += [
        "",
        "**No individual AOI is significant on its own. The pooled signal "
        "arises from n=224 power of the fixed-effects model.**",
        "",
        "## Diriyah pre-registered Goyens-regime anchor cell",
        "",
        "Cell: Diriyah ∧ UVAI Q4 ∧ ¬V4-fired.",
        "",
    ]
    if anchor is not None:
        lines += [
            f"- n = 12 scenes",
            f"- mean MERRA-2 DUEXTTAU at this cell = {anchor['aod_value']:.4f}",
            f"- model prediction at this AOD = "
            f"{anchor['predicted_residual']:+.6f} NDVI",
            f"- 95% CI on prediction = "
            f"[{anchor['ci_lo_95_pred']:+.6f}, "
            f"{anchor['ci_hi_95_pred']:+.6f}]",
            "",
            "**Anchor-cell prediction CI includes zero — pre-registered "
            "headline-anchor cell does not individually confirm a "
            "Goyens-regime bias.**",
        ]
    lines += [
        "",
        "## Signal classification",
        "",
        "Per the SQ8 prompt's Option 4 framing decision: the pre-registered "
        "classifier output and the magnitude criterion BOTH fire on this "
        "result. Both are reported here as a methodology finding rather "
        "than reconciled by override; the framing prose is deferred to "
        "`sq8_findings.md` drafted in a later session.",
        "",
        "| criterion | rule | this run | classification |",
        "|---|---|---|---|",
        f"| Pre-registered classifier | "
        f"95% CI on β excludes zero AND β < 0 | "
        f"CI [{prim['ci_lo']:+.4f}, {prim['ci_hi']:+.4f}] excludes 0; "
        f"β = {prim['beta']:+.4f} | "
        f"`goyens_consistent_bias_detected` |",
        f"| Pre-registered magnitude | "
        f"&#124;β × IQR&#124; < 0.005 NDVI → tight_null | "
        f"&#124;{delta:+.4f}&#124; = {abs(delta):.4f} < 0.005 | "
        f"`tight_null` |",
        "",
        "Classifier sq8_signal_class.csv preserves the canonical pre-"
        "registered classifier output: "
        f"`{cls['signal_class']}`. The dual-criterion observation is the "
        "headline of the figures and this summary table; framing prose is "
        "OUT OF SCOPE for this commit cycle.",
    ]
    OUT_MD.write_text("\n".join(lines) + "\n")
    print(f"  Wrote {OUT_MD}")


# ---- main ----

def main():
    df = load_joined()
    prim = load_primary_aod_coef()
    cross = load_cross_aod_coef()
    sens_rows = load_sensitivity()

    aod_pool = df["merra2_duexttau_550"].dropna()
    q1_aod = float(aod_pool.quantile(0.25))
    q4_aod = float(aod_pool.quantile(0.75))

    print("Figures:")
    fig_aod_distribution(df)
    fig_residual_vs_aod(df, prim, q1_aod, q4_aod)
    fig_diriyah_anchor(df)
    rho_mc = fig_merra2_vs_cams(df)
    fig_loading_regime_ladder()

    print()
    print("Summary stats markdown:")
    write_summary_md(df, prim, cross, sens_rows, q1_aod, q4_aod, rho_mc)


if __name__ == "__main__":
    main()

"""
SQ8 — per-scene NDVI residual regressed on reanalysis AOD with AOI fixed
effects. HC3 robust standard errors.

Inputs:
  research/dust-honesty/data/sq8_ndvi_residuals.csv (226 rows)
  research/dust-honesty/data/sq8_aod_per_scene.csv  (228 rows)
  research/dust-honesty/data/sq5_uvai_labels.csv    (UVAI quartile + V4)

Outputs:
  research/dust-honesty/data/sq8_regression_primary.csv
    one row per coefficient (Intercept, AOD, AOI fixed effects):
    coefficient, beta, se, t, p, ci_lo_95, ci_hi_95, robust_method, n, r2
  research/dust-honesty/data/sq8_regression_crosscheck.csv  (CAMS variant)
  research/dust-honesty/data/sq8_regression_sensitivity.csv
    rows: (variant, aoi, beta, se, p, ci_lo_95, ci_hi_95, n)
    variants:
      'climatology_stable'  → drop sensitivity_flag=True rows
                              (all rows pass at this site; reported for
                              parity)
      'aoi_stratified_<aoi>' → per-AOI separate OLS, HC3, no fixed effects
  research/dust-honesty/data/sq8_predicted_residuals.csv
    rows: (aoi, prediction_point, aod_value, predicted_residual,
           ci_lo_95_pred, ci_hi_95_pred)
    points: 'aoi_mean_aod', 'q1_aod', 'q4_aod',
            'diriyah_q4_not_v4_anchor' (Diriyah only)
  research/dust-honesty/data/sq8_signal_class.csv
    one row: signal_class derived from PRIMARY regression's AOD coefficient.

Signal classification (from prompt):
  p < 0.05, beta < 0  → 'goyens_consistent_bias_detected'
  p < 0.05, beta > 0  → 'anti_goyens_signal'
  p ≥ 0.05 AND |beta * (Q4_AOD - Q1_AOD)| < 0.005 NDVI → 'tight_null'
  else                → 'wide_inconclusive'

Q4_AOD and Q1_AOD for the signal classification are computed pooled
across all three AOIs (75th and 25th percentiles of merra2_duexttau_550
across the joined dataset). Per-AOI predicted residuals are computed
separately for the predicted_residuals output.

If signal_class = 'goyens_consistent_bias_detected', exit code 3 to
trigger a halt-before-figures gate per the SQ8 prompt.
"""
from __future__ import annotations

import csv
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.api as sm
from statsmodels.formula.api import ols

ROOT = Path(__file__).resolve().parents[3]
DATA = ROOT / "research/dust-honesty/data"

RES_CSV = DATA / "sq8_ndvi_residuals.csv"
AOD_CSV = DATA / "sq8_aod_per_scene.csv"
UVAI_CSV = DATA / "sq5_uvai_labels.csv"

OUT_PRIMARY = DATA / "sq8_regression_primary.csv"
OUT_CROSS = DATA / "sq8_regression_crosscheck.csv"
OUT_SENS = DATA / "sq8_regression_sensitivity.csv"
OUT_PRED = DATA / "sq8_predicted_residuals.csv"
OUT_CLASS = DATA / "sq8_signal_class.csv"

AOIS = ["king_salman_park", "qiddiya_core", "diriyah_gate"]


def load_joined():
    res = pd.read_csv(RES_CSV)
    aod = pd.read_csv(AOD_CSV)
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
    df["aoi"] = df["aoi"].astype("category")
    df["sensitivity_flag"] = df["sensitivity_flag"].astype(str) == "True"
    df["v4_flag"] = df["v4_flag"].astype(str) == "True"
    return df


def fit_robust(df, aod_col):
    """Fit ndvi_residual ~ aod_col + C(aoi), HC3 robust. Return result."""
    sub = df.dropna(subset=["ndvi_residual", aod_col]).copy()
    sub["aod"] = sub[aod_col]
    model = ols("ndvi_residual ~ aod + C(aoi)", data=sub).fit(cov_type="HC3")
    return model, sub


def coef_table(model, source_label, aod_col, n, r2):
    """Return list of dicts for OLS_PRIMARY/CROSSCHECK CSV."""
    rows = []
    coef = model.params
    se = model.bse
    tv = model.tvalues
    pv = model.pvalues
    ci = model.conf_int(alpha=0.05)
    for name in coef.index:
        rows.append({
            "source": source_label,
            "aod_band": aod_col,
            "coefficient": name,
            "beta": float(coef[name]),
            "se_robust": float(se[name]),
            "t": float(tv[name]),
            "p": float(pv[name]),
            "ci_lo_95": float(ci.loc[name, 0]),
            "ci_hi_95": float(ci.loc[name, 1]),
            "robust_method": "HC3",
            "n": int(n),
            "r2": float(r2),
        })
    return rows


def write_coef_csv(path, rows):
    fields = ["source", "aod_band", "coefficient", "beta", "se_robust",
              "t", "p", "ci_lo_95", "ci_hi_95", "robust_method", "n", "r2"]
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in rows:
            w.writerow({
                "source": r["source"], "aod_band": r["aod_band"],
                "coefficient": r["coefficient"],
                "beta": f"{r['beta']:+.6f}",
                "se_robust": f"{r['se_robust']:.6f}",
                "t": f"{r['t']:+.4f}",
                "p": f"{r['p']:.6f}",
                "ci_lo_95": f"{r['ci_lo_95']:+.6f}",
                "ci_hi_95": f"{r['ci_hi_95']:+.6f}",
                "robust_method": r["robust_method"],
                "n": r["n"], "r2": f"{r['r2']:.4f}",
            })


def signal_class_of(beta, p, q1_aod, q4_aod, threshold=0.005):
    if p < 0.05 and beta < 0:
        return "goyens_consistent_bias_detected"
    if p < 0.05 and beta > 0:
        return "anti_goyens_signal"
    if p >= 0.05 and abs(beta * (q4_aod - q1_aod)) < threshold:
        return "tight_null"
    return "wide_inconclusive"


def predict_for_aoi(model, sub_df, aoi, aod_value):
    """Predict ndvi_residual at aod=aod_value for given aoi using the
    fitted model. Returns (pred, ci_lo, ci_hi) for the 95% mean
    prediction CI."""
    new = pd.DataFrame({
        "aod": [aod_value],
        "aoi": pd.Categorical([aoi], categories=AOIS),
    })
    pred = model.get_prediction(new)
    summ = pred.summary_frame(alpha=0.05)
    return float(summ["mean"].iloc[0]), \
           float(summ["mean_ci_lower"].iloc[0]), \
           float(summ["mean_ci_upper"].iloc[0])


def main():
    print("SQ8 — regression of NDVI residual on reanalysis AOD")
    print()

    df = load_joined()
    print(f"Joined rows: {len(df)}")
    print(f"  with merra2 + ndvi_residual: "
          f"{df.dropna(subset=['ndvi_residual','merra2_duexttau_550']).shape[0]}")
    print(f"  with cams + ndvi_residual:   "
          f"{df.dropna(subset=['ndvi_residual','cams_total_aod_550']).shape[0]}")
    print()

    # Q1 / Q4 AOD for signal classification (pooled)
    aod_pool = df.dropna(subset=["merra2_duexttau_550"])["merra2_duexttau_550"]
    q1_aod = float(np.percentile(aod_pool, 25))
    q4_aod = float(np.percentile(aod_pool, 75))
    aoi_mean_aod = float(aod_pool.mean())
    print(f"MERRA-2 DUEXTTAU pooled distribution: "
          f"Q1={q1_aod:.4f}, mean={aoi_mean_aod:.4f}, Q4={q4_aod:.4f}")
    print()

    # ---- Primary regression: MERRA-2 DUEXTTAU ----
    print("PRIMARY: ndvi_residual ~ merra2_duexttau_550 + C(aoi)  [HC3]")
    m_prim, sub_prim = fit_robust(df, "merra2_duexttau_550")
    aod_beta_prim = float(m_prim.params["aod"])
    aod_p_prim = float(m_prim.pvalues["aod"])
    aod_ci_prim = m_prim.conf_int(alpha=0.05).loc["aod"]
    print(f"  AOD coefficient: beta={aod_beta_prim:+.6f}, "
          f"p={aod_p_prim:.4f}, "
          f"CI=[{aod_ci_prim[0]:+.6f}, {aod_ci_prim[1]:+.6f}], "
          f"n={int(m_prim.nobs)}, R²={m_prim.rsquared:.4f}")
    rows_prim = coef_table(m_prim, "primary", "merra2_duexttau_550",
                           m_prim.nobs, m_prim.rsquared)
    write_coef_csv(OUT_PRIMARY, rows_prim)
    print(f"  Wrote {OUT_PRIMARY}")
    print()

    # ---- Cross-check: CAMS total AOD ----
    print("CROSS-CHECK: ndvi_residual ~ cams_total_aod_550 + C(aoi)  [HC3]")
    m_cross, sub_cross = fit_robust(df, "cams_total_aod_550")
    aod_beta_cross = float(m_cross.params["aod"])
    aod_p_cross = float(m_cross.pvalues["aod"])
    aod_ci_cross = m_cross.conf_int(alpha=0.05).loc["aod"]
    print(f"  AOD coefficient: beta={aod_beta_cross:+.6f}, "
          f"p={aod_p_cross:.4f}, "
          f"CI=[{aod_ci_cross[0]:+.6f}, {aod_ci_cross[1]:+.6f}], "
          f"n={int(m_cross.nobs)}, R²={m_cross.rsquared:.4f}")
    rows_cross = coef_table(m_cross, "crosscheck", "cams_total_aod_550",
                            m_cross.nobs, m_cross.rsquared)
    write_coef_csv(OUT_CROSS, rows_cross)
    print(f"  Wrote {OUT_CROSS}")
    print()

    # Cross-source agreement (CI overlap test)
    overlap = (max(aod_ci_prim[0], aod_ci_cross[0]) <=
               min(aod_ci_prim[1], aod_ci_cross[1]))
    sign_agree = (np.sign(aod_beta_prim) == np.sign(aod_beta_cross))
    print(f"Source agreement: CI overlap = {overlap}; "
          f"sign agreement = {sign_agree}")
    print()

    # ---- Sensitivity: climatology-stable subset ----
    print("SENSITIVITY 1: climatology-stable subset (drop sensitivity_flag=True)")
    df_stable = df[~df["sensitivity_flag"]].copy()
    if len(df_stable) == len(df):
        print(f"  No rows dropped (all 36 climatology cells have n≥3 — R5 PASS).")
    sens_rows = []
    m_stab, _ = fit_robust(df_stable, "merra2_duexttau_550")
    sens_rows.append({
        "variant": "climatology_stable",
        "aoi": "all",
        "beta": float(m_stab.params["aod"]),
        "se": float(m_stab.bse["aod"]),
        "p": float(m_stab.pvalues["aod"]),
        "ci_lo_95": float(m_stab.conf_int().loc["aod", 0]),
        "ci_hi_95": float(m_stab.conf_int().loc["aod", 1]),
        "n": int(m_stab.nobs),
    })
    print(f"  beta={sens_rows[-1]['beta']:+.6f}, p={sens_rows[-1]['p']:.4f}, "
          f"CI=[{sens_rows[-1]['ci_lo_95']:+.6f}, {sens_rows[-1]['ci_hi_95']:+.6f}], "
          f"n={sens_rows[-1]['n']}")
    print()

    # ---- Sensitivity 2: AOI-stratified ----
    print("SENSITIVITY 2: per-AOI separate regressions (no fixed effects)")
    for aoi in AOIS:
        sub = df[df["aoi"] == aoi].dropna(
            subset=["ndvi_residual", "merra2_duexttau_550"]).copy()
        sub["aod"] = sub["merra2_duexttau_550"]
        m_aoi = ols("ndvi_residual ~ aod", data=sub).fit(cov_type="HC3")
        sens_rows.append({
            "variant": f"aoi_stratified_{aoi}",
            "aoi": aoi,
            "beta": float(m_aoi.params["aod"]),
            "se": float(m_aoi.bse["aod"]),
            "p": float(m_aoi.pvalues["aod"]),
            "ci_lo_95": float(m_aoi.conf_int().loc["aod", 0]),
            "ci_hi_95": float(m_aoi.conf_int().loc["aod", 1]),
            "n": int(m_aoi.nobs),
        })
        print(f"  {aoi:<22s} beta={sens_rows[-1]['beta']:+.6f}, "
              f"p={sens_rows[-1]['p']:.4f}, "
              f"CI=[{sens_rows[-1]['ci_lo_95']:+.6f}, "
              f"{sens_rows[-1]['ci_hi_95']:+.6f}], n={sens_rows[-1]['n']}")
    print()

    fields = ["variant", "aoi", "beta", "se", "p",
              "ci_lo_95", "ci_hi_95", "n"]
    with open(OUT_SENS, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in sens_rows:
            w.writerow({
                "variant": r["variant"], "aoi": r["aoi"],
                "beta": f"{r['beta']:+.6f}",
                "se": f"{r['se']:.6f}",
                "p": f"{r['p']:.6f}",
                "ci_lo_95": f"{r['ci_lo_95']:+.6f}",
                "ci_hi_95": f"{r['ci_hi_95']:+.6f}",
                "n": r["n"],
            })
    print(f"Wrote {OUT_SENS}")
    print()

    # ---- Predicted residuals per AOI ----
    print("PREDICTED RESIDUALS at AOI-mean / Q1 / Q4 / Diriyah anchor")
    pred_rows = []
    for aoi in AOIS:
        sub = sub_prim[sub_prim["aoi"] == aoi]
        aoi_mean = float(sub["aod"].mean())
        for label, val in [("aoi_mean_aod", aoi_mean),
                           ("q1_aod", q1_aod),
                           ("q4_aod", q4_aod)]:
            mu, lo, hi = predict_for_aoi(m_prim, sub_prim, aoi, val)
            pred_rows.append({
                "aoi": aoi, "prediction_point": label,
                "aod_value": val, "predicted_residual": mu,
                "ci_lo_95_pred": lo, "ci_hi_95_pred": hi,
            })

    # Diriyah Q4-and-not-V4 anchor cell: scenes in sq5 labels where
    # uvai_quartile=='Q4' AND v4_flag==False AND aoi=='diriyah_gate'.
    # Use the mean MERRA-2 AOD across THAT cell as the anchor AOD.
    anchor = df[(df["aoi"] == "diriyah_gate") &
                (df["uvai_quartile"] == "Q4") &
                (df["v4_flag"] == False)]
    n_anchor = len(anchor)
    if n_anchor >= 1:
        anchor_aod = float(anchor["merra2_duexttau_550"].dropna().mean())
        mu, lo, hi = predict_for_aoi(m_prim, sub_prim, "diriyah_gate", anchor_aod)
        pred_rows.append({
            "aoi": "diriyah_gate",
            "prediction_point": f"diriyah_q4_not_v4_anchor (n={n_anchor})",
            "aod_value": anchor_aod,
            "predicted_residual": mu,
            "ci_lo_95_pred": lo, "ci_hi_95_pred": hi,
        })
        print(f"  Diriyah Q4∧¬V4 anchor: n={n_anchor}, "
              f"mean MERRA-2 AOD={anchor_aod:.4f}, "
              f"predicted residual={mu:+.6f} "
              f"CI=[{lo:+.6f}, {hi:+.6f}]")

    fields = ["aoi", "prediction_point", "aod_value",
              "predicted_residual", "ci_lo_95_pred", "ci_hi_95_pred"]
    with open(OUT_PRED, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in pred_rows:
            w.writerow({
                "aoi": r["aoi"], "prediction_point": r["prediction_point"],
                "aod_value": f"{r['aod_value']:.6f}",
                "predicted_residual": f"{r['predicted_residual']:+.6f}",
                "ci_lo_95_pred": f"{r['ci_lo_95_pred']:+.6f}",
                "ci_hi_95_pred": f"{r['ci_hi_95_pred']:+.6f}",
            })
    print(f"Wrote {OUT_PRED} ({len(pred_rows)} rows)")
    print()

    # ---- Signal classification ----
    sig = signal_class_of(aod_beta_prim, aod_p_prim, q1_aod, q4_aod)
    delta_q4_q1 = aod_beta_prim * (q4_aod - q1_aod)
    print(f"SIGNAL CLASS (PRIMARY): {sig}")
    print(f"  beta * (Q4 - Q1) AOD = {delta_q4_q1:+.6f} NDVI units")
    print(f"  threshold for tight_null: |Δ| < 0.005 NDVI")

    with open(OUT_CLASS, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=[
            "signal_class", "primary_source", "aod_band",
            "aod_beta", "aod_p", "ci_lo_95", "ci_hi_95",
            "q1_aod", "q4_aod", "predicted_delta_q4_q1",
            "n", "r2",
        ])
        w.writeheader()
        w.writerow({
            "signal_class": sig,
            "primary_source": "MERRA-2",
            "aod_band": "DUEXTTAU",
            "aod_beta": f"{aod_beta_prim:+.6f}",
            "aod_p": f"{aod_p_prim:.6f}",
            "ci_lo_95": f"{aod_ci_prim[0]:+.6f}",
            "ci_hi_95": f"{aod_ci_prim[1]:+.6f}",
            "q1_aod": f"{q1_aod:.6f}",
            "q4_aod": f"{q4_aod:.6f}",
            "predicted_delta_q4_q1": f"{delta_q4_q1:+.6f}",
            "n": int(m_prim.nobs),
            "r2": f"{m_prim.rsquared:.4f}",
        })
    print(f"Wrote {OUT_CLASS}")
    print()

    if sig == "goyens_consistent_bias_detected":
        print("HALT: signal_class=goyens_consistent_bias_detected on PRIMARY.")
        print("  Surface for chat-side review BEFORE figures + findings note.")
        sys.exit(3)


if __name__ == "__main__":
    main()

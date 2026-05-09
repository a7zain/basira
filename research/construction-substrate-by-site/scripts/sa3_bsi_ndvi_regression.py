"""
SA3 -- Direct mechanism test: does BSI predict NDVI residuals at
Qiddiya independently of aerosol load?

Pre-registered specification (per pre_registration.md §SA3 +
sa3_implementation.md addendum):

    ndvi_residual ~ bsi + aod + C(aoi)        (pooled, AOI fixed effects)
    ndvi_residual ~ bsi + aod                  (per-AOI heterogeneity)

HC3 robust standard errors. Dual criterion (significance + magnitude).
S30-only on the BSI side (cross-sensor questions belong to SA4).

Inputs (all reused from piece B / SA1, no recomputation)
--------------------------------------------------------
- BSI: SA1 S30 outputs at
    research/construction-substrate-by-site/data/sa1_bsi_baseline/
      {qiddiya,ksp,diriyah}_s30_bsi_per_scene.csv
  Schema: scene_date, sensor, bsi, cloud_fraction, bare_epoch_flag, ...
  Filter: cloud_fraction < 0.10  (SA1's strict cut; inherits, not relaxes,
  the pre-reg's < 0.30 SA3 filter -- documented in sa3_implementation.md).

- NDVI residual (piece B SQ8):
    research/dust-honesty/data/high_aod_regression/ndvi_residuals_sq8.csv
  Schema: aoi, acquisition_date, ndvi, ndvi_climatology, ndvi_residual,
          n_climatology_support, sensitivity_flag
  Per-AOI per-month residual against piece B's calendar-month climatology.

- AOD (piece B):
    research/dust-honesty/data/high_aod_regression/aod_per_scene_sq8.csv
  Schema: aoi, acquisition_date, merra2_duexttau_550, ...
  We use merra2_duexttau_550 as the AOD covariate (DUEXTTAU per pre-reg).

Join keys
---------
Inner join on (aoi, scene_date) via three-table merge:
  SA1 BSI(aoi, scene_date) JOIN piece B NDVI(aoi, acquisition_date)
    JOIN piece B AOD(aoi, acquisition_date)
SA1 column scene_date == piece B column acquisition_date by construction.
Missing in any source = scene drops out. No imputation.

AOI key normalisation: SA1 file stems (qiddiya, ksp, diriyah) are mapped
to piece B AOI strings (qiddiya_core, king_salman_park, diriyah_gate)
at load time so the merge keys align.

Halt rules (per pre-reg)
------------------------
- Per-AOI usable n < 20 after merge -> halt the per-AOI regression for
  that site. Pooled-only result still ships. Halt receipt under
  data/halts/sa3_coverage/{aoi}.md.
- All-AOI usable n < 60 (pooled) -> halt SA3 entirely. Surface coverage
  deficit as structural finding.

Dual criterion (per pre-reg, applied per spec)
----------------------------------------------
- Significance: beta_bsi 95% CI excludes zero.
- Magnitude: |beta_bsi| * IQR(BSI) > 0.005 (operational change-detection
  threshold from piece B SQ8). IQR computed pooled for the pooled spec,
  per-AOI for per-AOI specs.
- Both must hold for a "passes dual criterion" verdict. Disagreement
  is a finding per pre-reg, not a failure.

Hypothesis classification (per pre-reg)
--------------------------------------
- substrate_primary: beta_bsi sig + magnitude met; beta_aod near zero.
- aerosol_primary  : beta_aod sig dominant; beta_bsi near zero.
- equivalence      : both coefficients comparable magnitude.
- inconclusive     : neither clearly dominates.
Operationalised: "near zero" = CI includes zero AND |beta * IQR| < 0.005.
"comparable magnitude" = both magnitude_passes True AND ratio of magnitude
effects within [0.5, 2.0].

Outputs
-------
- data/sa3_bsi_ndvi_regression/regression_results.csv
- data/sa3_bsi_ndvi_regression/SA3_summary.md
- figures/sa3_bsi_vs_ndvi_residual.png   (partial regression plot, pooled)
- data/halts/sa3_coverage/{aoi}.md       (only if per-AOI halt fires)

Run
---
$ /opt/anaconda3/envs/sarsat/bin/python \\
    research/construction-substrate-by-site/scripts/sa3_bsi_ndvi_regression.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import statsmodels.formula.api as smf

ROOT = Path(__file__).resolve().parents[3]

PIECE_DIR = ROOT / "research/construction-substrate-by-site"
DATA = PIECE_DIR / "data"
SA1_DIR = DATA / "sa1_bsi_baseline"
OUT_DIR = DATA / "sa3_bsi_ndvi_regression"
FIG_DIR = PIECE_DIR / "figures"
HALT_DIR = DATA / "halts/sa3_coverage"

PIECE_B = ROOT / "research/dust-honesty/data/high_aod_regression"
NDVI_CSV = PIECE_B / "ndvi_residuals_sq8.csv"
AOD_CSV = PIECE_B / "aod_per_scene_sq8.csv"

CLOUD_FILTER = 0.10
HALT_PER_AOI_N = 20
HALT_POOLED_N = 60
MAGNITUDE_THRESHOLD = 0.005   # piece B SQ8 operational threshold

# (sa1 stem, piece-B aoi key, display name)
AOIS = [
    ("qiddiya", "qiddiya_core", "Qiddiya"),
    ("ksp",     "king_salman_park", "King Salman Park"),
    ("diriyah", "diriyah_gate", "Diriyah Gate"),
]


def load_sa1_bsi() -> pd.DataFrame:
    """Concat all three AOIs' SA1 S30 outputs, cloud-filter,
    drop NaN BSI, attach piece-B-style AOI key. Returns columns:
    aoi, acquisition_date, bsi."""
    frames = []
    for stem, dbb_key, _ in AOIS:
        df = pd.read_csv(SA1_DIR / f"{stem}_s30_bsi_per_scene.csv")
        df = df.dropna(subset=["bsi", "cloud_fraction"])
        df = df[df["cloud_fraction"] < CLOUD_FILTER].copy()
        df["aoi"] = dbb_key
        df = df.rename(columns={"scene_date": "acquisition_date"})
        frames.append(df[["aoi", "acquisition_date", "bsi"]])
    return pd.concat(frames, ignore_index=True)


def merge_three_table() -> tuple[pd.DataFrame, dict]:
    """Inner join SA1 BSI + piece B NDVI residual + piece B AOD on
    (aoi, acquisition_date). Return (merged_df, provenance_counts)."""
    bsi = load_sa1_bsi()

    ndvi = pd.read_csv(NDVI_CSV)[["aoi", "acquisition_date", "ndvi_residual"]]
    aod = pd.read_csv(AOD_CSV)[["aoi", "acquisition_date", "merra2_duexttau_550"]]
    aod = aod.rename(columns={"merra2_duexttau_550": "aod"})

    counts = {
        "n_sa1_cf": len(bsi),
        "n_pieceB_ndvi": len(ndvi),
        "n_pieceB_aod": len(aod),
    }
    counts["n_sa1_cf_per_aoi"] = (
        bsi.groupby("aoi").size().to_dict()
    )

    step1 = bsi.merge(ndvi, on=["aoi", "acquisition_date"], how="inner")
    step2 = step1.merge(aod, on=["aoi", "acquisition_date"], how="inner")

    counts["n_step1_bsi_x_ndvi"] = len(step1)
    counts["n_step2_full_join"] = len(step2)
    counts["n_pooled_per_aoi"] = step2.groupby("aoi").size().to_dict()
    return step2, counts


# --- Regression machinery ---------------------------------------------------

def fit_spec(formula: str, df: pd.DataFrame) -> dict:
    """Fit OLS with HC3 robust SE; return coefficient summary for bsi
    and aod plus IQR(BSI) on this dataset."""
    res = smf.ols(formula, data=df).fit(cov_type="HC3")
    bsi_b = float(res.params["bsi"])
    bsi_se = float(res.bse["bsi"])
    bsi_ci = res.conf_int().loc["bsi"].astype(float).tolist()
    bsi_p = float(res.pvalues["bsi"])
    aod_b = float(res.params["aod"])
    aod_se = float(res.bse["aod"])
    aod_ci = res.conf_int().loc["aod"].astype(float).tolist()
    aod_p = float(res.pvalues["aod"])
    iqr = float(df["bsi"].quantile(0.75) - df["bsi"].quantile(0.25))
    mag_effect = bsi_b * iqr

    sig_pass = (bsi_ci[0] > 0) or (bsi_ci[1] < 0)  # CI excludes zero
    mag_pass = abs(mag_effect) > MAGNITUDE_THRESHOLD

    return {
        "n": int(res.nobs),
        "beta_bsi": bsi_b, "se_bsi": bsi_se,
        "ci_lo_bsi": bsi_ci[0], "ci_hi_bsi": bsi_ci[1],
        "p_bsi": bsi_p,
        "beta_aod": aod_b, "se_aod": aod_se,
        "ci_lo_aod": aod_ci[0], "ci_hi_aod": aod_ci[1],
        "p_aod": aod_p,
        "iqr_bsi": iqr,
        "magnitude_effect": mag_effect,
        "significance_pass": sig_pass,
        "magnitude_pass": mag_pass,
        "_full": res,   # not written to CSV
    }


def classify_hypothesis(r: dict) -> str:
    """Pre-reg hypothesis classification.

    near_zero = CI includes zero AND |beta * IQR| < threshold.
    """
    bsi_near_zero = (
        not r["significance_pass"] and abs(r["magnitude_effect"]) < MAGNITUDE_THRESHOLD
    )
    aod_iqr_proxy = abs(r["beta_aod"]) * r["iqr_bsi"]  # proxy magnitude on the AOD scale; we don't have IQR(AOD) here
    aod_sig = (r["ci_lo_aod"] > 0) or (r["ci_hi_aod"] < 0)
    aod_near_zero = (not aod_sig)  # without IQR(AOD), use significance only

    bsi_dom = r["significance_pass"] and r["magnitude_pass"]

    if bsi_dom and aod_near_zero:
        return "substrate_primary"
    if aod_sig and bsi_near_zero:
        return "aerosol_primary"
    if bsi_dom and aod_sig:
        return "equivalence"
    return "inconclusive"


# --- Halt + figure ----------------------------------------------------------

def write_halt_receipt(aoi_name: str, dbb_key: str, n: int, n_floor: int) -> None:
    HALT_DIR.mkdir(parents=True, exist_ok=True)
    path = HALT_DIR / f"{dbb_key}.md"
    path.write_text("\n".join([
        f"# SA3 halt -- {aoi_name} per-AOI usable n < {n_floor}",
        "",
        "**Pre-registered halt rule (piece A SA3):** per-AOI usable n "
        f"after the BSI x NDVI x AOD inner join must be >= {n_floor}. "
        "If below floor, halt the per-AOI regression for this site. "
        "Pooled-only result still ships.",
        "",
        f"- AOI: {aoi_name} ({dbb_key})",
        f"- Usable n after merge: {n}",
        f"- Floor: {n_floor}",
        f"- Decision: HALT per-AOI regression",
        "",
        "## Effect on outputs",
        "",
        "- `regression_results.csv` omits the per-AOI row for this AOI.",
        "- Pooled regression still includes this AOI's rows; pooled "
        "result is unaffected by per-AOI halts.",
        "",
        "## Why a halt and not a workaround",
        "",
        "Per piece B stop-rule philosophy carried into piece A: when a "
        "halt fires, the cheapest possible scope review is the one "
        "happening mid-run. Reducing the per-AOI floor post-hoc would "
        "conflate \"this site has no signal\" with \"this site has "
        "too few scenes for the test.\" The halt is the finding.",
        "",
    ]))
    print(f"  halt receipt: {path}")


def partial_regression_plot(merged: pd.DataFrame, pooled_full,
                            out_path: Path) -> None:
    """Pooled spec partial regression: residualize ndvi_residual against
    [aod + C(aoi)] and bsi against the same; scatter and overlay the
    pooled beta_bsi line."""
    aux_y = smf.ols("ndvi_residual ~ aod + C(aoi)", data=merged).fit()
    aux_x = smf.ols("bsi ~ aod + C(aoi)", data=merged).fit()
    e_y = aux_y.resid
    e_x = aux_x.resid

    fig, ax = plt.subplots(figsize=(7, 5), dpi=150)
    aoi_to_color = {
        "qiddiya_core": "#B87333",        # accent ochre
        "king_salman_park": "#3a6b3a",
        "diriyah_gate": "#5a5a8a",
    }
    aoi_to_label = {
        "qiddiya_core": "Qiddiya",
        "king_salman_park": "KSP",
        "diriyah_gate": "Diriyah",
    }
    for aoi_key, color in aoi_to_color.items():
        mask = (merged["aoi"] == aoi_key).values
        ax.scatter(
            e_x[mask], e_y[mask],
            color=color, s=22, alpha=0.65,
            edgecolor="white", linewidth=0.5,
            label=aoi_to_label[aoi_key],
        )

    # Pooled beta_bsi line through (0, 0) with slope from full pooled fit.
    beta = float(pooled_full.params["bsi"])
    x_lo, x_hi = float(e_x.min()), float(e_x.max())
    pad = 0.05 * (x_hi - x_lo) if x_hi > x_lo else 0.01
    xs = np.linspace(x_lo - pad, x_hi + pad, 50)
    ax.plot(xs, beta * xs, color="#1A1A1A", linewidth=1.2, zorder=5,
            label=f"pooled β_bsi = {beta:+.3f}")

    ax.axhline(0, color="gray", linewidth=0.5, alpha=0.4)
    ax.axvline(0, color="gray", linewidth=0.5, alpha=0.4)
    ax.set_xlabel("BSI residual (after partialling AOD + AOI FE)")
    ax.set_ylabel("NDVI residual (after partialling AOD + AOI FE)")
    ax.set_title("SA3 partial regression: BSI vs NDVI residual\n"
                 "pooled, AOI fixed effects, HC3 robust SE")
    ax.legend(frameon=False, loc="best", fontsize=9)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    fig.tight_layout()

    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
    print(f"  wrote {out_path}")


# --- Output writers ---------------------------------------------------------

CSV_FIELDS = [
    "spec", "n",
    "beta_bsi", "se_bsi", "ci_lo_bsi", "ci_hi_bsi",
    "beta_aod", "se_aod", "ci_lo_aod", "ci_hi_aod",
    "iqr_bsi", "magnitude_effect",
    "significance_pass", "magnitude_pass",
    "hypothesis_classification",
]


def write_results_csv(rows: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    out = pd.DataFrame(rows)[CSV_FIELDS].copy()
    # Format numerics for stable diffs.
    for col in ("beta_bsi", "se_bsi", "ci_lo_bsi", "ci_hi_bsi",
                "beta_aod", "se_aod", "ci_lo_aod", "ci_hi_aod",
                "iqr_bsi", "magnitude_effect"):
        out[col] = out[col].map(lambda x: f"{x:+.6f}")
    out.to_csv(path, index=False)
    print(f"  wrote {path}")


def write_summary(rows: list[dict], counts: dict, halts: list[str],
                  out_path: Path) -> None:
    lines = [
        "# SA3 -- BSI vs NDVI residual regression summary",
        "",
        "**Goal:** direct mechanism test. Does BSI predict piece B SQ8 "
        "NDVI residuals at Qiddiya independently of MERRA-2 AOD? "
        "Pooled-with-AOI-fixed-effects headline + per-AOI heterogeneity "
        "check, both pre-registered. HC3 robust SE. S30-only.",
        "",
        "## Input provenance",
        "",
        "- BSI: SA1 outputs at `data/sa1_bsi_baseline/{aoi}_s30_bsi_per_scene.csv`. "
        f"Cloud-filtered (cloud_fraction < {CLOUD_FILTER}). Total cloud-filtered "
        f"S30 scenes pooled: {counts['n_sa1_cf']}.",
        "- NDVI residual: `research/dust-honesty/data/high_aod_regression/"
        f"ndvi_residuals_sq8.csv` (piece B SQ8). Rows: {counts['n_pieceB_ndvi']}.",
        "- AOD (DUEXTTAU 550nm): `research/dust-honesty/data/high_aod_regression/"
        f"aod_per_scene_sq8.csv` (piece B; column `merra2_duexttau_550`). "
        f"Rows: {counts['n_pieceB_aod']}.",
        "",
        "**Three-table inner join on (aoi, acquisition_date):**",
        "",
        "| AOI | SA1 S30 cloud-filtered | After NDVI ⨝ | After AOD ⨝ (final) |",
        "|-----|-----------------------:|-------------:|--------------------:|",
    ]
    for _, dbb_key, name in AOIS:
        sa1_n = counts["n_sa1_cf_per_aoi"].get(dbb_key, 0)
        final_n = counts["n_pooled_per_aoi"].get(dbb_key, 0)
        lines.append(f"| {name} | {sa1_n} | (intermediate) | {final_n} |")
    lines += [
        f"| **pooled** | {counts['n_sa1_cf']} | {counts['n_step1_bsi_x_ndvi']} | "
        f"{counts['n_step2_full_join']} |",
        "",
        "## Halt rule outcome",
        "",
        f"- Per-AOI floor: usable n >= {HALT_PER_AOI_N}.",
        f"- Pooled floor: usable n >= {HALT_POOLED_N}.",
        "",
    ]
    if halts:
        lines.append("**Per-AOI halts fired:** " + ", ".join(halts) + ". "
                     "Per-AOI rows omitted from the regression results "
                     "table for halted AOIs; pooled regression unaffected.")
    else:
        lines.append("**No halts fired.** All per-AOI cells cleared the "
                     f"floor of {HALT_PER_AOI_N}; pooled n >= "
                     f"{HALT_POOLED_N}.")

    # Pooled headline table
    lines += [
        "",
        "## Pooled regression (headline)",
        "",
        "Specification: `ndvi_residual ~ bsi + aod + C(aoi)`, HC3 robust SE.",
        "",
        "| spec | n | β_bsi | SE | 95% CI | β_aod | SE | 95% CI |",
        "|------|--:|------:|---:|:-------|------:|---:|:-------|",
    ]
    pooled = next(r for r in rows if r["spec"] == "pooled")
    lines.append(_pooled_row_md(pooled))

    lines += [
        "",
        "## Per-AOI heterogeneity",
        "",
        "Specification: `ndvi_residual ~ bsi + aod` filtered to one AOI, "
        "HC3 robust SE.",
        "",
        "| AOI | n | β_bsi | SE | 95% CI | β_aod | SE | 95% CI |",
        "|-----|--:|------:|---:|:-------|------:|---:|:-------|",
    ]
    name_by_key = {dbb: name for _, dbb, name in AOIS}
    for r in rows:
        if r["spec"] == "pooled":
            continue
        lines.append(_per_aoi_row_md(r, name_by_key))

    # Dual criterion + classification
    lines += [
        "",
        "## Dual criterion + hypothesis classification",
        "",
        "Significance: β_bsi 95% CI excludes zero. "
        f"Magnitude: |β_bsi × IQR(BSI)| > {MAGNITUDE_THRESHOLD} "
        "(piece B SQ8 operational threshold).",
        "",
        "| spec | IQR(BSI) | β_bsi × IQR | sig? | mag? | dual? | classification |",
        "|------|---------:|------------:|:----:|:----:|:-----:|----------------|",
    ]
    for r in rows:
        spec_disp = (r["spec"] if r["spec"] == "pooled"
                     else name_by_key.get(r["spec"], r["spec"]))
        dual = r["significance_pass"] and r["magnitude_pass"]
        lines.append(
            f"| {spec_disp} | {r['iqr_bsi']:.4f} | "
            f"{r['magnitude_effect']:+.5f} | "
            f"{'✓' if r['significance_pass'] else '✗'} | "
            f"{'✓' if r['magnitude_pass'] else '✗'} | "
            f"{'✓' if dual else '✗'} | "
            f"{r['hypothesis_classification']} |"
        )

    lines += [
        "",
        "## Interpretation",
        "",
        _interpretation_paragraph(rows, halts, name_by_key),
        "",
        "## Outputs",
        "",
        "- `data/sa3_bsi_ndvi_regression/regression_results.csv`",
        "- `data/sa3_bsi_ndvi_regression/SA3_summary.md` (this file)",
        "- `figures/sa3_bsi_vs_ndvi_residual.png` "
        "(partial regression plot, pooled spec)",
    ]
    if halts:
        lines.append("- `data/halts/sa3_coverage/{aoi}.md` "
                     "(one per halted AOI)")
    lines.append("")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines))
    print(f"  wrote {out_path}")


def _pooled_row_md(r: dict) -> str:
    return (
        f"| pooled | {r['n']} | {r['beta_bsi']:+.4f} | {r['se_bsi']:.4f} | "
        f"[{r['ci_lo_bsi']:+.4f}, {r['ci_hi_bsi']:+.4f}] | "
        f"{r['beta_aod']:+.4f} | {r['se_aod']:.4f} | "
        f"[{r['ci_lo_aod']:+.4f}, {r['ci_hi_aod']:+.4f}] |"
    )


def _per_aoi_row_md(r: dict, name_by_key: dict) -> str:
    name = name_by_key.get(r["spec"], r["spec"])
    return (
        f"| {name} | {r['n']} | {r['beta_bsi']:+.4f} | {r['se_bsi']:.4f} | "
        f"[{r['ci_lo_bsi']:+.4f}, {r['ci_hi_bsi']:+.4f}] | "
        f"{r['beta_aod']:+.4f} | {r['se_aod']:.4f} | "
        f"[{r['ci_lo_aod']:+.4f}, {r['ci_hi_aod']:+.4f}] |"
    )


def _interpretation_paragraph(rows: list[dict], halts: list[str],
                              name_by_key: dict) -> str:
    """One paragraph, pre-reg-style. No overclaim. Surface what fires."""
    pooled = next(r for r in rows if r["spec"] == "pooled")
    bits = []

    bits.append(
        f"Pooled headline: β_bsi = {pooled['beta_bsi']:+.4f} "
        f"(95% CI [{pooled['ci_lo_bsi']:+.4f}, {pooled['ci_hi_bsi']:+.4f}]), "
        f"β_aod = {pooled['beta_aod']:+.4f} "
        f"(95% CI [{pooled['ci_lo_aod']:+.4f}, {pooled['ci_hi_aod']:+.4f}]), "
        f"n = {pooled['n']}."
    )

    sig = "significant" if pooled["significance_pass"] else "not significant"
    mag = "passes" if pooled["magnitude_pass"] else "does not pass"
    bits.append(
        f"Dual criterion on the pooled spec: BSI is {sig} at 95%, "
        f"magnitude effect (β_bsi × IQR) {mag} the "
        f"piece B SQ8 operational threshold of {MAGNITUDE_THRESHOLD}. "
        f"Hypothesis classification: {pooled['hypothesis_classification']}."
    )

    # Per-AOI heterogeneity
    per_aoi = [r for r in rows if r["spec"] != "pooled"]
    if per_aoi:
        het_bits = []
        for r in per_aoi:
            name = name_by_key.get(r["spec"], r["spec"])
            dual = r["significance_pass"] and r["magnitude_pass"]
            het_bits.append(
                f"{name} β_bsi = {r['beta_bsi']:+.4f} "
                f"(dual: {'✓' if dual else '✗'}, "
                f"class: {r['hypothesis_classification']})"
            )
        bits.append("Per-AOI heterogeneity: " + "; ".join(het_bits) + ".")

    # Pre-reg interpretation rule
    qiddiya_loaded = any(
        r["spec"] == "qiddiya_core"
        and r["significance_pass"] and r["magnitude_pass"]
        for r in per_aoi
    )
    others_loaded = any(
        r["spec"] in ("king_salman_park", "diriyah_gate")
        and r["significance_pass"] and r["magnitude_pass"]
        for r in per_aoi
    )
    if pooled["significance_pass"] and pooled["magnitude_pass"]:
        if qiddiya_loaded and not others_loaded:
            bits.append(
                "Per pre-registered interpretation rule: pooled fires "
                "with the effect concentrated at Qiddiya. This is the "
                "expected pattern under the substrate hypothesis (active-"
                "construction site loaded, less-construction sites quiet) "
                "and ships as substrate-primary."
            )
        elif others_loaded and not qiddiya_loaded:
            bits.append(
                "Per pre-registered interpretation rule: pooled fires but "
                "the effect concentrates at KSP / Diriyah rather than "
                "Qiddiya -- substantive surprise, ships as primary "
                "finding requiring scope rethink."
            )
        elif qiddiya_loaded and others_loaded:
            bits.append(
                "Per pre-registered interpretation rule: pooled fires "
                "uniformly across AOIs -- substrate signal is more general "
                "than the original Qiddiya-only prediction; ships as "
                "primary finding."
            )

    if halts:
        bits.append(
            "Halt receipts shipped under `data/halts/sa3_coverage/` for "
            "halted AOIs; per pre-reg these halts ride into prose as "
            "findings rather than appendix material."
        )

    return " ".join(bits)


# --- Main -------------------------------------------------------------------

def main():
    sys.stdout.reconfigure(line_buffering=True)

    print("SA3 -- BSI x NDVI residual regression (S30-only, HC3 robust SE)")
    print(f"  Cloud filter: cloud_fraction < {CLOUD_FILTER}")
    print(f"  Magnitude threshold: {MAGNITUDE_THRESHOLD}")
    print()

    merged, counts = merge_three_table()
    print(f"Merge complete: pooled n = {counts['n_step2_full_join']}")
    for _, dbb_key, name in AOIS:
        n = counts["n_pooled_per_aoi"].get(dbb_key, 0)
        print(f"  {name:<22s}: n = {n}")

    if counts["n_step2_full_join"] < HALT_POOLED_N:
        print(f"\nFATAL: pooled n ({counts['n_step2_full_join']}) < "
              f"{HALT_POOLED_N}. SA3 halted entirely per pre-reg.")
        sys.exit(2)

    # Per-AOI halts (computed before fitting to skip cleanly).
    halts = []
    fit_aois = []
    for _, dbb_key, name in AOIS:
        n = counts["n_pooled_per_aoi"].get(dbb_key, 0)
        if n < HALT_PER_AOI_N:
            halts.append(name)
            write_halt_receipt(name, dbb_key, n, HALT_PER_AOI_N)
        else:
            fit_aois.append((dbb_key, name))

    rows = []

    # Pooled fit
    print("\nFitting pooled spec ...")
    pooled = fit_spec("ndvi_residual ~ bsi + aod + C(aoi)", merged)
    pooled["spec"] = "pooled"
    pooled["hypothesis_classification"] = classify_hypothesis(pooled)
    pooled_full = pooled.pop("_full")
    rows.append(pooled)
    print(f"  pooled: n={pooled['n']}  β_bsi={pooled['beta_bsi']:+.4f}  "
          f"β_aod={pooled['beta_aod']:+.4f}  "
          f"class={pooled['hypothesis_classification']}")

    # Per-AOI fits
    for dbb_key, name in fit_aois:
        sub = merged[merged["aoi"] == dbb_key].copy()
        r = fit_spec("ndvi_residual ~ bsi + aod", sub)
        r["spec"] = dbb_key
        r["hypothesis_classification"] = classify_hypothesis(r)
        r.pop("_full")
        rows.append(r)
        print(f"  {name:<22s}: n={r['n']}  β_bsi={r['beta_bsi']:+.4f}  "
              f"β_aod={r['beta_aod']:+.4f}  "
              f"class={r['hypothesis_classification']}")

    # Outputs
    print("\nWriting outputs ...")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    write_results_csv(rows, OUT_DIR / "regression_results.csv")
    partial_regression_plot(merged, pooled_full,
                            FIG_DIR / "sa3_bsi_vs_ndvi_residual.png")
    write_summary(rows, counts, halts, OUT_DIR / "SA3_summary.md")

    print("\nSA3 done.")


if __name__ == "__main__":
    main()

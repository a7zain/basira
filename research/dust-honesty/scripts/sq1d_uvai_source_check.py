"""
SQ1D UVAI source check — STOP-GATE for SQ1C source-mixing decision.

Re-fetches GEE COPERNICUS/S5P/OFFL/L3_AER_AI UVAI mean over the KSP
tightened bbox for a 30-date sample (seed=42) drawn from the existing
sq1d_ksp_uvai_all.csv, and compares against the value already on file.

Note on data provenance discovered during this check (2026-04-30):
The existing KSP UVAI CSV was produced by sq1d_ksp_uvai_search.py which
already pulls from GEE COPERNICUS/S5P/OFFL/L3_AER_AI (the CLAUDE.md
"Sentinel Hub on CDSE" framing for UVAI predates this script). So this
check is a pipeline-reproducibility validation rather than a true
SH-vs-GEE source comparison: it confirms the GEE-native reduction with
the stricter parameters specified for SQ1C (bestEffort=False, exact
TROPOMI native scale = 1113.2 m) is consistent with the values written
to disk. If gate passes, GEE is fit for the Diriyah all-months pull.

Outputs:
  research/dust-honesty/data/sq1d_uvai_source_check.csv
  research/dust-honesty/data/sq1d_uvai_source_check.png

Stop-gate rules:
  * n_both_present < 20  -> STOP
  * Spearman rho < 0.85  -> STOP (source-mixing not defensible)
  * Otherwise            -> PASS, commit, proceed to Unit 2.
"""
from __future__ import annotations

import csv
import os
import sys
from pathlib import Path

import ee
import numpy as np
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from src.phase1_aois import get_bbox  # noqa: E402

DATA = ROOT / "research/dust-honesty/data"
KSP_CSV = DATA / "calibration" / "uvai_ksp_sq1d.csv"
OUT_CSV = DATA / "calibration" / "_archive" / "uvai_source_check_sq1d.csv"
OUT_PNG = ROOT / "research/dust-honesty/figures/calibration/_archive/uvai_source_check_sq1d.png"

AOI = "king_salman_park"
TROPOMI_SCALE = 1113.2
SAMPLE_N = 30
SEED = 42


def gee_uvai_mean(date_str, geom):
    """Mean absorbing_aerosol_index over geom on date_str (GEE OFFL L3),
    using the SQ1C-specified reduction params: ee.Reducer.mean(),
    bestEffort=False, scale=1113.2. Returns (mean_or_None, n_images)."""
    nxt = (np.datetime64(date_str) + np.timedelta64(1, "D")).astype(str)
    coll = (
        ee.ImageCollection("COPERNICUS/S5P/OFFL/L3_AER_AI")
        .filterDate(date_str, nxt)
        .filterBounds(geom)
        .select("absorbing_aerosol_index")
    )
    n = coll.size().getInfo()
    if n == 0:
        return None, 0
    stats = coll.mean().reduceRegion(
        reducer=ee.Reducer.mean(),
        geometry=geom,
        scale=TROPOMI_SCALE,
        maxPixels=1e9,
        bestEffort=False,
    ).getInfo()
    return stats.get("absorbing_aerosol_index"), n


def pearson(xs, ys):
    xs = np.asarray(xs); ys = np.asarray(ys)
    mx, my = xs.mean(), ys.mean()
    num = ((xs - mx) * (ys - my)).sum()
    den = np.sqrt(((xs - mx) ** 2).sum() * ((ys - my) ** 2).sum())
    return float(num / den) if den else float("nan")


def spearman(xs, ys):
    def rank(a):
        order = np.argsort(np.argsort(a))
        return order.astype(float)
    return pearson(rank(np.asarray(xs)), rank(np.asarray(ys)))


def plot_scatter(rows_both, rho_p, rho_s, out_path):
    import matplotlib.pyplot as plt
    sh = np.array([r["sh_uvai_mean"] for r in rows_both])
    ge = np.array([r["gee_uvai_mean"] for r in rows_both])
    fig, ax = plt.subplots(figsize=(6.5, 6.5))
    ax.scatter(sh, ge, color="#b4793b", edgecolor="black", s=70, alpha=0.85)
    lo = float(min(sh.min(), ge.min())); hi = float(max(sh.max(), ge.max()))
    pad = (hi - lo) * 0.05 + 1e-3
    ax.plot([lo - pad, hi + pad], [lo - pad, hi + pad], "--", color="grey", alpha=0.6)
    ax.set_xlabel("Existing CSV UVAI mean (sh_uvai_mean)")
    ax.set_ylabel("GEE re-fetch UVAI mean (gee_uvai_mean)")
    ax.set_title(f"SQ1D UVAI source check — KSP bbox\n"
                 f"n={len(rows_both)}  Pearson r={rho_p:.4f}  Spearman ρ={rho_s:.4f}")
    ax.set_xlim(lo - pad, hi + pad); ax.set_ylim(lo - pad, hi + pad)
    fig.tight_layout()
    fig.savefig(out_path, dpi=120)
    print(f"Wrote {out_path}")


def main():
    load_dotenv(ROOT / ".env")
    ee.Initialize(project=os.environ["GEE_PROJECT"])

    with open(KSP_CSV) as f:
        all_rows = list(csv.DictReader(f))
    rng = np.random.default_rng(SEED)
    sample_idx = rng.choice(len(all_rows), size=SAMPLE_N, replace=False)
    sample_rows = [all_rows[i] for i in sorted(sample_idx)]
    print(f"Sampled {SAMPLE_N} dates from {KSP_CSV.name} (seed={SEED})")

    bbox = get_bbox(AOI)
    geom = ee.Geometry.Rectangle(list(bbox))

    out_rows = []
    for i, r in enumerate(sample_rows, 1):
        date = r["date"]
        sh = float(r["uvai_mean"])
        try:
            gee, n_img = gee_uvai_mean(date, geom)
        except Exception as e:
            print(f"  [{i:2d}] {date} GEE error: {e}")
            gee, n_img = None, 0
        both = (gee is not None)
        diff = (sh - gee) if both else None
        print(f"  [{i:2d}] {date}  sh={sh:+.4f}  gee={gee if gee is None else f'{gee:+.4f}'}  "
              f"n_img={n_img}  diff={diff if diff is None else f'{diff:+.4f}'}")
        out_rows.append({
            "date": date,
            "sh_uvai_mean": sh,
            "gee_uvai_mean": gee if gee is not None else "",
            "sh_minus_gee": diff if diff is not None else "",
            "both_present": both,
        })

    fields = ["date", "sh_uvai_mean", "gee_uvai_mean", "sh_minus_gee", "both_present"]
    with open(OUT_CSV, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in out_rows:
            w.writerow(r)
    print(f"\nWrote {OUT_CSV}")

    rows_both = [r for r in out_rows if r["both_present"]]
    n_both = len(rows_both)
    if n_both > 0:
        sh = [r["sh_uvai_mean"] for r in rows_both]
        ge = [r["gee_uvai_mean"] for r in rows_both]
        diffs = [r["sh_minus_gee"] for r in rows_both]
        rp = pearson(sh, ge)
        rs = spearman(sh, ge)
        m_diff = float(np.mean(diffs))
        s_diff = float(np.std(diffs))
        print(f"\n=== Source-check stats ===")
        print(f"  n_both_present = {n_both}")
        print(f"  Pearson r      = {rp:.4f}")
        print(f"  Spearman rho   = {rs:.4f}")
        print(f"  mean(sh-gee)   = {m_diff:+.4f}")
        print(f"  stdev(sh-gee)  = {s_diff:.4f}")
        plot_scatter(rows_both, rp, rs, OUT_PNG)
    else:
        rp = rs = float("nan")
        print(f"\nn_both_present = 0  — no overlap; gate cannot proceed.")

    # ---- gate ----
    if n_both < 20:
        print(f"\n[GATE STOP] insufficient overlap for source check, "
              f"n={n_both}. Halting before Unit 2.")
        sys.exit(2)
    if not (rs >= 0.85):
        print(f"\n[GATE STOP] Spearman ρ = {rs:.4f} < 0.85. "
              f"GEE and existing CSV not measuring the same thing closely "
              f"enough for source-mixing to be defensible. Scatter at "
              f"{OUT_PNG}. Halting before Unit 2.")
        sys.exit(3)
    print(f"\n[GATE PASS] Spearman ρ = {rs:.4f}, n = {n_both}. "
          f"GEE TROPOMI UVAI fit for SQ1C source-mixing.")


if __name__ == "__main__":
    main()

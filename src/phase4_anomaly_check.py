"""
Phase 4 — Anomaly Investigation
=================================
Reads the NDVI time-series CSV and flags months with |z-score| > 3 for
any ROI.  For each flagged month, saves a cropped RGB quicklook from
the corresponding monthly scene so you can visually inspect the anomaly.

Read-only: does NOT modify the time-series CSV.

Usage:
    python src/phase4_anomaly_check.py

Outputs:
    outputs/phase4_anomalies/<roi>_<YYYY_MM>.png  — cropped RGB quicklooks
    stdout: table of flagged anomalies
"""

import csv
import json
import os
import re
from collections import defaultdict

import numpy as np
import matplotlib.pyplot as plt
import rasterio

# ── Paths ───────────────────────────────────────────────────
MONTHLY_DIR = "data/processed/monthly"
OUT_DIR     = "outputs"
ANOMALY_DIR = os.path.join(OUT_DIR, "phase4_anomalies")
CSV_PATH    = os.path.join(OUT_DIR, "phase4_ndvi_timeseries.csv")
PIXEL_PATH  = os.path.join(OUT_DIR, "phase4_rois_pixel.json")

Z_THRESHOLD = 3.0


def load_timeseries():
    """Load the NDVI time-series CSV. Returns list of dicts."""
    with open(CSV_PATH, newline="") as f:
        return list(csv.DictReader(f))


def load_roi_windows():
    """Load pixel-space ROI windows from JSON."""
    with open(PIXEL_PATH) as f:
        return json.load(f)


def find_outliers(records):
    """
    For each ROI, compute z-scores and flag |z| > threshold.
    Returns list of (roi_name, date, mean_ndvi, z_score).
    """
    # Group by ROI
    by_roi = defaultdict(list)
    for r in records:
        if r["mean_ndvi"] == "":
            continue
        by_roi[r["roi_name"]].append({
            "date": r["date"],
            "mean_ndvi": float(r["mean_ndvi"]),
        })

    flagged = []
    for roi_name, entries in by_roi.items():
        values = np.array([e["mean_ndvi"] for e in entries])
        mu = np.mean(values)
        sigma = np.std(values)
        if sigma < 1e-10:
            continue

        for entry, val in zip(entries, values):
            z = (val - mu) / sigma
            if abs(z) > Z_THRESHOLD:
                flagged.append({
                    "roi_name": roi_name,
                    "date": entry["date"],
                    "mean_ndvi": val,
                    "z_score": z,
                    "roi_mean": mu,
                    "roi_std": sigma,
                })

    flagged.sort(key=lambda x: (x["roi_name"], x["date"]))
    return flagged


def save_roi_quicklook(date_str, roi_name, windows):
    """
    Crop the RGB from the monthly scene for the flagged month/ROI
    and save as a PNG.
    """
    # date_str is YYYY-MM-15 — extract YYYY_MM for filename
    parts = date_str.split("-")
    year_month = f"{parts[0]}_{parts[1]}"
    tif_path = os.path.join(MONTHLY_DIR, f"{year_month}.tif")

    if not os.path.exists(tif_path):
        print(f"    WARNING: {tif_path} not found, skipping quicklook")
        return None

    w = windows[roi_name]
    rs, re_ = w["row_start"], w["row_stop"]
    cs, ce_ = w["col_start"], w["col_stop"]

    with rasterio.open(tif_path) as src:
        red   = src.read(3)[rs:re_, cs:ce_].astype(np.float32)  # B04
        green = src.read(2)[rs:re_, cs:ce_].astype(np.float32)  # B03
        blue  = src.read(1)[rs:re_, cs:ce_].astype(np.float32)  # B02

    rgb = np.stack([red, green, blue], axis=-1)

    # Percentile stretch
    for b in range(3):
        band = rgb[:, :, b]
        valid = band[band > 0]
        if valid.size == 0:
            continue
        lo = np.percentile(valid, 2)
        hi = np.percentile(valid, 98)
        if hi > lo:
            rgb[:, :, b] = np.clip((band - lo) / (hi - lo), 0, 1)
        else:
            rgb[:, :, b] = 0

    os.makedirs(ANOMALY_DIR, exist_ok=True)
    out_path = os.path.join(ANOMALY_DIR, f"{roi_name}_{year_month}.png")

    fig, ax = plt.subplots(1, 1, figsize=(6, 5))
    ax.imshow(rgb, aspect="equal")
    ax.set_title(f"{roi_name.replace('_', ' ').title()} — {year_month}\n"
                 f"RGB (B04/B03/B02)", fontsize=10, pad=6)
    ax.axis("off")
    plt.tight_layout()
    plt.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close()
    return out_path


def main():
    print("Phase 4 — Anomaly Investigation")
    print("=" * 55)

    if not os.path.exists(CSV_PATH):
        print(f"ERROR: Time-series CSV not found: {CSV_PATH}")
        print("Run phase4_ndvi_timeseries.py first.")
        return

    if not os.path.exists(PIXEL_PATH):
        print(f"ERROR: ROI pixel windows not found: {PIXEL_PATH}")
        print("Run phase4_rois.py first.")
        return

    records = load_timeseries()
    windows = load_roi_windows()

    print(f"  Loaded {len(records)} rows from CSV")
    print(f"  Z-score threshold: |z| > {Z_THRESHOLD}")
    print()

    # ── Per-ROI stats ─────────────────────────────────────────
    by_roi = defaultdict(list)
    for r in records:
        if r["mean_ndvi"] != "":
            by_roi[r["roi_name"]].append(float(r["mean_ndvi"]))

    print("  Per-ROI baseline stats:")
    print(f"  {'ROI':>25s}  {'N':>4s}  {'Mean':>8s}  {'Std':>8s}  "
          f"{'Min':>8s}  {'Max':>8s}")
    print("  " + "-" * 65)
    for roi_name, vals in sorted(by_roi.items()):
        arr = np.array(vals)
        print(f"  {roi_name:>25s}  {len(arr):>4d}  {arr.mean():>8.4f}  "
              f"{arr.std():>8.4f}  {arr.min():>8.4f}  {arr.max():>8.4f}")
    print()

    # ── Find outliers ─────────────────────────────────────────
    flagged = find_outliers(records)

    if not flagged:
        print("  No anomalies found (no months with |z-score| > "
              f"{Z_THRESHOLD}).")
        print("  This is fine — the time series is clean.")
        return

    print(f"  FLAGGED ANOMALIES ({len(flagged)} months):")
    print(f"  {'ROI':>25s}  {'Date':>12s}  {'NDVI':>8s}  {'z-score':>8s}  "
          f"{'Direction':>10s}")
    print("  " + "-" * 70)

    for f in flagged:
        direction = "HIGH" if f["z_score"] > 0 else "LOW"
        print(f"  {f['roi_name']:>25s}  {f['date']:>12s}  "
              f"{f['mean_ndvi']:>8.4f}  {f['z_score']:>+8.2f}  "
              f"{direction:>10s}")

    # ── Save quicklooks for each flagged month ────────────────
    print()
    print("  Saving cropped quicklooks for flagged scenes...")
    for f in flagged:
        out = save_roi_quicklook(f["date"], f["roi_name"], windows)
        if out:
            print(f"    Saved: {out}")

    print()
    print("Done. Inspect outputs/phase4_anomalies/ to visually check "
          "each flagged scene.")
    print("=" * 55)


if __name__ == "__main__":
    main()

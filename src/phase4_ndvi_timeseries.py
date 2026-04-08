"""
Phase 4 — NDVI Time-Series Analysis per ROI
=============================================
For each of 4 ROIs and each of 76 monthly scenes, computes mean and
median NDVI using only pixels that pass the common valid mask.

Includes deseasonalization: computes per-calendar-month climatology,
then anomaly = value - climatology. Trend is fit on both raw and
deseasonalized series.

Outputs:
    outputs/phase4_ndvi_timeseries.csv     — full table (incl. anomaly)
    outputs/phase4_ndvi_timeseries.png     — 4-panel raw NDVI plot
    outputs/phase4_ndvi_anomaly.png        — 4-panel anomaly plot

Usage:
    python src/phase4_ndvi_timeseries.py
"""

import csv
import json
import os
import glob
import re

import numpy as np
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import rasterio
from datetime import datetime

from utils import TARGET_CRS

# ── Paths ───────────────────────────────────────────────────
MONTHLY_DIR  = "data/processed/monthly"
NDVI_DIR     = "data/processed/ndvi"
OUT_DIR      = "outputs"
MASK_PATH    = "outputs/phase4_valid_mask.tif"
PIXEL_PATH   = "outputs/phase4_rois_pixel.json"

# ── Bands in monthly .tif files ──────────────────────────────
BAND_RED = 3  # B04
BAND_NIR = 4  # B08

# ── Minimum valid pixels per ROI-month ───────────────────────
MIN_VALID_PIXELS = 500  # below this, record NaN (partial-coverage artifact)


def list_monthly_tifs(directory):
    """Return sorted list of (year, month, path) tuples."""
    pattern = os.path.join(directory, "*.tif")
    files = sorted(glob.glob(pattern))
    result = []
    for f in files:
        m = re.search(r"(\d{4})_(\d{2})\.tif$", f)
        if m:
            result.append((int(m.group(1)), int(m.group(2)), f))
    return result


def load_mask():
    """Load the common valid mask (uint8: 0=invalid, 1=valid)."""
    with rasterio.open(MASK_PATH) as src:
        return src.read(1).astype(bool)


def load_roi_windows():
    """Load pixel-space ROI windows from JSON."""
    with open(PIXEL_PATH) as f:
        return json.load(f)


def compute_ndvi_from_bands(red, nir):
    """Compute NDVI as float32."""
    return (nir - red) / (nir + red + 1e-10)


def main():
    print("Phase 4 — NDVI Time-Series per ROI")
    print("=" * 50)

    # ── Load prerequisites ────────────────────────────────────
    if not os.path.exists(MASK_PATH):
        print(f"ERROR: Valid mask not found: {MASK_PATH}")
        print("Run phase4_valid_mask.py first.")
        return

    if not os.path.exists(PIXEL_PATH):
        print(f"ERROR: ROI pixel windows not found: {PIXEL_PATH}")
        print("Run phase4_rois.py first.")
        return

    mask = load_mask()
    windows = load_roi_windows()
    roi_names = list(windows.keys())

    # ── Defensive check: mask must have enough valid pixels ───
    total_valid = int(mask.sum())
    total_px = mask.shape[0] * mask.shape[1]
    if total_valid < 100_000:
        print(f"  ABORT: Valid mask has only {total_valid:,} valid pixels "
              f"(out of {total_px:,}).")
        print(f"  Expected at least 100,000. The mask is likely broken.")
        print(f"  Re-run phase4_valid_mask.py and check the output.")
        return

    # ── Per-ROI sanity check ──────────────────────────────────
    print(f"  Valid mask: {total_valid:,} / {total_px:,} pixels "
          f"({100.0 * total_valid / total_px:.1f}%)")
    print()
    print("  ROI sanity check:")
    for roi_name in roi_names:
        w = windows[roi_name]
        rs, re_ = w["row_start"], w["row_stop"]
        cs, ce_ = w["col_start"], w["col_stop"]
        roi_total = (re_ - rs) * (ce_ - cs)
        mask_roi = mask[rs:re_, cs:ce_]
        roi_valid = int(mask_roi.sum())
        print(f"    {roi_name:>25s}: {roi_total:,} px in window, "
              f"{roi_valid:,} valid after mask "
              f"({100.0 * roi_valid / roi_total:.1f}%)"
              if roi_total > 0 else
              f"    {roi_name:>25s}: EMPTY WINDOW")
        if roi_valid == 0:
            print(f"    WARNING: {roi_name} has ZERO valid pixels — "
                  f"all NDVI values will be N/A.")
    print()

    # Check for pre-computed NDVI files, fall back to raw bands
    ndvi_scenes = list_monthly_tifs(NDVI_DIR)
    raw_scenes = list_monthly_tifs(MONTHLY_DIR)
    use_precomputed = len(ndvi_scenes) == len(raw_scenes) and len(ndvi_scenes) > 0

    scenes = ndvi_scenes if use_precomputed else raw_scenes
    source_label = "pre-computed NDVI" if use_precomputed else "raw 4-band"

    print(f"  ROIs: {', '.join(roi_names)}")
    print(f"  Scenes: {len(scenes)} ({source_label})")
    print()

    # ── Compute NDVI stats per ROI per month ──────────────────
    records = []  # for CSV
    dropped_counts = {name: 0 for name in roi_names}  # per-ROI drop counter

    for i, (y, m, path) in enumerate(scenes, 1):
        label = f"{y}-{m:02d}"
        date_str = f"{y}-{m:02d}-15"
        print(f"  [{i:>2}/{len(scenes)}] {label}...", end=" ", flush=True)

        if use_precomputed:
            with rasterio.open(path) as src:
                ndvi_full = src.read(1).astype(np.float32)
                nodata_val = src.nodata if src.nodata is not None else -9999.0
            data_valid = (ndvi_full != nodata_val)
        else:
            with rasterio.open(path) as src:
                red = src.read(BAND_RED).astype(np.float32)
                nir = src.read(BAND_NIR).astype(np.float32)
            ndvi_full = compute_ndvi_from_bands(red, nir)
            data_valid = (red != 0) | (nir != 0)

        parts = []
        for roi_name in roi_names:
            w = windows[roi_name]
            rs, re_ = w["row_start"], w["row_stop"]
            cs, ce_ = w["col_start"], w["col_stop"]

            ndvi_roi = ndvi_full[rs:re_, cs:ce_]
            mask_roi = mask[rs:re_, cs:ce_]
            data_roi = data_valid[rs:re_, cs:ce_]

            # Valid = in common mask AND has data in this scene
            combined = mask_roi & data_roi
            valid_pixels = ndvi_roi[combined]
            n_valid = valid_pixels.size

            if n_valid >= MIN_VALID_PIXELS:
                mean_val = float(np.mean(valid_pixels))
                median_val = float(np.median(valid_pixels))
            elif n_valid > 0:
                # Too few pixels — partial-coverage artifact
                mean_val = None
                median_val = None
                dropped_counts[roi_name] += 1
                print(f"\n    DROPPED {roi_name}: only {n_valid} valid px "
                      f"(< {MIN_VALID_PIXELS} threshold)", end="")
            else:
                mean_val = None
                median_val = None
                dropped_counts[roi_name] += 1
                n_mask = int(mask_roi.sum())
                n_data = int(data_roi.sum())
                print(f"\n    N/A for {roi_name}: "
                      f"mask_valid={n_mask}, scene_valid={n_data}, "
                      f"combined=0", end="")

            records.append({
                "date": date_str,
                "roi_name": roi_name,
                "mean_ndvi": f"{mean_val:.6f}" if mean_val is not None else "",
                "median_ndvi": f"{median_val:.6f}" if median_val is not None else "",
                "valid_pixel_count": n_valid,
            })
            parts.append(f"{roi_name}={mean_val:.4f}" if mean_val else
                         f"{roi_name}=N/A({n_valid}px)")

        print("  ".join(parts))

    # ── Report dropped months ─────────────────────────────────
    print()
    print(f"  Months dropped per ROI (< {MIN_VALID_PIXELS} valid pixels):")
    for roi_name in roi_names:
        n = dropped_counts[roi_name]
        print(f"    {roi_name:>25s}: {n} / {len(scenes)} months dropped")
    print()

    # ── Deseasonalization ────────────────────────────────────
    # Compute climatology (mean NDVI per calendar month per ROI)
    # and anomaly (value - climatology)
    print("\n  Computing climatology and anomalies...")

    from collections import defaultdict as _dd
    climatology = {}  # (roi_name, cal_month) -> mean
    cal_buckets = _dd(list)  # (roi_name, cal_month) -> [values]

    for r in records:
        if r["mean_ndvi"] == "":
            continue
        cal_month = int(r["date"].split("-")[1])
        cal_buckets[(r["roi_name"], cal_month)].append(float(r["mean_ndvi"]))

    for key, vals in cal_buckets.items():
        climatology[key] = float(np.mean(vals))

    # Add climatology + anomaly columns to records
    for r in records:
        if r["mean_ndvi"] == "":
            r["ndvi_climatology"] = ""
            r["ndvi_anomaly"] = ""
            continue
        cal_month = int(r["date"].split("-")[1])
        clim = climatology.get((r["roi_name"], cal_month))
        if clim is not None:
            r["ndvi_climatology"] = f"{clim:.6f}"
            r["ndvi_anomaly"] = f"{float(r['mean_ndvi']) - clim:.6f}"
        else:
            r["ndvi_climatology"] = ""
            r["ndvi_anomaly"] = ""

    # ── Save CSV ──────────────────────────────────────────────
    os.makedirs(OUT_DIR, exist_ok=True)
    csv_path = os.path.join(OUT_DIR, "phase4_ndvi_timeseries.csv")
    with open(csv_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "date", "roi_name", "mean_ndvi", "median_ndvi",
            "valid_pixel_count", "ndvi_climatology", "ndvi_anomaly",
        ])
        writer.writeheader()
        writer.writerows(records)
    print(f"  Saved CSV: {csv_path} ({len(records)} rows)")

    # ── Helper: plot one figure ───────────────────────────────
    roi_colors = {
        "wadi_hanifa":        "#00cc66",
        "king_salman_park":   "#ff5533",
        "northern_expansion": "#3388ff",
        "central_urban":      "#ddaa00",
    }

    def plot_timeseries(value_key, title, ylabel, out_path, zero_line=False):
        """Generic 2x2 time-series plotter. Returns {roi: slope}."""
        fig, axes = plt.subplots(2, 2, figsize=(16, 10), sharex=True)
        fig.patch.set_facecolor("white")
        axes_flat = axes.flatten()
        slopes_out = {}

        for idx, roi_name in enumerate(roi_names):
            ax = axes_flat[idx]
            roi_recs = [r for r in records
                        if r["roi_name"] == roi_name and r[value_key] != ""]
            if not roi_recs:
                ax.text(0.5, 0.5, "No data", transform=ax.transAxes,
                        ha="center", va="center")
                continue

            dates = [datetime.strptime(r["date"], "%Y-%m-%d")
                     for r in roi_recs]
            vals = [float(r[value_key]) for r in roi_recs]
            color = roi_colors.get(roi_name, "#888888")

            # Monthly values
            ax.plot(dates, vals, color=color, alpha=0.4, linewidth=0.8,
                    marker=".", markersize=3, label="Monthly")

            # 12-month rolling mean
            if len(vals) >= 12:
                rolling = np.convolve(vals, np.ones(12) / 12, mode="valid")
                ax.plot(dates[11:], rolling, color=color, linewidth=2,
                        label="12-month rolling mean")

            # Linear trend
            days = np.array([(d - dates[0]).days for d in dates], dtype=float)
            years_elapsed = days / 365.25
            arr = np.array(vals)
            if len(arr) >= 2:
                coeffs = np.polyfit(years_elapsed, arr, 1)
                slope = coeffs[0]
                slopes_out[roi_name] = slope
                trend_y = np.polyval(coeffs, years_elapsed)
                ax.plot(dates, trend_y, color="gray", linewidth=1,
                        linestyle="--", alpha=0.7,
                        label=f"Trend: {slope:+.5f}/yr")

            if zero_line:
                ax.axhline(0, color="#666", linewidth=0.5, linestyle=":")

            ax.set_title(roi_name.replace("_", " ").title(),
                         fontsize=11, fontweight="bold", pad=6)
            ax.set_ylabel(ylabel, fontsize=9)
            ax.legend(fontsize=7, loc="upper left")
            ax.grid(True, alpha=0.3)
            ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
            ax.xaxis.set_major_locator(mdates.YearLocator())

        fig.suptitle(title, fontsize=13, y=1.02)
        plt.tight_layout()
        plt.savefig(out_path, dpi=200, bbox_inches="tight", facecolor="white")
        plt.close()
        print(f"  Saved plot: {out_path}")
        return slopes_out

    # ── Raw NDVI plot ─────────────────────────────────────────
    raw_slopes = plot_timeseries(
        "mean_ndvi",
        "NDVI Time Series by ROI — Riyadh AOI\n"
        "Sentinel-2 L2A  |  20 m  |  Common valid mask applied",
        "NDVI",
        os.path.join(OUT_DIR, "phase4_ndvi_timeseries.png"),
    )

    # ── Anomaly plot ──────────────────────────────────────────
    anom_slopes = plot_timeseries(
        "ndvi_anomaly",
        "NDVI Anomaly (Deseasonalized) by ROI — Riyadh AOI\n"
        "anomaly = monthly NDVI - calendar-month climatology",
        "NDVI Anomaly",
        os.path.join(OUT_DIR, "phase4_ndvi_anomaly.png"),
        zero_line=True,
    )

    # ── Print trend summary ───────────────────────────────────
    print()
    print("  NDVI Trend Summary:")
    print("  " + "-" * 70)
    print(f"  {'ROI':>25s}  {'Raw slope':>12s}  {'Deseas. slope':>14s}  "
          f"{'Interpretation':>15s}")
    print("  " + "-" * 70)
    for roi_name in roi_names:
        raw_s = raw_slopes.get(roi_name)
        anom_s = anom_slopes.get(roi_name)
        if anom_s is not None:
            if anom_s > 0.002:
                interp = "GREENING"
            elif anom_s < -0.002:
                interp = "BROWNING"
            else:
                interp = "STABLE"
        else:
            interp = "N/A"
        raw_str = f"{raw_s:+.5f}" if raw_s is not None else "N/A"
        anom_str = f"{anom_s:+.5f}" if anom_s is not None else "N/A"
        print(f"  {roi_name:>25s}  {raw_str:>12s}  {anom_str:>14s}  "
              f"{interp:>15s}")
    print("  " + "-" * 70)
    print()
    print("Done.")
    print("=" * 50)


if __name__ == "__main__":
    main()

"""
Phase 4 — Pixel-Level Greening Map
====================================
Computes per-pixel vegetation persistence (fraction of months with
NDVI > 0.20) for 2020 and 2025, then classifies pixels as:
    0 = other
    1 = stable_green  (both years > 0.6 persistence)
    2 = new_green      (2020 < 0.2 AND 2025 > 0.6)
    3 = lost_green     (2020 > 0.6 AND 2025 < 0.2)

Usage:
    python src/phase4_green_map.py

Outputs:
    outputs/phase4_green_map.tif  — uint8 classification
    outputs/phase4_green_map.png  — visualization with ROI overlays
"""

import json
import os
import glob
import re

import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import rasterio

from utils import TARGET_CRS

# ── Paths ───────────────────────────────────────────────────
MONTHLY_DIR = "data/processed/monthly"
OUT_DIR     = "outputs"
MASK_PATH   = os.path.join(OUT_DIR, "phase4_valid_mask.tif")
PIXEL_PATH  = os.path.join(OUT_DIR, "phase4_rois_pixel.json")

# ── Parameters ──────────────────────────────────────────────
NDVI_VEG_THRESHOLD = 0.20   # NDVI above this = "vegetated"
PERSIST_HIGH       = 0.6    # persistence above this = "green"
PERSIST_LOW        = 0.2    # persistence below this = "not green"

# ── Bands ───────────────────────────────────────────────────
BAND_RED = 3  # B04
BAND_NIR = 4  # B08

PIXEL_RES = 20  # metres


def list_monthly_tifs_for_year(year):
    """Return sorted paths for all scenes in a given year."""
    pattern = os.path.join(MONTHLY_DIR, f"{year}_*.tif")
    return sorted(glob.glob(pattern))


def compute_persistence(paths, mask, threshold=NDVI_VEG_THRESHOLD):
    """
    For a list of monthly GeoTIFFs, compute per-pixel fraction of months
    where NDVI > threshold, considering only valid-mask pixels.

    Returns (persistence, n_scenes) — both same shape as mask.
    persistence is float32 in [0, 1]; masked pixels get NaN.
    """
    height, width = mask.shape
    veg_count = np.zeros((height, width), dtype=np.float32)
    scene_count = np.zeros((height, width), dtype=np.float32)

    for path in paths:
        with rasterio.open(path) as src:
            red = src.read(BAND_RED).astype(np.float32)
            nir = src.read(BAND_NIR).astype(np.float32)

        # Per-scene validity: all bands nonzero
        scene_valid = (red != 0) & (nir != 0)
        combined = mask & scene_valid

        ndvi = (nir - red) / (nir + red + 1e-10)

        veg_count += (combined & (ndvi > threshold)).astype(np.float32)
        scene_count += combined.astype(np.float32)

    # Persistence = fraction of valid months that were vegetated
    persistence = np.full((height, width), np.nan, dtype=np.float32)
    has_data = scene_count > 0
    persistence[has_data] = veg_count[has_data] / scene_count[has_data]

    return persistence, scene_count


def find_basemap_scene(min_size_mb=30):
    """Find the most recent full-coverage scene."""
    pattern = os.path.join(MONTHLY_DIR, "*.tif")
    files = sorted(glob.glob(pattern), reverse=True)
    for f in files:
        if os.path.getsize(f) / 1e6 >= min_size_mb:
            return f
    return max(files, key=os.path.getsize) if files else None


def load_rgb_stretched(path):
    """Load an RGB image with percentile stretch."""
    with rasterio.open(path) as src:
        red   = src.read(3).astype(np.float32)
        green = src.read(2).astype(np.float32)
        blue  = src.read(1).astype(np.float32)

    rgb = np.stack([red, green, blue], axis=-1)
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
    return rgb


def main():
    print("Phase 4 — Pixel-Level Greening Map")
    print("=" * 50)

    # ── Load prerequisites ────────────────────────────────────
    if not os.path.exists(MASK_PATH):
        print(f"ERROR: Valid mask not found: {MASK_PATH}")
        return

    with rasterio.open(MASK_PATH) as src:
        mask = src.read(1).astype(bool)
        profile = src.profile.copy()

    windows = {}
    if os.path.exists(PIXEL_PATH):
        with open(PIXEL_PATH) as f:
            windows = json.load(f)

    # ── Compute persistence for 2020 and 2025 ────────────────
    paths_2020 = list_monthly_tifs_for_year(2020)
    paths_2025 = list_monthly_tifs_for_year(2025)

    print(f"  2020 scenes: {len(paths_2020)}")
    print(f"  2025 scenes: {len(paths_2025)}")
    print(f"  NDVI threshold: {NDVI_VEG_THRESHOLD}")
    print(f"  Persistence high/low: {PERSIST_HIGH}/{PERSIST_LOW}")
    print()

    print("  Computing 2020 vegetation persistence...")
    persist_2020, count_2020 = compute_persistence(paths_2020, mask)
    print(f"    Done. Mean persistence (valid pixels): "
          f"{np.nanmean(persist_2020):.4f}")

    print("  Computing 2025 vegetation persistence...")
    persist_2025, count_2025 = compute_persistence(paths_2025, mask)
    print(f"    Done. Mean persistence (valid pixels): "
          f"{np.nanmean(persist_2025):.4f}")
    print()

    # ── Classify ──────────────────────────────────────────────
    has_data = (~np.isnan(persist_2020)) & (~np.isnan(persist_2025))

    green_map = np.zeros(mask.shape, dtype=np.uint8)

    # 1 = stable green
    stable = has_data & (persist_2020 > PERSIST_HIGH) & (persist_2025 > PERSIST_HIGH)
    green_map[stable] = 1

    # 2 = new green
    new = has_data & (persist_2020 < PERSIST_LOW) & (persist_2025 > PERSIST_HIGH)
    green_map[new] = 2

    # 3 = lost green
    lost = has_data & (persist_2020 > PERSIST_HIGH) & (persist_2025 < PERSIST_LOW)
    green_map[lost] = 3

    # ── Save GeoTIFF ──────────────────────────────────────────
    os.makedirs(OUT_DIR, exist_ok=True)

    out_profile = profile.copy()
    out_profile.update(
        count=1,
        dtype="uint8",
        nodata=0,
        compress="deflate",
    )
    out_profile.pop("predictor", None)

    tif_path = os.path.join(OUT_DIR, "phase4_green_map.tif")
    with rasterio.open(tif_path, "w", **out_profile) as dst:
        dst.write(green_map, 1)
    print(f"  Saved: {tif_path}")

    # ── Visualization ─────────────────────────────────────────
    basemap_path = find_basemap_scene()
    if basemap_path:
        rgb = load_rgb_stretched(basemap_path)
    else:
        rgb = np.zeros((*mask.shape, 3), dtype=np.float32)

    # Build RGBA overlay
    h, w = mask.shape
    overlay = np.zeros((h, w, 4), dtype=np.float32)

    # stable green: dark green
    overlay[green_map == 1] = [0.0, 0.5, 0.0, 0.7]
    # new green: bright lime
    overlay[green_map == 2] = [0.2, 1.0, 0.0, 0.8]
    # lost green: red
    overlay[green_map == 3] = [1.0, 0.1, 0.1, 0.8]

    fig, ax = plt.subplots(1, 1, figsize=(14, 11))
    fig.patch.set_facecolor("white")
    ax.imshow(rgb, aspect="equal")
    ax.imshow(overlay, aspect="equal")

    # Draw ROI rectangles
    roi_colors_map = {
        "wadi_hanifa":        "#00ff88",
        "king_salman_park":   "#ff6644",
        "northern_expansion": "#44aaff",
        "central_urban":      "#ffdd44",
    }
    for roi_name, win in windows.items():
        color = roi_colors_map.get(roi_name, "#ffffff")
        rect = mpatches.Rectangle(
            (win["col_start"], win["row_start"]),
            win["col_stop"] - win["col_start"],
            win["row_stop"] - win["row_start"],
            linewidth=1.5, edgecolor=color, facecolor="none",
        )
        ax.add_patch(rect)
        cx = (win["col_start"] + win["col_stop"]) / 2
        cy = win["row_start"] - 8
        ax.text(cx, cy, roi_name.replace("_", " ").title(),
                fontsize=6, color=color, fontweight="bold", ha="center",
                bbox=dict(boxstyle="round,pad=0.15", facecolor="black",
                          alpha=0.5, edgecolor="none"))

    # Legend
    legend_patches = [
        mpatches.Patch(color=(0.0, 0.5, 0.0), label="Stable green"),
        mpatches.Patch(color=(0.2, 1.0, 0.0), label="New green (2020→2025)"),
        mpatches.Patch(color=(1.0, 0.1, 0.1), label="Lost green (2020→2025)"),
    ]
    ax.legend(handles=legend_patches, loc="lower right", fontsize=9,
              framealpha=0.85)

    ax.set_title(
        "Vegetation Change Map — Riyadh AOI\n"
        f"NDVI > {NDVI_VEG_THRESHOLD} persistence: 2020 vs 2025  |  "
        f"20 m  |  {len(paths_2020)} + {len(paths_2025)} scenes",
        fontsize=11, pad=10,
    )
    ax.axis("off")

    png_path = os.path.join(OUT_DIR, "phase4_green_map.png")
    plt.savefig(png_path, dpi=200, bbox_inches="tight", facecolor="white")
    plt.close()
    print(f"  Saved: {png_path}")

    # ── Summary statistics ────────────────────────────────────
    px_area_km2 = (PIXEL_RES ** 2) / 1e6

    n_stable = int(np.sum(green_map == 1))
    n_new    = int(np.sum(green_map == 2))
    n_lost   = int(np.sum(green_map == 3))

    print()
    print("  AOI-wide summary:")
    print(f"    Stable green:  {n_stable:>8,} px  ({n_stable * px_area_km2:.2f} km2)")
    print(f"    New green:     {n_new:>8,} px  ({n_new * px_area_km2:.2f} km2)")
    print(f"    Lost green:    {n_lost:>8,} px  ({n_lost * px_area_km2:.2f} km2)")
    if n_lost > 0:
        print(f"    New/Lost ratio: {n_new / n_lost:.2f}")
    else:
        print(f"    New/Lost ratio: inf (no lost pixels)")

    # ── Per-ROI breakdown ─────────────────────────────────────
    if windows:
        print()
        print("  Per-ROI breakdown:")
        print(f"  {'ROI':>25s}  {'Stable':>8s}  {'New':>8s}  "
              f"{'Lost':>8s}  {'New km2':>8s}  {'Lost km2':>9s}  "
              f"{'Ratio':>6s}")
        print("  " + "-" * 80)

        for roi_name, win in windows.items():
            rs, re_ = win["row_start"], win["row_stop"]
            cs, ce_ = win["col_start"], win["col_stop"]
            roi_map = green_map[rs:re_, cs:ce_]

            r_stable = int(np.sum(roi_map == 1))
            r_new    = int(np.sum(roi_map == 2))
            r_lost   = int(np.sum(roi_map == 3))
            ratio_str = (f"{r_new / r_lost:.2f}" if r_lost > 0
                         else ("inf" if r_new > 0 else "—"))

            print(f"  {roi_name:>25s}  {r_stable:>8,}  {r_new:>8,}  "
                  f"{r_lost:>8,}  {r_new * px_area_km2:>8.3f}  "
                  f"{r_lost * px_area_km2:>9.3f}  {ratio_str:>6s}")

        print("  " + "-" * 80)

    print()
    print("Done.")
    print("=" * 50)


if __name__ == "__main__":
    main()

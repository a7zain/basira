"""
Phase 4 — Common Valid Mask (Coverage Threshold)
=================================================
Builds a per-pixel coverage count (how many of the 76 scenes have valid
data at each pixel), then thresholds at 80% to produce a binary mask
for time-series analysis.

This avoids the strict-AND problem where ~10 partial-coverage scenes
(diagonal nodata strips) wipe out the entire western half of the AOI.

Usage:
    python src/phase4_valid_mask.py

Outputs:
    outputs/phase4_pixel_coverage.tif  — uint8, count of valid scenes (0-N)
    outputs/phase4_pixel_coverage.png  — heatmap visualization
    outputs/phase4_valid_mask.tif      — uint8, 0=excluded, 1=valid for TS
    outputs/phase4_valid_mask.png      — binary mask visualization
"""

import os
import glob
import re

import numpy as np
import matplotlib.pyplot as plt
import rasterio

from utils import TARGET_CRS

# ── Paths ───────────────────────────────────────────────────
MONTHLY_DIR = "data/processed/monthly"
OUT_DIR     = "outputs"

# ── Parameters ──────────────────────────────────────────────
COVERAGE_THRESHOLD = 0.80   # pixel must be valid in >= 80% of scenes
PIXEL_RES = 20              # metres


def list_monthly_tifs():
    """Return sorted list of (year, month, path) tuples."""
    pattern = os.path.join(MONTHLY_DIR, "*.tif")
    files = sorted(glob.glob(pattern))
    result = []
    for f in files:
        m = re.search(r"(\d{4})_(\d{2})\.tif$", f)
        if m:
            result.append((int(m.group(1)), int(m.group(2)), f))
    return result


def main():
    print("Phase 4 — Common Valid Mask (Coverage Threshold)")
    print("=" * 50)

    scenes = list_monthly_tifs()
    if not scenes:
        print(f"ERROR: No .tif files found in {MONTHLY_DIR}/")
        return

    n_scenes = len(scenes)
    threshold_count = int(np.ceil(COVERAGE_THRESHOLD * n_scenes))

    print(f"  Found {n_scenes} monthly scenes")
    print(f"  Coverage threshold: {COVERAGE_THRESHOLD:.0%} = "
          f"pixel must be valid in >= {threshold_count}/{n_scenes} scenes")
    print()

    # ── Read reference metadata from first scene ──────────────
    with rasterio.open(scenes[0][2]) as ref:
        profile = ref.profile.copy()
        height, width = ref.shape

    # ── Count valid scenes per pixel ──────────────────────────
    coverage = np.zeros((height, width), dtype=np.uint8)

    for i, (y, m, path) in enumerate(scenes, 1):
        print(f"  [{i:>2}/{n_scenes}] {y}-{m:02d}...", end=" ", flush=True)

        with rasterio.open(path) as src:
            # A pixel is valid if ALL 4 bands are nonzero
            scene_valid = np.ones((height, width), dtype=bool)
            for b in range(1, 5):
                band = src.read(b)
                scene_valid &= (band != 0)

        n_invalid = (~scene_valid).sum()
        coverage += scene_valid.astype(np.uint8)
        print(f"nodata: {n_invalid:,} px")

    # ── Build binary mask from coverage threshold ─────────────
    mask = (coverage >= threshold_count).astype(np.uint8)

    # ── Save coverage count raster ────────────────────────────
    os.makedirs(OUT_DIR, exist_ok=True)

    cov_profile = profile.copy()
    cov_profile.update(
        count=1,
        dtype="uint8",
        nodata=None,
        compress="deflate",
    )
    cov_profile.pop("predictor", None)

    cov_path = os.path.join(OUT_DIR, "phase4_pixel_coverage.tif")
    with rasterio.open(cov_path, "w", **cov_profile) as dst:
        dst.write(coverage, 1)
    print(f"\n  Saved coverage raster: {cov_path}")

    # ── Save binary mask raster ───────────────────────────────
    mask_profile = cov_profile.copy()
    mask_profile.update(nodata=0)

    mask_path = os.path.join(OUT_DIR, "phase4_valid_mask.tif")
    with rasterio.open(mask_path, "w", **mask_profile) as dst:
        dst.write(mask, 1)
    print(f"  Saved valid mask: {mask_path}")

    # ── Coverage heatmap PNG ──────────────────────────────────
    fig, ax = plt.subplots(1, 1, figsize=(12, 9))
    fig.patch.set_facecolor("black")
    im = ax.imshow(coverage, cmap="viridis", vmin=0, vmax=n_scenes,
                   aspect="equal")
    cbar = plt.colorbar(im, ax=ax, shrink=0.8, pad=0.02)
    cbar.set_label(f"Valid scene count (out of {n_scenes})",
                   color="white", fontsize=10)
    cbar.ax.yaxis.set_tick_params(color="white")
    plt.setp(cbar.ax.yaxis.get_ticklabels(), color="white")
    ax.set_title(
        f"Per-Pixel Temporal Coverage — Riyadh AOI\n"
        f"{n_scenes} monthly scenes  |  Bright = good coverage",
        fontsize=11, color="white", pad=10,
    )
    ax.axis("off")

    cov_png = os.path.join(OUT_DIR, "phase4_pixel_coverage.png")
    plt.savefig(cov_png, dpi=150, bbox_inches="tight", facecolor="black")
    plt.close()
    print(f"  Saved coverage heatmap: {cov_png}")

    # ── Binary mask PNG ───────────────────────────────────────
    fig, ax = plt.subplots(1, 1, figsize=(12, 9))
    fig.patch.set_facecolor("black")
    ax.imshow(mask, cmap="gray", vmin=0, vmax=1, aspect="equal")
    ax.set_title(
        f"Valid Mask — Riyadh AOI\n"
        f"White = valid in >= {COVERAGE_THRESHOLD:.0%} of scenes "
        f"({threshold_count}/{n_scenes})  |  Black = excluded",
        fontsize=10, color="white", pad=10,
    )
    ax.axis("off")

    mask_png = os.path.join(OUT_DIR, "phase4_valid_mask.png")
    plt.savefig(mask_png, dpi=150, bbox_inches="tight", facecolor="black")
    plt.close()
    print(f"  Saved mask PNG: {mask_png}")

    # ── Summary statistics ────────────────────────────────────
    total_px = height * width
    valid_px = int(mask.sum())
    invalid_px = total_px - valid_px
    pct_valid = 100.0 * valid_px / total_px
    area_km2 = valid_px * (PIXEL_RES ** 2) / 1e6

    print()
    print("  Summary:")
    print(f"    Raster size:      {width} x {height} = {total_px:,} pixels")
    print(f"    Threshold:        >= {threshold_count}/{n_scenes} scenes "
          f"({COVERAGE_THRESHOLD:.0%})")
    print(f"    Valid pixels:     {valid_px:,} ({pct_valid:.1f}%)")
    print(f"    Excluded pixels:  {invalid_px:,} ({100 - pct_valid:.1f}%)")
    print(f"    Valid area:       {area_km2:.1f} km2 (at {PIXEL_RES}m)")

    # Coverage distribution
    print()
    print("  Coverage distribution:")
    for lo, hi, label in [
        (n_scenes, n_scenes, f"  {n_scenes}/{n_scenes} (all)"),
        (threshold_count, n_scenes - 1, f"  {threshold_count}-{n_scenes-1}"),
        (1, threshold_count - 1, f"  1-{threshold_count-1} (below threshold)"),
        (0, 0, "  0 (never valid)"),
    ]:
        count = int(np.sum((coverage >= lo) & (coverage <= hi)))
        pct = 100.0 * count / total_px
        print(f"    {label:>25s}: {count:>10,} px ({pct:.1f}%)")

    # Sanity check
    if pct_valid < 50:
        print()
        print(f"  WARNING: Only {pct_valid:.1f}% valid — something may be wrong.")
        print("  Expected 85-95% for Riyadh with 80% threshold.")

    print("=" * 50)


if __name__ == "__main__":
    main()

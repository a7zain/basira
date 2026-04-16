"""
Phase 4.10 — Export Coverage Confidence Mask as Web-Ready PNG
==============================================================
Reads the pixel coverage raster (count of valid scenes per pixel),
maps low-coverage areas to a grey haze overlay, and exports as a
transparent PNG for the Leaflet web app.

High coverage = transparent. Low coverage = grey haze.

Outputs (under webapp/data/phase4/):
    coverage_mask.png          — RGBA overlay (WGS84)
    coverage_mask_bounds.json  — bounding box for L.imageOverlay

Usage:
    python src/phase4_export_coverage.py
"""

import json
import os
import sys

import numpy as np
from PIL import Image

sys.path.insert(0, os.path.join(os.path.dirname(__file__)))
from phase4_export_web import reproject_to_wgs84

# ── Paths ───────────────────────────────────────────────────
COVERAGE_TIF = "outputs/phase4_pixel_coverage.tif"
MASK_TIF = "outputs/phase4_valid_mask.tif"
WEB_DIR = "webapp/data/phase4"


def main():
    print("Phase 4.10 — Export Coverage Confidence Mask")
    print("=" * 50)

    if not os.path.exists(COVERAGE_TIF):
        print(f"  ERROR: {COVERAGE_TIF} not found")
        return

    # ── Reproject to WGS84 ────────────────────────────────
    print("  Reprojecting coverage to EPSG:4326...")
    data, bounds, _ = reproject_to_wgs84(COVERAGE_TIF)
    coverage = data[0]  # uint8, 0-76

    h, w = coverage.shape
    print(f"  Reprojected size: {h} x {w}")

    # Valid pixels = coverage > 0 (nodata/outside = 0 after reprojection)
    valid = coverage > 0
    valid_vals = coverage[valid]

    # ── Percentile analysis ───────────────────────────────
    print(f"\n  Coverage statistics (valid pixels only, n={valid_vals.size:,}):")
    for p in [10, 25, 50, 75, 90]:
        print(f"    P{p:2d}: {np.percentile(valid_vals, p):.0f} scenes")
    print(f"    Mean: {valid_vals.mean():.1f}")
    print(f"    Std:  {valid_vals.std():.1f}")

    # Check: fraction below haze threshold (60)
    below_60 = (valid_vals < 60).sum()
    pct_below_60 = 100 * below_60 / valid_vals.size
    print(f"\n  Pixels below 60 (will be hazed): {below_60:,} ({pct_below_60:.1f}%)")

    if pct_below_60 > 40:
        print("\n  *** WARNING: >40% of AOI would be hazed. ***")
        print("  *** Review thresholds before proceeding.  ***")
        return

    # ── Map to RGBA ───────────────────────────────────────
    # Thresholds calibrated to actual distribution:
    #   P50=67, 98% >= 66, only 0.7% below 60.
    #   We haze only the sparse tail to highlight genuinely weak areas.
    rgba = np.zeros((h, w, 4), dtype=np.uint8)
    grey = (60, 60, 60)

    # coverage >= 60: transparent (well-covered, default)
    # coverage 50-59: light haze
    m = valid & (coverage >= 50) & (coverage < 60)
    rgba[m] = (*grey, 60)

    # coverage 40-49: medium
    m = valid & (coverage >= 40) & (coverage < 50)
    rgba[m] = (*grey, 110)

    # coverage 30-39: heavy
    m = valid & (coverage >= 30) & (coverage < 40)
    rgba[m] = (*grey, 160)

    # coverage < 30: near-opaque
    m = valid & (coverage < 30)
    rgba[m] = (*grey, 200)

    # nodata stays (0,0,0,0)

    # ── Per-band counts ───────────────────────────────────
    alpha = rgba[:, :, 3]
    bands = [
        ("alpha=0   (transparent, >= 70)", 0),
        ("alpha=60  (light haze, 60-69)", 60),
        ("alpha=110 (medium haze, 50-59)", 110),
        ("alpha=160 (heavy haze, 40-49)", 160),
        ("alpha=200 (near-opaque, < 40)", 200),
    ]
    print(f"\n  Alpha band pixel counts:")
    total_hazed = 0
    for label, val in bands:
        count = int((alpha == val).sum())
        pct = 100 * count / (h * w)
        print(f"    {label}: {count:>10,}  ({pct:5.1f}%)")
        if val > 0:
            total_hazed += count
    total_aoi = int(valid.sum())
    print(f"    Total hazed: {total_hazed:,} / {total_aoi:,} valid "
          f"({100 * total_hazed / total_aoi:.1f}% of AOI)")

    # ── Save PNG ──────────────────────────────────────────
    os.makedirs(WEB_DIR, exist_ok=True)
    img = Image.fromarray(rgba, "RGBA")
    png_path = os.path.join(WEB_DIR, "coverage_mask.png")
    img.save(png_path, optimize=True)
    print(f"\n  Saved: {png_path} ({os.path.getsize(png_path) / 1024:.0f} KB)")

    bounds_path = os.path.join(WEB_DIR, "coverage_mask_bounds.json")
    with open(bounds_path, "w") as f:
        json.dump(bounds, f, indent=2)
    print(f"  Saved: {bounds_path}")
    print(f"  Bounds: {bounds}")
    print("=" * 50)


if __name__ == "__main__":
    main()

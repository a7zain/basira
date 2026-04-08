"""
Phase 4 — NDVI Computation
===========================
Computes NDVI from monthly 4-band Sentinel-2 GeoTIFFs and saves
single-band float32 NDVI rasters.

Band mapping in each .tif:
    Band 1 = B02 (blue)
    Band 2 = B03 (green)
    Band 3 = B04 (red)
    Band 4 = B08 (NIR)

NDVI = (B08 - B04) / (B08 + B04 + 1e-10)

Usage:
    python src/phase4_ndvi.py
"""

import os
import glob
import re

import numpy as np
import rasterio

from utils import TARGET_CRS

# ── Paths ───────────────────────────────────────────────────
MONTHLY_DIR = "data/processed/monthly"
NDVI_DIR    = "data/processed/ndvi"
OUT_DIR     = "outputs"


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


def compute_ndvi(src_path, dst_path):
    """
    Compute NDVI from a 4-band GeoTIFF and save as single-band float32.
    Returns mean NDVI of valid pixels, or None on failure.
    """
    with rasterio.open(src_path) as src:
        red = src.read(3).astype(np.float32)   # B04
        nir = src.read(4).astype(np.float32)   # B08
        profile = src.profile.copy()

    # Nodata mask: pixels where either band is 0 (no observation)
    nodata_mask = (red == 0) & (nir == 0)

    # NDVI
    ndvi = (nir - red) / (nir + red + 1e-10)

    # Mask nodata
    ndvi_nodata = -9999.0
    ndvi[nodata_mask] = ndvi_nodata

    # Update profile for single-band float32 output
    profile.update(
        count=1,
        dtype="float32",
        nodata=ndvi_nodata,
        compress="deflate",
        predictor=3,
        tiled=True,
        blockxsize=256,
        blockysize=256,
    )

    os.makedirs(os.path.dirname(dst_path), exist_ok=True)
    with rasterio.open(dst_path, "w", **profile) as dst:
        dst.write(ndvi, 1)

    # Compute mean NDVI of valid pixels
    valid = ndvi[~nodata_mask]
    if valid.size > 0:
        return float(np.mean(valid))
    return None


def main():
    print("Phase 4 — NDVI Computation")
    print("=" * 40)

    scenes = list_monthly_tifs()
    if not scenes:
        print(f"ERROR: No .tif files found in {MONTHLY_DIR}/")
        return

    print(f"  Found {len(scenes)} monthly scenes")
    print(f"  Range: {scenes[0][0]}-{scenes[0][1]:02d} to "
          f"{scenes[-1][0]}-{scenes[-1][1]:02d}")
    print(f"  Output: {NDVI_DIR}/")
    print()

    os.makedirs(NDVI_DIR, exist_ok=True)

    created = 0
    skipped = 0
    mean_ndvi = {}  # (year, month) -> mean

    for i, (y, m, src_path) in enumerate(scenes, 1):
        label = f"{y}-{m:02d}"
        dst_path = os.path.join(NDVI_DIR, f"{y}_{m:02d}.tif")

        if os.path.exists(dst_path):
            print(f"  [{i:>2}/{len(scenes)}] {label} — SKIP (exists)")
            # Still compute mean for summary
            with rasterio.open(dst_path) as src:
                ndvi = src.read(1)
                nodata = src.nodata or -9999.0
                valid = ndvi[ndvi != nodata]
                if valid.size > 0:
                    mean_ndvi[(y, m)] = float(np.mean(valid))
            skipped += 1
            continue

        print(f"  [{i:>2}/{len(scenes)}] {label} — computing...", end=" ",
              flush=True)
        avg = compute_ndvi(src_path, dst_path)
        if avg is not None:
            mean_ndvi[(y, m)] = avg
        size_mb = os.path.getsize(dst_path) / 1e6
        print(f"OK ({size_mb:.1f} MB, mean NDVI={avg:.4f})" if avg else "OK")
        created += 1

    # ── Summary ───────────────────────────────────────────────
    print()
    print("=" * 40)
    print(f"  NDVI files created: {created}")
    print(f"  NDVI files skipped: {skipped}")
    print(f"  Total NDVI files: {created + skipped}")

    if mean_ndvi:
        sorted_keys = sorted(mean_ndvi.keys())
        oldest_key = sorted_keys[0]
        newest_key = sorted_keys[-1]
        oldest_val = mean_ndvi[oldest_key]
        newest_val = mean_ndvi[newest_key]
        diff = newest_val - oldest_val

        print()
        print(f"  Oldest scene ({oldest_key[0]}-{oldest_key[1]:02d}): "
              f"mean NDVI = {oldest_val:.4f}")
        print(f"  Newest scene ({newest_key[0]}-{newest_key[1]:02d}): "
              f"mean NDVI = {newest_val:.4f}")
        print(f"  Difference: {diff:+.4f}")

        if diff > 0:
            print("  Trend: POSITIVE — suggests greening over the period.")
        elif diff < 0:
            print("  Trend: NEGATIVE — suggests browning or land-use change.")
        else:
            print("  Trend: NEUTRAL — no detectable change.")

    print("=" * 40)


if __name__ == "__main__":
    main()

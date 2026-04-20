"""
Phase 5 — Annual NDVI (city-agnostic)
======================================
Computes NDVI rasters for the two annual scenes of a given city
(baseline and current years). Writes single-band float32 GeoTIFFs
under city.ndvi_dir.

Band order in source GeoTIFF:
    1=B02 blue, 2=B03 green, 3=B04 red, 4=B08 NIR

Usage:
    python src/phase5_ndvi_annual.py --city riyadh
    python src/phase5_ndvi_annual.py --city jeddah
"""

import argparse
import os

import numpy as np
import rasterio

from city_config import add_city_arg, load_city


def compute_ndvi(src_path, dst_path):
    with rasterio.open(src_path) as src:
        red = src.read(3).astype(np.float32)
        nir = src.read(4).astype(np.float32)
        profile = src.profile.copy()

    nodata_mask = (red == 0) & (nir == 0)
    ndvi = (nir - red) / (nir + red + 1e-10)
    ndvi_nodata = -9999.0
    ndvi[nodata_mask] = ndvi_nodata

    profile.update(
        count=1, dtype="float32", nodata=ndvi_nodata,
        compress="deflate", predictor=3,
        tiled=True, blockxsize=256, blockysize=256,
    )
    os.makedirs(os.path.dirname(dst_path), exist_ok=True)
    with rasterio.open(dst_path, "w", **profile) as dst:
        dst.write(ndvi, 1)

    valid = ndvi[~nodata_mask]
    return float(np.mean(valid)) if valid.size else None


def main():
    parser = argparse.ArgumentParser()
    add_city_arg(parser)
    args = parser.parse_args()
    city = load_city(args.city)

    print(f"Phase 5 — Annual NDVI for {city.display_name}")
    print("=" * 50)
    os.makedirs(city.ndvi_dir, exist_ok=True)

    for year, month in [
        (city.baseline_year, city.baseline_month),
        (city.current_year, city.current_month),
    ]:
        src = os.path.join(city.monthly_dir, f"{year}_{month:02d}.tif")
        dst = os.path.join(city.ndvi_dir, f"{year}_{month:02d}.tif")
        if not os.path.exists(src):
            print(f"  ERROR: missing source scene {src}")
            return
        print(f"  {year}-{month:02d} → {dst}", end=" … ", flush=True)
        mean = compute_ndvi(src, dst)
        print(f"OK (mean NDVI={mean:.4f})" if mean is not None else "OK")

    print("=" * 50)


if __name__ == "__main__":
    main()

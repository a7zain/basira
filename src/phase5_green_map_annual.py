"""
Phase 5 — Annual Green Map (city-agnostic)
===========================================
Classifies pixels using two annual NDVI rasters (baseline + current):
    0 = other
    1 = stable_green  (both years NDVI > threshold)
    2 = new_green     (baseline <= threshold, current > threshold)
    3 = lost_green    (baseline > threshold, current <= threshold)

Writes the classified GeoTIFF and a WGS84 RGBA PNG + bounds JSON
under city.web_dir. Also writes latest_rgb.png + bounds from the
current-year scene.

Usage:
    python src/phase5_green_map_annual.py --city riyadh
    python src/phase5_green_map_annual.py --city jeddah
"""

import argparse
import json
import os
import shutil

import numpy as np
import rasterio
from rasterio.warp import calculate_default_transform, reproject, Resampling

from city_config import add_city_arg, load_city

DST_CRS = "EPSG:4326"


def load_ndvi(path):
    with rasterio.open(path) as src:
        data = src.read(1)
        nodata = src.nodata if src.nodata is not None else -9999.0
        profile = src.profile.copy()
    return data, nodata, profile


def reproject_band(src_path, band_index=1, resampling=Resampling.nearest):
    """Return (array, bounds_dict) reprojected to WGS84."""
    with rasterio.open(src_path) as src:
        transform, width, height = calculate_default_transform(
            src.crs, DST_CRS, src.width, src.height, *src.bounds,
        )
        out = np.zeros((height, width), dtype=src.dtypes[band_index - 1])
        reproject(
            source=rasterio.band(src, band_index),
            destination=out,
            src_transform=src.transform,
            src_crs=src.crs,
            dst_transform=transform,
            dst_crs=DST_CRS,
            resampling=resampling,
        )
    west = transform.c
    north = transform.f
    east = west + transform.a * width
    south = north + transform.e * height
    bounds = {
        "north": max(north, south),
        "south": min(north, south),
        "east": max(east, west),
        "west": min(east, west),
    }
    return out, bounds


def reproject_multi(src_path):
    """Reproject all bands to WGS84. Returns (data[B,H,W], bounds)."""
    with rasterio.open(src_path) as src:
        transform, width, height = calculate_default_transform(
            src.crs, DST_CRS, src.width, src.height, *src.bounds,
        )
        data = np.zeros((src.count, height, width), dtype=src.dtypes[0])
        for b in range(1, src.count + 1):
            reproject(
                source=rasterio.band(src, b),
                destination=data[b - 1],
                src_transform=src.transform,
                src_crs=src.crs,
                dst_transform=transform,
                dst_crs=DST_CRS,
                resampling=Resampling.bilinear,
            )
    west = transform.c
    north = transform.f
    east = west + transform.a * width
    south = north + transform.e * height
    bounds = {
        "north": max(north, south),
        "south": min(north, south),
        "east": max(east, west),
        "west": min(east, west),
    }
    return data, bounds


def build_rois_geojson(city):
    features = []
    for roi in city.rois:
        features.append({
            "type": "Feature",
            "properties": {
                "name": roi["name"],
                "description": roi.get("description", ""),
            },
            "geometry": {
                "type": "Polygon",
                "coordinates": [[
                    [roi["lon_min"], roi["lat_min"]],
                    [roi["lon_max"], roi["lat_min"]],
                    [roi["lon_max"], roi["lat_max"]],
                    [roi["lon_min"], roi["lat_max"]],
                    [roi["lon_min"], roi["lat_min"]],
                ]],
            },
        })
    return {"type": "FeatureCollection", "features": features}


def main():
    parser = argparse.ArgumentParser()
    add_city_arg(parser)
    args = parser.parse_args()
    city = load_city(args.city)

    print(f"Phase 5 — Annual Green Map for {city.display_name}")
    print("=" * 50)

    threshold = float(city.green_map_params.get("ndvi_veg_threshold", 0.20))
    baseline_path = os.path.join(
        city.ndvi_dir, f"{city.baseline_year}_{city.baseline_month:02d}.tif",
    )
    current_path = os.path.join(
        city.ndvi_dir, f"{city.current_year}_{city.current_month:02d}.tif",
    )

    if not (os.path.exists(baseline_path) and os.path.exists(current_path)):
        print(f"  ERROR: NDVI rasters missing; run phase5_ndvi_annual.py first")
        return

    ndvi_base, nodata_b, profile = load_ndvi(baseline_path)
    ndvi_curr, nodata_c, _ = load_ndvi(current_path)
    valid = (ndvi_base != nodata_b) & (ndvi_curr != nodata_c)

    green_map = np.zeros(ndvi_base.shape, dtype=np.uint8)
    veg_base = valid & (ndvi_base > threshold)
    veg_curr = valid & (ndvi_curr > threshold)

    stable = veg_base & veg_curr
    new = (~veg_base) & veg_curr & valid
    lost = veg_base & (~veg_curr) & valid

    green_map[stable] = 1
    green_map[new] = 2
    green_map[lost] = 3

    # ── Save UTM GeoTIFF ────────────────────────────────────
    os.makedirs(city.web_dir, exist_ok=True)
    outputs_tif = os.path.join(city.web_dir, "green_map_utm.tif")
    out_profile = profile.copy()
    out_profile.update(count=1, dtype="uint8", nodata=0, compress="deflate")
    out_profile.pop("predictor", None)
    with rasterio.open(outputs_tif, "w", **out_profile) as dst:
        dst.write(green_map, 1)

    # ── Reproject to WGS84 for web overlay ──────────────────
    classes_wgs, gm_bounds = reproject_band(outputs_tif, band_index=1)
    h, w = classes_wgs.shape
    rgba = np.zeros((h, w, 4), dtype=np.uint8)
    rgba[classes_wgs == 1] = [0, 128, 0, 200]
    rgba[classes_wgs == 2] = [50, 255, 0, 220]
    rgba[classes_wgs == 3] = [255, 25, 25, 220]

    from PIL import Image
    gm_png = os.path.join(city.web_dir, "green_map.png")
    Image.fromarray(rgba, "RGBA").save(gm_png)
    with open(os.path.join(city.web_dir, "green_map_bounds.json"), "w") as f:
        json.dump(gm_bounds, f, indent=2)
    print(f"  green_map.png: {os.path.getsize(gm_png)/1024:.1f} KB")

    # ── Latest RGB PNG ──────────────────────────────────────
    current_scene = os.path.join(
        city.monthly_dir, f"{city.current_year}_{city.current_month:02d}.tif",
    )
    data, rgb_bounds = reproject_multi(current_scene)
    # Bands: 1=B02 blue, 2=B03 green, 3=B04 red, 4=B08 NIR
    red = data[2].astype(np.float32)
    green = data[1].astype(np.float32)
    blue = data[0].astype(np.float32)
    rgb = np.stack([red, green, blue], axis=-1)
    for b in range(3):
        band = rgb[:, :, b]
        v = band[band > 0]
        if v.size == 0:
            continue
        lo, hi = np.percentile(v, 2), np.percentile(v, 98)
        if hi > lo:
            rgb[:, :, b] = np.clip((band - lo) / (hi - lo), 0, 1)
        else:
            rgb[:, :, b] = 0
    rgb_u8 = (np.clip(rgb, 0, 1) * 255).astype(np.uint8)
    rgb_png = os.path.join(city.web_dir, "latest_rgb.png")
    Image.fromarray(rgb_u8, "RGB").save(rgb_png, optimize=True)
    with open(os.path.join(city.web_dir, "latest_rgb_bounds.json"), "w") as f:
        json.dump(rgb_bounds, f, indent=2)
    print(f"  latest_rgb.png: {os.path.getsize(rgb_png)/1024:.1f} KB")

    # ── ROIs GeoJSON ─────────────────────────────────────────
    rois = build_rois_geojson(city)
    roi_path = os.path.join(city.web_dir, "rois.geojson")
    with open(roi_path, "w") as f:
        json.dump(rois, f, indent=2)
    print(f"  rois.geojson: {len(city.rois)} ROIs")

    # ── Stats ────────────────────────────────────────────────
    px_area_km2 = (city.resolution_m ** 2) / 1e6
    n_stable = int(np.sum(green_map == 1))
    n_new = int(np.sum(green_map == 2))
    n_lost = int(np.sum(green_map == 3))
    print()
    print(f"  Stable green: {n_stable:>8,} px  ({n_stable * px_area_km2:.2f} km²)")
    print(f"  New green:    {n_new:>8,} px  ({n_new * px_area_km2:.2f} km²)")
    print(f"  Lost green:   {n_lost:>8,} px  ({n_lost * px_area_km2:.2f} km²)")
    print("=" * 50)


if __name__ == "__main__":
    main()

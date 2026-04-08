"""
Phase 4 — Web-Ready Export
============================
Produces files the existing Leaflet web app can ingest, without
modifying any existing webapp files.

Outputs (all under webapp/data/phase4/):
    green_map.png           — transparent RGBA overlay (WGS84)
    green_map_bounds.json   — bounding box for L.imageOverlay
    latest_rgb.png          — most recent full-coverage RGB (WGS84)
    latest_rgb_bounds.json  — bounding box
    ndvi_timeseries.json    — per-ROI time series (NaN entries skipped)
    rois.geojson            — ROI polygons (copied, already WGS84)

Usage:
    python src/phase4_export_web.py
"""

import csv
import json
import os
import glob
import shutil
from collections import defaultdict

import numpy as np
import rasterio
from rasterio.warp import calculate_default_transform, reproject, Resampling

from utils import RIYADH_BBOX

# ── Paths ───────────────────────────────────────────────────
MONTHLY_DIR = "data/processed/monthly"
OUT_DIR     = "outputs"
WEB_DIR     = "webapp/data/phase4"

GREEN_MAP_TIF = os.path.join(OUT_DIR, "phase4_green_map.tif")
TIMESERIES_CSV = os.path.join(OUT_DIR, "phase4_ndvi_timeseries.csv")
ROIS_GEOJSON = os.path.join(OUT_DIR, "phase4_rois.geojson")

DST_CRS = "EPSG:4326"


def find_basemap_scene(min_size_mb=30):
    """Find the most recent full-coverage scene."""
    pattern = os.path.join(MONTHLY_DIR, "*.tif")
    files = sorted(glob.glob(pattern), reverse=True)
    for f in files:
        if os.path.getsize(f) / 1e6 >= min_size_mb:
            return f
    return max(files, key=os.path.getsize) if files else None


def reproject_to_wgs84(src_path):
    """
    Reproject a raster to EPSG:4326, returning the reprojected data
    and the WGS84 bounds.
    Returns (data_array, bounds_dict, profile).
    data_array shape: (bands, height, width)
    """
    with rasterio.open(src_path) as src:
        transform, width, height = calculate_default_transform(
            src.crs, DST_CRS, src.width, src.height, *src.bounds,
        )
        dst_profile = src.profile.copy()
        dst_profile.update(
            crs=DST_CRS,
            transform=transform,
            width=width,
            height=height,
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
                resampling=Resampling.nearest,
            )

    # Compute WGS84 bounds from the transform
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

    return data, bounds, dst_profile


def export_green_map():
    """Export green map as transparent RGBA PNG in WGS84."""
    print("  Green map...")

    if not os.path.exists(GREEN_MAP_TIF):
        print(f"    SKIP: {GREEN_MAP_TIF} not found")
        return None

    data, bounds, _ = reproject_to_wgs84(GREEN_MAP_TIF)
    classes = data[0]  # single band: 0=other, 1=stable, 2=new, 3=lost

    h, w = classes.shape
    rgba = np.zeros((h, w, 4), dtype=np.uint8)

    # stable green: dark green
    m = classes == 1
    rgba[m] = [0, 128, 0, 200]

    # new green: bright lime
    m = classes == 2
    rgba[m] = [50, 255, 0, 220]

    # lost green: red
    m = classes == 3
    rgba[m] = [255, 25, 25, 220]

    # Everything else: transparent (alpha=0, already default)

    from PIL import Image
    img = Image.fromarray(rgba, "RGBA")
    png_path = os.path.join(WEB_DIR, "green_map.png")
    img.save(png_path)

    bounds_path = os.path.join(WEB_DIR, "green_map_bounds.json")
    with open(bounds_path, "w") as f:
        json.dump(bounds, f, indent=2)

    print(f"    Saved: {png_path} ({os.path.getsize(png_path) / 1024:.0f} KB)")
    print(f"    Saved: {bounds_path}")
    return png_path


def export_latest_rgb():
    """Export the latest full-coverage scene as RGB PNG in WGS84."""
    print("  Latest RGB...")

    scene_path = find_basemap_scene()
    if not scene_path:
        print("    SKIP: No full-coverage scene found")
        return None

    print(f"    Source: {os.path.basename(scene_path)}")

    data, bounds, _ = reproject_to_wgs84(scene_path)
    # Bands: 1=B02(blue), 2=B03(green), 3=B04(red), 4=B08(NIR)
    red   = data[2].astype(np.float32)  # B04
    green = data[1].astype(np.float32)  # B03
    blue  = data[0].astype(np.float32)  # B02

    rgb = np.stack([red, green, blue], axis=-1)

    # Percentile stretch (2nd-98th)
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

    rgb_uint8 = (np.clip(rgb, 0, 1) * 255).astype(np.uint8)

    from PIL import Image
    img = Image.fromarray(rgb_uint8, "RGB")
    png_path = os.path.join(WEB_DIR, "latest_rgb.png")
    img.save(png_path, optimize=True)

    bounds_path = os.path.join(WEB_DIR, "latest_rgb_bounds.json")
    with open(bounds_path, "w") as f:
        json.dump(bounds, f, indent=2)

    print(f"    Saved: {png_path} ({os.path.getsize(png_path) / 1024:.0f} KB)")
    print(f"    Saved: {bounds_path}")
    return png_path


def export_timeseries_json():
    """Export NDVI time series as JSON grouped by ROI."""
    print("  NDVI time series JSON...")

    if not os.path.exists(TIMESERIES_CSV):
        print(f"    SKIP: {TIMESERIES_CSV} not found")
        return None

    with open(TIMESERIES_CSV, newline="") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    # Group by ROI, skip empty entries
    by_roi = defaultdict(list)
    for r in rows:
        if r["mean_ndvi"] == "":
            continue
        entry = {
            "date": r["date"],
            "mean_ndvi": float(r["mean_ndvi"]),
        }
        if r.get("ndvi_anomaly", "") != "":
            entry["anomaly"] = float(r["ndvi_anomaly"])
        by_roi[r["roi_name"]].append(entry)

    output = []
    for roi_name, entries in by_roi.items():
        output.append({
            "roi_name": roi_name,
            "data": entries,
        })

    json_path = os.path.join(WEB_DIR, "ndvi_timeseries.json")
    with open(json_path, "w") as f:
        json.dump(output, f)

    print(f"    Saved: {json_path} ({os.path.getsize(json_path) / 1024:.0f} KB)")
    return json_path


def export_rois_geojson():
    """Copy ROIs GeoJSON to webapp directory."""
    print("  ROIs GeoJSON...")

    if not os.path.exists(ROIS_GEOJSON):
        print(f"    SKIP: {ROIS_GEOJSON} not found")
        return None

    dst_path = os.path.join(WEB_DIR, "rois.geojson")
    shutil.copy2(ROIS_GEOJSON, dst_path)
    print(f"    Copied: {dst_path}")
    return dst_path


def main():
    print("Phase 4 — Web-Ready Export")
    print("=" * 50)

    os.makedirs(WEB_DIR, exist_ok=True)

    files_created = []

    result = export_green_map()
    if result:
        files_created.append(result)
        files_created.append(result.replace(".png", "_bounds.json"))

    result = export_latest_rgb()
    if result:
        files_created.append(result)
        files_created.append(result.replace(".png", "_bounds.json"))

    result = export_timeseries_json()
    if result:
        files_created.append(result)

    result = export_rois_geojson()
    if result:
        files_created.append(result)

    # ── Summary ───────────────────────────────────────────────
    print()
    print("  Files created:")
    total_size = 0
    for fp in sorted(files_created):
        sz = os.path.getsize(fp)
        total_size += sz
        print(f"    {fp:50s}  {sz / 1024:>8.1f} KB")
    print(f"    {'TOTAL':50s}  {total_size / 1024:>8.1f} KB")
    print()
    print(f"  Verify: ls webapp/data/phase4/  "
          f"(expect {len(files_created)} files)")
    print("=" * 50)


if __name__ == "__main__":
    main()

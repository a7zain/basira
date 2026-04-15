"""
Phase 4.7 — Export Pixel Classification as Web-Ready PNG
=========================================================
Reads the K-means classified raster (outputs/phase4_pixel_classes.tif),
maps clusters to RGBA colors, reprojects to WGS84, and saves a
transparent overlay PNG for the Leaflet web app.

Outputs (under webapp/data/phase4/):
    pixel_classes.png          — RGBA overlay (WGS84)
    pixel_classes_bounds.json  — bounding box for L.imageOverlay

Usage:
    python src/phase4_export_pixel_classes.py
"""

import json
import os
import sys

import numpy as np
from PIL import Image

sys.path.insert(0, os.path.join(os.path.dirname(__file__)))
from phase4_export_web import reproject_to_wgs84

# ── Paths ───────────────────────────────────────────────────
SRC_TIF = "outputs/phase4_pixel_classes.tif"
WEB_DIR = "webapp/data/phase4"

# ── Cluster color map (id -> RGBA) ──────────────────────────
COLOR_MAP = {
    0: (0, 0, 0, 0),              # nodata — transparent
    1: (10, 110, 61, 200),         # established vegetation — dark green
    2: (230, 210, 168, 0),         # stable desert — fully transparent
    3: (138, 138, 138, 180),       # stable built-up — grey
    4: (158, 201, 119, 200),       # sparse/suburban green — light green
    5: (198, 40, 40, 230),         # vegetation loss — red
}

LABEL_MAP = {
    0: "nodata",
    1: "Established vegetation",
    2: "Stable desert",
    3: "Stable built-up",
    4: "Sparse / suburban green",
    5: "Vegetation loss",
}


def main():
    print("Phase 4.7 — Export Pixel Classification PNG")
    print("=" * 50)

    if not os.path.exists(SRC_TIF):
        print(f"  ERROR: {SRC_TIF} not found. Run phase4_pixel_classify.py first.")
        return

    # ── Reproject to WGS84 ────────────────────────────────
    print("  Reprojecting to EPSG:4326...")
    data, bounds, _ = reproject_to_wgs84(SRC_TIF)
    classes = data[0]  # single band, uint8 values 0-5

    h, w = classes.shape
    print(f"  Reprojected size: {h} x {w}")

    # ── Map to RGBA ───────────────────────────────────────
    rgba = np.zeros((h, w, 4), dtype=np.uint8)
    for cid, color in COLOR_MAP.items():
        m = classes == cid
        rgba[m] = color

    # ── Save PNG ──────────────────────────────────────────
    os.makedirs(WEB_DIR, exist_ok=True)
    img = Image.fromarray(rgba, "RGBA")
    png_path = os.path.join(WEB_DIR, "pixel_classes.png")
    img.save(png_path, optimize=True)
    print(f"  Saved: {png_path} ({os.path.getsize(png_path) / 1024:.0f} KB)")

    bounds_path = os.path.join(WEB_DIR, "pixel_classes_bounds.json")
    with open(bounds_path, "w") as f:
        json.dump(bounds, f, indent=2)
    print(f"  Saved: {bounds_path}")

    # ── Per-class pixel counts (sanity check) ─────────────
    print(f"\n  Per-class pixel counts in final PNG:")
    total_valid = 0
    for cid in sorted(COLOR_MAP.keys()):
        count = int((classes == cid).sum())
        label = LABEL_MAP.get(cid, f"class {cid}")
        pct = 100 * count / classes.size
        print(f"    {cid} ({label:30s}): {count:>10,}  ({pct:5.1f}%)")
        if cid > 0:
            total_valid += count
    print(f"    {'':33s}  {total_valid:>10,} valid total")

    print(f"\n  Bounds: {bounds}")
    print("=" * 50)


if __name__ == "__main__":
    main()

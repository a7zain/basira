"""
Phase 4 — Region of Interest (ROI) Definitions
================================================
Defines 4 analysis ROIs for the Riyadh AOI, saves them as GeoJSON,
computes their pixel-space windows in the UTM raster grid, and
renders a visual overlay on a recent full-coverage scene.

Usage:
    python src/phase4_rois.py

Outputs:
    outputs/phase4_rois.geojson      — WGS84 FeatureCollection
    outputs/phase4_rois_pixel.json   — pixel windows in raster space
    outputs/phase4_rois_overlay.png  — visual sanity check
"""

import json
import os
import glob
import re

import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import rasterio
from pyproj import Transformer

from utils import TARGET_CRS

# ── Paths ───────────────────────────────────────────────────
MONTHLY_DIR = "data/processed/monthly"
OUT_DIR     = "outputs"

# ── ROI Definitions (WGS84 lat/lon) ─────────────────────────
ROIS = [
    {
        "name": "wadi_hanifa",
        "description": "Wadi Hanifa corridor — narrow NW-SE greenbelt, "
                       "known greening and rehabilitation area.",
        "lat_min": 24.62,
        "lat_max": 24.78,
        "lon_min": 46.58,
        "lon_max": 46.65,
    },
    {
        "name": "king_salman_park",
        "description": "King Salman Park / Royal Arts Complex — major "
                       "construction zone on the NW edge of the AOI.",
        "lat_min": 24.80,
        "lat_max": 24.85,
        "lon_min": 46.55,
        "lon_max": 46.62,
    },
    {
        "name": "northern_expansion",
        "description": "Northern suburban expansion — new grading and "
                       "infrastructure development north of central Riyadh.",
        "lat_min": 24.80,
        "lat_max": 24.85,
        "lon_min": 46.65,
        "lon_max": 46.75,
    },
    {
        "name": "central_urban",
        "description": "Central urban core — established dense city, "
                       "expected to be stable (control baseline).",
        "lat_min": 24.66,
        "lat_max": 24.71,
        "lon_min": 46.68,
        "lon_max": 46.74,
    },
]

# ── Colors for overlays ─────────────────────────────────────
ROI_COLORS = {
    "wadi_hanifa":        "#00ff88",
    "king_salman_park":   "#ff6644",
    "northern_expansion": "#44aaff",
    "central_urban":      "#ffdd44",
}


def build_geojson(rois):
    """Build a GeoJSON FeatureCollection from the ROI definitions."""
    features = []
    for roi in rois:
        lon_min, lat_min = roi["lon_min"], roi["lat_min"]
        lon_max, lat_max = roi["lon_max"], roi["lat_max"]
        feature = {
            "type": "Feature",
            "properties": {
                "name": roi["name"],
                "description": roi["description"],
            },
            "geometry": {
                "type": "Polygon",
                "coordinates": [[
                    [lon_min, lat_min],
                    [lon_max, lat_min],
                    [lon_max, lat_max],
                    [lon_min, lat_max],
                    [lon_min, lat_min],
                ]],
            },
        }
        features.append(feature)

    return {
        "type": "FeatureCollection",
        "features": features,
    }


def compute_pixel_windows(rois, raster_path):
    """
    Reproject each ROI from WGS84 to the raster CRS, then compute
    the pixel row/col window within the raster grid.

    Returns a dict: { roi_name: { row_start, row_stop, col_start, col_stop } }
    """
    transformer = Transformer.from_crs("EPSG:4326", TARGET_CRS, always_xy=True)

    with rasterio.open(raster_path) as src:
        transform = src.transform
        height, width = src.shape

    windows = {}
    for roi in rois:
        # Reproject corners to UTM
        x_min, y_min = transformer.transform(roi["lon_min"], roi["lat_min"])
        x_max, y_max = transformer.transform(roi["lon_max"], roi["lat_max"])

        # Convert UTM coords to pixel coords
        # rasterio transform: (x, y) -> (col, row)
        col_min, row_max = ~transform * (x_min, y_min)  # y_min -> row_max
        col_max, row_min = ~transform * (x_max, y_max)  # y_max -> row_min

        # Clamp to raster bounds
        row_start = max(0, int(np.floor(row_min)))
        row_stop  = min(height, int(np.ceil(row_max)))
        col_start = max(0, int(np.floor(col_min)))
        col_stop  = min(width, int(np.ceil(col_max)))

        windows[roi["name"]] = {
            "row_start": row_start,
            "row_stop": row_stop,
            "col_start": col_start,
            "col_stop": col_stop,
            "utm_bounds": {
                "x_min": x_min, "y_min": y_min,
                "x_max": x_max, "y_max": y_max,
            },
        }

    return windows


def find_basemap_scene(min_size_mb=30):
    """Find the most recent scene with file size >= min_size_mb."""
    pattern = os.path.join(MONTHLY_DIR, "*.tif")
    files = sorted(glob.glob(pattern), reverse=True)  # newest first
    for f in files:
        size_mb = os.path.getsize(f) / 1e6
        if size_mb >= min_size_mb:
            return f
    # Fallback: largest file
    return max(files, key=os.path.getsize) if files else None


def render_overlay(raster_path, windows, rois):
    """Render RGB basemap with ROI rectangles overlaid."""
    with rasterio.open(raster_path) as src:
        red   = src.read(3).astype(np.float32)  # B04
        green = src.read(2).astype(np.float32)  # B03
        blue  = src.read(1).astype(np.float32)  # B02

    rgb = np.stack([red, green, blue], axis=-1)

    # Percentile stretch for visibility
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

    # Plot
    fig, ax = plt.subplots(1, 1, figsize=(12, 10))
    fig.patch.set_facecolor("white")
    ax.imshow(rgb, aspect="equal")

    # Draw ROI rectangles
    legend_handles = []
    for roi in rois:
        name = roi["name"]
        w = windows[name]
        color = ROI_COLORS.get(name, "#ffffff")

        rect = mpatches.Rectangle(
            (w["col_start"], w["row_start"]),
            w["col_stop"] - w["col_start"],
            w["row_stop"] - w["row_start"],
            linewidth=2, edgecolor=color, facecolor="none",
            linestyle="-",
        )
        ax.add_patch(rect)

        # Label inside the rectangle
        cx = (w["col_start"] + w["col_stop"]) / 2
        cy = w["row_start"] + 15
        ax.text(cx, cy, name.replace("_", " ").title(),
                fontsize=7, color=color, fontweight="bold",
                ha="center", va="top",
                bbox=dict(boxstyle="round,pad=0.2", facecolor="black",
                          alpha=0.6, edgecolor="none"))

        legend_handles.append(
            mpatches.Patch(facecolor="none", edgecolor=color,
                           linewidth=2, label=name)
        )

    ax.legend(handles=legend_handles, loc="lower right", fontsize=8,
              framealpha=0.8)

    # Extract date from filename for title
    basename = os.path.basename(raster_path).replace(".tif", "")
    ax.set_title(f"Riyadh AOI — ROI Overlay on {basename}\n"
                 f"Sentinel-2 RGB (B04/B03/B02)  |  20 m  |  EPSG:32638",
                 fontsize=11, pad=10)
    ax.axis("off")

    out_path = os.path.join(OUT_DIR, "phase4_rois_overlay.png")
    plt.savefig(out_path, dpi=200, bbox_inches="tight", facecolor="white")
    plt.close()
    print(f"  Saved overlay PNG: {out_path}")
    return out_path


def main():
    print("Phase 4 — Region of Interest Definitions")
    print("=" * 40)

    os.makedirs(OUT_DIR, exist_ok=True)

    # ── Save GeoJSON ──────────────────────────────────────────
    geojson = build_geojson(ROIS)
    geojson_path = os.path.join(OUT_DIR, "phase4_rois.geojson")
    with open(geojson_path, "w") as f:
        json.dump(geojson, f, indent=2)
    print(f"  Saved GeoJSON: {geojson_path} ({len(ROIS)} ROIs)")

    # ── Compute pixel windows ─────────────────────────────────
    # Use any scene for the raster grid reference
    ref_scene = find_basemap_scene()
    if not ref_scene:
        print("ERROR: No scenes found in data/processed/monthly/")
        return

    windows = compute_pixel_windows(ROIS, ref_scene)

    pixel_path = os.path.join(OUT_DIR, "phase4_rois_pixel.json")
    with open(pixel_path, "w") as f:
        json.dump(windows, f, indent=2)
    print(f"  Saved pixel windows: {pixel_path}")

    print()
    for roi in ROIS:
        name = roi["name"]
        w = windows[name]
        rows = w["row_stop"] - w["row_start"]
        cols = w["col_stop"] - w["col_start"]
        print(f"  {name:>25s}: rows [{w['row_start']}:{w['row_stop']}] "
              f"cols [{w['col_start']}:{w['col_stop']}] "
              f"= {cols}x{rows} px "
              f"({cols * 20 / 1000:.1f} x {rows * 20 / 1000:.1f} km)")
    print()

    # ── Render overlay ────────────────────────────────────────
    print(f"  Basemap scene: {os.path.basename(ref_scene)} "
          f"({os.path.getsize(ref_scene) / 1e6:.1f} MB)")
    render_overlay(ref_scene, windows, ROIS)

    print()
    print("Done.")
    print("=" * 40)


if __name__ == "__main__":
    main()

"""
Phase 1 — AOI preview with polygon overlay
===========================================
For a named primary Phase 1 AOI, render the most recent downloaded month
as natural-color RGB with the AOI polygon outlined in yellow and any
sub-region polygons in cyan.

Usage:
    python src/phase1_quicklook.py --aoi <name>
"""

import argparse
import glob
import os
import re

import numpy as np
import matplotlib.pyplot as plt
import rasterio
from pyproj import Transformer

from phase1_aois import get_aoi, list_primary_aois, list_subregions, AOIS

DATA_ROOT = "data/phase1"
OUT_DIR = "outputs/phase1"
TARGET_CRS = "EPSG:32638"


def latest_month_tif(aoi_key):
    files = sorted(glob.glob(os.path.join(DATA_ROOT, aoi_key, "*.tif")))
    if not files:
        return None, None
    path = files[-1]
    m = re.search(r"(\d{4})-(\d{2})\.tif$", path)
    label = f"{m.group(1)}-{m.group(2)}" if m else os.path.basename(path)
    return path, label


def load_rgb(path):
    with rasterio.open(path) as src:
        red = src.read(3).astype(np.float32)
        green = src.read(2).astype(np.float32)
        blue = src.read(1).astype(np.float32)
        bounds = src.bounds
    rgb = np.stack([red, green, blue], axis=-1)
    for b in range(3):
        band = rgb[:, :, b]
        valid = band[band > 0]
        if valid.size == 0:
            continue
        lo, hi = np.percentile(valid, 2), np.percentile(valid, 98)
        if hi > lo:
            rgb[:, :, b] = np.clip((band - lo) / (hi - lo), 0, 1)
        else:
            rgb[:, :, b] = 0
    return rgb, bounds


def polygon_to_utm_xy(polygon_lonlat):
    t = Transformer.from_crs("EPSG:4326", TARGET_CRS, always_xy=True)
    xs, ys = [], []
    for lon, lat in polygon_lonlat:
        x, y = t.transform(lon, lat)
        xs.append(x); ys.append(y)
    if (xs[0], ys[0]) != (xs[-1], ys[-1]):
        xs.append(xs[0]); ys.append(ys[0])
    return xs, ys


def parse_args():
    p = argparse.ArgumentParser(description="Phase 1 AOI preview PNG")
    p.add_argument("--aoi", required=True, choices=list_primary_aois())
    return p.parse_args()


def main():
    args = parse_args()
    aoi = get_aoi(args.aoi)
    os.makedirs(OUT_DIR, exist_ok=True)

    path, label = latest_month_tif(args.aoi)
    if path is None:
        print(f"ERROR: no .tif found under {DATA_ROOT}/{args.aoi}/")
        return

    print(f"  Using: {path} ({label})")
    rgb, bounds = load_rgb(path)

    fig, ax = plt.subplots(figsize=(8, 8))
    extent = (bounds.left, bounds.right, bounds.bottom, bounds.top)
    ax.imshow(rgb, extent=extent, origin="upper")

    xs, ys = polygon_to_utm_xy(aoi["polygon"])
    ax.plot(xs, ys, color="yellow", linewidth=2.0,
            label=aoi["name"])

    sub_keys = list_subregions(args.aoi)
    for k in sub_keys:
        sx, sy = polygon_to_utm_xy(AOIS[k]["polygon"])
        ax.plot(sx, sy, color="cyan", linewidth=1.2,
                label=AOIS[k]["name"])

    if sub_keys:
        ax.legend(loc="lower right", fontsize=8, framealpha=0.7)

    ax.set_title(
        f"{aoi['name']} — {label}\n"
        f"Sentinel-2 RGB (B04/B03/B02) · 10 m · UTM 38N",
        fontsize=11,
    )
    ax.set_xlabel("UTM Easting (m)")
    ax.set_ylabel("UTM Northing (m)")

    out_path = os.path.join(OUT_DIR, f"{args.aoi}_preview.png")
    plt.tight_layout()
    plt.savefig(out_path, dpi=180, bbox_inches="tight")
    plt.close()
    print(f"  Saved: {out_path}")


if __name__ == "__main__":
    main()

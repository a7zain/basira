"""
Prepare Web App Data
====================
Converts optical GeoTIFFs and change map into web-ready PNG
image overlays for the Leaflet-based web app.

Outputs (all in webapp/data/):
  optical_2020.png, optical_2023.png, optical_2026.png  — RGB overlays
  change_overlay.png  — RGBA change overlay (stable = transparent)
  thumbnails/         — 256x256 crop thumbnails for popup before/after
  bounds.json         — geographic bounds for all overlays

Usage:
    python src/prepare_webapp_data.py
"""

import json
import os
import numpy as np
import rasterio
from PIL import Image

OPTICAL_DIR = "data/optical"
CHANGE_TIF  = "outputs/optical_change_2020_2026.tif"
WEBAPP_DATA = "webapp/data"
THUMB_DIR   = f"{WEBAPP_DATA}/thumbs"

YEARS = ["2020", "2023", "2026"]

# Change class mapping (from optical_change.py sorted output):
# 0 = Stable, 1 = Vegetation change, 2 = New construction, 3 = Land clearing
CHANGE_COLORS = {
    # class: (R, G, B, A)  — medium vivid at ~65% opacity
    0: None,                        # stable → transparent
    1: (244,  67,  54, 165),        # vegetation change → #F44336
    2: ( 76, 175,  80, 165),        # new construction → #4CAF50
    3: ( 33, 150, 243, 165),        # land clearing → #2196F3
    255: None,                      # nodata → transparent
}

# Desert masking: remove false-positive changes in sandy/bright areas
DESERT_MASK_ENABLED = True

CHANGE_LABELS = {
    0: "Stable",
    1: "Vegetation change",
    2: "New construction",
    3: "Land clearing",
    255: "No data",
}

# Thumbnail grid: divide the image into tiles for click popups
THUMB_SIZE = 256  # pixels


def convert_optical(year, bounds):
    """Convert a 3-band uint8 GeoTIFF to PNG with gentle linear stretch."""
    src_path = f"{OPTICAL_DIR}/riyadh_{year}.tif"
    dst_path = f"{WEBAPP_DATA}/optical_{year}.png"

    with rasterio.open(src_path) as src:
        r = src.read(1).astype(np.float32)
        g = src.read(2).astype(np.float32)
        b = src.read(3).astype(np.float32)

    # Gentle per-channel 2nd–98th percentile linear stretch
    channels = []
    for ch in [r, g, b]:
        valid = ch[ch > 0]  # exclude nodata
        if valid.size == 0:
            channels.append(ch.astype(np.uint8))
            continue
        lo = np.percentile(valid, 2)
        hi = np.percentile(valid, 98)
        stretched = np.clip((ch - lo) / (hi - lo) * 255, 0, 255)
        channels.append(stretched.astype(np.uint8))

    img = np.stack(channels, axis=-1)
    pil = Image.fromarray(img, "RGB")
    pil.save(dst_path, optimize=True)
    print(f"  Saved: {dst_path} ({pil.size[0]}x{pil.size[1]})")
    return pil.size


def make_desert_mask():
    """
    Build a boolean mask of desert/sandy areas from the 2020 optical image.
    Pixels matching bright sandy colors are marked True (to be excluded).
    """
    src_path = f"{OPTICAL_DIR}/riyadh_2020.tif"
    with rasterio.open(src_path) as src:
        r = src.read(1).astype(np.float32)
        g = src.read(2).astype(np.float32)
        b = src.read(3).astype(np.float32)

    brightness = (r + g + b) / 3.0
    desert = (r > 180) & ((r - b) > 60) & (r > g) & (brightness > 150)
    print(f"    Desert mask: {desert.sum():,} px ({100*desert.sum()/desert.size:.1f}%) masked")
    return desert


def convert_change_overlay(bounds):
    """Convert the classified change map to an RGBA PNG overlay."""
    dst_path = f"{WEBAPP_DATA}/change_overlay.png"

    with rasterio.open(CHANGE_TIF) as src:
        classes = src.read(1)

    h, w = classes.shape
    rgba = np.zeros((h, w, 4), dtype=np.uint8)

    for cls_val, color in CHANGE_COLORS.items():
        if color is None:
            continue
        mask = classes == cls_val
        rgba[mask] = color

    # Apply desert mask to suppress false positives in sandy areas
    if DESERT_MASK_ENABLED:
        print("  Applying desert mask...")
        desert = make_desert_mask()
        # Resize desert mask if dimensions differ from change map
        if desert.shape != (h, w):
            desert_img = Image.fromarray(desert.astype(np.uint8) * 255, "L")
            desert_img = desert_img.resize((w, h), Image.NEAREST)
            desert = np.array(desert_img) > 127
        before = (rgba[:, :, 3] > 0).sum()
        rgba[desert] = 0  # make desert pixels fully transparent
        after = (rgba[:, :, 3] > 0).sum()
        print(f"    Visible change pixels: {before:,} → {after:,} "
              f"(removed {before - after:,})")

    pil = Image.fromarray(rgba, "RGBA")
    pil.save(dst_path, optimize=True)
    print(f"  Saved: {dst_path} ({w}x{h})")

    # Print stats
    total = classes.size
    for cls_val, label in CHANGE_LABELS.items():
        if cls_val == 0 or cls_val == 255:
            continue
        count = (classes == cls_val).sum()
        print(f"    {label}: {count:,} px ({100*count/total:.1f}%)")


def generate_thumbnails(bounds):
    """
    Generate before/after thumbnail crops for click interaction.
    Divides the image into a grid and saves each cell as a small PNG.
    Also generates a JSON index mapping grid cells to geo coordinates
    and change class.
    """
    os.makedirs(THUMB_DIR, exist_ok=True)

    # Load images
    imgs = {}
    for year in ["2020", "2026"]:
        with rasterio.open(f"{OPTICAL_DIR}/riyadh_{year}.tif") as src:
            imgs[year] = np.moveaxis(src.read(), 0, -1)  # (H, W, 3)
            h, w = src.height, src.width
            transform = src.transform

    # Load change map
    with rasterio.open(CHANGE_TIF) as src:
        change = src.read(1)

    # Grid dimensions
    n_rows = (h + THUMB_SIZE - 1) // THUMB_SIZE
    n_cols = (w + THUMB_SIZE - 1) // THUMB_SIZE

    grid_index = {
        "thumb_size": THUMB_SIZE,
        "n_rows": n_rows,
        "n_cols": n_cols,
        "image_h": h,
        "image_w": w,
        "bounds": bounds,
        "cells": [],
    }

    saved = 0
    for r in range(n_rows):
        for c in range(n_cols):
            y0 = r * THUMB_SIZE
            x0 = c * THUMB_SIZE
            y1 = min(y0 + THUMB_SIZE, h)
            x1 = min(x0 + THUMB_SIZE, w)

            # Check if this cell has any change
            cell_change = change[y0:y1, x0:x1]
            change_mask = (cell_change > 0) & (cell_change < 255)
            n_changed = change_mask.sum()
            cell_total = cell_change.size

            if n_changed < 10:
                continue  # skip mostly-stable cells

            # Dominant change class in this cell
            changed_vals = cell_change[change_mask]
            vals, counts = np.unique(changed_vals, return_counts=True)
            dominant_class = int(vals[counts.argmax()])
            change_pct = 100 * n_changed / cell_total

            # Center coordinates (geo)
            cx_px = (x0 + x1) / 2
            cy_px = (y0 + y1) / 2
            # pixel to geo: transform * (col, row)
            cx_geo = transform.c + cx_px * transform.a
            cy_geo = transform.f + cy_px * transform.e

            # Save thumbnails
            cell_id = f"{r}_{c}"
            for year in ["2020", "2026"]:
                crop = imgs[year][y0:y1, x0:x1]
                pil = Image.fromarray(crop, "RGB")
                pil_resized = pil.resize((THUMB_SIZE, THUMB_SIZE),
                                         Image.LANCZOS)
                pil_resized.save(f"{THUMB_DIR}/{year}_{cell_id}.jpg",
                                 quality=80)
            saved += 1

            grid_index["cells"].append({
                "id": cell_id,
                "row": r, "col": c,
                "lat": round(cy_geo, 5),
                "lng": round(cx_geo, 5),
                "class": dominant_class,
                "label": CHANGE_LABELS.get(dominant_class, "Unknown"),
                "change_pct": round(change_pct, 1),
            })

    # Save grid index
    idx_path = f"{WEBAPP_DATA}/grid_index.json"
    with open(idx_path, "w") as f:
        json.dump(grid_index, f, indent=2)
    print(f"  Saved: {idx_path} ({len(grid_index['cells'])} cells)")
    print(f"  Thumbnails: {saved * 2} images in {THUMB_DIR}/")


def main():
    os.makedirs(WEBAPP_DATA, exist_ok=True)

    # Get bounds from the first optical image
    with rasterio.open(f"{OPTICAL_DIR}/riyadh_2020.tif") as src:
        b = src.bounds
        bounds = {
            "south": b.bottom,
            "north": b.top,
            "west": b.left,
            "east": b.right,
        }

    print("Converting optical imagery to PNG overlays...")
    for year in YEARS:
        convert_optical(year, bounds)

    print("\nConverting change detection overlay...")
    convert_change_overlay(bounds)

    print("\nGenerating click thumbnails...")
    generate_thumbnails(bounds)

    # Save bounds
    bounds_path = f"{WEBAPP_DATA}/bounds.json"
    with open(bounds_path, "w") as f:
        json.dump(bounds, f, indent=2)
    print(f"\n  Saved: {bounds_path}")

    print("\n✓ Web app data preparation complete.")
    print(f"  All files in: {WEBAPP_DATA}/")


if __name__ == "__main__":
    main()

"""
Phase 1 — Per-AOI polygon masks
================================
For each AOI, render a white-inside-polygon / black-outside-polygon PNG
at the SAME pixel dimensions as the timelapse (after NN upscale). The
mask is used by CSS mask-image to clip the timelapse video to the
AOI polygon, letting the per-AOI blurred backdrop show through where
the rectangular video extends past the polygon.

Output: site/assets/<aoi>_mask.png
"""

import os
import sys

import numpy as np
import rasterio
from PIL import Image, ImageDraw

from phase1_aois import get_aoi, list_primary_aois
from phase1_timelapse import (
    list_monthly_tifs, load_rgb_array, polygon_pixel_coords,
    stretch_rgb, upscale_nn, compute_fixed_stretch,
)

OUT_DIR = "site/assets"


def extract(aoi_key):
    scenes = list_monthly_tifs(aoi_key)
    if not scenes:
        print(f"  ERROR: no scenes for {aoi_key}", file=sys.stderr)
        return False

    # Use the first scene to get geographic bounds + native pixel dims.
    # Then mirror the timelapse's stretch+upscale path so dims match exactly.
    ref_path = scenes[0][2]
    rgb, bounds = load_rgb_array(ref_path)
    fixed_lo_hi = compute_fixed_stretch([p for _, _, p in scenes])
    img8 = stretch_rgb(rgb, "stretch", fixed_lo_hi)
    img8, scale = upscale_nn(img8)
    h, w = img8.shape[:2]

    aoi = get_aoi(aoi_key)
    pts = polygon_pixel_coords(aoi["polygon"], bounds, w, h, scale)

    mask = Image.new("L", (w, h), 0)
    draw = ImageDraw.Draw(mask)
    draw.polygon(pts, fill=255)

    out = os.path.join(OUT_DIR, f"{aoi_key}_mask.png")
    mask.save(out, optimize=True)

    arr = np.array(mask)
    inside_pct = 100.0 * (arr > 127).mean()
    print(f"    wrote {out}  {w}x{h}  inside={inside_pct:.1f}%")
    return True


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    ok = 0
    for aoi in list_primary_aois():
        if extract(aoi):
            ok += 1
    print(f"Done: {ok} masks written to {OUT_DIR}/")


if __name__ == "__main__":
    main()

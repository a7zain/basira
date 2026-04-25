"""
Phase 1 — Per-AOI blurred Sentinel-2 backdrops
===============================================
For each AOI, take the wide-context unclipped Sentinel-2 RGB composite
from assets/backdrops/<aoi>_context.jpg (built by phase1_backdrops.py
in a prior session), apply Gaussian blur (radius 18) and brightness 60%
per the §Imagery spec, and write to site/assets/<aoi>_backdrop.png.

Why the context jpg, not the monthly scenes: the monthly GeoTIFFs are
polygon-clipped (zero outside the AOI polygon), so a median-of-scenes
backdrop is black outside the polygon — defeating the §Imagery
composition (which needs real data showing through where the
rectangular video frame extends past the polygon mask).
"""

import os
import sys

from PIL import Image, ImageEnhance, ImageFilter

from phase1_aois import list_primary_aois

CONTEXT_DIR = "assets/backdrops"
OUT_DIR = "site/assets"
BLUR_RADIUS = 18
BRIGHTNESS = 0.60


def extract(aoi_key):
    src = os.path.join(CONTEXT_DIR, f"{aoi_key}_context.jpg")
    if not os.path.exists(src):
        print(f"  ERROR: missing {src}", file=sys.stderr)
        return False

    pil = Image.open(src).convert("RGB")
    print(f"  {aoi_key}: source {pil.width}x{pil.height} from {src}")

    pil = pil.filter(ImageFilter.GaussianBlur(radius=BLUR_RADIUS))
    pil = ImageEnhance.Brightness(pil).enhance(BRIGHTNESS)

    out = os.path.join(OUT_DIR, f"{aoi_key}_backdrop.png")
    pil.save(out, optimize=True)
    print(f"    wrote {out}  {pil.width}x{pil.height}")
    return True


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    ok = 0
    for aoi in list_primary_aois():
        if extract(aoi):
            ok += 1
    print(f"Done: {ok} backdrops written to {OUT_DIR}/")


if __name__ == "__main__":
    main()

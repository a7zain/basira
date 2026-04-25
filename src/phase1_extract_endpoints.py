"""
Phase 1 — Endpoint stills extractor
====================================
For each AOI, render the first month (2020-01) and last month (2026-04) as
PNGs using the SAME pipeline as phase1_timelapse.py: fixed cross-stack
contrast stretch, NN upscale, RGB from B04/B03/B02. No annotations, no
polygon outline. Output: site/assets/<aoi>_<YYYY>_<MM>.png

Usage:
    python src/phase1_extract_endpoints.py [--first 2020-01] [--last 2026-04]
"""

import argparse
import os
import sys

from PIL import Image

from phase1_aois import list_primary_aois
from phase1_timelapse import (
    list_monthly_tifs, load_rgb_array, compute_fixed_stretch,
    stretch_rgb, upscale_nn,
)

OUT_DIR = "site/assets"


def find_scene(scenes, ym):
    y, m = ym.split("-")
    y, m = int(y), int(m)
    for sy, sm, p in scenes:
        if sy == y and sm == m:
            return p
    return None


def extract(aoi_key, first_ym, last_ym):
    scenes = list_monthly_tifs(aoi_key)
    if not scenes:
        print(f"  ERROR: no scenes for {aoi_key}", file=sys.stderr)
        return 0

    print(f"  {aoi_key}: {len(scenes)} scenes, computing fixed stretch...")
    fixed_lo_hi = compute_fixed_stretch([p for _, _, p in scenes])

    out_paths = []
    for ym in (first_ym, last_ym):
        path = find_scene(scenes, ym)
        if not path:
            print(f"  WARN: {aoi_key} missing {ym}", file=sys.stderr)
            continue
        rgb, _ = load_rgb_array(path)
        img8 = stretch_rgb(rgb, "stretch", fixed_lo_hi)
        img8, _ = upscale_nn(img8)
        y, m = ym.split("-")
        out = os.path.join(OUT_DIR, f"{aoi_key}_{y}_{m}.png")
        Image.fromarray(img8, mode="RGB").save(out, optimize=True)
        print(f"    wrote {out}  {img8.shape[1]}x{img8.shape[0]}")
        out_paths.append(out)
    return len(out_paths)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--first", default="2020-01")
    p.add_argument("--last", default="2026-04")
    args = p.parse_args()

    os.makedirs(OUT_DIR, exist_ok=True)
    total = 0
    for aoi in list_primary_aois():
        total += extract(aoi, args.first, args.last)
    print(f"Done: {total} PNGs written to {OUT_DIR}/")


if __name__ == "__main__":
    main()

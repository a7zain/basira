"""
SQ1D — render a proposed king_salman_park bbox thumbnail for visual
review. Proposed bbox is centered on the Wikipedia-published KSP
center (24.719N, 46.724E) at ~4.1 km square (~16.8 km^2, matching the
published 16.6 km^2 park area).

Output: research/dust-honesty/data/sq1d_ksp_bbox_proposal.png
"""
import io
import os
import sys
import zipfile
from pathlib import Path

import ee
import numpy as np
import requests
from dotenv import load_dotenv
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from src.phase1_aois import get_bbox  # noqa: E402

OUT_PATH = ROOT / "research/dust-honesty/figures/calibration/_archive/bbox_proposal_ksp_sq1d.png"

# Wikipedia: 24°43'08"N 46°43'26"E => 24.71889N 46.72389E, 16.6 km^2.
CENTER_LAT = 24.71889
CENTER_LON = 46.72389
TARGET_KM2 = 16.6
SIDE_KM = TARGET_KM2 ** 0.5  # ~4.07 km

# Proposed bbox
import math
half_lat = (SIDE_KM / 2) / 110.57
half_lon = (SIDE_KM / 2) / (111.32 * math.cos(math.radians(CENTER_LAT)))
PROPOSED = (
    CENTER_LON - half_lon,
    CENTER_LAT - half_lat,
    CENTER_LON + half_lon,
    CENTER_LAT + half_lat,
)

# Pick a recent clean date over Riyadh — re-use 2024-12-05 (verified low
# cloud over T38RPN in earlier KSP search)
PICK_DATE = "2024-12-05"


def fetch_rgb(date_str, geom):
    nxt = (np.datetime64(date_str) + np.timedelta64(1, "D")).astype(str)
    coll = (
        ee.ImageCollection("COPERNICUS/S2_HARMONIZED")
        .filterBounds(geom)
        .filterDate(date_str, nxt)
        .select(["B4", "B3", "B2"])
    )
    n = coll.size().getInfo()
    if n == 0:
        raise RuntimeError(f"No L1C scene on {date_str}")
    img = coll.mosaic().clip(geom)
    url = img.getDownloadURL(
        {
            "region": geom,
            "scale": 10,
            "crs": "EPSG:4326",
            "format": "GEO_TIFF",
            "bands": ["B4", "B3", "B2"],
        }
    )
    r = requests.get(url, timeout=180)
    r.raise_for_status()
    content = r.content
    if content[:2] == b"PK":
        zf = zipfile.ZipFile(io.BytesIO(content))
        tif_name = next(n for n in zf.namelist() if n.endswith(".tif"))
        content = zf.read(tif_name)
    try:
        import rasterio
        from rasterio.io import MemoryFile
        with MemoryFile(content) as mem:
            with mem.open() as src:
                arr = src.read()
    except ImportError:
        import tifffile
        arr = tifffile.imread(io.BytesIO(content))
        if arr.ndim == 3 and arr.shape[2] == 3:
            arr = arr.transpose(2, 0, 1)
    return arr.astype(np.float32) / 10000.0


def main():
    load_dotenv(ROOT / ".env")
    ee.Initialize(project=os.environ["GEE_PROJECT"])

    cur = get_bbox("king_salman_park")
    cur_center = ((cur[0] + cur[2]) / 2, (cur[1] + cur[3]) / 2)
    cur_w = (cur[2] - cur[0]) * 111.32 * math.cos(math.radians(cur_center[1]))
    cur_h = (cur[3] - cur[1]) * 110.57
    prop_w = (PROPOSED[2] - PROPOSED[0]) * 111.32 * math.cos(math.radians(CENTER_LAT))
    prop_h = (PROPOSED[3] - PROPOSED[1]) * 110.57

    print("=== Current 'king_salman_park' bbox in src/phase1_aois.py ===")
    print(f"  bbox: {cur}")
    print(f"  center: lon={cur_center[0]:.5f} lat={cur_center[1]:.5f}")
    print(f"  size: {cur_w:.2f} km x {cur_h:.2f} km = {cur_w*cur_h:.2f} km^2")
    print()
    print("=== Wikipedia King Salman Park ===")
    print(f"  center: lon={CENTER_LON} lat={CENTER_LAT}")
    print(f"  area:   {TARGET_KM2} km^2 (=> {SIDE_KM:.2f} km square equivalent)")
    print()
    print("=== Proposed new bbox ===")
    print(f"  bbox: ({PROPOSED[0]:.6f}, {PROPOSED[1]:.6f}, {PROPOSED[2]:.6f}, {PROPOSED[3]:.6f})")
    print(f"  size: {prop_w:.2f} km x {prop_h:.2f} km = {prop_w*prop_h:.2f} km^2")
    dx_km = (CENTER_LON - cur_center[0]) * 111.32 * math.cos(math.radians(CENTER_LAT))
    dy_km = (CENTER_LAT - cur_center[1]) * 110.57
    print(f"  center offset from current: dx={dx_km:+.2f} km, dy={dy_km:+.2f} km")
    print()

    # Render proposed bbox
    geom = ee.Geometry.Rectangle(list(PROPOSED))
    print(f"Fetching {PICK_DATE} L1C TOA RGB over proposed bbox...")
    arr = fetch_rgb(PICK_DATE, geom)
    print(f"  shape: {arr.shape}")

    # Per-AOI 2/98 stretch
    stretches = []
    for ch in range(3):
        v = arr[ch].ravel()
        v = v[np.isfinite(v) & (v > 0)]
        lo = float(np.percentile(v, 2))
        hi = float(np.percentile(v, 98))
        stretches.append((lo, hi))
    print(f"  stretch (R, G, B): {stretches}")

    def stretch(b, lo, hi):
        return np.clip((b - lo) / max(hi - lo, 1e-6), 0, 1)

    rgb = np.dstack(
        [stretch(arr[0], *stretches[0]),
         stretch(arr[1], *stretches[1]),
         stretch(arr[2], *stretches[2])]
    )
    rgb8 = (rgb * 255).astype(np.uint8)
    img = Image.fromarray(rgb8)
    if img.width < 700:
        s = int(np.ceil(700 / img.width))
        img = img.resize((img.width * s, img.height * s), Image.NEAREST)

    draw = ImageDraw.Draw(img)
    line1 = "PROPOSED king_salman_park (new bbox)"
    line2 = (
        f"bbox: ({PROPOSED[0]:.5f}, {PROPOSED[1]:.5f}, "
        f"{PROPOSED[2]:.5f}, {PROPOSED[3]:.5f})"
    )
    line3 = f"date: {PICK_DATE}  L1C TOA RGB"
    try:
        font = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial.ttf", 22)
        font_small = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial.ttf", 16)
    except OSError:
        font = ImageFont.load_default()
        font_small = font

    pad = 6
    lines = [(line1, font), (line2, font_small), (line3, font_small)]
    heights = []
    widths = []
    for txt, f in lines:
        b = draw.textbbox((0, 0), txt, font=f)
        widths.append(b[2] - b[0])
        heights.append(b[3] - b[1])
    box_w = max(widths) + 2 * pad
    box_h = sum(heights) + 4 * pad
    x, y = 10, img.height - box_h - 10
    draw.rectangle([x, y, x + box_w, y + box_h], fill=(0, 0, 0, 200))
    cy = y + pad
    for (txt, f), h in zip(lines, heights):
        draw.text((x + pad, cy), txt, fill=(255, 255, 255), font=f)
        cy += h + pad

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    img.save(OUT_PATH)
    print(f"\nWrote {OUT_PATH}")


if __name__ == "__main__":
    main()

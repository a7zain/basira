"""
SQ1D — render verification thumbnail for the new king_salman_park bbox
loaded directly from src.phase1_aois.get_bbox(). Should look identical
to sq1d_ksp_bbox_proposal.png.
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

OUT_PATH = ROOT / "research/dust-honesty/data/sq1d_ksp_bbox_verified.png"
PICK_DATE = "2024-12-05"


def fetch_rgb(date_str, geom):
    nxt = (np.datetime64(date_str) + np.timedelta64(1, "D")).astype(str)
    coll = (
        ee.ImageCollection("COPERNICUS/S2_HARMONIZED")
        .filterBounds(geom).filterDate(date_str, nxt)
        .select(["B4", "B3", "B2"])
    )
    img = coll.mosaic().clip(geom)
    url = img.getDownloadURL({"region": geom, "scale": 10, "crs": "EPSG:4326",
                               "format": "GEO_TIFF", "bands": ["B4", "B3", "B2"]})
    r = requests.get(url, timeout=180); r.raise_for_status()
    content = r.content
    if content[:2] == b"PK":
        zf = zipfile.ZipFile(io.BytesIO(content))
        tif = next(n for n in zf.namelist() if n.endswith(".tif"))
        content = zf.read(tif)
    try:
        import rasterio
        from rasterio.io import MemoryFile
        with MemoryFile(content) as mem, mem.open() as src:
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

    bbox = get_bbox("king_salman_park")
    print(f"Loaded bbox from phase1_aois.py: {bbox}")
    geom = ee.Geometry.Rectangle(list(bbox))

    arr = fetch_rgb(PICK_DATE, geom)
    print(f"Array shape: {arr.shape}")

    stretches = []
    for ch in range(3):
        v = arr[ch].ravel()
        v = v[np.isfinite(v) & (v > 0)]
        stretches.append((float(np.percentile(v, 2)), float(np.percentile(v, 98))))
    print(f"stretch (R, G, B): {stretches}")

    def stretch(b, lo, hi):
        return np.clip((b - lo) / max(hi - lo, 1e-6), 0, 1)
    rgb = np.dstack([stretch(arr[i], *stretches[i]) for i in range(3)])
    rgb8 = (rgb * 255).astype(np.uint8)
    img = Image.fromarray(rgb8)
    if img.width < 700:
        s = int(np.ceil(700 / img.width))
        img = img.resize((img.width * s, img.height * s), Image.NEAREST)

    draw = ImageDraw.Draw(img)
    line1 = "VERIFIED king_salman_park (new bbox)"
    line2 = (f"bbox: ({bbox[0]:.5f}, {bbox[1]:.5f}, {bbox[2]:.5f}, {bbox[3]:.5f})")
    line3 = f"date: {PICK_DATE}  L1C TOA RGB"
    try:
        font = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial.ttf", 22)
        font_small = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial.ttf", 16)
    except OSError:
        font = ImageFont.load_default(); font_small = font

    pad = 6
    lines = [(line1, font), (line2, font_small), (line3, font_small)]
    widths, heights = [], []
    for txt, f in lines:
        b = draw.textbbox((0, 0), txt, font=f)
        widths.append(b[2] - b[0]); heights.append(b[3] - b[1])
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
    print(f"Wrote {OUT_PATH}")


if __name__ == "__main__":
    main()

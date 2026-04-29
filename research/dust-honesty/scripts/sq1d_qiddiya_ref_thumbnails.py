"""
SQ1D — render quicklook RGB thumbnails for qiddiya_core reference
candidates (L1C TOA, B4/B3/B2) and a 2x2 montage.

Uses GEE getDownloadURL → GeoTIFF → numpy. Per-AOI 2/98 stretch is
derived fresh from the 4-scene set (same convention as
regen_thumbnails.py).

Outputs:
  research/dust-honesty/data/sq1d_qiddiya_ref_thumbnails/<date>.png
  research/dust-honesty/data/sq1d_qiddiya_ref_montage.png
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

OUT_DIR = ROOT / "research/dust-honesty/data/sq1d_qiddiya_ref_thumbnails"
MONTAGE_PATH = ROOT / "research/dust-honesty/data/sq1d_qiddiya_ref_montage.png"
AOI = "qiddiya_core"

CANDIDATES = [
    ("2020-01-31", -0.230, "current visually-labeled pick"),
    ("2021-01-10", -1.166, "UVAI extremum"),
    ("2022-12-11",  0.112, "post-2022 best"),
    ("2024-01-20",  0.310, "post-2024 best, cloud 4.21%"),
]


def fetch_rgb_array(date_str, geom):
    """Pull B4/B3/B2 from L1C scene closest to date over geom; return
    HxWx3 float array of TOA reflectance."""
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
    # If it's a zip, unwrap
    content = r.content
    if content[:2] == b"PK":
        zf = zipfile.ZipFile(io.BytesIO(content))
        tif_name = next(n for n in zf.namelist() if n.endswith(".tif"))
        content = zf.read(tif_name)
    # Parse GeoTIFF with rasterio if available, else PIL/tifffile
    try:
        import rasterio
        from rasterio.io import MemoryFile
        with MemoryFile(content) as mem:
            with mem.open() as src:
                arr = src.read()  # (3, H, W)
    except ImportError:
        import tifffile
        arr = tifffile.imread(io.BytesIO(content))
        if arr.ndim == 3 and arr.shape[2] == 3:
            arr = arr.transpose(2, 0, 1)
    arr = arr.astype(np.float32) / 10000.0  # TOA reflectance
    return arr  # (3, H, W) order R, G, B


def main():
    load_dotenv(ROOT / ".env")
    ee.Initialize(project=os.environ["GEE_PROJECT"])

    bbox = get_bbox(AOI)
    geom = ee.Geometry.Rectangle(list(bbox))

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    arrs = {}
    for date_str, _uvai, _note in CANDIDATES:
        print(f"  fetching {date_str}...")
        arrs[date_str] = fetch_rgb_array(date_str, geom)
        print(f"    shape {arrs[date_str].shape}")

    # Per-AOI 2/98 stretch derived from the 4-scene set
    rgb_lo_hi = []
    for ch in range(3):
        all_vals = np.concatenate(
            [a[ch].ravel()[np.isfinite(a[ch].ravel())] for a in arrs.values()]
        )
        lo = float(np.percentile(all_vals, 2))
        hi = float(np.percentile(all_vals, 98))
        rgb_lo_hi.append((lo, hi))
    print(f"\nDerived stretch (R, G, B): {rgb_lo_hi}")

    def stretch(band, lo, hi):
        v = (band - lo) / max(hi - lo, 1e-6)
        return np.clip(v, 0, 1)

    pngs = {}
    for date_str, uvai, _note in CANDIDATES:
        a = arrs[date_str]
        rgb = np.dstack(
            [
                stretch(a[0], *rgb_lo_hi[0]),
                stretch(a[1], *rgb_lo_hi[1]),
                stretch(a[2], *rgb_lo_hi[2]),
            ]
        )
        rgb8 = (rgb * 255).astype(np.uint8)
        img = Image.fromarray(rgb8)
        # Upscale if narrow
        if img.width < 600:
            scale = int(np.ceil(600 / img.width))
            img = img.resize((img.width * scale, img.height * scale), Image.NEAREST)
        # Label
        draw = ImageDraw.Draw(img)
        label = f"{date_str}  UVAI={uvai:+.3f}"
        try:
            font = ImageFont.truetype(
                "/System/Library/Fonts/Supplemental/Arial.ttf", 22
            )
        except OSError:
            font = ImageFont.load_default()
        # Box behind text
        bbox_txt = draw.textbbox((0, 0), label, font=font)
        tw = bbox_txt[2] - bbox_txt[0]
        th = bbox_txt[3] - bbox_txt[1]
        pad = 6
        x, y = 10, img.height - th - 2 * pad - 10
        draw.rectangle(
            [x, y, x + tw + 2 * pad, y + th + 2 * pad], fill=(0, 0, 0, 180)
        )
        draw.text((x + pad, y + pad), label, fill=(255, 255, 255), font=font)
        out = OUT_DIR / f"{date_str}.png"
        img.save(out)
        pngs[date_str] = img
        print(f"  wrote {out}")

    # 2x2 montage
    order = [c[0] for c in CANDIDATES]
    w = max(pngs[d].width for d in order)
    h = max(pngs[d].height for d in order)
    montage = Image.new("RGB", (w * 2, h * 2), (20, 20, 20))
    for i, d in enumerate(order):
        col = i % 2
        row = i // 2
        im = pngs[d]
        # paste centered
        ox = col * w + (w - im.width) // 2
        oy = row * h + (h - im.height) // 2
        montage.paste(im, (ox, oy))
    montage.save(MONTAGE_PATH)
    print(f"\nWrote montage → {MONTAGE_PATH}")


if __name__ == "__main__":
    main()

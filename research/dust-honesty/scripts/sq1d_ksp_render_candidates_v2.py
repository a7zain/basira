"""
SQ1D — render KSP reference candidate thumbnails on tightened bbox.

Reads sq1d_ksp_reference_candidates.csv. Fetches L1C TOA RGB (B4/B3/B2)
for each candidate via GEE, computes per-AOI 2/98 percentile stretch
across the candidate pool, renders captioned PNGs and a montage.

The derived stretch (R, G, B) is persisted to JSON so the test-scene
renderer can use the identical stretch for visual comparability.

Outputs:
  research/dust-honesty/data/sq1d_ksp_ref_thumbnails/<date>.png
  research/dust-honesty/data/sq1d_ksp_ref_montage.png
  research/dust-honesty/data/sq1d_ksp_stretch.json
"""
import csv
import io
import json
import math
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

CAND_CSV = ROOT / "research/dust-honesty/data/sq1d_ksp_reference_candidates.csv"
OUT_DIR = ROOT / "research/dust-honesty/data/sq1d_ksp_ref_thumbnails"
MONTAGE_PATH = ROOT / "research/dust-honesty/data/sq1d_ksp_ref_montage.png"
STRETCH_JSON = ROOT / "research/dust-honesty/data/sq1d_ksp_stretch.json"
AOI = "king_salman_park"


def fetch_rgb_array(date_str, geom):
    nxt = (np.datetime64(date_str) + np.timedelta64(1, "D")).astype(str)
    coll = (
        ee.ImageCollection("COPERNICUS/S2_HARMONIZED")
        .filterBounds(geom)
        .filterDate(date_str, nxt)
        .select(["B4", "B3", "B2"])
    )
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


def caption(img, text, font):
    draw = ImageDraw.Draw(img)
    bb = draw.textbbox((0, 0), text, font=font)
    tw, th = bb[2] - bb[0], bb[3] - bb[1]
    pad = 6
    x, y = 10, img.height - th - 2 * pad - 10
    draw.rectangle(
        [x, y, x + tw + 2 * pad, y + th + 2 * pad], fill=(0, 0, 0)
    )
    draw.text((x + pad, y + pad), text, fill=(255, 255, 255), font=font)


def main():
    load_dotenv(ROOT / ".env")
    ee.Initialize(project=os.environ["GEE_PROJECT"])

    candidates = list(csv.DictReader(open(CAND_CSV)))
    print(f"Candidates ({len(candidates)}):")
    for c in candidates:
        print(f"  {c['date']}  UVAI={float(c['uvai_mean']):+.4f}  pool {c['pool']} rank {c['rank']}")

    bbox = get_bbox(AOI)
    geom = ee.Geometry.Rectangle(list(bbox))
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    arrs = {}
    for c in candidates:
        d = c["date"]
        print(f"\nfetching {d}...")
        arrs[d] = fetch_rgb_array(d, geom)
        print(f"  shape {arrs[d].shape}")

    rgb_lo_hi = []
    for ch in range(3):
        per_scene = []
        for a in arrs.values():
            v = a[ch].ravel()
            v = v[np.isfinite(v) & (v > 0)]
            if v.size:
                per_scene.append(v)
        all_vals = np.concatenate(per_scene)
        lo = float(np.percentile(all_vals, 2))
        hi = float(np.percentile(all_vals, 98))
        rgb_lo_hi.append((lo, hi))
    print(f"\nDerived per-AOI 2/98 stretch (R, G, B):")
    for ch_name, (lo, hi) in zip("RGB", rgb_lo_hi):
        print(f"  {ch_name}: [{lo:.4f}, {hi:.4f}]")

    STRETCH_JSON.write_text(json.dumps(
        {"R": rgb_lo_hi[0], "G": rgb_lo_hi[1], "B": rgb_lo_hi[2]},
        indent=2,
    ))
    print(f"Wrote stretch → {STRETCH_JSON}")

    def stretch(band, lo, hi):
        v = (band - lo) / max(hi - lo, 1e-6)
        return np.clip(v, 0, 1)

    try:
        font = ImageFont.truetype(
            "/System/Library/Fonts/Supplemental/Arial.ttf", 22
        )
    except OSError:
        font = ImageFont.load_default()

    pngs = {}
    for c in candidates:
        d = c["date"]
        a = arrs[d]
        rgb = np.dstack([stretch(a[i], *rgb_lo_hi[i]) for i in range(3)])
        rgb8 = (rgb * 255).astype(np.uint8)
        img = Image.fromarray(rgb8)
        if img.width < 600:
            scale = int(np.ceil(600 / img.width))
            img = img.resize((img.width * scale, img.height * scale), Image.NEAREST)
        label = (
            f"{d}  UVAI={float(c['uvai_mean']):+.3f}  pool {c['pool']} (rank {c['rank']})"
        )
        caption(img, label, font)
        out = OUT_DIR / f"{d}.png"
        img.save(out)
        pngs[d] = img
        print(f"wrote {out}")

    n = len(candidates)
    w = max(p.width for p in pngs.values())
    h = max(p.height for p in pngs.values())
    cols = math.ceil(math.sqrt(n))
    rows_n = math.ceil(n / cols)
    montage = Image.new("RGB", (w * cols, h * rows_n), (20, 20, 20))
    for i, c in enumerate(candidates):
        col = i % cols
        row = i // cols
        im = pngs[c["date"]]
        ox = col * w + (w - im.width) // 2
        oy = row * h + (h - im.height) // 2
        montage.paste(im, (ox, oy))
    montage.save(MONTAGE_PATH)
    print(f"\nWrote montage → {MONTAGE_PATH}")


if __name__ == "__main__":
    main()

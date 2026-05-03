"""
SQ1D — render quicklook RGB thumbnails for king_salman_park reference
candidates (L1C TOA, B4/B3/B2). Per-AOI 2/98 stretch derived fresh.

Window 4/5 best candidates resolved at runtime from
sq1d_ksp_uvai_all.csv.

Outputs:
  research/dust-honesty/data/sq1d_ksp_ref_thumbnails/<date>.png
  research/dust-honesty/data/sq1d_ksp_ref_montage.png
"""
import csv
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

KSP_CSV = ROOT / "research/dust-honesty/data/calibration/uvai_ksp_sq1d.csv"
OUT_DIR = ROOT / "research/dust-honesty/data/calibration/thumbnails/ksp_ref_sq1d"
MONTAGE_PATH = ROOT / "research/dust-honesty/figures/calibration/montages/ref_ksp_sq1d.png"
AOI = "king_salman_park"

# Pre-known fixed candidates
FIXED = [
    {"date": "2021-01-10", "uvai_mean": -1.4249, "cloud_pct": 0.00,
     "note": "UVAI extremum (full-range best)"},
    {"date": "2023-10-27", "uvai_mean": -0.0797, "cloud_pct": 0.32,
     "note": "current pick, only post-2022 negative"},
]


def best_in_window(rows, start, end):
    sub = [r for r in rows if start <= r["date"] <= end]
    sub.sort(key=lambda r: float(r["uvai_mean"]))
    return sub[0] if sub else None


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


def main():
    load_dotenv(ROOT / ".env")
    ee.Initialize(project=os.environ["GEE_PROJECT"])

    rows = list(csv.DictReader(open(KSP_CSV)))
    w4 = best_in_window(rows, "2024-01-01", "2026-04-30")
    w5 = best_in_window(rows, "2025-01-01", "2026-04-30")

    candidates = list(FIXED)
    candidates.append(
        {
            "date": w4["date"],
            "uvai_mean": float(w4["uvai_mean"]),
            "cloud_pct": float(w4["cloud_pct"]),
            "note": "Window 4 best (2024-2026)",
        }
    )
    if w5["date"] != w4["date"]:
        candidates.append(
            {
                "date": w5["date"],
                "uvai_mean": float(w5["uvai_mean"]),
                "cloud_pct": float(w5["cloud_pct"]),
                "note": "Window 5 best (2025-2026)",
            }
        )
    print("Candidates to render:")
    for c in candidates:
        print(f"  {c['date']}  UVAI={c['uvai_mean']:+.4f}  cloud={c['cloud_pct']:.2f}%  ({c['note']})")

    bbox = get_bbox(AOI)
    geom = ee.Geometry.Rectangle(list(bbox))
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    arrs = {}
    for c in candidates:
        d = c["date"]
        print(f"\nfetching {d}...")
        arrs[d] = fetch_rgb_array(d, geom)
        print(f"  shape {arrs[d].shape}")

    # Per-AOI 2/98 stretch from the candidate set
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
    for c in candidates:
        d = c["date"]
        a = arrs[d]
        rgb = np.dstack(
            [stretch(a[i], *rgb_lo_hi[i]) for i in range(3)]
        )
        rgb8 = (rgb * 255).astype(np.uint8)
        img = Image.fromarray(rgb8)
        if img.width < 600:
            scale = int(np.ceil(600 / img.width))
            img = img.resize((img.width * scale, img.height * scale), Image.NEAREST)
        draw = ImageDraw.Draw(img)
        label = f"{d}  UVAI={c['uvai_mean']:+.3f}  cloud={c['cloud_pct']:.2f}%"
        try:
            font = ImageFont.truetype(
                "/System/Library/Fonts/Supplemental/Arial.ttf", 22
            )
        except OSError:
            font = ImageFont.load_default()
        bb = draw.textbbox((0, 0), label, font=font)
        tw, th = bb[2] - bb[0], bb[3] - bb[1]
        pad = 6
        x, y = 10, img.height - th - 2 * pad - 10
        draw.rectangle(
            [x, y, x + tw + 2 * pad, y + th + 2 * pad], fill=(0, 0, 0, 180)
        )
        draw.text((x + pad, y + pad), label, fill=(255, 255, 255), font=font)
        out = OUT_DIR / f"{d}.png"
        img.save(out)
        pngs[d] = img
        print(f"wrote {out}")

    # Montage: 2x2 if 4 candidates, 1x3 if 3
    n = len(candidates)
    w = max(p.width for p in pngs.values())
    h = max(p.height for p in pngs.values())
    if n == 4:
        cols, rows_n = 2, 2
    else:
        cols, rows_n = n, 1
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

"""
SQ1D — render Qiddiya test thumbnails with VISUALLY-BLIND captions
(date only, no UVAI / no old label / no AOI text). For AI pre-label
step that must receive only visual evidence.

Per-month scene pick: query GEE COPERNICUS/S2_HARMONIZED with cloud<5,
pick lowest CLOUDY_PIXEL_PERCENTAGE (leastCC, matches phase1).

Stretch: hardcoded from CLAUDE.md (SQ1 originals on the unchanged
Qiddiya bbox), persisted to sq1d_qiddiya_stretch.json. After the FIRST
scene renders, prints stretched RGB min/max as a sanity check; aborts
if results look anomalous (all-clipped or empty).

Outputs:
  research/dust-honesty/data/sq1d_qiddiya_stretch.json
  research/dust-honesty/data/sq1d_qiddiya_test_thumbnails/<YYYY-MM>.png
  research/dust-honesty/data/sq1d_qiddiya_test_montage.png
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

LABELS_CSV = ROOT / "research/dust-honesty/data/sq1_manual_labels.csv"
STRETCH_JSON = ROOT / "research/dust-honesty/data/sq1d_qiddiya_stretch.json"
OUT_DIR = ROOT / "research/dust-honesty/data/sq1d_qiddiya_test_thumbnails"
MONTAGE_PATH = ROOT / "research/dust-honesty/data/sq1d_qiddiya_test_montage.png"
AOI = "qiddiya_core"

# SQ1 original Qiddiya stretch (CLAUDE.md):
#   R [0.279, 0.635], G [0.213, 0.520], B [0.136, 0.398]
RGB_LO_HI = [
    (0.279, 0.635),
    (0.213, 0.520),
    (0.136, 0.398),
]


def month_range(ym):
    y, m = (int(x) for x in ym.split("-"))
    start = f"{y:04d}-{m:02d}-01"
    end = f"{y+1:04d}-01-01" if m == 12 else f"{y:04d}-{m+1:02d}-01"
    return start, end


def pick_scene_date(geom, ym):
    start, end = month_range(ym)
    coll = (
        ee.ImageCollection("COPERNICUS/S2_HARMONIZED")
        .filterBounds(geom)
        .filterDate(start, end)
        .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", 5.0))
        .sort("CLOUDY_PIXEL_PERCENTAGE")
    )
    n = coll.size().getInfo()
    if n == 0:
        return None
    first = ee.Image(coll.first())
    return ee.Date(first.get("system:time_start")).format("YYYY-MM-dd").getInfo()


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


def stretch_band(band, lo, hi):
    v = (band - lo) / max(hi - lo, 1e-6)
    return np.clip(v, 0, 1)


def main():
    load_dotenv(ROOT / ".env")
    ee.Initialize(project=os.environ["GEE_PROJECT"])

    STRETCH_JSON.parent.mkdir(parents=True, exist_ok=True)
    STRETCH_JSON.write_text(json.dumps(
        {"R": list(RGB_LO_HI[0]), "G": list(RGB_LO_HI[1]), "B": list(RGB_LO_HI[2])},
        indent=2,
    ))
    print(f"Wrote stretch → {STRETCH_JSON}")
    for ch_name, (lo, hi) in zip("RGB", RGB_LO_HI):
        print(f"  {ch_name}: [{lo:.4f}, {hi:.4f}]")

    months = []
    with open(LABELS_CSV) as f:
        for row in csv.DictReader(f):
            if row["AOI"] == AOI:
                months.append(row["date"])
    months.sort()
    print(f"\nQiddiya test months ({len(months)}): {months}")

    bbox = get_bbox(AOI)
    geom = ee.Geometry.Rectangle(list(bbox))

    scene_dates = {}
    for ym in months:
        d = pick_scene_date(geom, ym)
        if d is None:
            print(f"\nSTOP: no eligible scene for {ym}")
            sys.exit(2)
        scene_dates[ym] = d
        print(f"  {ym} → {d}")

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    try:
        font = ImageFont.truetype(
            "/System/Library/Fonts/Supplemental/Arial.ttf", 22
        )
    except OSError:
        font = ImageFont.load_default()

    pngs = {}
    for idx, ym in enumerate(months):
        d = scene_dates[ym]
        print(f"\nfetching {d} ({ym})...")
        a = fetch_rgb_array(d, geom)
        rgb = np.dstack([stretch_band(a[i], *RGB_LO_HI[i]) for i in range(3)])

        if idx == 0:
            r_min, r_max = float(rgb[..., 0].min()), float(rgb[..., 0].max())
            g_min, g_max = float(rgb[..., 1].min()), float(rgb[..., 1].max())
            b_min, b_max = float(rgb[..., 2].min()), float(rgb[..., 2].max())
            r_mean, g_mean, b_mean = (
                float(rgb[..., i].mean()) for i in range(3)
            )
            print(
                f"\nFirst-scene stretched RGB sanity check ({ym}, {d}):\n"
                f"  R: min={r_min:.3f} max={r_max:.3f} mean={r_mean:.3f}\n"
                f"  G: min={g_min:.3f} max={g_max:.3f} mean={g_mean:.3f}\n"
                f"  B: min={b_min:.3f} max={b_max:.3f} mean={b_mean:.3f}"
            )
            anomaly = []
            if r_max < 0.05 or g_max < 0.05 or b_max < 0.05:
                anomaly.append("max too low (likely all-black)")
            if r_min > 0.95 or g_min > 0.95 or b_min > 0.95:
                anomaly.append("min too high (likely all-clipped white)")
            if r_mean < 0.02 and g_mean < 0.02 and b_mean < 0.02:
                anomaly.append("mean too low across channels")
            if anomaly:
                print(f"\nSTOP: anomalous first-scene output: {anomaly}")
                sys.exit(3)

        rgb8 = (rgb * 255).astype(np.uint8)
        img = Image.fromarray(rgb8)
        if img.width < 600:
            scale = int(np.ceil(600 / img.width))
            img = img.resize((img.width * scale, img.height * scale), Image.NEAREST)
        caption(img, ym, font)
        out = OUT_DIR / f"{ym}.png"
        img.save(out)
        pngs[ym] = img
        print(f"  shape {a.shape} → {out}")

    n = len(months)
    w = max(p.width for p in pngs.values())
    h = max(p.height for p in pngs.values())
    cols = math.ceil(math.sqrt(n))
    rows_n = math.ceil(n / cols)
    montage = Image.new("RGB", (w * cols, h * rows_n), (20, 20, 20))
    for i, ym in enumerate(months):
        col = i % cols
        row = i // cols
        im = pngs[ym]
        ox = col * w + (w - im.width) // 2
        oy = row * h + (h - im.height) // 2
        montage.paste(im, (ox, oy))
    montage.save(MONTAGE_PATH)
    print(f"\nWrote montage → {MONTAGE_PATH}")


if __name__ == "__main__":
    main()

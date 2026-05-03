"""
SQ1D — re-thumbnail the KSP test scenes from sq1_manual_labels.csv on
the tightened bbox.

For each labeled month, picks the lowest cloud_pct scene from
sq1d_ksp_uvai_all.csv (matches the original phase1 leastCC convention),
fetches L1C TOA RGB via GEE, and renders with the SAME per-AOI 2/98
stretch derived from the candidate pool (sq1d_ksp_stretch.json).
Writes captioned PNGs, a montage, and the relabel CSV.

If a labeled month has no eligible UVAI row, STOP and report.

Outputs:
  research/dust-honesty/data/sq1d_ksp_test_thumbnails/<date>.png
  research/dust-honesty/data/sq1d_ksp_test_montage.png
  research/dust-honesty/data/sq1d_ksp_relabel.csv
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

UVAI_CSV = ROOT / "research/dust-honesty/data/calibration/uvai_ksp_sq1d.csv"
LABELS_CSV = ROOT / "research/dust-honesty/data/calibration/manual_labels_sq1.csv"
STRETCH_JSON = ROOT / "research/dust-honesty/data/calibration/stretch_ksp_sq1d.json"
OUT_DIR = ROOT / "research/dust-honesty/data/calibration/thumbnails/ksp_test_sq1d"
MONTAGE_PATH = ROOT / "research/dust-honesty/figures/calibration/montages/test_ksp_sq1d.png"
RELABEL_CSV = ROOT / "research/dust-honesty/data/calibration/relabel_ksp_sq1d.csv"
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

    labels = []
    with open(LABELS_CSV) as f:
        for row in csv.DictReader(f):
            if row["AOI"] == AOI:
                labels.append(row)
    labels.sort(key=lambda r: r["date"])
    print(f"KSP test scenes from labels CSV: {len(labels)}")

    uvai_rows = list(csv.DictReader(open(UVAI_CSV)))
    by_month = {}
    for r in uvai_rows:
        ym = r["date"][:7]
        by_month.setdefault(ym, []).append(r)

    selected = []
    missing = []
    for lab in labels:
        ym = lab["date"]
        cands = by_month.get(ym, [])
        if not cands:
            missing.append(ym)
            continue
        cands_sorted = sorted(cands, key=lambda r: float(r["cloud_pct"]))
        pick = cands_sorted[0]
        selected.append({
            "label_month": ym,
            "scene_date": pick["date"],
            "cloud_pct": float(pick["cloud_pct"]),
            "uvai_mean": float(pick["uvai_mean"]),
            "old_label": lab["label"],
        })

    if missing:
        print(f"\nSTOP: no UVAI rows for KSP labeled months: {missing}")
        sys.exit(2)

    print("\nSelected scene per labeled month:")
    for s in selected:
        print(
            f"  {s['label_month']} → {s['scene_date']}  "
            f"cloud={s['cloud_pct']:.2f}%  UVAI={s['uvai_mean']:+.3f}  "
            f"old={s['old_label']}"
        )

    stretch_data = json.loads(STRETCH_JSON.read_text())
    rgb_lo_hi = [tuple(stretch_data[k]) for k in "RGB"]
    print(f"\nUsing stretch from {STRETCH_JSON.name}:")
    for ch_name, (lo, hi) in zip("RGB", rgb_lo_hi):
        print(f"  {ch_name}: [{lo:.4f}, {hi:.4f}]")

    bbox = get_bbox(AOI)
    geom = ee.Geometry.Rectangle(list(bbox))
    OUT_DIR.mkdir(parents=True, exist_ok=True)

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
    failed = []
    for s in selected:
        d = s["scene_date"]
        print(f"\nfetching {d} ({s['label_month']})...")
        try:
            a = fetch_rgb_array(d, geom)
        except Exception as e:
            failed.append((s["label_month"], d, str(e)))
            continue
        rgb = np.dstack([stretch(a[i], *rgb_lo_hi[i]) for i in range(3)])
        rgb8 = (rgb * 255).astype(np.uint8)
        img = Image.fromarray(rgb8)
        if img.width < 600:
            scale = int(np.ceil(600 / img.width))
            img = img.resize((img.width * scale, img.height * scale), Image.NEAREST)
        label_text = (
            f"{s['label_month']} ({d})  UVAI={s['uvai_mean']:+.3f}  "
            f"old={s['old_label']}"
        )
        caption(img, label_text, font)
        out = OUT_DIR / f"{s['label_month']}.png"
        img.save(out)
        pngs[s["label_month"]] = img
        print(f"  shape {a.shape} → {out}")

    if failed:
        print(f"\nSTOP: {len(failed)} scenes failed to render:")
        for ym, d, err in failed:
            print(f"  {ym} ({d}): {err}")
        sys.exit(3)

    n = len(selected)
    w = max(p.width for p in pngs.values())
    h = max(p.height for p in pngs.values())
    cols = math.ceil(math.sqrt(n))
    rows_n = math.ceil(n / cols)
    montage = Image.new("RGB", (w * cols, h * rows_n), (20, 20, 20))
    for i, s in enumerate(selected):
        col = i % cols
        row = i // cols
        im = pngs[s["label_month"]]
        ox = col * w + (w - im.width) // 2
        oy = row * h + (h - im.height) // 2
        montage.paste(im, (ox, oy))
    montage.save(MONTAGE_PATH)
    print(f"\nWrote montage → {MONTAGE_PATH}")

    with open(RELABEL_CSV, "w", newline="") as f:
        w_csv = csv.DictWriter(
            f,
            fieldnames=[
                "date",
                "sub_aoi",
                "scene_date",
                "uvai_mean",
                "old_label",
                "old_confidence",
                "final_label",
            ],
        )
        w_csv.writeheader()
        for s in selected:
            w_csv.writerow(
                {
                    "date": s["label_month"],
                    "sub_aoi": AOI,
                    "scene_date": s["scene_date"],
                    "uvai_mean": f"{s['uvai_mean']:.4f}",
                    "old_label": s["old_label"],
                    "old_confidence": "",
                    "final_label": "",
                }
            )
    print(f"Wrote relabel CSV → {RELABEL_CSV}  ({len(selected)} rows)")


if __name__ == "__main__":
    main()

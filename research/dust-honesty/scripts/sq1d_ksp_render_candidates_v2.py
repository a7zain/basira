"""
SQ1D — render KSP reference candidate thumbnails on tightened bbox.

Reads sq1d_ksp_reference_candidates.csv. Fetches L1C TOA RGB (B4/B3/B2)
for each candidate via GEE, computes per-AOI 2/98 percentile stretch
across the candidate pool, renders captioned PNGs and a montage.

The derived stretch (R, G, B) is persisted to JSON so the test-scene
renderer can use the identical stretch for visual comparability.

Silent-failure guard (hardened 2026-04-30):
  GEE returns a zero-filled array when an L1C scene matches filterBounds
  at the tile level but the scene's actual data footprint doesn't cover
  the requested geometry (partial-strip acquisition, scan gaps). Each
  fetched array is now validated with `array_has_data()`; failed slots
  are SKIPPED (logged + rendered as a visibly-blank slate panel marked
  "NO DATA") rather than producing a stretchable-looking black thumbnail
  with a caption painted on top.

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

CAND_CSV = ROOT / "research/dust-honesty/data/calibration/candidates_ref_ksp_sq1d.csv"
OUT_DIR = ROOT / "research/dust-honesty/data/calibration/thumbnails/ksp_ref_sq1d"
MONTAGE_PATH = ROOT / "research/dust-honesty/figures/calibration/montages/ref_ksp_sq1d.png"
STRETCH_JSON = ROOT / "research/dust-honesty/data/calibration/stretch_ksp_sq1d.json"
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


# Guard: a "good" array has >= MIN_POS_FRAC positive (non-zero, finite)
# pixels in every band. GEE silently returns all-zero arrays when an L1C
# scene's data footprint doesn't cover the requested geometry.
MIN_POS_FRAC = 0.5


def array_has_data(arr) -> tuple[bool, str]:
    """Return (ok, reason). ok=True iff every band has >= MIN_POS_FRAC
    positive finite pixels."""
    fracs = []
    for b in range(arr.shape[0]):
        v = arr[b]
        ok = np.isfinite(v) & (v > 0)
        fracs.append(float(ok.mean()))
    if min(fracs) < MIN_POS_FRAC:
        return False, f"empty/no-data fetch (per-band positive fractions: {[f'{f:.3f}' for f in fracs]})"
    return True, "ok"


def render_skip_panel(date_str, reason, w, h, font):
    """Visibly-blank slate (mid-grey) with NO-DATA banner; replaces the
    silent-black-with-caption-only failure mode."""
    img = Image.new("RGB", (w, h), (60, 60, 60))
    draw = ImageDraw.Draw(img)
    # diagonal hatch
    for offset in range(-h, w + h, 24):
        draw.line([(offset, 0), (offset + h, h)], fill=(85, 85, 85), width=1)
    # banner
    banner = f"SKIPPED: {date_str}\nNO DATA over AOI"
    bb = draw.multiline_textbbox((0, 0), banner, font=font)
    tw, th = bb[2] - bb[0], bb[3] - bb[1]
    pad = 10
    bx, by = (w - tw) // 2 - pad, (h - th) // 2 - pad
    draw.rectangle([bx, by, bx + tw + 2 * pad, by + th + 2 * pad], fill=(20, 20, 20))
    draw.multiline_text((bx + pad, by + pad), banner, fill=(255, 220, 100), font=font, align="center")
    # secondary footnote with the reason
    foot = f"reason: {reason}"
    draw.text((10, h - 28), foot, fill=(220, 220, 220), font=font)
    return img


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
    skipped = {}  # date -> reason
    for c in candidates:
        d = c["date"]
        print(f"\nfetching {d}...")
        arr = fetch_rgb_array(d, geom)
        print(f"  shape {arr.shape}")
        ok, reason = array_has_data(arr)
        if ok:
            arrs[d] = arr
        else:
            skipped[d] = reason
            print(f"  SKIPPED: {d}: {reason}")

    if not arrs:
        raise RuntimeError("All candidates were skipped — no usable data to derive stretch.")

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

    # Probe one rendered shape to size the skip panels consistently.
    probe = next(iter(arrs.values()))
    probe_w = probe.shape[2]
    probe_h = probe.shape[1]
    if probe_w < 600:
        sc = int(np.ceil(600 / probe_w))
        probe_w *= sc
        probe_h *= sc

    pngs = {}
    for c in candidates:
        d = c["date"]
        out = OUT_DIR / f"{d}.png"
        if d in skipped:
            img = render_skip_panel(d, skipped[d], probe_w, probe_h, font)
            img.save(out)
            pngs[d] = img
            print(f"wrote SKIP panel {out}  ({skipped[d]})")
            continue
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

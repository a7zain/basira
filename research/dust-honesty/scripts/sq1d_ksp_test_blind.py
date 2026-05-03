"""
SQ1D — re-render KSP test thumbnails with VISUALLY-BLIND captions
(date only, no UVAI / no old label / no AOI text). For AI pre-label
step that must receive only visual evidence.

Per-month scene pick: query GEE COPERNICUS/S2_HARMONIZED with cloud<5,
pick lowest CLOUDY_PIXEL_PERCENTAGE (leastCC, matches phase1).

Stretch loaded from sq1d_ksp_stretch.json (committed a5ea00a, derived
on tightened 16.6 km^2 bbox). Not recomputed.

Outputs:
  research/dust-honesty/data/sq1d_ksp_test_thumbnails/<YYYY-MM>.png  (overwrites)
  research/dust-honesty/data/sq1d_ksp_test_montage.png  (overwrites)
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

LABELS_CSV = ROOT / "research/dust-honesty/data/calibration/manual_labels_sq1.csv"
STRETCH_JSON = ROOT / "research/dust-honesty/data/calibration/stretch_ksp_sq1d.json"
OUT_DIR = ROOT / "research/dust-honesty/data/calibration/thumbnails/ksp_test_sq1d"
MONTAGE_PATH = ROOT / "research/dust-honesty/figures/calibration/montages/test_ksp_sq1d.png"
MANIFEST_CSV = ROOT / "research/dust-honesty/data/calibration/manifest_sq1d.csv"
AOI = "king_salman_park"


def load_manifest_lookup():
    """Return {(aoi, month_slot): (system_index, acquisition_date)} from
    sq1d_scene_manifest.csv, or {} if the manifest doesn't exist yet."""
    if not MANIFEST_CSV.exists():
        return {}
    out = {}
    with open(MANIFEST_CSV) as f:
        for r in csv.DictReader(f):
            out[(r["aoi"], r["month_slot"])] = (r["system_index"], r["acquisition_date"])
    return out


def assert_manifest_match(geom, acq_date, expected_sys_idx):
    """Verify that filtering S2_HARMONIZED by `acq_date` over `geom`
    contains the expected system:index. Raises if not, so a manifest
    that points at a rolled-out index fails loud rather than rendering
    the wrong scene silently."""
    nxt = (np.datetime64(acq_date) + np.timedelta64(1, "D")).astype(str)
    coll = (
        ee.ImageCollection("COPERNICUS/S2_HARMONIZED")
        .filterBounds(geom)
        .filterDate(acq_date, nxt)
    )
    ids = coll.aggregate_array("system:index").getInfo()
    if expected_sys_idx not in ids:
        raise RuntimeError(
            f"manifest mismatch: expected system:index {expected_sys_idx} "
            f"on {acq_date}, got {ids}. GEE may have rolled the index — "
            f"investigate before re-rendering."
        )


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


# Guard: a "good" array has >= MIN_POS_FRAC positive (non-zero, finite)
# pixels in every band. GEE silently returns all-zero arrays when an L1C
# scene's data footprint doesn't cover the requested geometry.
# (Helpers ported byte-identical from sq1d_ksp_render_candidates_v2.py @ ec88f93.)
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

    months = []
    with open(LABELS_CSV) as f:
        for row in csv.DictReader(f):
            if row["AOI"] == AOI:
                months.append(row["date"])
    months.sort()
    print(f"KSP test months ({len(months)}): {months}")

    bbox = get_bbox(AOI)
    geom = ee.Geometry.Rectangle(list(bbox))

    manifest = load_manifest_lookup()
    print(f"Manifest entries loaded: {len(manifest)} "
          f"(source: {MANIFEST_CSV.name if MANIFEST_CSV.exists() else 'absent'})")

    # Resolve each month to either a manifest-locked system_index or a
    # deterministic-pick acquisition_date.
    locked = {}        # ym -> (system_index, acquisition_date) from manifest
    scene_dates = {}   # ym -> acquisition_date from deterministic pick (fallback)
    for ym in months:
        m = manifest.get((AOI, ym))
        if m:
            locked[ym] = m
            print(f"  {ym} → manifest {m[0]} (acq {m[1]})")
            continue
        d = pick_scene_date(geom, ym)
        if d is None:
            print(f"\nSTOP: no eligible scene for {ym}")
            sys.exit(2)
        scene_dates[ym] = d
        print(f"  [MANIFEST GAP] no entry for {AOI} {ym}; using deterministic "
              f"pick → {d} — scene NOT locked, will drift on catalog change.")

    stretch_data = json.loads(STRETCH_JSON.read_text())
    rgb_lo_hi = [tuple(stretch_data[k]) for k in "RGB"]
    print(f"\nUsing stretch from {STRETCH_JSON.name}:")
    for ch_name, (lo, hi) in zip("RGB", rgb_lo_hi):
        print(f"  {ch_name}: [{lo:.4f}, {hi:.4f}]")

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
    skipped = {}  # ym -> reason
    probe_w = probe_h = None
    for ym in months:
        if ym in locked:
            sys_idx, acq_date = locked[ym]
            src_label = f"{sys_idx} (manifest-locked, acq {acq_date})"
            print(f"\nfetching {src_label} ({ym})...")
            assert_manifest_match(geom, acq_date, sys_idx)
            a = fetch_rgb_array(acq_date, geom)
        else:
            src_label = scene_dates[ym]
            print(f"\nfetching {src_label} ({ym})...")
            a = fetch_rgb_array(src_label, geom)
        ok, reason = array_has_data(a)
        if not ok:
            skipped[ym] = reason
            print(f"  SKIPPED: {ym} ({src_label}): {reason}")
            continue
        rgb = np.dstack([stretch(a[i], *rgb_lo_hi[i]) for i in range(3)])
        rgb8 = (rgb * 255).astype(np.uint8)
        img = Image.fromarray(rgb8)
        if img.width < 600:
            scale = int(np.ceil(600 / img.width))
            img = img.resize((img.width * scale, img.height * scale), Image.NEAREST)
        caption(img, ym, font)
        out = OUT_DIR / f"{ym}.png"
        img.save(out)
        pngs[ym] = img
        if probe_w is None:
            probe_w, probe_h = img.width, img.height
        print(f"  shape {a.shape} → {out}")

    # Render skip panels for any failed slots, sized to match the rendered ones.
    for ym, reason in skipped.items():
        if probe_w is None:
            # all slots failed — fall back to a reasonable default
            probe_w, probe_h = 900, 822
        img = render_skip_panel(ym, reason, probe_w, probe_h, font)
        out = OUT_DIR / f"{ym}.png"
        img.save(out)
        pngs[ym] = img
        print(f"  wrote SKIP panel {out}")

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

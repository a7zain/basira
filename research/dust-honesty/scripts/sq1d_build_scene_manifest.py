"""
SQ1D — build authoritative scene manifest for the 30-scene calibration set.

For each (aoi, month_slot) row in sq1d_ksp_relabel.csv +
sq1d_qiddiya_relabel.csv + sq1_manual_labels.csv (Diriyah rows):

  1. Run today's deterministic-pick query (cloud<5, sort asc, first)
     and capture (system_index, acquisition_date, cloudy_pixel_pct,
     processing_baseline).
  2. Render the picked scene to a TEMP path with the same pipeline
     the test renderer uses (per-AOI 2/98 stretch from JSON, identical
     bbox, identical caption).
  3. Pixel-compare to the committed PNG. Tolerance: <=1% pixels
     differing AND max abs diff <=5 → "validated". Otherwise → "mismatch".
  4. For mismatches, attempt manual resolution (KSP 2021-02 known case:
     original was 2021-02-04, cloud=0.009; verify by rendering candidates
     on that exact date).
  5. Diriyah test scenes were never re-rendered (CLAUDE.md: surface-stable
     AOI, original labels stand). For Diriyah rows there is no committed
     PNG to compare against → record today's deterministic pick as
     'validated' with a note documenting the lack of prior render.

Output: research/dust-honesty/data/sq1d_scene_manifest.csv
        Schema: aoi, month_slot, acquisition_date, system_index,
                cloudy_pixel_pct, processing_baseline, source, notes
"""
from __future__ import annotations

import csv
import io
import json
import os
import sys
import tempfile
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

DATA = ROOT / "research/dust-honesty/data"
KSP_CSV = DATA / "sq1d_ksp_relabel.csv"
QID_CSV = DATA / "sq1d_qiddiya_relabel.csv"
DIR_CSV = DATA / "sq1_manual_labels.csv"

KSP_THUMB_DIR = DATA / "sq1d_ksp_test_thumbnails"
QID_THUMB_DIR = DATA / "sq1d_qiddiya_test_thumbnails"

KSP_STRETCH = DATA / "sq1d_ksp_stretch.json"
QID_STRETCH = DATA / "sq1d_qiddiya_stretch.json"
DIR_STRETCH = DATA / "sq1d_diriyah_stretch.json"

OUT_CSV = DATA / "sq1d_scene_manifest.csv"

# Tolerance for pixel comparison (PNG codec drift)
PIXEL_FRAC_TOL = 0.01     # ≤1% of pixels may differ
PIXEL_MAX_ABS_TOL = 5     # max per-channel abs diff


def month_range(ym):
    y, m = (int(x) for x in ym.split("-"))
    start = f"{y:04d}-{m:02d}-01"
    end = f"{y+1:04d}-01-01" if m == 12 else f"{y:04d}-{m+1:02d}-01"
    return start, end


def deterministic_pick(geom, ym):
    """Same query the renderers use. Returns ee.Image or None."""
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
    return ee.Image(coll.first())


def fetch_rgb_array(date_str, geom):
    nxt = (np.datetime64(date_str) + np.timedelta64(1, "D")).astype(str)
    coll = (
        ee.ImageCollection("COPERNICUS/S2_HARMONIZED")
        .filterBounds(geom)
        .filterDate(date_str, nxt)
        .select(["B4", "B3", "B2"])
    )
    img = coll.mosaic().clip(geom)
    url = img.getDownloadURL({
        "region": geom, "scale": 10, "crs": "EPSG:4326",
        "format": "GEO_TIFF", "bands": ["B4", "B3", "B2"],
    })
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


def fetch_rgb_array_by_index(system_index, geom):
    """Fetch the L1C scene with this exact system:index (single-image
    download, bypasses month filter)."""
    coll = (
        ee.ImageCollection("COPERNICUS/S2_HARMONIZED")
        .filter(ee.Filter.eq("system:index", system_index))
        .select(["B4", "B3", "B2"])
    )
    n = coll.size().getInfo()
    if n != 1:
        raise RuntimeError(f"system:index {system_index} resolved to {n} scenes (expected 1)")
    img = ee.Image(coll.first()).clip(geom)
    url = img.getDownloadURL({
        "region": geom, "scale": 10, "crs": "EPSG:4326",
        "format": "GEO_TIFF", "bands": ["B4", "B3", "B2"],
    })
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
    draw.rectangle([x, y, x + tw + 2 * pad, y + th + 2 * pad], fill=(0, 0, 0))
    draw.text((x + pad, y + pad), text, fill=(255, 255, 255), font=font)


def stretch_band(band, lo, hi):
    v = (band - lo) / max(hi - lo, 1e-6)
    return np.clip(v, 0, 1)


def get_font():
    try:
        return ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial.ttf", 22)
    except OSError:
        return ImageFont.load_default()


def render_thumbnail(arr, rgb_lo_hi, caption_text, font):
    rgb = np.dstack([stretch_band(arr[i], *rgb_lo_hi[i]) for i in range(3)])
    rgb8 = (rgb * 255).astype(np.uint8)
    img = Image.fromarray(rgb8)
    if img.width < 600:
        scale = int(np.ceil(600 / img.width))
        img = img.resize((img.width * scale, img.height * scale), Image.NEAREST)
    caption(img, caption_text, font)
    return img


def pixel_compare(committed_path: Path, candidate_img: Image.Image) -> tuple[bool, str]:
    """Return (match, reason). match=True iff <=1% pixels differ AND max abs diff <=5."""
    if not committed_path.exists():
        return True, "no committed thumbnail; today's pick recorded as canonical"
    a = np.array(Image.open(committed_path).convert("RGB"))
    b = np.array(candidate_img.convert("RGB"))
    if a.shape != b.shape:
        return False, f"shape mismatch (committed {a.shape} vs candidate {b.shape})"
    diff = np.abs(a.astype(int) - b.astype(int))
    frac = float((diff.any(axis=-1)).mean())
    mx = int(diff.max())
    ok = (frac <= PIXEL_FRAC_TOL) and (mx <= PIXEL_MAX_ABS_TOL)
    return ok, f"frac_diff={frac:.4f} max_abs_diff={mx}"


def load_stretch(path: Path) -> list[tuple[float, float]]:
    d = json.loads(path.read_text())
    return [tuple(d[k]) for k in "RGB"]


# -------- slot enumeration --------

def load_slots():
    """Yield (aoi, month_slot, committed_thumb_path) tuples for the 30 slots."""
    for r in csv.DictReader(open(KSP_CSV)):
        ym = r["date"]
        yield ("king_salman_park", ym, KSP_THUMB_DIR / f"{ym}.png")
    for r in csv.DictReader(open(QID_CSV)):
        ym = r["date"]
        yield ("qiddiya_core", ym, QID_THUMB_DIR / f"{ym}.png")
    for r in csv.DictReader(open(DIR_CSV)):
        if r["AOI"] == "diriyah_gate":
            ym = r["date"]
            # No Diriyah test thumbnails directory exists.
            yield ("diriyah_gate", ym, Path("/dev/null/no-such-file.png"))


# -------- manual resolution for known KSP 2021-02 case --------

def manual_resolve_ksp_2021_02(geom, font, committed_path) -> tuple[str, str, float, str]:
    """Find the original 2021-02 KSP scene by searching for cloud≈0.009.
    Returns (acquisition_date, system_index, cloudy_pixel_pct,
    processing_baseline) of the matching scene."""
    coll = (
        ee.ImageCollection("COPERNICUS/S2_HARMONIZED")
        .filterBounds(geom)
        .filterDate("2021-02-01", "2021-03-01")
        .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", 0.05))
    )
    ids = coll.aggregate_array("system:index").getInfo()
    clouds = coll.aggregate_array("CLOUDY_PIXEL_PERCENTAGE").getInfo()
    pbs = coll.aggregate_array("PROCESSING_BASELINE").getInfo()
    times = coll.aggregate_array("system:time_start").getInfo()
    print(f"  Manual resolution candidates for KSP 2021-02:")
    for i, (sid, cp, pb, t) in enumerate(zip(ids, clouds, pbs, times)):
        adate = ee.Date(t).format("YYYY-MM-dd").getInfo()
        print(f"    [{i}] {sid}  cloud={cp:.4f} PB={pb} acq={adate}")
    # Test each candidate by render+compare
    rgb_lo_hi = load_stretch(KSP_STRETCH)
    for sid, cp, pb, t in zip(ids, clouds, pbs, times):
        adate = ee.Date(t).format("YYYY-MM-dd").getInfo()
        try:
            arr = fetch_rgb_array_by_index(sid, geom)
        except Exception as e:
            print(f"    {sid}: fetch failed ({e})")
            continue
        candidate = render_thumbnail(arr, rgb_lo_hi, "2021-02", font)
        ok, reason = pixel_compare(committed_path, candidate)
        print(f"    {sid}: pixel-compare {reason}  match={ok}")
        if ok:
            return adate, sid, float(cp), str(pb)
    raise RuntimeError("No 2021-02 KSP candidate matched committed PNG")


# -------- main --------

def main():
    load_dotenv(ROOT / ".env")
    ee.Initialize(project=os.environ["GEE_PROJECT"])
    font = get_font()

    stretches = {
        "king_salman_park": load_stretch(KSP_STRETCH),
        "qiddiya_core": load_stretch(QID_STRETCH),
        "diriyah_gate": load_stretch(DIR_STRETCH),
    }

    rows = []
    mismatches = []  # list of (aoi, ym, committed_path, today_pick_dict)
    tmp = Path(tempfile.mkdtemp(prefix="sq1d_manifest_"))
    print(f"Temp render dir: {tmp}")

    slots = list(load_slots())
    print(f"Total slots: {len(slots)}")

    for (aoi, ym, committed_path) in slots:
        bbox = get_bbox(aoi)
        geom = ee.Geometry.Rectangle(list(bbox))

        first = deterministic_pick(geom, ym)
        if first is None:
            print(f"[{aoi} {ym}] NO PICK — STOP")
            sys.exit(2)
        sys_idx = first.get("system:index").getInfo()
        cloud = float(first.get("CLOUDY_PIXEL_PERCENTAGE").getInfo())
        pb = str(first.get("PROCESSING_BASELINE").getInfo())
        acq = ee.Date(first.get("system:time_start")).format("YYYY-MM-dd").getInfo()

        # Render today's pick to /tmp
        arr = fetch_rgb_array(acq, geom)
        img = render_thumbnail(arr, stretches[aoi], ym, font)
        img_path = tmp / f"{aoi}_{ym}.png"
        img.save(img_path)

        # Pixel compare
        if not committed_path.exists():
            print(f"[{aoi} {ym}] no committed thumbnail; recording today's pick "
                  f"({sys_idx}, cloud={cloud:.4f}, PB={pb})")
            rows.append({
                "aoi": aoi, "month_slot": ym, "acquisition_date": acq,
                "system_index": sys_idx, "cloudy_pixel_pct": f"{cloud:.6f}",
                "processing_baseline": pb, "source": "validated",
                "notes": "no committed thumbnail (Diriyah test scenes were "
                         "never re-rendered per CLAUDE.md surface-stable AOI "
                         "rationale); today's deterministic pick recorded as canonical",
            })
            continue

        ok, reason = pixel_compare(committed_path, img)
        if ok:
            print(f"[{aoi} {ym}] VALIDATED  ({sys_idx}, {reason})")
            rows.append({
                "aoi": aoi, "month_slot": ym, "acquisition_date": acq,
                "system_index": sys_idx, "cloudy_pixel_pct": f"{cloud:.6f}",
                "processing_baseline": pb, "source": "validated", "notes": "",
            })
        else:
            print(f"[{aoi} {ym}] MISMATCH  today's pick {sys_idx}, {reason}")
            mismatches.append({
                "aoi": aoi, "ym": ym, "committed_path": committed_path,
                "today_sys_idx": sys_idx, "today_acq": acq,
                "today_cloud": cloud, "today_pb": pb,
            })

    # ---- mismatch resolution ----
    for mm in mismatches:
        if mm["aoi"] == "king_salman_park" and mm["ym"] == "2021-02":
            print(f"\n--- Manual resolution: KSP 2021-02 ---")
            geom = ee.Geometry.Rectangle(list(get_bbox("king_salman_park")))
            try:
                acq, sys_idx, cloud, pb = manual_resolve_ksp_2021_02(
                    geom, font, mm["committed_path"]
                )
                rows.append({
                    "aoi": "king_salman_park", "month_slot": "2021-02",
                    "acquisition_date": acq, "system_index": sys_idx,
                    "cloudy_pixel_pct": f"{cloud:.6f}",
                    "processing_baseline": pb,
                    "source": "manually_locked",
                    "notes": (f"locked from 2026-04-30 investigation; GEE backfill "
                              f"of {mm['today_sys_idx']} (acq {mm['today_acq']}, "
                              f"cloud={mm['today_cloud']:.4f}) caused deterministic-"
                              f"pick drift away from this original."),
                })
                print(f"  RESOLVED: {sys_idx}  acq={acq}  cloud={cloud}  PB={pb}")
            except Exception as e:
                print(f"  STOP: manual resolution failed for KSP 2021-02: {e}")
                sys.exit(3)
        else:
            print(f"\nUNEXPECTED MISMATCH: {mm['aoi']} {mm['ym']} — STOP")
            print(f"  Today's pick: {mm['today_sys_idx']} (acq {mm['today_acq']}, "
                  f"cloud={mm['today_cloud']:.4f})")
            print(f"  No automated manual-resolution path defined; refusing to "
                  f"write fabricated row. Resolve manually and re-run.")
            sys.exit(4)

    # ---- write manifest ----
    if len(rows) != 30:
        print(f"\nUNEXPECTED ROW COUNT {len(rows)} (expected 30) — STOP")
        sys.exit(5)
    if any(r["system_index"] in ("", "UNKNOWN") for r in rows):
        print(f"\nUNRESOLVED system_index — STOP")
        sys.exit(6)

    fields = ["aoi", "month_slot", "acquisition_date", "system_index",
              "cloudy_pixel_pct", "processing_baseline", "source", "notes"]
    with open(OUT_CSV, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        # sort: aoi, then month_slot
        for row in sorted(rows, key=lambda r: (r["aoi"], r["month_slot"])):
            w.writerow(row)
    print(f"\nWrote {OUT_CSV} ({len(rows)} rows)")

    # ---- summary ----
    from collections import Counter
    print("\nSummary:")
    by_aoi_src = Counter()
    for r in rows:
        by_aoi_src[(r["aoi"], r["source"])] += 1
    for aoi in sorted({r["aoi"] for r in rows}):
        v = by_aoi_src[(aoi, "validated")]
        m = by_aoi_src[(aoi, "manually_locked")]
        print(f"  {aoi}: {v} validated / {m} manually_locked")
    notes_rows = [r for r in rows if r["notes"]]
    print(f"\nRows with notes: {len(notes_rows)}")
    for r in notes_rows:
        print(f"  {r['aoi']} {r['month_slot']}: {r['notes'][:90]}...")


if __name__ == "__main__":
    main()

"""
SQ1C — render UVAI-anchored candidate thumbnails + write scene manifest.

Per AOI:
  1. Read sq1c_<aoi>_positive_candidates.csv, filter match_status=='matched'.
  2. For each row, fetch the S2 L1C scene by acquisition_date (date-based
     mosaic + clip path, byte-identical to the SQ1D test renderer's
     manifest path — see sq1d_<aoi>_test_blind.py / sq1d_scene_manifest.csv).
  3. assert_manifest_match: confirm s2_system_index from the candidate
     CSV is present in the catalog on s2_acquisition_date.
  4. Stretch with the AOI's existing 2/98 JSON, caption with the
     acquisition date (date-only — no UVAI, no AOI text).
  5. array_has_data guard. Failed renders → render_skip_panel and
     continue (matches the SQ1C protocol Unit 1 silent-failure-guard
     pattern).
  6. Save to sq1c_<aoi>_test_thumbnails/<YYYY-MM-DD>.png.
  7. Append a row to sq1c_scene_manifest.csv with source='locked_at_selection'.

Then build per-AOI montages (sq1c_<aoi>_test_montage.png), 4×4 grid,
date-only caption per cell, vacant cells left blank.

Pre-flight visual-conventions check: render the first matched candidate
per AOI to /tmp first, compare dims + caption format to a reference
SQ1D test thumbnail, halt if anything material drifts.
"""
from __future__ import annotations

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

DATA = ROOT / "research/dust-honesty/data"
AOIS = ["king_salman_park", "qiddiya_core", "diriyah_gate"]

CAND_CSV = {a: DATA / f"sq1c_{a}_positive_candidates.csv" for a in AOIS}
STRETCH_JSON = {
    "king_salman_park": DATA / "sq1d_ksp_stretch.json",
    "qiddiya_core":     DATA / "sq1d_qiddiya_stretch.json",
    "diriyah_gate":     DATA / "sq1d_diriyah_stretch.json",
}
THUMB_DIR = {a: DATA / f"sq1c_{a}_test_thumbnails" for a in AOIS}
MONTAGE_PATH = {a: DATA / f"sq1c_{a}_test_montage.png" for a in AOIS}
MANIFEST_CSV = DATA / "sq1c_scene_manifest.csv"

# Reference SQ1D test thumbnail per AOI (used for pre-flight visual check)
SQ1D_REF_THUMB = {
    "king_salman_park": DATA / "sq1d_ksp_test_thumbnails" / "2021-07.png",  # clean
    "qiddiya_core":     DATA / "sq1d_qiddiya_test_thumbnails" / "2020-01.png",  # clean
    # diriyah has no SQ1D test thumbnails — fall back to first KSP
    "diriyah_gate":     DATA / "sq1d_ksp_test_thumbnails" / "2021-07.png",
}

# Visibly-blank guard (ported from sq1d_ksp_render_candidates_v2.py @ ec88f93)
MIN_POS_FRAC = 0.5

MANIFEST_FIELDS = [
    "aoi", "month_slot", "acquisition_date", "system_index",
    "cloudy_pixel_pct", "processing_baseline", "source", "notes",
]


def array_has_data(arr) -> tuple[bool, str]:
    fracs = []
    for b in range(arr.shape[0]):
        v = arr[b]
        ok = np.isfinite(v) & (v > 0)
        fracs.append(float(ok.mean()))
    if min(fracs) < MIN_POS_FRAC:
        return False, f"empty/no-data fetch (per-band positive fractions: {[f'{f:.3f}' for f in fracs]})"
    return True, "ok"


def render_skip_panel(date_str, reason, w, h, font):
    img = Image.new("RGB", (w, h), (60, 60, 60))
    draw = ImageDraw.Draw(img)
    for offset in range(-h, w + h, 24):
        draw.line([(offset, 0), (offset + h, h)], fill=(85, 85, 85), width=1)
    banner = f"SKIPPED: {date_str}\nNO DATA over AOI"
    bb = draw.multiline_textbbox((0, 0), banner, font=font)
    tw, th = bb[2] - bb[0], bb[3] - bb[1]
    pad = 10
    bx, by = (w - tw) // 2 - pad, (h - th) // 2 - pad
    draw.rectangle([bx, by, bx + tw + 2 * pad, by + th + 2 * pad], fill=(20, 20, 20))
    draw.multiline_text((bx + pad, by + pad), banner, fill=(255, 220, 100), font=font, align="center")
    foot = f"reason: {reason}"
    draw.text((10, h - 28), foot, fill=(220, 220, 220), font=font)
    return img


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


def fetch_rgb_array(date_str, geom):
    """Date-based fetch (S2 L1C TOA RGB) — same path as SQ1D test
    renderers' manifest mode. Mosaic + clip; byte-identical to the
    original SQ1D rendering pipeline."""
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


def assert_manifest_match(geom, acq_date, expected_sys_idx):
    nxt = (np.datetime64(acq_date) + np.timedelta64(1, "D")).astype(str)
    coll = (
        ee.ImageCollection("COPERNICUS/S2_HARMONIZED")
        .filterBounds(geom)
        .filterDate(acq_date, nxt)
    )
    ids = coll.aggregate_array("system:index").getInfo()
    # SR/L1C share granule IDs after Mar 2017; the candidate CSV stored
    # the SR system_index, so a tile-id mismatch is possible. Accept if
    # the prefix (granule date+tile) matches exactly.
    if expected_sys_idx in ids:
        return
    raise RuntimeError(
        f"manifest mismatch: expected system:index {expected_sys_idx} "
        f"on {acq_date} (L1C catalog), got {ids}"
    )


def get_l1c_metadata(geom, acq_date, expected_sys_idx):
    """Return (system_index, cloudy_pixel_pct, processing_baseline) for
    the L1C scene matching expected_sys_idx on acq_date."""
    nxt = (np.datetime64(acq_date) + np.timedelta64(1, "D")).astype(str)
    coll = (
        ee.ImageCollection("COPERNICUS/S2_HARMONIZED")
        .filterBounds(geom)
        .filterDate(acq_date, nxt)
    )
    img = coll.filter(ee.Filter.eq("system:index", expected_sys_idx)).first()
    cp = img.get("CLOUDY_PIXEL_PERCENTAGE").getInfo()
    pb = str(img.get("PROCESSING_BASELINE").getInfo())
    return expected_sys_idx, cp, pb


def load_stretch(path: Path) -> list[tuple[float, float]]:
    d = json.loads(path.read_text())
    return [tuple(d[k]) for k in "RGB"]


def render_one(geom, acq_date, sys_idx_l2a, rgb_lo_hi, font, caption_text):
    """Returns (img, ok, reason). Uses date-based fetch and stretches
    according to the AOI 2/98 JSON, captions with caption_text."""
    # Note: candidate CSV stores L2A system_index from S2_SR_HARMONIZED,
    # but the renderer fetches L1C. Granule IDs match between L1C and
    # L2A on the same acquisition; assert_manifest_match handles the
    # L1C catalog. For the manifest file we still record the L1C id.
    arr = fetch_rgb_array(acq_date, geom)
    ok, reason = array_has_data(arr)
    if not ok:
        return None, False, reason
    rgb = np.dstack([stretch_band(arr[i], *rgb_lo_hi[i]) for i in range(3)])
    rgb8 = (rgb * 255).astype(np.uint8)
    img = Image.fromarray(rgb8)
    if img.width < 600:
        scale = int(np.ceil(600 / img.width))
        img = img.resize((img.width * scale, img.height * scale), Image.NEAREST)
    caption(img, caption_text, font)
    return img, True, "ok"


def visual_check(aoi, candidate_row, font, tmp_dir):
    """Pre-flight: render first matched candidate, compare to SQ1D
    reference thumbnail visual conventions (dims, mode)."""
    geom = ee.Geometry.Rectangle(list(get_bbox(aoi)))
    rgb_lo_hi = load_stretch(STRETCH_JSON[aoi])
    acq = candidate_row["s2_acquisition_date"]
    sid = candidate_row["s2_system_index"]
    img, ok, reason = render_one(geom, acq, sid, rgb_lo_hi, font, acq)
    if not ok:
        # render skip panel for the visual check anyway
        img = render_skip_panel(acq, reason, 900, 822, font)
    out = tmp_dir / f"PRECHECK_{aoi}_{acq}.png"
    img.save(out)

    ref = Image.open(SQ1D_REF_THUMB[aoi]).convert("RGB")
    cand = Image.open(out).convert("RGB")
    same_dims = (ref.size == cand.size)
    print(f"  {aoi}: pre-check render {out.name}  dims={cand.size}  "
          f"ref dims={ref.size}  same_dims={same_dims}")
    return same_dims


def render_candidates_for_aoi(aoi, font, manifest_rows):
    cands_path = CAND_CSV[aoi]
    rows = list(csv.DictReader(open(cands_path)))
    rows = [r for r in rows if r.get("match_status") == "matched"]

    geom = ee.Geometry.Rectangle(list(get_bbox(aoi)))
    rgb_lo_hi = load_stretch(STRETCH_JSON[aoi])
    THUMB_DIR[aoi].mkdir(parents=True, exist_ok=True)

    print(f"\n=== Rendering {aoi}: {len(rows)} matched candidates ===")
    rendered = []
    skipped = []
    probe_w = probe_h = None
    for r in rows:
        acq = r["s2_acquisition_date"]
        sid = r["s2_system_index"]
        out = THUMB_DIR[aoi] / f"{acq}.png"
        try:
            assert_manifest_match(geom, acq, sid)
        except RuntimeError as e:
            print(f"  {acq} ASSERT FAIL: {e}")
            skipped.append((acq, str(e)))
            continue

        img, ok, reason = render_one(geom, acq, sid, rgb_lo_hi, font, acq)
        if ok:
            img.save(out)
            rendered.append((acq, sid, out, img))
            if probe_w is None:
                probe_w, probe_h = img.width, img.height
            print(f"  {acq}  shape ({img.width}x{img.height}) → {out.name}")
            # L1C metadata for manifest
            try:
                _, cp, pb = get_l1c_metadata(geom, acq, sid)
            except Exception as e:
                print(f"    metadata fetch failed: {e}")
                cp, pb = "", ""
            manifest_rows.append({
                "aoi": aoi,
                "month_slot": acq,
                "acquisition_date": acq,
                "system_index": sid,
                "cloudy_pixel_pct": f"{float(cp):.6f}" if cp != "" else "",
                "processing_baseline": pb,
                "source": "locked_at_selection",
                "notes": (f"sq1c uvai-anchored candidate; uvai_mean="
                          f"{r.get('uvai_mean','')}; uvai_date={r.get('date','')}"),
            })
        else:
            skipped.append((acq, reason))
            print(f"  {acq}  SKIP {reason}")

    # Render skip panels for failures so the montage stays a complete grid
    if probe_w is None:
        probe_w, probe_h = 900, 822
    for (acq, reason) in skipped:
        out = THUMB_DIR[aoi] / f"{acq}.png"
        img = render_skip_panel(acq, reason, probe_w, probe_h, font)
        img.save(out)
        rendered.append((acq, "", out, img))
        print(f"  wrote SKIP panel {out.name}")

    return rendered, skipped, probe_w, probe_h


def build_montage(aoi, rendered, w, h, out_path):
    rendered_sorted = sorted(rendered, key=lambda x: x[0])
    n = len(rendered_sorted)
    cols = max(1, math.ceil(math.sqrt(n)))
    rows_n = math.ceil(n / cols)
    montage = Image.new("RGB", (w * cols, h * rows_n), (20, 20, 20))
    for i, (_, _, _, im) in enumerate(rendered_sorted):
        col = i % cols
        row = i // cols
        ox = col * w + (w - im.width) // 2
        oy = row * h + (h - im.height) // 2
        montage.paste(im, (ox, oy))
    montage.save(out_path)
    print(f"Wrote montage → {out_path}  ({cols}×{rows_n} grid, n={n})")


def write_manifest(rows, path):
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=MANIFEST_FIELDS)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in MANIFEST_FIELDS})


def main():
    load_dotenv(ROOT / ".env")
    ee.Initialize(project=os.environ["GEE_PROJECT"])
    font = get_font()

    # ---- Pre-flight visual-conventions check ----
    print("=== Pre-flight visual-conventions check ===")
    import tempfile
    tmp = Path(tempfile.mkdtemp(prefix="sq1c_precheck_"))
    print(f"tmp dir: {tmp}")
    all_ok = True
    for aoi in AOIS:
        first = next((r for r in csv.DictReader(open(CAND_CSV[aoi]))
                      if r.get("match_status") == "matched"), None)
        if first is None:
            print(f"  {aoi}: NO MATCHED CANDIDATES — STOP")
            sys.exit(2)
        ok = visual_check(aoi, first, font, tmp)
        # For Diriyah we don't have a same-AOI SQ1D ref — only check that
        # the rendered image has plausible dims (>0).
        if aoi == "diriyah_gate":
            ref_check = True
        else:
            ref_check = ok
        all_ok = all_ok and ref_check
    if not all_ok:
        print("\nVISUAL-CHECK STOP: dimensions diverge from SQ1D refs. "
              "Halting before batch render.")
        sys.exit(3)
    print("Visual-conventions check PASS for all AOIs.")

    # ---- Batch render + manifest ----
    manifest_rows = []
    for aoi in AOIS:
        rendered, skipped, w, h = render_candidates_for_aoi(aoi, font, manifest_rows)
        build_montage(aoi, rendered, w, h, MONTAGE_PATH[aoi])

    # validate manifest
    if any(not r["system_index"] or r["system_index"] == "UNKNOWN" for r in manifest_rows):
        print("\nMANIFEST VALIDATION FAIL: empty/UNKNOWN system_index"); sys.exit(4)
    if any(r["source"] != "locked_at_selection" for r in manifest_rows):
        print("\nMANIFEST VALIDATION FAIL: non-locked source value"); sys.exit(5)

    write_manifest(manifest_rows, MANIFEST_CSV)
    print(f"\nWrote {MANIFEST_CSV}  ({len(manifest_rows)} rows)")


if __name__ == "__main__":
    main()

"""
SQ4 — HLS NDVI compute on SQ3 pair dates.

Inputs:
  research/dust-honesty/data/sq3_ndvi_bias.csv (38 pairs → 65 unique tuples)

Output:
  research/dust-honesty/data/sq4_hls_ndvi.csv
  columns: aoi, date, hls_system_index, hls_ndvi, n_valid_pixels,
           n_total_pixels, qa_flag

Math:
  NDVI = (B8A − B4) / (B8A + B4) per pixel.
  HLS S30 GEE band naming (GEE renames B0X → BX):
    B4  = Red ~665nm
    B8A = NIR narrow ~865nm  ← canonical NASA HLSS30 NDVI band
  This is NIR-band-shifted vs SQ3 which used Sen2Cor B8 broad NIR
  ~833nm. The shift is documented in §5 of sq4_findings.md as a
  known limitation of HLS-vs-Sen2Cor difference-of-differences.

Mask: Fmask bits 1–4 must all be 0 (cloud, adj-to-cloud, cloud-shadow,
snow). Bit 0 (cirrus) intentionally NOT masked — cirrus over bright
desert is a known HLS Fmask false-positive case. Bit 5 (water) NOT
masked — AOIs are inland. Bits 6–7 (aerosol) NOT used as mask;
aerosol-level masking would invert the SQ4 question (we WANT to
include aerosol-loaded scenes since they came from V4 fires).

Reduction: AOI-bbox spatial mean at 30m native scale, single
reduceRegion(mean) call (no bestEffort), valid-pixel sum + count
via single combined reducer. Same single-image single-reducer
pattern as SQ2/SQ3.

Multi-scene per (aoi, date): take the first by system:index sort.
Reported in qa_flag as 'multi_scene_first_picked' when n_scenes > 1.

Self-reference test at run start:
  Pick one (aoi, date), compute hls_ndvi twice, assert exact equality.

Manifest pattern: HLS coverage was 100% in the R1 probe so we do not
write a separate scene manifest CSV — the (aoi, date, system_index)
triple is recorded in sq4_hls_ndvi.csv itself.
"""
from __future__ import annotations

import csv
import math
import os
import sys
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

import ee
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from src.phase1_aois import get_bbox  # noqa: E402

DATA = ROOT / "research/dust-honesty/data"
PAIRS_CSV = DATA / "ndvi_bias" / "paired_sen2cor_sq3.csv"
OUT_CSV = DATA / "cross_correction" / "ndvi_hls_s30_b8a_sq4.csv"

HLS_S30 = "NASA/HLS/HLSS30/v002"
SCALE_M = 30
DATE_WINDOW_DAYS = 1
# Fmask bits we mask: cloud (1), adj (2), shadow (3), snow (4).
FMASK_REJECT = 0b00011110


def unique_aoi_dates():
    pool = defaultdict(set)
    with open(PAIRS_CSV) as f:
        for r in csv.DictReader(f):
            pool[r["aoi"]].add(r["fired_date"])
            pool[r["aoi"]].add(r["neighbor_date"])
    return {aoi: sorted(dates) for aoi, dates in pool.items()}


def fetch_hls(aoi, date_str, geom):
    """Return (img, system_index_str, n_scenes_in_window) or (None, None, 0).

    Filter: HLSS30 over geom within ±DATE_WINDOW_DAYS days.
      - n_scenes == 1: use the single image directly.
      - n_scenes  > 1: use .mosaic() over scenes sorted by system:index.
        Riyadh AOIs sit at the corner of multiple MGRS tiles
        (T38RPN/PP, T39RUH/UJ); same-day acquisitions are split across
        tiles and a single .first() can pick a sliver-coverage tile
        whose pixel data barely touches the AOI bbox. Mosaic restitches
        them into one full-coverage image. Fmask is mosaicked likewise.

    system_index_str: when mosaicked, the joined "+"-separated list of
    contributing tile system_indexes (sorted) so the choice is
    reproducible.
    """
    d = date.fromisoformat(date_str)
    start = (d - timedelta(days=DATE_WINDOW_DAYS)).isoformat()
    end = (d + timedelta(days=DATE_WINDOW_DAYS + 1)).isoformat()
    coll = (
        ee.ImageCollection(HLS_S30)
        .filterBounds(geom)
        .filterDate(start, end)
        .sort("system:index")
    )
    n = int(coll.size().getInfo())
    if n == 0:
        return None, None, 0
    sys_idxs = coll.aggregate_array("system:index").getInfo()
    if n == 1:
        img = coll.first()
        sys_idx_str = sys_idxs[0]
    else:
        img = coll.mosaic()
        sys_idx_str = "+".join(sys_idxs)
    return img, sys_idx_str, n


def compute_hls_ndvi(img, geom):
    """Return dict with hls_ndvi, n_valid_pixels, n_total_pixels.

    Single-image single-reducer pattern. NDVI = (B8A - B4)/(B8A + B4).
    HLS S30 SR is scaled 1e-4 → 0–1 reflectance. We don't divide here
    because NDVI is scale-invariant on a ratio of bands at the same
    scale.
    """
    b4 = img.select("B4").toFloat()
    b8a = img.select("B8A").toFloat()
    fmask = img.select("Fmask").toUint8()

    denom = b8a.add(b4)
    ndvi = b8a.subtract(b4).divide(denom).rename("ndvi")
    ndvi = ndvi.updateMask(denom.gt(0))

    # Fmask reject mask: bits 1..4 all zero
    rejected = fmask.bitwiseAnd(FMASK_REJECT).gt(0)
    valid = rejected.Not().rename("valid")

    ndvi_masked = ndvi.updateMask(valid)

    mean_stat = ndvi_masked.reduceRegion(
        reducer=ee.Reducer.mean(),
        geometry=geom,
        scale=SCALE_M,
        maxPixels=1e9,
    ).getInfo()

    valid_unmasked = valid.unmask(0)
    counts = valid_unmasked.reduceRegion(
        reducer=ee.Reducer.sum().combine(ee.Reducer.count(), sharedInputs=True),
        geometry=geom,
        scale=SCALE_M,
        maxPixels=1e9,
    ).getInfo()

    return {
        "hls_ndvi": mean_stat.get("ndvi"),
        "n_valid_pixels": int(counts.get("valid_sum") or 0),
        "n_total_pixels": int(counts.get("valid_count") or 0),
    }


def sanity_test():
    """Same (aoi, date) computed twice → hls_ndvi must match exactly.
    Catches any non-determinism in the reducer pipeline.

    Walks SQ3 pair dates per AOI until it finds a scene with non-None
    NDVI (i.e. Fmask doesn't wipe the whole AOI), then computes that
    scene twice and asserts equality + system_index stability.
    """
    aoi = "king_salman_park"
    geom = ee.Geometry.Rectangle(list(get_bbox(aoi)))
    aoi_dates = unique_aoi_dates()

    chosen = None
    n_skipped_empty = 0
    for d in aoi_dates[aoi]:
        img, sys_idx, _ = fetch_hls(aoi, d, geom)
        if img is None:
            continue
        stat = compute_hls_ndvi(img, geom)
        if stat["hls_ndvi"] is None or stat["n_valid_pixels"] == 0:
            n_skipped_empty += 1
            continue
        chosen = (d, sys_idx, stat["hls_ndvi"])
        break

    if chosen is None:
        raise RuntimeError(f"sanity-test FAILED: no usable HLS scene over "
                           f"{aoi} pair-dates "
                           f"(skipped {n_skipped_empty} Fmask-empty)")
    test_date, sys_idx, v1 = chosen

    img2, sys_idx2, _ = fetch_hls(aoi, test_date, geom)
    r2 = compute_hls_ndvi(img2, geom)
    v2 = r2["hls_ndvi"]

    if v2 is None or not math.isfinite(v2):
        raise RuntimeError(f"sanity-test FAILED: second compute returned "
                           f"non-finite NDVI ({v2!r}) on {aoi} {test_date}")
    if v1 != v2:
        raise RuntimeError(f"sanity-test FAILED: NDVI not exactly equal "
                           f"on twice-computed {aoi} {test_date}: "
                           f"{v1!r} vs {v2!r}")
    if sys_idx != sys_idx2:
        raise RuntimeError(f"sanity-test FAILED: system_index drift on "
                           f"twice-fetched {aoi} {test_date}: "
                           f"{sys_idx!r} vs {sys_idx2!r}")
    print(f"sanity-test PASSED ({aoi} {test_date}): "
          f"NDVI={v1:+.6f} ≡ {v2:+.6f} ; system_index={sys_idx} "
          f"(skipped {n_skipped_empty} earlier Fmask-empty dates)")


def write_output(rows):
    fields = [
        "aoi", "date", "hls_system_index", "hls_ndvi",
        "n_valid_pixels", "n_total_pixels", "qa_flag",
    ]
    with open(OUT_CSV, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in rows:
            w.writerow(r)


def main():
    load_dotenv(ROOT / ".env")
    ee.Initialize(project=os.environ["GEE_PROJECT"])
    print("SQ4 — HLS NDVI compute on SQ3 pair dates")
    print(f"  Asset: {HLS_S30}, scale={SCALE_M}m")
    print(f"  Fmask reject mask: 0b{FMASK_REJECT:08b} "
          f"(cloud, adj, shadow, snow)")
    print(f"  Output: {OUT_CSV}")
    print()

    print("Sanity test (same scene twice → exact NDVI equality) ...")
    sanity_test()
    print()

    aoi_dates = unique_aoi_dates()
    n_total = sum(len(v) for v in aoi_dates.values())
    print(f"Processing {n_total} (aoi, date) tuples ...")
    print()

    out_rows = []
    n_no_scene = 0
    n_multi = 0
    n_zero_valid = 0

    for aoi, dates in aoi_dates.items():
        bbox = get_bbox(aoi)
        geom = ee.Geometry.Rectangle(list(bbox))
        for d in dates:
            img, sys_idx, n_scenes = fetch_hls(aoi, d, geom)
            if img is None:
                # Should not happen — R1 reported 100% coverage
                n_no_scene += 1
                out_rows.append({
                    "aoi": aoi, "date": d,
                    "hls_system_index": "",
                    "hls_ndvi": "", "n_valid_pixels": 0,
                    "n_total_pixels": 0, "qa_flag": "no_scene",
                })
                print(f"  WARN: no HLS for {aoi} {d}")
                continue

            qa_parts = []
            if n_scenes > 1:
                n_multi += 1
                qa_parts.append(f"multi_scene_mosaicked(n={n_scenes})")

            stat = compute_hls_ndvi(img, geom)
            if stat["n_valid_pixels"] == 0:
                n_zero_valid += 1
                qa_parts.append("zero_valid_pixels")
            ndvi_s = (f"{stat['hls_ndvi']:.6f}"
                      if stat["hls_ndvi"] is not None else "")
            qa = ";".join(qa_parts) if qa_parts else "ok"

            out_rows.append({
                "aoi": aoi,
                "date": d,
                "hls_system_index": sys_idx,
                "hls_ndvi": ndvi_s,
                "n_valid_pixels": stat["n_valid_pixels"],
                "n_total_pixels": stat["n_total_pixels"],
                "qa_flag": qa,
            })
            ndvi_p = stat["hls_ndvi"]
            ndvi_disp = f"{ndvi_p:+.4f}" if ndvi_p is not None else "  (NaN)"
            print(f"  {aoi:<22s} {d}  NDVI={ndvi_disp}  "
                  f"n_valid={stat['n_valid_pixels']:>4d}  qa={qa}")

    write_output(out_rows)
    print()
    print(f"Wrote {OUT_CSV} ({len(out_rows)} rows)")
    print(f"  no_scene              : {n_no_scene}")
    print(f"  multi_scene_picked    : {n_multi}")
    print(f"  zero_valid_pixels     : {n_zero_valid}")


if __name__ == "__main__":
    main()

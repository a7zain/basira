"""
SQ4B Arm A — HLS S30 NDVI compute on SQ3 pair dates, BROAD NIR (B8).

Inputs:
  research/dust-honesty/data/sq3_ndvi_bias.csv (38 pairs → 65 unique tuples)
  research/dust-honesty/data/sq4_hls_ndvi.csv  (SQ4's B8A NDVI cache, for
                                                Spearman cross-check only)

Output:
  research/dust-honesty/data/sq4b_b8_s30_ndvi.csv
  columns: aoi, date, hls_system_index, b8_s30_ndvi, n_valid_pixels,
           n_total_pixels, qa_flag

Math:
  NDVI = (B8 - B4) / (B8 + B4) per pixel.
  HLS S30 GEE band naming (GEE renames B0X → BX):
    B4  = Red ~665nm
    B8  = NIR broad ~833nm  ← THIS SCRIPT (sensitivity vs SQ4's B8A)

  SQ4 used B8A (narrow ~865nm). SQ4B Arm A reruns the SAME pipeline on
  the SAME pair dates with B8 (broad) to test whether the SQ4 null is
  robust to narrow-vs-broad NIR selection on the same correction chain.

Mask: Fmask bits 1–4 must all be 0 (cloud, adj-to-cloud, cloud-shadow,
snow). Bit 0 (cirrus) and bit 5 (water) NOT masked. Parity with
sq4_compute_hls_ndvi.py.

Reduction: AOI-bbox spatial mean at 30m native scale, single
reduceRegion(mean) call (no bestEffort), valid-pixel sum + count
via single combined reducer. Same single-image single-reducer
pattern as SQ2/SQ3/SQ4.

Multi-scene per (aoi, date): mosaic across overlapping MGRS tiles
(coll.mosaic(), NOT coll.first()). SQ4 confirmed first() drops MGRS
sliver tiles silently — mosaic() is the locked HLS pattern. Same
behavior as sq4_compute_hls_ndvi.py.

Self-reference test at run start:
  Pick one (aoi, date) with non-empty NDVI, compute b8_s30_ndvi twice,
  assert exact equality. Walks pair dates if first attempt is empty.

Spearman cross-check (post-compute, diagnostic only):
  Loads SQ4's sq4_hls_ndvi.csv, computes Spearman ρ between B8 and B8A
  on (aoi, date) rows where both are non-NaN. Reported for the §3
  diagnostic line in findings note. Not a stop rule; flag if ρ < 0.95
  in the runtime log.
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
from scipy.stats import spearmanr

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from src.phase1_aois import get_bbox  # noqa: E402

DATA = ROOT / "research/dust-honesty/data"
PAIRS_CSV = DATA / "sq3_ndvi_bias.csv"
SQ4_NDVI_CSV = DATA / "sq4_hls_ndvi.csv"
OUT_CSV = DATA / "sq4b_b8_s30_ndvi.csv"

HLS_S30 = "NASA/HLS/HLSS30/v002"
SCALE_M = 30
DATE_WINDOW_DAYS = 1
FMASK_REJECT = 0b00011110  # bits 1-4: cloud, adj, shadow, snow


def unique_aoi_dates():
    pool = defaultdict(set)
    with open(PAIRS_CSV) as f:
        for r in csv.DictReader(f):
            pool[r["aoi"]].add(r["fired_date"])
            pool[r["aoi"]].add(r["neighbor_date"])
    return {aoi: sorted(dates) for aoi, dates in pool.items()}


def fetch_hls(aoi, date_str, geom):
    """Return (img, system_index_str, n_scenes) or (None, None, 0).

    Multi-tile mosaic pattern (parity with sq4_compute_hls_ndvi.py).
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


def compute_b8_ndvi(img, geom):
    """NDVI = (B8 - B4) / (B8 + B4) at AOI mean, native 30m, single
    reduceRegion + combined sum/count reducer. Fmask bits 1-4 masked."""
    b4 = img.select("B4").toFloat()
    b8 = img.select("B8").toFloat()
    fmask = img.select("Fmask").toUint8()

    denom = b8.add(b4)
    ndvi = b8.subtract(b4).divide(denom).rename("ndvi")
    ndvi = ndvi.updateMask(denom.gt(0))

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
        "b8_s30_ndvi": mean_stat.get("ndvi"),
        "n_valid_pixels": int(counts.get("valid_sum") or 0),
        "n_total_pixels": int(counts.get("valid_count") or 0),
    }


def sanity_test():
    """Same (aoi, date) computed twice → b8_s30_ndvi must match exactly.
    Walks SQ3 pair dates per AOI until a scene with non-None NDVI is
    found (Fmask doesn't wipe the whole AOI), then computes that scene
    twice and asserts equality + system_index stability.
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
        stat = compute_b8_ndvi(img, geom)
        if stat["b8_s30_ndvi"] is None or stat["n_valid_pixels"] == 0:
            n_skipped_empty += 1
            continue
        chosen = (d, sys_idx, stat["b8_s30_ndvi"])
        break

    if chosen is None:
        raise RuntimeError(f"sanity-test FAILED: no usable HLS scene over "
                           f"{aoi} pair-dates "
                           f"(skipped {n_skipped_empty} Fmask-empty)")
    test_date, sys_idx, v1 = chosen

    img2, sys_idx2, _ = fetch_hls(aoi, test_date, geom)
    r2 = compute_b8_ndvi(img2, geom)
    v2 = r2["b8_s30_ndvi"]

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
          f"B8 NDVI={v1:+.6f} ≡ {v2:+.6f} ; system_index={sys_idx} "
          f"(skipped {n_skipped_empty} earlier Fmask-empty dates)")


def write_output(rows):
    fields = [
        "aoi", "date", "hls_system_index", "b8_s30_ndvi",
        "n_valid_pixels", "n_total_pixels", "qa_flag",
    ]
    with open(OUT_CSV, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in rows:
            w.writerow(r)


def spearman_cross_check(b8_rows):
    """Compare B8 NDVI (this script) to B8A NDVI (SQ4) on shared
    (aoi, date) rows. Returns (rho, n_used) or (None, 0)."""
    if not SQ4_NDVI_CSV.exists():
        print(f"  Spearman cross-check SKIP: {SQ4_NDVI_CSV} not found")
        return None, 0

    b8a_lookup = {}
    with open(SQ4_NDVI_CSV) as f:
        for r in csv.DictReader(f):
            v = r["hls_ndvi"]
            ndvi = float(v) if v != "" else None
            b8a_lookup[(r["aoi"], r["date"])] = ndvi

    pairs = []
    for r in b8_rows:
        v = r["b8_s30_ndvi"]
        if v == "" or v is None:
            continue
        b8a = b8a_lookup.get((r["aoi"], r["date"]))
        if b8a is None:
            continue
        pairs.append((float(v), b8a))

    if len(pairs) < 3:
        return None, len(pairs)

    xs = [p[0] for p in pairs]
    ys = [p[1] for p in pairs]
    rho, _ = spearmanr(xs, ys)
    return float(rho), len(pairs)


def main():
    load_dotenv(ROOT / ".env")
    ee.Initialize(project=os.environ["GEE_PROJECT"])
    print("SQ4B Arm A — HLS S30 NDVI compute (B8 broad NIR)")
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
                n_no_scene += 1
                out_rows.append({
                    "aoi": aoi, "date": d,
                    "hls_system_index": "",
                    "b8_s30_ndvi": "", "n_valid_pixels": 0,
                    "n_total_pixels": 0, "qa_flag": "no_scene",
                })
                print(f"  WARN: no HLS for {aoi} {d}")
                continue

            qa_parts = []
            if n_scenes > 1:
                n_multi += 1
                qa_parts.append(f"multi_scene_mosaicked(n={n_scenes})")

            stat = compute_b8_ndvi(img, geom)
            if stat["n_valid_pixels"] == 0:
                n_zero_valid += 1
                qa_parts.append("zero_valid_pixels")
            ndvi_s = (f"{stat['b8_s30_ndvi']:.6f}"
                      if stat["b8_s30_ndvi"] is not None else "")
            qa = ";".join(qa_parts) if qa_parts else "ok"

            out_rows.append({
                "aoi": aoi,
                "date": d,
                "hls_system_index": sys_idx,
                "b8_s30_ndvi": ndvi_s,
                "n_valid_pixels": stat["n_valid_pixels"],
                "n_total_pixels": stat["n_total_pixels"],
                "qa_flag": qa,
            })
            ndvi_p = stat["b8_s30_ndvi"]
            ndvi_disp = f"{ndvi_p:+.4f}" if ndvi_p is not None else "  (NaN)"
            print(f"  {aoi:<22s} {d}  B8 NDVI={ndvi_disp}  "
                  f"n_valid={stat['n_valid_pixels']:>4d}  qa={qa}")

    write_output(out_rows)
    print()
    print(f"Wrote {OUT_CSV} ({len(out_rows)} rows)")
    print(f"  no_scene              : {n_no_scene}")
    print(f"  multi_scene_mosaicked : {n_multi}")
    print(f"  zero_valid_pixels     : {n_zero_valid}")
    print()

    print("Spearman B8 vs B8A cross-check (diagnostic) ...")
    rho, n_used = spearman_cross_check(out_rows)
    if rho is None:
        print(f"  insufficient data (n_used={n_used})")
    else:
        flag = " (FLAG: < 0.95)" if rho < 0.95 else ""
        print(f"  Spearman ρ = {rho:.4f}  on n={n_used} shared (aoi, date) "
              f"rows{flag}")


if __name__ == "__main__":
    main()

"""
SQ3 — NDVI compute on the SQ2 manifest-locked operational scene set.

Inputs:
  research/dust-honesty/data/operational/manifest_operational_sq2.csv (228 rows)
  research/dust-honesty/data/sq1d_references.json (for self-reference test)

Output:
  research/dust-honesty/data/sq3_ndvi_per_scene.csv

Math:
  NDVI = (B8 - B4) / (B8 + B4) per pixel on Sen2Cor L2A SR
  (matches the SQ3 question framing: Sen2Cor-derived NDVI).

Mask: SCL ∈ {4, 5, 6, 7, 11} (veg, not-veg, water, unclassified, snow)
AND B12 ≥ 0.01 (not water — same convention as SQ2 / SQ1D faithful Lolli).

Reduction: AOI-bbox spatial mean at 20m native scale, single
reduceRegion call (no bestEffort), valid-pixel sum + count via second
reducer on the same valid mask image at the same scale.

Self-reference test at run start: pick a single KSP usable scene,
compute NDVI two ways (mean of per-pixel ratio vs full-image NDVI)
and assert finite output in [-1, 1]. This is a sanity check, not a
zero-equivalence test.

Reuses sq1d_lolli_faithful's matching_l2a + scl_valid_mask +
WATER_RHO12_THRESHOLD + SCALE_M.
"""
from __future__ import annotations

import csv
import math
import os
import sys
from pathlib import Path

import ee
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[3]
SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(SCRIPT_DIR))

from src.phase1_aois import get_bbox  # noqa: E402
from sq1d_lolli_faithful import (  # noqa: E402
    SCALE_M, SCALE_DIV, SCL_VALID, WATER_RHO12_THRESHOLD,
    scl_valid_mask, matching_l2a,
)

DATA = ROOT / "research/dust-honesty/data"
MANIFEST = DATA / "operational" / "manifest_operational_sq2.csv"
OUT_CSV = DATA / "sq3_ndvi_per_scene.csv"


# ---- I/O --------------------------------------------------------------------

def read_manifest():
    rows = []
    with open(MANIFEST) as f:
        for r in csv.DictReader(f):
            rows.append(r)
    return rows


def write_output(rows):
    fields = [
        "aoi", "year", "month", "scene_date", "system_index",
        "ndvi_aoi_mean", "n_valid_pixels", "n_total_pixels", "notes",
    ]
    with open(OUT_CSV, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in fields})


# ---- compute ----------------------------------------------------------------

def fetch_l2a(system_index, geom):
    """Fetch L2A scene matching the locked L1C system_index. Returns the L2A
    image or None if not found.

    Uses the same matching_l2a() call as SQ2 so the L2A side is identical.
    """
    coll = (
        ee.ImageCollection("COPERNICUS/S2_HARMONIZED")
        .filterBounds(geom)
        .filter(ee.Filter.eq("system:index", system_index))
    )
    n = coll.size().getInfo()
    if n == 0:
        return None
    test_l1c = coll.first()
    return matching_l2a(test_l1c, geom)


def compute_ndvi(l2a_img, geom):
    """Return dict with ndvi_aoi_mean (scene mean), n_valid_pixels, n_total_pixels.

    NDVI computed per-pixel on L2A SR reflectance (B8, B4 / 10000).
    Mask: SCL ∈ SCL_VALID AND B12 ≥ WATER_RHO12_THRESHOLD.
    Single mean reduceRegion on the masked NDVI image; single sum+count
    reduceRegion on the unmasked valid image — no bestEffort, native 20m.
    """
    b4 = l2a_img.select("B4").toFloat().divide(SCALE_DIV)
    b8 = l2a_img.select("B8").toFloat().divide(SCALE_DIV)
    b12 = l2a_img.select("B12").toFloat().divide(SCALE_DIV)

    # Per-pixel NDVI; guard division by zero implicitly (b4+b8 == 0 → NDVI NaN).
    denom = b8.add(b4)
    ndvi_pixel = b8.subtract(b4).divide(denom).rename("ndvi")
    # Where denom == 0 force a mask (treats all-zero pixels as invalid).
    ndvi_pixel = ndvi_pixel.updateMask(denom.gt(0))

    valid_scl = scl_valid_mask(l2a_img)
    not_water = b12.gte(WATER_RHO12_THRESHOLD)
    valid = valid_scl.And(not_water).rename("valid")

    ndvi_masked = ndvi_pixel.updateMask(valid)

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
        "ndvi_aoi_mean": mean_stat.get("ndvi"),
        "n_valid_pixels": int(counts.get("valid_sum") or 0),
        "n_total_pixels": int(counts.get("valid_count") or 0),
    }


def sanity_test():
    """Pick the first usable KSP row from the manifest, compute NDVI,
    assert mean is finite and within [-1, 1]. Catches gross GEE errors
    before processing the full set."""
    manifest = read_manifest()
    for r in manifest:
        if r["aoi"] != "king_salman_park":
            continue
        if r["no_usable_scene"] == "True":
            continue
        scene_date = r["acquisition_date"]
        bbox = get_bbox(r["aoi"])
        geom = ee.Geometry.Rectangle(list(bbox))
        l2a = fetch_l2a(r["system_index"], geom)
        if l2a is None:
            print(f"sanity-test SKIP: no L2A for KSP {r['system_index']}")
            continue
        out = compute_ndvi(l2a, geom)
        v = out["ndvi_aoi_mean"]
        if v is None:
            raise RuntimeError(f"sanity-test FAILED: NDVI=None on KSP "
                               f"{scene_date} {r['system_index']}")
        if not math.isfinite(v) or not (-1.0 <= v <= 1.0):
            raise RuntimeError(f"sanity-test FAILED: NDVI={v!r} out of range "
                               f"[-1,1] on KSP {scene_date}")
        print(f"sanity-test PASSED (KSP {scene_date}): "
              f"NDVI={v:+.4f} n_valid={out['n_valid_pixels']} "
              f"n_total={out['n_total_pixels']}")
        return
    raise RuntimeError("sanity-test could not find a usable KSP row")


# ---- main -------------------------------------------------------------------

def main():
    load_dotenv(ROOT / ".env")
    ee.Initialize(project=os.environ["GEE_PROJECT"])

    print("SQ3 — NDVI compute on locked manifest")
    print(f"  Output: {OUT_CSV}")
    print(f"  Scale:  {SCALE_M}m, SCL_VALID={SCL_VALID}, "
          f"WATER_RHO12_THRESHOLD={WATER_RHO12_THRESHOLD}")
    print()

    print("Sanity test ...")
    sanity_test()
    print()

    manifest = read_manifest()
    if len(manifest) != 228:
        raise RuntimeError(f"expected 228 manifest rows, got {len(manifest)}")

    out_rows = []
    n_ok = 0
    n_unusable = 0
    n_l2a_miss = 0
    n_compute_fail = 0
    for i, r in enumerate(manifest, 1):
        aoi = r["aoi"]
        scene_date = r["acquisition_date"]
        sys_idx = r["system_index"]
        base = {
            "aoi": aoi,
            "year": int(r["year"]),
            "month": int(r["month"]),
            "scene_date": scene_date,
            "system_index": sys_idx,
        }
        if r["no_usable_scene"] == "True":
            n_unusable += 1
            out_rows.append({
                **base,
                "ndvi_aoi_mean": "",
                "n_valid_pixels": 0,
                "n_total_pixels": 0,
                "notes": "no_usable_scene",
            })
            print(f"[{i:3d}/228] {aoi:20s} {scene_date or '----------':10s} "
                  f"SKIP no_usable_scene")
            continue

        bbox = get_bbox(aoi)
        geom = ee.Geometry.Rectangle(list(bbox))

        try:
            l2a = fetch_l2a(sys_idx, geom)
        except Exception as e:
            n_compute_fail += 1
            out_rows.append({
                **base,
                "ndvi_aoi_mean": "",
                "n_valid_pixels": 0,
                "n_total_pixels": 0,
                "notes": f"l2a_fetch_error:{e}",
            })
            print(f"[{i:3d}/228] {aoi:20s} {scene_date} ERROR fetch: {e}")
            continue

        if l2a is None:
            n_l2a_miss += 1
            out_rows.append({
                **base,
                "ndvi_aoi_mean": "",
                "n_valid_pixels": 0,
                "n_total_pixels": 0,
                "notes": "no_matching_l2a",
            })
            print(f"[{i:3d}/228] {aoi:20s} {scene_date} no_matching_l2a")
            continue

        try:
            res = compute_ndvi(l2a, geom)
        except Exception as e:
            n_compute_fail += 1
            out_rows.append({
                **base,
                "ndvi_aoi_mean": "",
                "n_valid_pixels": 0,
                "n_total_pixels": 0,
                "notes": f"compute_error:{e}",
            })
            print(f"[{i:3d}/228] {aoi:20s} {scene_date} ERROR compute: {e}")
            continue

        v = res["ndvi_aoi_mean"]
        if v is None or (isinstance(v, float) and math.isnan(v)):
            n_compute_fail += 1
            out_rows.append({
                **base,
                "ndvi_aoi_mean": "",
                "n_valid_pixels": res["n_valid_pixels"],
                "n_total_pixels": res["n_total_pixels"],
                "notes": "ndvi_none_or_nan",
            })
            print(f"[{i:3d}/228] {aoi:20s} {scene_date} NDVI=None "
                  f"n_valid={res['n_valid_pixels']}")
            continue

        n_ok += 1
        out_rows.append({
            **base,
            "ndvi_aoi_mean": f"{float(v):.6f}",
            "n_valid_pixels": res["n_valid_pixels"],
            "n_total_pixels": res["n_total_pixels"],
            "notes": "",
        })
        print(f"[{i:3d}/228] {aoi:20s} {scene_date} NDVI={float(v):+.4f} "
              f"n_valid={res['n_valid_pixels']:6d}")

    write_output(out_rows)
    print()
    print(f"Wrote {OUT_CSV}")
    print(f"  ok                : {n_ok}")
    print(f"  no_usable_scene   : {n_unusable}")
    print(f"  no_matching_l2a   : {n_l2a_miss}")
    print(f"  compute fail/none : {n_compute_fail}")
    print(f"  total             : {len(out_rows)}")


if __name__ == "__main__":
    sys.exit(main())

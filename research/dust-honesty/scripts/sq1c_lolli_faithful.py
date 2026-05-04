"""
SQ1C — faithful Lolli DBB on the 43-scene UVAI-anchored expansion set.

Mirrors sq1d_lolli_faithful.py but reads SQ1C calibration rows from the
three sq1c_<aoi>_relabel.csv files (date is YYYY-MM-DD specific, not a
month slot), uses primary references from references_sq1d.json, and
applies the same bug-fixed reducer (single image, sum + count, no
bestEffort, identical native scale).

Output: research/dust-honesty/data/dbb_compute/dbb_calibration_sq1c.csv
"""
from __future__ import annotations

import csv
import json
import os
import sys
from pathlib import Path

import ee
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from src.phase1_aois import get_bbox  # noqa: E402

# Reuse the SQ1D Lolli compute helpers (already bug-fixed in 0d905ca).
sys.path.insert(0, str(ROOT / "research/dust-honesty/scripts"))
from sq1d_lolli_faithful import (  # noqa: E402
    REFS_JSON, BANDS, SCALE_M, SCALE_DIV,
    compute_dbb, best_l1c_image, matching_l2a, day_bounds,
)

DATA = ROOT / "research/dust-honesty/data"
SQ1C_RELABEL = {
    "king_salman_park": DATA / "calibration" / "relabel_ksp_sq1c.csv",
    "qiddiya_core":     DATA / "calibration" / "relabel_qiddiya_sq1c.csv",
    "diriyah_gate":     DATA / "calibration" / "relabel_diriyah_sq1c.csv",
}
OUT_CSV = DATA / "dbb_compute" / "dbb_calibration_sq1c.csv"


def load_sq1c_set():
    rows = []
    for aoi, path in SQ1C_RELABEL.items():
        for r in csv.DictReader(open(path)):
            if not r.get("final_label"):
                continue
            rows.append({
                "date": r["date"],         # YYYY-MM-DD
                "sub_aoi": r["sub_aoi"],
                "final_label": r["final_label"],
                "ai_confidence": r.get("ai_confidence", ""),
                "bias_exposed": r.get("bias_exposed_during_ai_labeling", "False"),
            })
    return rows


def load_primary_refs():
    cfg = json.loads(REFS_JSON.read_text())
    return {aoi: meta["primary"]["date"] for aoi, meta in cfg["aois"].items()}


def fetch_l1c_by_date(geom, date_yyyy_mm_dd):
    """Single-day L1C; matches SQ1C manifest semantics (we have an
    exact acquisition date, not a month slot)."""
    start, end = day_bounds(date_yyyy_mm_dd)
    coll = (
        ee.ImageCollection("COPERNICUS/S2_HARMONIZED")
        .filterBounds(geom)
        .filterDate(start, end)
        .sort("CLOUDY_PIXEL_PERCENTAGE")
    )
    n = coll.size().getInfo()
    if n == 0:
        return None
    return coll.first()


def process_one(row, refs):
    sub_aoi = row["sub_aoi"]
    test_date = row["date"]                # YYYY-MM-DD
    ref_date = refs[sub_aoi]

    bbox = get_bbox(sub_aoi)
    geom = ee.Geometry.Rectangle(list(bbox))

    test_l1c = fetch_l1c_by_date(geom, test_date)
    if test_l1c is None:
        return {**row, "ref_date": ref_date, "dbb_faithful": None,
                "n_valid_pixels": 0, "n_total_pixels": 0,
                "notes": "no_l1c_test_scene"}
    test_l2a = matching_l2a(test_l1c, geom)
    if test_l2a is None:
        return {**row, "ref_date": ref_date, "dbb_faithful": None,
                "n_valid_pixels": 0, "n_total_pixels": 0,
                "notes": "no_l2a_test_scene"}

    r_start, r_end = day_bounds(ref_date)
    ref_coll = (
        ee.ImageCollection("COPERNICUS/S2_HARMONIZED")
        .filterBounds(geom)
        .filterDate(r_start, r_end)
        .sort("CLOUDY_PIXEL_PERCENTAGE")
    )
    if ref_coll.size().getInfo() == 0:
        return {**row, "ref_date": ref_date, "dbb_faithful": None,
                "n_valid_pixels": 0, "n_total_pixels": 0,
                "notes": "no_l1c_ref_scene"}
    ref_l1c = ref_coll.first()
    ref_l2a = matching_l2a(ref_l1c, geom)
    if ref_l2a is None:
        return {**row, "ref_date": ref_date, "dbb_faithful": None,
                "n_valid_pixels": 0, "n_total_pixels": 0,
                "notes": "no_l2a_ref_scene"}

    test_id = test_l1c.get("system:index").getInfo()
    ref_id = ref_l1c.get("system:index").getInfo()

    out = compute_dbb(test_l1c, ref_l1c, ref_l2a, test_l2a, geom)

    return {
        **row,
        "ref_date": ref_date,
        "dbb_faithful": out["dbb_faithful"],
        "n_valid_pixels": out["n_valid_pixels"],
        "n_total_pixels": out["n_total_pixels"],
        "notes": f"test_id={test_id};ref_id={ref_id}",
    }


def main():
    load_dotenv(ROOT / ".env")
    ee.Initialize(project=os.environ["GEE_PROJECT"])

    cal = load_sq1c_set()
    print(f"SQ1C calibration rows: {len(cal)}")
    assert len(cal) == 43, f"Expected 43 SQ1C rows, got {len(cal)}"
    refs = load_primary_refs()
    print(f"References (PRIMARY): {refs}\n")

    out_rows = []
    for i, row in enumerate(cal, 1):
        print(f"[{i:2d}/{len(cal)}] {row['sub_aoi']} {row['date']} ({row['final_label']}) ... ",
              end="", flush=True)
        try:
            res = process_one(row, refs)
            out_rows.append(res)
            v = res["dbb_faithful"]
            if v is not None:
                print(f"DBB={v:+.4f} n_valid={res['n_valid_pixels']} "
                      f"n_total={res['n_total_pixels']}")
            else:
                print(f"FAIL {res['notes']}")
        except Exception as e:
            print(f"ERROR {e}")
            out_rows.append({**row, "ref_date": refs.get(row["sub_aoi"]),
                             "dbb_faithful": None, "n_valid_pixels": 0,
                             "n_total_pixels": 0, "notes": f"exception:{e}"})

    fieldnames = ["date", "sub_aoi", "final_label", "ai_confidence",
                  "bias_exposed", "ref_date",
                  "dbb_faithful", "n_valid_pixels", "n_total_pixels",
                  "source", "notes"]
    with open(OUT_CSV, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in out_rows:
            r["source"] = "SQ1C"
            w.writerow({k: r.get(k) for k in fieldnames})
    print(f"\nWrote {OUT_CSV}")

    # Validate
    valid_rows = [r for r in out_rows if r["dbb_faithful"] is not None]
    print(f"\nValid rows: {len(valid_rows)} / {len(out_rows)}")
    invariant_violations = sum(
        1 for r in valid_rows
        if r["n_valid_pixels"] > r["n_total_pixels"]
    )
    print(f"n_valid > n_total violations: {invariant_violations}")
    assert invariant_violations == 0

    # Median by (aoi, label)
    from collections import defaultdict
    import statistics
    buckets = defaultdict(list)
    for r in valid_rows:
        buckets[(r["sub_aoi"], r["final_label"])].append(r["dbb_faithful"])
    print(f"\n{'sub_aoi':<20s} {'label':<12s} {'n':>3s} {'median':>9s}")
    for (aoi, lab), vals in sorted(buckets.items()):
        print(f"{aoi:<20s} {lab:<12s} {len(vals):>3d} {statistics.median(vals):>9.4f}")


if __name__ == "__main__":
    main()

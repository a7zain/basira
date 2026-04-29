"""
SQ1D Part B — Faithful Lolli 2024 DBB on the 30-scene calibration set.

Implements the formula in research/dust-honesty/docs/sq1d_lolli_formula.md:

              1     ρ_k^TOA(test) − ρ̄_k^TOA(ref)
DBB(i,j) = ─── ∑    ─────────────────────────────       k ∈ {2,3,4,11,12}
              5  k         ρ̄_k(L2A ref)

Per-scene scalar = spatial mean of DBB over (valid_test ∩ valid_ref ∩ not_water).

Test side  : COPERNICUS/S2_HARMONIZED (L1C TOA), lowest-cloud scene per
             (calendar-month, sub_aoi). SCL mask from matching L2A.
Reference  : PRIMARY date from sq1d_references.json. Both L1C (numerator)
             and L2A (denominator + SCL + water mask) on the exact date.

Output: research/dust-honesty/data/sq1d_dbb_faithful.csv
"""
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

DATA = ROOT / "research/dust-honesty/data"
REFS_JSON = DATA / "sq1d_references.json"
KSP_CSV = DATA / "sq1d_ksp_relabel.csv"
QID_CSV = DATA / "sq1d_qiddiya_relabel.csv"
DIR_CSV = DATA / "sq1_manual_labels.csv"
OUT_CSV = DATA / "sq1d_dbb_faithful.csv"

BANDS = ["B2", "B3", "B4", "B11", "B12"]
SCALE_M = 20  # see Choice 3 in spec doc
SCALE_DIV = 10000.0

# SCL valid classes (Choice 4): 4 veg, 5 not-veg, 6 water, 7 unclassified, 11 snow.
# Excluded: 0 nodata, 1 saturated/defective, 2 dark, 3 cloud_shadow,
#           8 cloud_med, 9 cloud_high, 10 thin_cirrus.
SCL_VALID = [4, 5, 6, 7, 11]
WATER_RHO12_THRESHOLD = 0.01


def load_calibration_set():
    """Build the 30-row (date, sub_aoi, final_label) list per the spec."""
    rows = []

    with open(KSP_CSV) as f:
        for r in csv.DictReader(f):
            rows.append(
                {"date": r["date"], "sub_aoi": r["sub_aoi"], "final_label": r["final_label"]}
            )

    with open(QID_CSV) as f:
        for r in csv.DictReader(f):
            rows.append(
                {"date": r["date"], "sub_aoi": r["sub_aoi"], "final_label": r["final_label"]}
            )

    with open(DIR_CSV) as f:
        for r in csv.DictReader(f):
            if r["AOI"] == "diriyah_gate":
                rows.append(
                    {"date": r["date"], "sub_aoi": r["AOI"], "final_label": r["label"]}
                )

    return rows


def load_references():
    with open(REFS_JSON) as f:
        cfg = json.load(f)
    return {aoi: meta["primary"]["date"] for aoi, meta in cfg["aois"].items()}


def month_bounds(yyyy_mm):
    y, m = map(int, yyyy_mm.split("-"))
    start = f"{y:04d}-{m:02d}-01"
    if m == 12:
        end = f"{y + 1:04d}-01-01"
    else:
        end = f"{y:04d}-{m + 1:02d}-01"
    return start, end


def day_bounds(yyyy_mm_dd):
    import datetime as dt
    d = dt.date.fromisoformat(yyyy_mm_dd)
    return yyyy_mm_dd, (d + dt.timedelta(days=1)).isoformat()


def best_l1c_image(geom, start, end):
    """Lowest-cloud L1C scene over geom in [start, end). None if empty."""
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


def matching_l2a(l1c_img, geom):
    """L2A scene matching the same granule as l1c_img, or lowest-cloud
    L2A on the same date over geom as fallback."""
    sys_idx = l1c_img.get("system:index").getInfo()
    date = ee.Date(l1c_img.get("system:time_start"))
    start = date.format("YYYY-MM-dd").getInfo()
    end = date.advance(1, "day").format("YYYY-MM-dd").getInfo()
    sr = ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED").filterDate(start, end).filterBounds(geom)
    # match on system:index (S2_SR shares granule IDs with S2 since 2017)
    exact = sr.filter(ee.Filter.eq("system:index", sys_idx))
    if exact.size().getInfo() >= 1:
        return exact.first()
    if sr.size().getInfo() >= 1:
        return sr.sort("CLOUDY_PIXEL_PERCENTAGE").first()
    return None


def scl_valid_mask(l2a_img):
    scl = l2a_img.select("SCL")
    mask = scl.eq(SCL_VALID[0])
    for v in SCL_VALID[1:]:
        mask = mask.Or(scl.eq(v))
    return mask


def reflectance(img):
    """Divide selected bands by 10000 → [0,1] reflectance float."""
    return img.select(BANDS).toFloat().divide(SCALE_DIV)


def compute_dbb(test_l1c, ref_l1c, ref_l2a, test_l2a, geom):
    """Return dict with dbb_faithful (scene mean), n_valid_pixels, n_total_pixels."""
    rho_test_toa = reflectance(test_l1c)
    rho_ref_toa = reflectance(ref_l1c)
    rho_ref_sr = reflectance(ref_l2a)

    # Per-band normalized differential
    diff = rho_test_toa.subtract(rho_ref_toa)
    # avoid divide-by-zero / negative SR
    sr_positive = rho_ref_sr.gt(0).reduce(ee.Reducer.min())  # 1 iff all 5 bands positive
    per_band = diff.divide(rho_ref_sr)  # band-wise division, only valid where sr_positive

    # DBB per pixel = mean across the 5 bands
    dbb_pixel = per_band.reduce(ee.Reducer.mean()).rename("dbb")

    # Masks
    valid_test = scl_valid_mask(test_l2a)
    valid_ref = scl_valid_mask(ref_l2a)
    not_water = rho_ref_sr.select("B12").gte(WATER_RHO12_THRESHOLD)
    valid = valid_test.And(valid_ref).And(not_water).And(sr_positive)

    dbb_masked = dbb_pixel.updateMask(valid)

    stats = dbb_masked.reduceRegion(
        reducer=ee.Reducer.mean().combine(ee.Reducer.count(), sharedInputs=True),
        geometry=geom,
        scale=SCALE_M,
        maxPixels=1e9,
        bestEffort=True,
    ).getInfo()

    # total pixels in AOI (pre-mask) at SCALE_M
    total = dbb_pixel.unmask(0).reduceRegion(
        reducer=ee.Reducer.count(),
        geometry=geom,
        scale=SCALE_M,
        maxPixels=1e9,
        bestEffort=True,
    ).getInfo()

    return {
        "dbb_faithful": stats.get("dbb_mean"),
        "n_valid_pixels": stats.get("dbb_count"),
        "n_total_pixels": total.get("dbb"),
    }


def process_one(row, refs):
    sub_aoi = row["sub_aoi"]
    test_ym = row["date"]
    ref_date = refs[sub_aoi]

    bbox = get_bbox(sub_aoi)
    geom = ee.Geometry.Rectangle(list(bbox))

    # --- TEST ---
    t_start, t_end = month_bounds(test_ym)
    test_l1c = best_l1c_image(geom, t_start, t_end)
    if test_l1c is None:
        return {**row, "ref_date": ref_date, "dbb_faithful": None,
                "n_valid_pixels": 0, "n_total_pixels": 0,
                "notes": "no_l1c_test_scene"}
    test_l2a = matching_l2a(test_l1c, geom)
    if test_l2a is None:
        return {**row, "ref_date": ref_date, "dbb_faithful": None,
                "n_valid_pixels": 0, "n_total_pixels": 0,
                "notes": "no_l2a_test_scene"}

    # --- REFERENCE ---
    r_start, r_end = day_bounds(ref_date)
    ref_l1c = best_l1c_image(geom, r_start, r_end)
    if ref_l1c is None:
        return {**row, "ref_date": ref_date, "dbb_faithful": None,
                "n_valid_pixels": 0, "n_total_pixels": 0,
                "notes": "no_l1c_ref_scene"}
    ref_l2a = matching_l2a(ref_l1c, geom)
    if ref_l2a is None:
        return {**row, "ref_date": ref_date, "dbb_faithful": None,
                "n_valid_pixels": 0, "n_total_pixels": 0,
                "notes": "no_l2a_ref_scene"}

    test_id = test_l1c.get("system:index").getInfo()
    ref_id = ref_l1c.get("system:index").getInfo()
    test_date = ee.Date(test_l1c.get("system:time_start")).format("YYYY-MM-dd").getInfo()

    out = compute_dbb(test_l1c, ref_l1c, ref_l2a, test_l2a, geom)

    return {
        **row,
        "ref_date": ref_date,
        "dbb_faithful": out["dbb_faithful"],
        "n_valid_pixels": out["n_valid_pixels"],
        "n_total_pixels": out["n_total_pixels"],
        "notes": f"test_id={test_id};test_date={test_date};ref_id={ref_id}",
    }


def per_aoi_label_summary(rows):
    from collections import defaultdict
    import statistics

    buckets = defaultdict(list)
    for r in rows:
        if r["dbb_faithful"] is None:
            continue
        buckets[(r["sub_aoi"], r["final_label"])].append(r["dbb_faithful"])

    print("\nPer-AOI per-label DBB summary:")
    print(f"{'sub_aoi':<20s} {'label':<12s} {'n':>3s} {'min':>9s} {'median':>9s} {'max':>9s}")
    for (aoi, lab), vals in sorted(buckets.items()):
        print(
            f"{aoi:<20s} {lab:<12s} {len(vals):>3d} "
            f"{min(vals):>9.4f} {statistics.median(vals):>9.4f} {max(vals):>9.4f}"
        )


def main():
    load_dotenv(ROOT / ".env")
    ee.Initialize(project=os.environ["GEE_PROJECT"])

    cal = load_calibration_set()
    assert len(cal) == 30, f"Expected 30 calibration rows, got {len(cal)}"
    refs = load_references()

    print(f"Calibration set: {len(cal)} scenes")
    print(f"References (PRIMARY): {refs}")
    print()

    out_rows = []
    for i, row in enumerate(cal, 1):
        print(f"[{i:2d}/{len(cal)}] {row['sub_aoi']} {row['date']} ({row['final_label']}) ... ", end="", flush=True)
        try:
            res = process_one(row, refs)
            out_rows.append(res)
            v = res["dbb_faithful"]
            print(f"DBB={v:+.4f} n={res['n_valid_pixels']}" if v is not None else f"FAIL {res['notes']}")
        except Exception as e:
            print(f"ERROR {e}")
            out_rows.append({**row, "ref_date": refs.get(row["sub_aoi"]),
                             "dbb_faithful": None, "n_valid_pixels": 0,
                             "n_total_pixels": 0, "notes": f"exception:{e}"})

    fieldnames = ["date", "sub_aoi", "final_label", "ref_date",
                  "dbb_faithful", "n_valid_pixels", "n_total_pixels", "notes"]
    with open(OUT_CSV, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in out_rows:
            w.writerow({k: r.get(k) for k in fieldnames})

    print(f"\nWrote {OUT_CSV}")
    per_aoi_label_summary(out_rows)


if __name__ == "__main__":
    main()

"""
SQ1D Part A.6 — KSP UVAI all-months search.

Find low-aerosol reference candidates over king_salman_park by scanning
TROPOMI UVAI for every cloud-free (<5%) Sentinel-2 L1C scene from
2020-01 through 2026-04.

Output: research/dust-honesty/data/calibration/uvai_ksp_sq1d.csv
"""
import csv
import math
import os
import sys
from pathlib import Path

import ee
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from src.phase1_aois import get_bbox  # noqa: E402

OUT_CSV = ROOT / "research/dust-honesty/data/calibration/uvai_ksp_sq1d.csv"
AOI = "king_salman_park"
START_YM = (2020, 1)
END_YM = (2026, 4)  # inclusive
CLOUD_MAX = 5.0
TROPOMI_SCALE = 1113


def iter_months(start, end):
    y, m = start
    ey, em = end
    while (y, m) <= (ey, em):
        yield y, m
        m += 1
        if m == 13:
            m = 1
            y += 1


def month_range(y, m):
    start = f"{y:04d}-{m:02d}-01"
    if m == 12:
        end = f"{y+1:04d}-01-01"
    else:
        end = f"{y:04d}-{m+1:02d}-01"
    return start, end


def next_day(yyyy_mm_dd):
    import datetime as dt
    return (dt.date.fromisoformat(yyyy_mm_dd) + dt.timedelta(days=1)).isoformat()


def main():
    load_dotenv(ROOT / ".env")
    ee.Initialize(project=os.environ["GEE_PROJECT"])

    bbox = get_bbox(AOI)
    geom = ee.Geometry.Rectangle(list(bbox))

    rows = []
    skipped_no_overpass = 0
    for y, m in iter_months(START_YM, END_YM):
        start, end = month_range(y, m)
        coll = (
            ee.ImageCollection("COPERNICUS/S2_HARMONIZED")
            .filterBounds(geom)
            .filterDate(start, end)
            .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", CLOUD_MAX))
        )
        ids = coll.aggregate_array("system:index").getInfo()
        clouds = coll.aggregate_array("CLOUDY_PIXEL_PERCENTAGE").getInfo()
        times = coll.aggregate_array("system:time_start").getInfo()
        if not ids:
            print(f"  {y:04d}-{m:02d}: 0 scenes")
            continue
        # convert times to dates server-side once
        dates = [
            ee.Date(t).format("YYYY-MM-dd").getInfo() for t in times
        ]
        for pid, cp, dt_str in zip(ids, clouds, dates):
            end_day = next_day(dt_str)
            tcol = (
                ee.ImageCollection("COPERNICUS/S5P/OFFL/L3_AER_AI")
                .filterDate(dt_str, end_day)
                .filterBounds(geom)
                .select("absorbing_aerosol_index")
            )
            n = tcol.size().getInfo()
            if n == 0:
                skipped_no_overpass += 1
                continue
            stats = tcol.mean().reduceRegion(
                reducer=ee.Reducer.mean().combine(
                    ee.Reducer.max(), sharedInputs=True
                ),
                geometry=geom,
                scale=TROPOMI_SCALE,
                maxPixels=1e9,
                bestEffort=True,
            ).getInfo()
            um = stats.get("absorbing_aerosol_index_mean")
            ux = stats.get("absorbing_aerosol_index_max")
            if um is None or ux is None:
                skipped_no_overpass += 1
                continue
            rows.append(
                {
                    "date": dt_str,
                    "l1c_product_id": pid,
                    "cloud_pct": cp,
                    "tropomi_n_images": n,
                    "uvai_mean": um,
                    "uvai_max": ux,
                }
            )
        print(f"  {y:04d}-{m:02d}: {len(ids)} scenes, kept {sum(1 for r in rows if r['date'].startswith(f'{y:04d}-{m:02d}'))}")

    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_CSV, "w", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "date",
                "l1c_product_id",
                "cloud_pct",
                "tropomi_n_images",
                "uvai_mean",
                "uvai_max",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)

    n_total = len(rows)
    n_clean = sum(1 for r in rows if r["uvai_mean"] < 0.3)
    print(f"\nTotal scene-dates with valid UVAI: {n_total}")
    print(f"Skipped (no TROPOMI overpass): {skipped_no_overpass}")
    print(f"Scenes with uvai_mean < 0.3 (genuinely clean): {n_clean}")

    # Stop rules
    if n_total < 30:
        print("\nSTOP: fewer than 30 valid TROPOMI overpasses. Halt.")
        return
    rows_sorted = sorted(rows, key=lambda r: r["uvai_mean"])
    lowest = rows_sorted[0]["uvai_mean"]
    if lowest > 0.5:
        print(f"\nSTOP: lowest uvai_mean across all months is {lowest:.4f} > 0.5. Halt — KSP may not have a clean atmospheric column in this window.")
        # still print top 10 for the record

    print("\n=== TOP 10 lowest uvai_mean across 2020-01 through 2026-04 ===")
    print(f"  {'rk':>2} {'date':10} {'cloud%':>7} {'n':>2} {'uvai_mean':>10} {'uvai_max':>10}  product_id")
    for i, r in enumerate(rows_sorted[:10]):
        print(
            f"  {i+1:>2} {r['date']:10} {r['cloud_pct']:>7.2f} {r['tropomi_n_images']:>2} "
            f"{r['uvai_mean']:>10.4f} {r['uvai_max']:>10.4f}  {r['l1c_product_id']}"
        )
    print(f"\nWrote {n_total} rows → {OUT_CSV}")


if __name__ == "__main__":
    main()

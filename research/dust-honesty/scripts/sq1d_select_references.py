"""
SQ1D Part A — select reference scene candidates per AOI.

For each AOI, take all 'clean'-labeled months from manual_labels_sq1.csv,
query GEE COPERNICUS/S2_HARMONIZED (L1C) for matching date×bbox, and rank
the top 5 cleanest L1C scenes per AOI by CLOUDY_PIXEL_PERCENTAGE.

Output: research/dust-honesty/data/calibration/_archive/reference_candidates_sq1d.csv
"""
import csv
import os
import sys
from pathlib import Path

import ee
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from src.phase1_aois import get_bbox  # noqa: E402

LABELS_CSV = ROOT / "research/dust-honesty/data/calibration/manual_labels_sq1.csv"
OUT_CSV = ROOT / "research/dust-honesty/data/calibration/_archive/reference_candidates_sq1d.csv"
TOP_N = 5


def month_range(yyyy_mm: str):
    y, m = yyyy_mm.split("-")
    y, m = int(y), int(m)
    start = f"{y:04d}-{m:02d}-01"
    if m == 12:
        end = f"{y+1:04d}-01-01"
    else:
        end = f"{y:04d}-{m+1:02d}-01"
    return start, end


def main():
    load_dotenv(ROOT / ".env")
    ee.Initialize(project=os.environ["GEE_PROJECT"])

    # Load clean rows by AOI
    clean_by_aoi = {}
    with open(LABELS_CSV) as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row.get("label", "").strip() == "clean":
                clean_by_aoi.setdefault(row["AOI"], []).append(row["date"])

    rows_out = []
    for aoi, months in clean_by_aoi.items():
        bbox = get_bbox(aoi)
        geom = ee.Geometry.Rectangle(list(bbox))
        candidates = []
        for ym in sorted(months):
            start, end = month_range(ym)
            coll = (
                ee.ImageCollection("COPERNICUS/S2_HARMONIZED")
                .filterBounds(geom)
                .filterDate(start, end)
            )
            info = coll.aggregate_array("system:index").getInfo()
            cloud_pcts = coll.aggregate_array("CLOUDY_PIXEL_PERCENTAGE").getInfo()
            dates = coll.aggregate_array("system:time_start").getInfo()
            for pid, cp, t in zip(info, cloud_pcts, dates):
                candidates.append(
                    {
                        "aoi": aoi,
                        "month": ym,
                        "date": ee.Date(t).format("YYYY-MM-dd").getInfo(),
                        "l1c_cloud_pct": cp,
                        "l1c_product_id": pid,
                    }
                )
            print(f"  {aoi} {ym}: {len(info)} L1C scenes")
        candidates.sort(key=lambda r: (r["l1c_cloud_pct"] if r["l1c_cloud_pct"] is not None else 999))
        top = candidates[:TOP_N]
        rows_out.extend(top)
        print(f"\n=== {aoi} top {TOP_N} ===")
        for r in top:
            print(f"  {r['date']}  cloud={r['l1c_cloud_pct']:.2f}%  {r['l1c_product_id']}")
        print()

    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_CSV, "w", newline="") as f:
        writer = csv.DictWriter(
            f, fieldnames=["aoi", "month", "date", "l1c_cloud_pct", "l1c_product_id"]
        )
        writer.writeheader()
        writer.writerows(rows_out)
    print(f"Wrote {len(rows_out)} rows → {OUT_CSV}")


if __name__ == "__main__":
    main()

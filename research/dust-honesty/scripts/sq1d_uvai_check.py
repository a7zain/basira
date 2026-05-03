"""
SQ1D Part A.5 — TROPOMI UVAI cross-check on reference candidates.

For each candidate scene, fetch TROPOMI OFFL UVAI on the same date and
reduce mean/max over the AOI bbox at 1113m scale (TROPOMI native).

Output: research/dust-honesty/data/calibration/_archive/reference_uvai_sq1d.csv
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

IN_CSV = ROOT / "research/dust-honesty/data/calibration/_archive/reference_candidates_sq1d.csv"
OUT_CSV = ROOT / "research/dust-honesty/data/calibration/_archive/reference_uvai_sq1d.csv"
TROPOMI_SCALE = 1113


def next_day(yyyy_mm_dd: str) -> str:
    import datetime as dt
    d = dt.date.fromisoformat(yyyy_mm_dd) + dt.timedelta(days=1)
    return d.isoformat()


def main():
    load_dotenv(ROOT / ".env")
    ee.Initialize(project=os.environ["GEE_PROJECT"])

    rows = list(csv.DictReader(open(IN_CSV)))
    out = []

    for row in rows:
        aoi = row["aoi"]
        date = row["date"]
        bbox = get_bbox(aoi)
        geom = ee.Geometry.Rectangle(list(bbox))
        end = next_day(date)

        coll = (
            ee.ImageCollection("COPERNICUS/S5P/OFFL/L3_AER_AI")
            .filterDate(date, end)
            .filterBounds(geom)
            .select("absorbing_aerosol_index")
        )
        n = coll.size().getInfo()

        if n == 0:
            uvai_mean = float("nan")
            uvai_max = float("nan")
        else:
            mean_img = coll.mean()
            stats = mean_img.reduceRegion(
                reducer=ee.Reducer.mean().combine(ee.Reducer.max(), sharedInputs=True),
                geometry=geom,
                scale=TROPOMI_SCALE,
                maxPixels=1e9,
                bestEffort=True,
            ).getInfo()
            uvai_mean = stats.get("absorbing_aerosol_index_mean")
            uvai_max = stats.get("absorbing_aerosol_index_max")
            if uvai_mean is None:
                uvai_mean = float("nan")
            if uvai_max is None:
                uvai_max = float("nan")

        out.append(
            {
                "aoi": aoi,
                "date": date,
                "l1c_cloud_pct": row["l1c_cloud_pct"],
                "l1c_product_id": row["l1c_product_id"],
                "tropomi_n_images": n,
                "uvai_mean": uvai_mean,
                "uvai_max": uvai_max,
            }
        )
        print(
            f"  {aoi} {date} n={n} "
            f"uvai_mean={uvai_mean:.4f} uvai_max={uvai_max:.4f}"
            if n > 0
            else f"  {aoi} {date} n=0 (no overpass)"
        )

    # Stop rule
    no_overpass = sum(1 for r in out if r["tropomi_n_images"] == 0)
    print(f"\nNo-overpass count: {no_overpass}/{len(out)}")
    if no_overpass > 5:
        print("STOP RULE: more than 5 candidates lack TROPOMI overpass.")
        # still write what we have
    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_CSV, "w", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "aoi",
                "date",
                "l1c_cloud_pct",
                "l1c_product_id",
                "tropomi_n_images",
                "uvai_mean",
                "uvai_max",
            ],
        )
        writer.writeheader()
        writer.writerows(out)
    print(f"\nWrote {len(out)} rows → {OUT_CSV}\n")

    # Ranked summary per AOI
    by_aoi = {}
    for r in out:
        by_aoi.setdefault(r["aoi"], []).append(r)

    for aoi, rs in by_aoi.items():
        def sort_key(r):
            v = r["uvai_mean"]
            no_op = r["tropomi_n_images"] == 0
            if no_op or (isinstance(v, float) and math.isnan(v)):
                return (1, 0)
            return (0, v)

        rs.sort(key=sort_key)
        winner_idx = next(
            (i for i, r in enumerate(rs) if r["tropomi_n_images"] > 0
             and not (isinstance(r["uvai_mean"], float) and math.isnan(r["uvai_mean"]))),
            None,
        )
        print(f"=== {aoi} (ranked by uvai_mean asc) ===")
        print(
            f"  {'rk':>2} {'date':10} {'cloud%':>7} {'n':>2} {'uvai_mean':>10} "
            f"{'uvai_max':>10}  product_id  win"
        )
        for i, r in enumerate(rs):
            tag = "  <-- winner" if i == winner_idx else ""
            cp = float(r["l1c_cloud_pct"])
            um = r["uvai_mean"]
            ux = r["uvai_max"]
            um_s = f"{um:>10.4f}" if isinstance(um, float) and not math.isnan(um) else f"{'NaN':>10}"
            ux_s = f"{ux:>10.4f}" if isinstance(ux, float) and not math.isnan(ux) else f"{'NaN':>10}"
            print(
                f"  {i+1:>2} {r['date']:10} {cp:>7.2f} {r['tropomi_n_images']:>2} "
                f"{um_s} {ux_s}  {r['l1c_product_id']}{tag}"
            )
        print()


if __name__ == "__main__":
    main()

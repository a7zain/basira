"""
SQ1D — Diriyah all-months UVAI pull via GEE COPERNICUS/S5P/OFFL/L3_AER_AI.

CDSE/Sentinel Hub has been 503 since 2026-04-28 (post-network-upgrade
residual instability). To unblock SQ1C, Diriyah's all-months UVAI pull
runs against GEE's TROPOMI OFFL L3 product (the same underlying ESA
Sentinel-5P L2 AER_AI gridded to L3) — same source family as the
existing KSP and Qiddiya all-months CSVs (which were also already from
GEE per sq1d_ksp_uvai_search.py / sq1d_qiddiya_uvai_search.py;
CLAUDE.md's "SH on CDSE" framing for UVAI predates the all-months
batch work; this is reframed in SQ1C protocol §9).

Pipeline mirrors sq1d_ksp_uvai_search.py: iterate calendar months,
query S2_HARMONIZED with cloud<5 to get the candidate scene-dates,
then for each scene-date query TROPOMI per-day mean over the AOI bbox.
Naive per-image iteration over the L3 collection is intractable
(L3 has ~14 orbital strips per day worldwide × 6 years = 32 k images,
all of which "intersect" any small AOI; reduceRegion across that many
is server-side hard-limited at 5 k elements). The S2-conditioned
pattern lands on ~300-400 rows for a small inland AOI, matching KSP
(320) and Qiddiya (302).

Schema mirrors uvai_ksp_sq1d.csv with one extra column:
  data_source = "GEE_OFFL_L3"

Output: research/dust-honesty/data/calibration/uvai_diriyah_sq1d.csv
"""
from __future__ import annotations

import csv
import os
import sys
from pathlib import Path

import ee
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from src.phase1_aois import get_bbox  # noqa: E402

OUT_CSV = ROOT / "research/dust-honesty/data/calibration/uvai_diriyah_sq1d.csv"
AOI = "diriyah_gate"
START_YM = (2020, 1)
END_YM = (2026, 3)   # inclusive, mirrors KSP/Qiddiya (2026-04 included → here 2026-03)
CLOUD_MAX = 5.0
TROPOMI_SCALE = 1113.2

FIELDS = [
    "date",
    "l1c_product_id",
    "cloud_pct",
    "tropomi_n_images",
    "uvai_mean",
    "uvai_max",
    "data_source",
]


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
        end = f"{y + 1:04d}-01-01"
    else:
        end = f"{y:04d}-{m + 1:02d}-01"
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
        dates = [ee.Date(t).format("YYYY-MM-dd").getInfo() for t in times]

        kept_this_month = 0
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
                reducer=ee.Reducer.mean().combine(ee.Reducer.max(), sharedInputs=True),
                geometry=geom,
                scale=TROPOMI_SCALE,
                maxPixels=1e9,
                bestEffort=False,
            ).getInfo()
            um = stats.get("absorbing_aerosol_index_mean")
            ux = stats.get("absorbing_aerosol_index_max")
            if um is None or ux is None:
                skipped_no_overpass += 1
                continue
            rows.append({
                "date": dt_str,
                "l1c_product_id": pid,
                "cloud_pct": cp,
                "tropomi_n_images": n,
                "uvai_mean": um,
                "uvai_max": ux,
                "data_source": "GEE_OFFL_L3",
            })
            kept_this_month += 1
        print(f"  {y:04d}-{m:02d}: {len(ids)} scenes, kept {kept_this_month}")

    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_CSV, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        for r in rows:
            w.writerow(r)
    n_total = len(rows)
    print(f"\nTotal scene-dates with valid UVAI: {n_total}")
    print(f"Skipped (no TROPOMI overpass): {skipped_no_overpass}")

    # ---- validation ----
    if not (100 <= n_total <= 700):
        print(f"\nSTOP: row count {n_total} outside plausibility window [100, 700]. "
              f"KSP=320, Qiddiya=302; investigate.")
        sys.exit(2)
    dates = [r["date"] for r in rows]
    earliest = min(dates); latest = max(dates)
    if not (earliest >= "2020-01-01"):
        print(f"\nSTOP: earliest date {earliest} < 2020-01-01"); sys.exit(3)
    if not (latest <= "2026-03-31"):
        print(f"\nSTOP: latest date {latest} > 2026-03-31"); sys.exit(4)
    years_present = sorted({d[:4] for d in dates})
    expected_years = {"2020", "2021", "2022", "2023", "2024", "2025"}
    missing = expected_years - set(years_present)
    if missing:
        print(f"\nSTOP: missing rows for years {sorted(missing)}"); sys.exit(5)
    means = sorted(r["uvai_mean"] for r in rows)
    median = means[len(means) // 2]
    if not (-5 <= median <= 5):
        print(f"\nSTOP: median UVAI {median:.4f} outside [-5, +5] sanity range")
        sys.exit(6)
    print(f"\nValidation OK:")
    print(f"  rows: {n_total}")
    print(f"  date range: [{earliest}, {latest}]")
    print(f"  years present: {years_present}")
    print(f"  uvai median: {median:+.4f}  range [{means[0]:+.4f}, {means[-1]:+.4f}]")
    print(f"\nWrote {n_total} rows → {OUT_CSV}")


if __name__ == "__main__":
    main()

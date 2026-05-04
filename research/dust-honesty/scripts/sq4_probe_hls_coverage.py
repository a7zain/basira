"""
SQ4 — RECON ONLY. Probe HLSS30 v002 coverage on the SQ3 pair dates.

R1: per-AOI coverage rate (n_covered / n_unique_dates).
R4: confirm Fmask QA band presence on a sample image.

HARD HALT (exit code 2) if any AOI < 50% coverage.

Output:
  research/dust-honesty/data/cross_correction/coverage_probe_sq4.csv

No NDVI compute here — just an existence check on
NASA/HLS/HLSS30/v002 filtered to AOI bbox + date ±1 day window.
"""
from __future__ import annotations

import csv
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
OUT_CSV = DATA / "cross_correction" / "coverage_probe_sq4.csv"

HLS_S30 = "NASA/HLS/HLSS30/v002"
COVERAGE_FLOOR = 0.50  # halt threshold per AOI
DATE_WINDOW_DAYS = 1   # ±1d for orbit matching


def unique_aoi_dates():
    """Return dict aoi -> sorted list of unique date strings from sq3_ndvi_bias."""
    pool = defaultdict(set)
    with open(PAIRS_CSV) as f:
        for r in csv.DictReader(f):
            pool[r["aoi"]].add(r["fired_date"])
            pool[r["aoi"]].add(r["neighbor_date"])
    return {aoi: sorted(dates) for aoi, dates in pool.items()}


def hls_size(aoi, date_str, geom):
    """Return scene count for HLSS30 over geom within ±DATE_WINDOW_DAYS."""
    d = date.fromisoformat(date_str)
    start = (d - timedelta(days=DATE_WINDOW_DAYS)).isoformat()
    end = (d + timedelta(days=DATE_WINDOW_DAYS + 1)).isoformat()  # end exclusive
    coll = (
        ee.ImageCollection(HLS_S30)
        .filterBounds(geom)
        .filterDate(start, end)
    )
    return int(coll.size().getInfo())


def fmask_present_check():
    """R4: pick any HLSS30 scene over Riyadh and confirm Fmask band exists."""
    geom = ee.Geometry.Rectangle(list(get_bbox("king_salman_park")))
    coll = (
        ee.ImageCollection(HLS_S30)
        .filterBounds(geom)
        .filterDate("2024-01-01", "2024-04-01")
    )
    n = coll.size().getInfo()
    if n == 0:
        print("R4 WARN: no HLSS30 scene over KSP in 2024 Q1 to inspect")
        return None
    img = coll.first()
    bands = img.bandNames().getInfo()
    has_fmask = "Fmask" in bands
    print(f"R4: HLSS30 sample bands = {bands}")
    print(f"R4: Fmask present = {has_fmask}")
    return has_fmask


def main():
    load_dotenv(ROOT / ".env")
    ee.Initialize(project=os.environ["GEE_PROJECT"])
    print("SQ4 R1+R4 — HLSS30 coverage probe")
    print(f"  Asset: {HLS_S30}")
    print(f"  Window: ±{DATE_WINDOW_DAYS} day(s)")
    print(f"  Halt threshold: {int(COVERAGE_FLOOR*100)}% per AOI")
    print()

    print("R4: Fmask presence check ...")
    has_fmask = fmask_present_check()
    print()

    aoi_dates = unique_aoi_dates()
    print(f"R1: total unique (aoi, date) tuples: "
          f"{sum(len(v) for v in aoi_dates.values())}")
    for aoi, dates in aoi_dates.items():
        print(f"  {aoi}: {len(dates)} unique dates")
    print()

    rows = []
    summary = []
    for aoi, dates in aoi_dates.items():
        bbox = get_bbox(aoi)
        geom = ee.Geometry.Rectangle(list(bbox))
        n_covered = 0
        for d in dates:
            n = hls_size(aoi, d, geom)
            covered = n > 0
            if covered:
                n_covered += 1
            rows.append({
                "aoi": aoi,
                "pair_date": d,
                "hls_scene_count": n,
                "covered": covered,
            })
        rate = n_covered / len(dates) if dates else 0.0
        summary.append((aoi, n_covered, len(dates), rate))
        print(f"  {aoi}: {n_covered}/{len(dates)} = {rate*100:.1f}%")

    print()
    with open(OUT_CSV, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["aoi", "pair_date", "hls_scene_count", "covered"])
        w.writeheader()
        for r in rows:
            w.writerow(r)
    print(f"Wrote {OUT_CSV} ({len(rows)} rows)")
    print()

    # Halt check
    failures = [(aoi, n, total, rate) for (aoi, n, total, rate) in summary
                if rate < COVERAGE_FLOOR]
    if failures:
        print("HARD HALT: HLS coverage below floor in:")
        for aoi, n, total, rate in failures:
            print(f"  {aoi}: {n}/{total} = {rate*100:.1f}% < "
                  f"{int(COVERAGE_FLOOR*100)}%")
        sys.exit(2)

    print(f"R1 PASS: all AOIs ≥ {int(COVERAGE_FLOOR*100)}% coverage.")
    if has_fmask:
        print("R4 PASS: Fmask band present.")
    else:
        print("R4 FLAG: Fmask absent on sampled scene — document in §5.")


if __name__ == "__main__":
    main()

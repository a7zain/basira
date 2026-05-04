"""
SQ4B — RECON ONLY. Probe HLSL30 v002 coverage on SQ3 pair dates.

R1: per-AOI L30 coverage rate (n_covered / n_unique_dates).
R4: confirm Fmask + B4 + B5 on L30; confirm B4 + B8 + B8A on S30.

Uses coll.mosaic() pattern (parity with SQ4's locked pattern).

HARD HALT (exit code 2) if any AOI < 50% L30 coverage.

Output:
  research/dust-honesty/data/cross_correction/l30_coverage_probe_sq4b.csv
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
OUT_CSV = DATA / "cross_correction" / "l30_coverage_probe_sq4b.csv"

HLS_S30 = "NASA/HLS/HLSS30/v002"
HLS_L30 = "NASA/HLS/HLSL30/v002"
COVERAGE_FLOOR = 0.50
DATE_WINDOW_DAYS = 1


def unique_aoi_dates():
    pool = defaultdict(set)
    with open(PAIRS_CSV) as f:
        for r in csv.DictReader(f):
            pool[r["aoi"]].add(r["fired_date"])
            pool[r["aoi"]].add(r["neighbor_date"])
    return {aoi: sorted(dates) for aoi, dates in pool.items()}


def l30_size(date_str, geom):
    d = date.fromisoformat(date_str)
    start = (d - timedelta(days=DATE_WINDOW_DAYS)).isoformat()
    end = (d + timedelta(days=DATE_WINDOW_DAYS + 1)).isoformat()
    coll = (
        ee.ImageCollection(HLS_L30)
        .filterBounds(geom)
        .filterDate(start, end)
    )
    return int(coll.size().getInfo())


def band_check():
    """R4: report bands actually exposed by GEE for both S30 and L30."""
    geom = ee.Geometry.Rectangle(list(get_bbox("king_salman_park")))
    s30 = (ee.ImageCollection(HLS_S30).filterBounds(geom)
           .filterDate("2024-01-01", "2024-04-01").first())
    l30 = (ee.ImageCollection(HLS_L30).filterBounds(geom)
           .filterDate("2024-01-01", "2024-04-01").first())
    s30_bands = s30.bandNames().getInfo() if s30 else []
    l30_bands = l30.bandNames().getInfo() if l30 else []
    print(f"R4: S30 bands = {s30_bands}")
    print(f"R4: L30 bands = {l30_bands}")
    needs_s30 = ["B4", "B8", "B8A", "Fmask"]
    needs_l30 = ["B4", "B5", "Fmask"]
    s30_missing = [b for b in needs_s30 if b not in s30_bands]
    l30_missing = [b for b in needs_l30 if b not in l30_bands]
    if s30_missing:
        print(f"R4 FAIL: S30 missing required bands {s30_missing}")
    if l30_missing:
        print(f"R4 FAIL: L30 missing required bands {l30_missing}")
    return (not s30_missing) and (not l30_missing)


def main():
    load_dotenv(ROOT / ".env")
    ee.Initialize(project=os.environ["GEE_PROJECT"])
    print("SQ4B R1+R4 — HLSL30 coverage probe + band check")
    print(f"  L30 asset: {HLS_L30}")
    print(f"  S30 asset: {HLS_S30}")
    print(f"  Window: ±{DATE_WINDOW_DAYS} day(s)")
    print(f"  Halt threshold: {int(COVERAGE_FLOOR*100)}% per AOI")
    print()

    print("R4: band-name check ...")
    bands_ok = band_check()
    print()

    aoi_dates = unique_aoi_dates()
    n_total = sum(len(v) for v in aoi_dates.values())
    print(f"R1: total unique (aoi, date) tuples: {n_total}")
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
            n = l30_size(d, geom)
            covered = n > 0
            if covered:
                n_covered += 1
            rows.append({
                "aoi": aoi, "pair_date": d,
                "l30_scene_count": n, "covered": covered,
            })
        rate = n_covered / len(dates) if dates else 0.0
        summary.append((aoi, n_covered, len(dates), rate))
        print(f"  {aoi}: {n_covered}/{len(dates)} = {rate*100:.1f}%")

    print()
    with open(OUT_CSV, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["aoi", "pair_date", "l30_scene_count", "covered"])
        w.writeheader()
        for r in rows:
            w.writerow(r)
    print(f"Wrote {OUT_CSV} ({len(rows)} rows)")
    print()

    failures = [(aoi, n, total, rate) for (aoi, n, total, rate) in summary
                if rate < COVERAGE_FLOOR]
    if failures:
        print("HARD HALT: L30 coverage below floor in:")
        for aoi, n, total, rate in failures:
            print(f"  {aoi}: {n}/{total} = {rate*100:.1f}%")
        sys.exit(2)

    print(f"R1 PASS: all AOIs ≥ {int(COVERAGE_FLOOR*100)}% L30 coverage.")
    if bands_ok:
        print("R4 PASS: S30 + L30 expose all required bands.")
    else:
        print("R4 FAIL: missing bands — see log; do not proceed to build.")
        sys.exit(2)


if __name__ == "__main__":
    main()

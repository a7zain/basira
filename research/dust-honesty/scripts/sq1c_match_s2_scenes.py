"""
SQ1C — match S2 L2A scenes to UVAI-anchored candidates.

For each row in each sq1c_<aoi>_positive_candidates.csv, search GEE
COPERNICUS/S2_SR_HARMONIZED for scenes intersecting the AOI bbox within
±3 days of the UVAI date. Filter by CLOUDY_PIXEL_PERCENTAGE ≤ 20.0
(tighter than the protocol's earlier ≤30 — high-UVAI candidates often
carry moderate cloud, and we want the labeler to see dust signal not
cloud cover). Pick the smallest |date_offset|; ties broken by lowest
cloud_pct.

In-place extension: append columns to the existing CSVs:
    s2_acquisition_date, s2_system_index, s2_cloud_pct,
    s2_date_offset_days, match_status

match_status ∈ {matched | no_s2_match | high_cloud_skip}.

Halt-condition: any AOI with <10 matched candidates → STOP.
"""
from __future__ import annotations

import csv
import datetime as dt
import os
import sys
from pathlib import Path

import ee
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from src.phase1_aois import get_bbox  # noqa: E402

DATA = ROOT / "research/dust-honesty/data"
AOIS = ["king_salman_park", "qiddiya_core", "diriyah_gate"]
CANDS = {a: DATA / f"sq1c_{a}_positive_candidates.csv" for a in AOIS}

CLOUD_MAX = 20.0
WINDOW_DAYS = 3
MIN_MATCHED_PER_AOI = 10

NEW_COLS = [
    "s2_acquisition_date", "s2_system_index",
    "s2_cloud_pct", "s2_date_offset_days", "match_status",
]


def find_s2_scene(geom, target_date):
    """Return (acq_date, sys_idx, cloud_pct, offset_days, status) for the
    best match within ±WINDOW_DAYS at cloud≤CLOUD_MAX, else a status row."""
    target = dt.date.fromisoformat(target_date)
    win_start = (target - dt.timedelta(days=WINDOW_DAYS)).isoformat()
    win_end = (target + dt.timedelta(days=WINDOW_DAYS + 1)).isoformat()

    coll = (
        ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
        .filterBounds(geom)
        .filterDate(win_start, win_end)
    )
    n = coll.size().getInfo()
    if n == 0:
        return ("", "", "", "", "no_s2_match")

    ids = coll.aggregate_array("system:index").getInfo()
    clouds = coll.aggregate_array("CLOUDY_PIXEL_PERCENTAGE").getInfo()
    times = coll.aggregate_array("system:time_start").getInfo()
    cands = []
    for sid, cp, t in zip(ids, clouds, times):
        adate = dt.datetime.utcfromtimestamp(t / 1000).date()
        offset = abs((adate - target).days)
        cands.append((offset, float(cp), adate.isoformat(), sid))

    # filter by cloud
    eligible = [c for c in cands if c[1] <= CLOUD_MAX]
    if not eligible:
        # Surface info about the closest scene we rejected
        closest = min(cands, key=lambda c: (c[0], c[1]))
        return ("", "", f"{closest[1]:.4f}", str(closest[0]), "high_cloud_skip")

    # smallest |offset|, tie-break on cloud
    eligible.sort(key=lambda c: (c[0], c[1]))
    offset, cp, adate, sid = eligible[0]
    return (adate, sid, f"{cp:.4f}", str(offset), "matched")


def process_aoi(aoi):
    path = CANDS[aoi]
    with open(path) as f:
        rows = list(csv.DictReader(f))
        existing_fields = list(rows[0].keys()) if rows else []

    bbox = get_bbox(aoi)
    geom = ee.Geometry.Rectangle(list(bbox))

    print(f"\n=== {aoi} ({len(rows)} candidates) ===")
    out_rows = []
    n_matched = n_no_match = n_high_cloud = 0
    offsets = []
    for r in rows:
        target = r["date"]
        adate, sid, cp, offset, status = find_s2_scene(geom, target)
        if status == "matched":
            n_matched += 1
            offsets.append(int(offset))
        elif status == "no_s2_match":
            n_no_match += 1
        else:
            n_high_cloud += 1
        new_r = {**r,
                 "s2_acquisition_date": adate,
                 "s2_system_index": sid,
                 "s2_cloud_pct": cp,
                 "s2_date_offset_days": offset,
                 "match_status": status}
        out_rows.append(new_r)
        print(f"  rank={r['rank']:>2} uvai_date={target} -> "
              f"{status:<16s}  acq={adate}  cloud={cp}  offset={offset}")

    # write back, with extra columns
    fields = existing_fields + [c for c in NEW_COLS if c not in existing_fields]
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for nr in out_rows:
            w.writerow({k: nr.get(k, "") for k in fields})

    mean_off = sum(offsets) / len(offsets) if offsets else 0.0
    max_off = max(offsets) if offsets else 0
    print(f"  matched={n_matched}  no_match={n_no_match}  "
          f"high_cloud_skip={n_high_cloud}  mean|off|={mean_off:.2f}  max|off|={max_off}")
    return {
        "aoi": aoi, "n_matched": n_matched, "n_no_match": n_no_match,
        "n_high_cloud_skip": n_high_cloud,
        "mean_abs_offset": mean_off, "max_abs_offset": max_off,
    }


def main():
    load_dotenv(ROOT / ".env")
    ee.Initialize(project=os.environ["GEE_PROJECT"])

    print(f"S2 match params: window=±{WINDOW_DAYS}d, cloud≤{CLOUD_MAX}%")

    summaries = []
    for aoi in AOIS:
        summaries.append(process_aoi(aoi))

    print("\n=== Summary ===")
    print(f"{'aoi':<22s} {'matched':>8s} {'no_match':>9s} {'high_cloud':>11s} "
          f"{'mean|off|':>10s} {'max|off|':>9s}")
    halt = []
    for s in summaries:
        print(f"  {s['aoi']:<20s} {s['n_matched']:>8d} {s['n_no_match']:>9d} "
              f"{s['n_high_cloud_skip']:>11d} {s['mean_abs_offset']:>10.2f} "
              f"{s['max_abs_offset']:>9d}")
        if s["n_matched"] < MIN_MATCHED_PER_AOI:
            halt.append(s["aoi"])

    if halt:
        print(f"\nHALT: {halt} have <{MIN_MATCHED_PER_AOI} matched candidates. "
              f"Insufficient n for V3/V4 scope. Investigate before render.")
        sys.exit(2)

    total_matched = sum(s["n_matched"] for s in summaries)
    print(f"\nTotal matched candidates ready for render: {total_matched}")


if __name__ == "__main__":
    main()

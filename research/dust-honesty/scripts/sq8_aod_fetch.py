"""
SQ8 — fetch reanalysis AOD per AOI per SQ2 manifest date.

R1 confirmed no AERONET station within 500km of Riyadh during the
SQ2 window (Solar_Village dead 2015-10-12, Bahrain dead 2007-03-06,
UAE cluster ~750-800km outside 500km outer ring). SQ8 retargets to
reanalysis-AOD primary; KAUST Thuwal AERONET (~820km, coastal) becomes
deferred SQ8B per CLAUDE.md commitment reconciliation.

Inputs:
  research/dust-honesty/data/operational/manifest_operational_sq2.csv (228 rows)

Outputs:
  research/dust-honesty/data/sq8_aod_per_scene.csv
  columns: aoi, acquisition_date, merra2_duexttau_550, cams_total_aod_550,
           merra2_n_images_used, cams_n_images_used,
           merra2_window_min_utc, merra2_window_max_utc,
           cams_window_min_utc, cams_window_max_utc

Sources:
  Primary: NASA/GSFC/MERRA/aer/2 band DUEXTTAU (dust extinction at 550nm).
           Hourly assimilated reanalysis. Mechanistic match to TROPOMI
           UVAI (absorbing-aerosol, dust-dominated at Riyadh) and V4 (DBB
           targets dust optical thickness).
  Cross:   ECMWF/CAMS/NRT band total_aerosol_optical_depth_at_550nm_surface.
           Hourly forecast (multiple lead times overlap at same validity
           time) — total aerosol mix, not dust-specific.

Temporal matching:
  S2 over Riyadh acquires roughly 07:00–07:50 UTC. We use a fixed
  07:30 UTC anchor per acquisition date and pull reanalysis images
  with system:time_start within a per-source window of that anchor:
    MERRA-2: ±60min  (genuinely hourly assimilated reanalysis)
    CAMS:    ±120min (CAMS NRT in GEE exposes only 3-hourly forecast
                      steps at 00/03/06/09/12/15/18/21 UTC; ±120min
                      around 07:30 brackets the 06:00 and 09:00 steps,
                      giving a temporal interpolant across the S2
                      acquisition time)
  Take AOI-mean of the temporal mean across the window. Multi-image
  averaging absorbs CAMS forecast-lead spread at the same validity
  time as well as the temporal step interpolation.

Spatial matching:
  Native MERRA-2 grid is ~0.5°×0.625° (~55×70km at this latitude).
  CAMS NRT is ~0.4° (~44km). Riyadh AOIs (5–15km) all sit within
  one or two reanalysis pixels. AOI-mean reducer at native scale —
  effectively returns the value of the containing reanalysis pixel.
  This spatial mismatch is documented as §5b of sq8_findings.md as
  a known attenuation effect on the regression coefficient; it cannot
  be improved without a higher-resolution reanalysis source.

Self-reference unit test:
  Pick one (aoi, date) with valid AOD, compute MERRA-2 + CAMS twice;
  values must match exactly. Catches non-determinism in the reducer
  pipeline.

Coverage stop rule: HALT if either source has <80% coverage on the
228 SQ2 manifest dates after the run.
"""
from __future__ import annotations

import csv
import math
import os
import sys
from datetime import date as Date, datetime, timedelta, timezone
from pathlib import Path

import ee
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from src.phase1_aois import get_bbox  # noqa: E402

DATA = ROOT / "research/dust-honesty/data"
MANIFEST = DATA / "operational" / "manifest_operational_sq2.csv"
OUT_CSV = DATA / "sq8_aod_per_scene.csv"

MERRA2_ASSET = "NASA/GSFC/MERRA/aer/2"
MERRA2_BAND = "DUEXTTAU"
CAMS_ASSET = "ECMWF/CAMS/NRT"
CAMS_BAND = "total_aerosol_optical_depth_at_550nm_surface"

S2_ANCHOR_HOUR_UTC = 7
S2_ANCHOR_MINUTE_UTC = 30
WINDOW_MERRA2_MIN = 60   # ±60min — MERRA-2 is hourly
WINDOW_CAMS_MIN = 120    # ±120min — CAMS NRT in GEE is 3-hourly

COVERAGE_FLOOR = 0.80
N_EXPECTED_DATES = 228


def s2_anchor_window(date_str, window_min):
    """Return (start_iso, end_iso) for the ±window_min window around the
    S2 anchor time on that date."""
    d = Date.fromisoformat(date_str)
    anchor = datetime(d.year, d.month, d.day,
                      S2_ANCHOR_HOUR_UTC, S2_ANCHOR_MINUTE_UTC,
                      tzinfo=timezone.utc)
    start = anchor - timedelta(minutes=window_min)
    end = anchor + timedelta(minutes=window_min + 1)  # end exclusive
    return start.strftime("%Y-%m-%dT%H:%M"), end.strftime("%Y-%m-%dT%H:%M")


def fetch_aod_mean(asset, band, geom, start_iso, end_iso):
    """Return (mean_value or None, n_images, ts_min, ts_max).

    Filters asset to geom + [start_iso, end_iso). Takes temporal mean
    of band across all images, then AOI-mean reduceRegion at native
    scale. n_images is the count contributing to the temporal mean;
    ts_min/ts_max bracket the validity-time spread.
    """
    coll = (ee.ImageCollection(asset)
            .filterBounds(geom)
            .filterDate(start_iso, end_iso)
            .select(band))
    n = int(coll.size().getInfo())
    if n == 0:
        return None, 0, None, None
    ts_arr = coll.aggregate_array("system:time_start").getInfo()
    ts_min = min(ts_arr)
    ts_max = max(ts_arr)
    # Temporal mean across all images, then spatial AOI-mean
    img = coll.mean()
    stat = img.reduceRegion(
        reducer=ee.Reducer.mean(),
        geometry=geom,
        scale=30000,  # ~native resolution; reducer averages over AOI
        maxPixels=1e9,
    ).getInfo()
    val = stat.get(band)

    def fmt(ts_ms):
        return datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc).strftime(
            "%Y-%m-%dT%H:%M")
    return val, n, fmt(ts_min), fmt(ts_max)


def sanity_test():
    """Pick KSP 2024-01-20 (known clear-air date from SQ1D references).
    Compute MERRA-2 + CAMS twice each; must match exactly."""
    aoi = "king_salman_park"
    test_date = "2024-01-20"
    geom = ee.Geometry.Rectangle(list(get_bbox(aoi)))
    sm, em = s2_anchor_window(test_date, WINDOW_MERRA2_MIN)
    sc, ec = s2_anchor_window(test_date, WINDOW_CAMS_MIN)
    m1, _, _, _ = fetch_aod_mean(MERRA2_ASSET, MERRA2_BAND, geom, sm, em)
    m2, _, _, _ = fetch_aod_mean(MERRA2_ASSET, MERRA2_BAND, geom, sm, em)
    c1, _, _, _ = fetch_aod_mean(CAMS_ASSET, CAMS_BAND, geom, sc, ec)
    c2, _, _, _ = fetch_aod_mean(CAMS_ASSET, CAMS_BAND, geom, sc, ec)
    if m1 is None or m2 is None or c1 is None or c2 is None:
        raise RuntimeError(f"sanity-test FAILED: a value was None on KSP "
                           f"{test_date} ({m1!r}, {m2!r}, {c1!r}, {c2!r})")
    if m1 != m2:
        raise RuntimeError(f"sanity-test FAILED: MERRA-2 not equal "
                           f"on twice-computed: {m1!r} vs {m2!r}")
    if c1 != c2:
        raise RuntimeError(f"sanity-test FAILED: CAMS not equal "
                           f"on twice-computed: {c1!r} vs {c2!r}")
    print(f"sanity-test PASSED ({aoi} {test_date}): "
          f"MERRA-2 DUEXTTAU={m1:.6f} ≡ {m2:.6f} ; "
          f"CAMS total={c1:.6f} ≡ {c2:.6f}")


def write_output(rows):
    fields = [
        "aoi", "acquisition_date",
        "merra2_duexttau_550", "cams_total_aod_550",
        "merra2_n_images_used", "cams_n_images_used",
        "merra2_window_min_utc", "merra2_window_max_utc",
        "cams_window_min_utc", "cams_window_max_utc",
    ]
    with open(OUT_CSV, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in rows:
            w.writerow(r)


def main():
    load_dotenv(ROOT / ".env")
    ee.Initialize(project=os.environ["GEE_PROJECT"])
    print("SQ8 — reanalysis AOD fetch")
    print(f"  Primary: {MERRA2_ASSET} band {MERRA2_BAND}")
    print(f"  Cross:   {CAMS_ASSET} band {CAMS_BAND}")
    print(f"  MERRA-2 window: ±{WINDOW_MERRA2_MIN}min around "
          f"{S2_ANCHOR_HOUR_UTC:02d}:{S2_ANCHOR_MINUTE_UTC:02d} UTC (hourly)")
    print(f"  CAMS    window: ±{WINDOW_CAMS_MIN}min around "
          f"{S2_ANCHOR_HOUR_UTC:02d}:{S2_ANCHOR_MINUTE_UTC:02d} UTC (3-hourly)")
    print(f"  Coverage floor: {int(COVERAGE_FLOOR*100)}% of "
          f"{N_EXPECTED_DATES} SQ2 manifest dates per source")
    print(f"  Output: {OUT_CSV}")
    print()

    print("Sanity test (twice-compute equality) ...")
    sanity_test()
    print()

    rows = []
    n_merra_ok = 0
    n_cams_ok = 0
    n_total = 0
    with open(MANIFEST) as f:
        manifest_rows = list(csv.DictReader(f))

    for r in manifest_rows:
        if r["no_usable_scene"] == "True":
            continue
        n_total += 1
        aoi = r["aoi"]
        d = r["acquisition_date"]
        geom = ee.Geometry.Rectangle(list(get_bbox(aoi)))
        sm, em = s2_anchor_window(d, WINDOW_MERRA2_MIN)
        sc, ec = s2_anchor_window(d, WINDOW_CAMS_MIN)

        m_val, m_n, m_min, m_max = fetch_aod_mean(
            MERRA2_ASSET, MERRA2_BAND, geom, sm, em)
        c_val, c_n, c_min, c_max = fetch_aod_mean(
            CAMS_ASSET, CAMS_BAND, geom, sc, ec)

        if m_val is not None:
            n_merra_ok += 1
        if c_val is not None:
            n_cams_ok += 1

        rows.append({
            "aoi": aoi,
            "acquisition_date": d,
            "merra2_duexttau_550": ("" if m_val is None else f"{m_val:.6f}"),
            "cams_total_aod_550": ("" if c_val is None else f"{c_val:.6f}"),
            "merra2_n_images_used": m_n,
            "cams_n_images_used": c_n,
            "merra2_window_min_utc": m_min or "",
            "merra2_window_max_utc": m_max or "",
            "cams_window_min_utc": c_min or "",
            "cams_window_max_utc": c_max or "",
        })

        m_disp = f"{m_val:.4f}" if m_val is not None else "  (NA)"
        c_disp = f"{c_val:.4f}" if c_val is not None else "  (NA)"
        print(f"  {aoi:<22s} {d}  MERRA-2 DUEXTTAU={m_disp} (n={m_n})  "
              f"CAMS AOD={c_disp} (n={c_n})")

    write_output(rows)
    print()
    print(f"Wrote {OUT_CSV} ({len(rows)} rows)")

    cov_merra = n_merra_ok / n_total if n_total else 0
    cov_cams = n_cams_ok / n_total if n_total else 0
    print(f"  Coverage MERRA-2 DUEXTTAU: {n_merra_ok}/{n_total} = "
          f"{cov_merra*100:.1f}%")
    print(f"  Coverage CAMS total AOD : {n_cams_ok}/{n_total} = "
          f"{cov_cams*100:.1f}%")

    if cov_merra < COVERAGE_FLOOR or cov_cams < COVERAGE_FLOOR:
        print()
        print("HARD HALT: AOD coverage below floor. Surface scope options.")
        sys.exit(2)
    print()
    print(f"Coverage PASS: both sources ≥ {int(COVERAGE_FLOOR*100)}%.")


if __name__ == "__main__":
    main()

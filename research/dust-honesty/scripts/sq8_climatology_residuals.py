"""
SQ8 — per-AOI per-calendar-month NDVI climatology + per-scene residuals.

Inputs:
  research/dust-honesty/data/sq3_ndvi_per_scene.csv  (228 rows, 226 with NDVI)

Outputs:
  research/dust-honesty/data/sq8_ndvi_residuals.csv
  columns: aoi, acquisition_date, ndvi, ndvi_climatology,
           ndvi_residual, n_climatology_support, sensitivity_flag

Climatology: for each (aoi, calendar_month), compute the mean NDVI
across all years 2020–2026. Residual = ndvi - climatology[aoi, month].

n_climatology_support is the number of scenes that contributed to
the (aoi, month) climatology cell. sensitivity_flag = True iff
n_climatology_support < 3 (R5 surfaced 0 such cells; flag included
for downstream sensitivity-regression robustness).

Self-reference unit test: re-run on the same input must produce
identical residuals (deterministic). HALT on fail.
"""
from __future__ import annotations

import csv
import math
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
DATA = ROOT / "research/dust-honesty/data"

NDVI_CSV = DATA / "sq3_ndvi_per_scene.csv"
OUT_CSV = DATA / "sq8_ndvi_residuals.csv"

SENSITIVITY_FLOOR = 3


def load_ndvi():
    """Yield dict rows from sq3_ndvi_per_scene.csv with NDVI present."""
    with open(NDVI_CSV) as f:
        for r in csv.DictReader(f):
            v = r["ndvi_aoi_mean"]
            if v == "":
                continue
            yield {
                "aoi": r["aoi"],
                "acquisition_date": r["scene_date"],
                "ndvi": float(v),
                "month": int(r["scene_date"].split("-")[1]),
            }


def compute_climatology(rows):
    """Return dict[(aoi, month)] -> (mean_ndvi, n_support)."""
    bucket = defaultdict(list)
    for r in rows:
        bucket[(r["aoi"], r["month"])].append(r["ndvi"])
    out = {}
    for k, vals in bucket.items():
        out[k] = (sum(vals) / len(vals), len(vals))
    return out


def assign_residuals(rows, clim):
    """Mutate rows in place to add ndvi_climatology, ndvi_residual,
    n_climatology_support, sensitivity_flag."""
    for r in rows:
        clim_mean, n = clim[(r["aoi"], r["month"])]
        r["ndvi_climatology"] = clim_mean
        r["ndvi_residual"] = r["ndvi"] - clim_mean
        r["n_climatology_support"] = n
        r["sensitivity_flag"] = (n < SENSITIVITY_FLOOR)


def sanity_test(rows_a, rows_b):
    if len(rows_a) != len(rows_b):
        raise RuntimeError(f"sanity-test FAILED: row count drift "
                           f"{len(rows_a)} vs {len(rows_b)}")
    for a, b in zip(rows_a, rows_b):
        if a["acquisition_date"] != b["acquisition_date"] or a["aoi"] != b["aoi"]:
            raise RuntimeError("sanity-test FAILED: row order drift")
        if a["ndvi_residual"] != b["ndvi_residual"]:
            raise RuntimeError(f"sanity-test FAILED: residual drift on "
                               f"{a['aoi']} {a['acquisition_date']}: "
                               f"{a['ndvi_residual']!r} vs {b['ndvi_residual']!r}")
    print(f"sanity-test PASSED ({len(rows_a)} rows, "
          f"identical residuals on twice-computed assignment)")


def write_output(rows):
    fields = ["aoi", "acquisition_date", "ndvi", "ndvi_climatology",
              "ndvi_residual", "n_climatology_support", "sensitivity_flag"]
    rows_sorted = sorted(rows, key=lambda r: (r["aoi"], r["acquisition_date"]))
    with open(OUT_CSV, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in rows_sorted:
            w.writerow({
                "aoi": r["aoi"],
                "acquisition_date": r["acquisition_date"],
                "ndvi": f"{r['ndvi']:.6f}",
                "ndvi_climatology": f"{r['ndvi_climatology']:.6f}",
                "ndvi_residual": f"{r['ndvi_residual']:+.6f}",
                "n_climatology_support": r["n_climatology_support"],
                "sensitivity_flag": "True" if r["sensitivity_flag"] else "False",
            })


def main():
    print("SQ8 — NDVI climatology + per-scene residuals")
    print()

    # First pass
    rows = list(load_ndvi())
    print(f"Loaded {len(rows)} scenes with NDVI")

    clim = compute_climatology(rows)
    print(f"Climatology cells: {len(clim)} (3 AOIs × 12 months = 36 expected)")
    n_low = sum(1 for (_, n) in clim.values() if n < SENSITIVITY_FLOOR)
    print(f"  cells with n_support < {SENSITIVITY_FLOOR}: {n_low}")

    assign_residuals(rows, clim)

    # Sanity: re-run independently
    rows_b = list(load_ndvi())
    clim_b = compute_climatology(rows_b)
    assign_residuals(rows_b, clim_b)
    rows_a_sorted = sorted(rows, key=lambda r: (r["aoi"], r["acquisition_date"]))
    rows_b_sorted = sorted(rows_b, key=lambda r: (r["aoi"], r["acquisition_date"]))
    sanity_test(rows_a_sorted, rows_b_sorted)
    print()

    # Quick descriptive stats
    print("Per-AOI residual descriptive stats:")
    by_aoi = defaultdict(list)
    for r in rows:
        by_aoi[r["aoi"]].append(r["ndvi_residual"])
    print(f"  {'aoi':<22s} {'n':>4s} {'mean':>10s} {'std':>10s} {'min':>10s} {'max':>10s}")
    for aoi, vals in sorted(by_aoi.items()):
        n = len(vals)
        mean = sum(vals) / n
        std = math.sqrt(sum((v-mean)**2 for v in vals) / max(1, n-1))
        print(f"  {aoi:<22s} {n:>4d} {mean:>+10.4f} {std:>10.4f} "
              f"{min(vals):>+10.4f} {max(vals):>+10.4f}")

    write_output(rows)
    print()
    print(f"Wrote {OUT_CSV} ({len(rows)} rows)")


if __name__ == "__main__":
    main()

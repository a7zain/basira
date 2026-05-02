"""
SQ5 — pair retention probe (HALT RECEIPT).

Inputs:
  research/dust-honesty/data/sq5_uvai_labels.csv

Outputs:
  research/dust-honesty/data/sq5_pair_retention_probe.csv
    columns: aoi, n_q4_total, n_q4_with_pair, retention_pct,
             floor_pct, halt_status
  research/dust-honesty/data/sq5_seasonal_stratification.csv
    columns: aoi, calendar_month, n_q1_scenes, n_q4_scenes
    (12 rows × 3 AOIs = 36 rows)

This script implements the same Q4→nearest-Q1-within-±60d pairing logic
that an SQ5 pair-and-diff would have used. It does NOT proceed to
compute Δ NDVI — the pre-registered 30% retention floor halted the
design at this point. The probe IS the receipt for that halt.

Why the design halts at Riyadh: high-UVAI scenes cluster in
spring/summer (shamal season); low-UVAI scenes cluster in winter. The
two quartiles are separated by ~6 months of seasonal cycle and do not
temporally interleave at the ±60-day scale. The seasonal stratification
table emitted alongside is the structural diagnostic and feeds the
seasonal_stratification chart.
"""
from __future__ import annotations

import csv
from collections import defaultdict
from datetime import date as Date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
DATA = ROOT / "research/dust-honesty/data"

LABELS_CSV = DATA / "sq5_uvai_labels.csv"
OUT_RETENTION = DATA / "sq5_pair_retention_probe.csv"
OUT_SEASONAL = DATA / "sq5_seasonal_stratification.csv"

AOIS = ["king_salman_park", "qiddiya_core", "diriyah_gate"]
WINDOW_DAYS = 60
RETENTION_FLOOR_PCT = 30.0


def load_labels():
    """Return dict aoi -> list of {date, quartile, uvai}."""
    out = defaultdict(list)
    with open(LABELS_CSV) as f:
        for r in csv.DictReader(f):
            out[r["aoi"]].append({
                "date": r["acquisition_date"],
                "quartile": r["uvai_quartile"],
                "uvai": float(r["uvai_mean"]),
            })
    return out


def estimate_retention(per_aoi):
    """For each AOI, count Q4 scenes that have at least one Q1 neighbor
    within ±WINDOW_DAYS. Returns list of dicts."""
    rows = []
    for aoi in AOIS:
        scenes = per_aoi[aoi]
        q4 = [s for s in scenes if s["quartile"] == "Q4"]
        q1_dates = sorted(Date.fromisoformat(s["date"])
                          for s in scenes if s["quartile"] == "Q1")
        n_q4 = len(q4)
        n_paired = 0
        for s in q4:
            qd = Date.fromisoformat(s["date"])
            if any(abs((qd - d1).days) <= WINDOW_DAYS for d1 in q1_dates):
                n_paired += 1
        retention = (100.0 * n_paired / n_q4) if n_q4 else 0.0
        halt = (retention < RETENTION_FLOOR_PCT)
        rows.append({
            "aoi": aoi,
            "n_q4_total": n_q4,
            "n_q4_with_pair": n_paired,
            "retention_pct": retention,
            "floor_pct": RETENTION_FLOOR_PCT,
            "halt_status": "HALT" if halt else "pass",
        })
    return rows


def seasonal_table(per_aoi):
    """Per AOI per calendar-month: count of Q1 scenes and Q4 scenes."""
    rows = []
    for aoi in AOIS:
        counts_q1 = defaultdict(int)
        counts_q4 = defaultdict(int)
        for s in per_aoi[aoi]:
            m = int(s["date"].split("-")[1])
            if s["quartile"] == "Q1":
                counts_q1[m] += 1
            elif s["quartile"] == "Q4":
                counts_q4[m] += 1
        for m in range(1, 13):
            rows.append({
                "aoi": aoi,
                "calendar_month": m,
                "n_q1_scenes": counts_q1[m],
                "n_q4_scenes": counts_q4[m],
            })
    return rows


def write_retention(rows):
    fields = ["aoi", "n_q4_total", "n_q4_with_pair", "retention_pct",
              "floor_pct", "halt_status"]
    with open(OUT_RETENTION, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in rows:
            w.writerow({
                "aoi": r["aoi"],
                "n_q4_total": r["n_q4_total"],
                "n_q4_with_pair": r["n_q4_with_pair"],
                "retention_pct": f"{r['retention_pct']:.2f}",
                "floor_pct": f"{r['floor_pct']:.2f}",
                "halt_status": r["halt_status"],
            })


def write_seasonal(rows):
    fields = ["aoi", "calendar_month", "n_q1_scenes", "n_q4_scenes"]
    with open(OUT_SEASONAL, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in rows:
            w.writerow(r)


def main():
    print("SQ5 — pair retention probe (HALT RECEIPT)")
    print(f"  Window: ±{WINDOW_DAYS} days; floor: {RETENTION_FLOOR_PCT:.0f}%")
    print()

    per_aoi = load_labels()

    retention_rows = estimate_retention(per_aoi)
    print("Per-AOI retention:")
    print(f"  {'aoi':<22s} {'n_q4':>5s} {'n_paired':>9s} {'ret%':>7s} {'status':<5s}")
    for r in retention_rows:
        print(f"  {r['aoi']:<22s} {r['n_q4_total']:>5d} "
              f"{r['n_q4_with_pair']:>9d} "
              f"{r['retention_pct']:>6.1f}% {r['halt_status']:<5s}")
    write_retention(retention_rows)
    print(f"Wrote {OUT_RETENTION}")
    print()

    seasonal_rows = seasonal_table(per_aoi)
    write_seasonal(seasonal_rows)
    print(f"Wrote {OUT_SEASONAL} ({len(seasonal_rows)} rows)")

    n_halted = sum(1 for r in retention_rows if r["halt_status"] == "HALT")
    print()
    if n_halted == len(AOIS):
        print(f"DESIGN HALT confirmed in {n_halted}/{len(AOIS)} AOIs.")
        print("  Pre-registered Q4-vs-Q1 paired temporal-neighbor design")
        print("  cannot proceed. Goyens-regime test promoted to SQ8 with")
        print("  regression design (sketched in sq5_findings.md §6).")
        print("  No pair-and-diff scripts to run.")
    else:
        # Defensive — should not reach in this halt-with-receipt ship.
        print(f"WARN: only {n_halted}/{len(AOIS)} AOIs halted. The SQ5")
        print("  ship is the halt receipt; if any AOI passes the floor,")
        print("  surface for scope review BEFORE writing pair-and-diff.")


if __name__ == "__main__":
    main()

"""
SQ1C — per-AOI positive-candidate selection.

For each AOI:
  1. Load the negative-class scenes (from sq1d_<aoi>_relabel.csv where
     final_label='clean'; for Diriyah, sq1_manual_labels.csv where
     AOI='diriyah_gate' AND label='clean').
  2. Compute allowed_months = set of calendar months (1..12) that have
     ≥1 scene in the negative class. This is the SZA-aware seasonal-
     balance constraint from §2 Step C of the protocol.
  3. Load the AOI's all-months UVAI CSV.
  4. Filter UVAI rows to those whose calendar month is in allowed_months
     AND whose date is not already in the negative class.
  5. Sort by uvai_mean descending.
  6. Take top top_n=15 (50% over the n_pos≥10 floor for attrition).

Outputs (per AOI):
  research/dust-honesty/data/sq1c_<aoi>_positive_candidates.csv

Stdout: per-AOI summary table.
"""
from __future__ import annotations

import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
DATA = ROOT / "research/dust-honesty/data"

AOIS = ["king_salman_park", "qiddiya_core", "diriyah_gate"]

_AOI_ABBREV = {"king_salman_park": "ksp", "qiddiya_core": "qiddiya", "diriyah_gate": "diriyah"}

NEGATIVE_CLASS_SOURCE = {
    "king_salman_park": (DATA / "calibration" / "relabel_ksp_sq1d.csv", "date", "final_label"),
    "qiddiya_core":     (DATA / "calibration" / "relabel_qiddiya_sq1d.csv", "date", "final_label"),
    "diriyah_gate":     (DATA / "calibration" / "manual_labels_sq1.csv", "date", "label"),
}

UVAI_CSV = {
    "king_salman_park": DATA / "calibration" / "uvai_ksp_sq1d.csv",
    "qiddiya_core":     DATA / "calibration" / "uvai_qiddiya_sq1d.csv",
    "diriyah_gate":     DATA / "calibration" / "uvai_diriyah_sq1d.csv",
}

OUT_CSV = {
    aoi: DATA / "calibration" / f"candidates_{_AOI_ABBREV[aoi]}_sq1c.csv" for aoi in AOIS
}

TOP_N = 15


def load_negative_class(aoi):
    """Return list of (date, calendar_month_int) tuples for clean scenes
    of the given AOI."""
    path, date_col, label_col = NEGATIVE_CLASS_SOURCE[aoi]
    out = []
    with open(path) as f:
        for r in csv.DictReader(f):
            # Diriyah rows are scoped by an AOI column; KSP/Qiddiya by file
            if aoi == "diriyah_gate" and r.get("AOI") != "diriyah_gate":
                continue
            if r.get(label_col) != "clean":
                continue
            d = r[date_col]  # YYYY-MM
            month = int(d.split("-")[1])
            out.append((d, month))
    return out


def allowed_months(aoi):
    return sorted({m for _, m in load_negative_class(aoi)})


def calendar_month_of(date_yyyymmdd):
    return int(date_yyyymmdd.split("-")[1])


def rank_uvai_candidates(aoi, top_n=TOP_N):
    neg = load_negative_class(aoi)
    neg_dates = {d for d, _ in neg}
    months = set(allowed_months(aoi))

    with open(UVAI_CSV[aoi]) as f:
        rows = list(csv.DictReader(f))

    # Filter
    candidates = []
    for r in rows:
        date = r["date"]                 # YYYY-MM-DD
        ym = date[:7]                    # YYYY-MM (matches negative-class slot key)
        if ym in neg_dates:
            continue
        m = calendar_month_of(date)
        if m not in months:
            continue
        try:
            uvai = float(r["uvai_mean"])
        except (TypeError, ValueError):
            continue
        candidates.append({"date": date, "uvai_mean": uvai, "calendar_month": m})

    candidates.sort(key=lambda x: x["uvai_mean"], reverse=True)
    selected = candidates[:top_n]
    for i, c in enumerate(selected, 1):
        c["rank"] = i
    return selected, candidates, months


def main():
    print(f"{'aoi':<20s} {'neg_n':>6s} {'allowed_months':<26s} "
          f"{'in_pool':>8s} {'selected':>9s}  top-3 (date | uvai_mean)")
    print("-" * 110)

    summary_lines = []
    for aoi in AOIS:
        selected, full_pool, months = rank_uvai_candidates(aoi)
        allowed_str = ",".join(f"{m:02d}" for m in sorted(months))
        neg = load_negative_class(aoi)
        top3 = " | ".join(f"{c['date']} {c['uvai_mean']:+.3f}" for c in selected[:3])
        line = (f"{aoi:<20s} {len(neg):>6d} {allowed_str:<26s} "
                f"{len(full_pool):>8d} {len(selected):>9d}  {top3}")
        print(line)
        summary_lines.append(line)

        # write CSV
        path = OUT_CSV[aoi]
        with open(path, "w", newline="") as f:
            w = csv.DictWriter(
                f,
                fieldnames=["rank", "date", "uvai_mean", "calendar_month",
                            "allowed_months_for_aoi"],
            )
            w.writeheader()
            for c in selected:
                w.writerow({
                    "rank": c["rank"],
                    "date": c["date"],
                    "uvai_mean": c["uvai_mean"],
                    "calendar_month": c["calendar_month"],
                    "allowed_months_for_aoi": allowed_str,
                })
        print(f"  → {path}")

    print()
    print("Summary:")
    for line in summary_lines:
        print("  " + line)


if __name__ == "__main__":
    main()

"""
SQ1D — build stratified KSP reference candidate pool on tightened bbox.

Pool A: top-3 cleanest UVAI across full window (2020-01..2026-04).
Pool B: top-3 cleanest UVAI from 2023-01 onward (recent, surface-state
        representative for late-stack test scenes).
Test months (sq1_manual_labels.csv where AOI=king_salman_park) are
excluded so candidates don't leak into the calibration set.

Output: research/dust-honesty/data/sq1d_ksp_reference_candidates.csv
"""
import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
UVAI_CSV = ROOT / "research/dust-honesty/data/sq1d_ksp_uvai_all.csv"
LABELS_CSV = ROOT / "research/dust-honesty/data/sq1_manual_labels.csv"
OUT_CSV = ROOT / "research/dust-honesty/data/sq1d_ksp_reference_candidates.csv"
AOI = "king_salman_park"
RECENT_START = "2023-01-01"
POOL_SIZE = 3


def main():
    test_months = set()
    with open(LABELS_CSV) as f:
        for row in csv.DictReader(f):
            if row["AOI"] == AOI:
                test_months.add(row["date"])  # YYYY-MM
    print(f"Excluded test months ({len(test_months)}): {sorted(test_months)}")

    rows = []
    with open(UVAI_CSV) as f:
        for row in csv.DictReader(f):
            ym = row["date"][:7]
            if ym in test_months:
                continue
            row["uvai_mean_f"] = float(row["uvai_mean"])
            rows.append(row)
    print(f"Eligible (non-test) UVAI scenes: {len(rows)}")

    full_sorted = sorted(rows, key=lambda r: r["uvai_mean_f"])
    pool_a = full_sorted[:POOL_SIZE]

    recent = [r for r in rows if r["date"] >= RECENT_START]
    recent_sorted = sorted(recent, key=lambda r: r["uvai_mean_f"])
    pool_b = recent_sorted[:POOL_SIZE]

    seen = set()
    combined = []
    for rk, r in enumerate(pool_a, 1):
        d = r["date"]
        if d in seen:
            continue
        seen.add(d)
        combined.append({**r, "pool": "A", "rank": rk})
    for rk, r in enumerate(pool_b, 1):
        d = r["date"]
        if d in seen:
            for existing in combined:
                if existing["date"] == d:
                    existing["pool"] = existing["pool"] + "+B"
                    existing["rank_b"] = rk
            continue
        seen.add(d)
        combined.append({**r, "pool": "B", "rank": rk})

    print(f"\nCandidate pool ({len(combined)} unique dates):")
    print(f"  {'date':10}  {'uvai_mean':>10}  {'cloud%':>7}  pool  rank")
    for c in combined:
        print(
            f"  {c['date']:10}  {c['uvai_mean_f']:>10.4f}  {float(c['cloud_pct']):>7.2f}  "
            f"{c['pool']:5}  {c['rank']}"
        )

    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_CSV, "w", newline="") as f:
        w = csv.DictWriter(
            f,
            fieldnames=[
                "date",
                "l1c_product_id",
                "cloud_pct",
                "uvai_mean",
                "uvai_max",
                "pool",
                "rank",
            ],
        )
        w.writeheader()
        for c in combined:
            w.writerow(
                {
                    "date": c["date"],
                    "l1c_product_id": c["l1c_product_id"],
                    "cloud_pct": c["cloud_pct"],
                    "uvai_mean": c["uvai_mean"],
                    "uvai_max": c["uvai_max"],
                    "pool": c["pool"],
                    "rank": c["rank"],
                }
            )
    print(f"\nWrote {len(combined)} rows → {OUT_CSV}")


if __name__ == "__main__":
    main()

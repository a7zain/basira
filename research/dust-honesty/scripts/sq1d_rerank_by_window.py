"""
SQ1D Part A.6.1 — re-rank KSP UVAI candidates by date window.

Read-only analysis on uvai_ksp_sq1d.csv. No GEE calls.
"""
import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
IN_CSV = ROOT / "research/dust-honesty/data/calibration/uvai_ksp_sq1d.csv"

WINDOWS = [
    ("Window 1: full range (2020-01 to 2026-04)", "2020-01-01", "2026-04-30"),
    ("Window 2: mid-stack onward (2022-01 to 2026-04)", "2022-01-01", "2026-04-30"),
    ("Window 3: recent (2023-01 to 2026-04)", "2023-01-01", "2026-04-30"),
    ("Window 4: very recent (2024-01 to 2026-04)", "2024-01-01", "2026-04-30"),
    ("Window 5: last 16 months (2025-01 to 2026-04)", "2025-01-01", "2026-04-30"),
]


def main():
    rows = list(csv.DictReader(open(IN_CSV)))
    for r in rows:
        r["uvai_mean"] = float(r["uvai_mean"])
        r["uvai_max"] = float(r["uvai_max"])
        r["cloud_pct"] = float(r["cloud_pct"])
        r["tropomi_n_images"] = int(r["tropomi_n_images"])

    for label, start, end in WINDOWS:
        sub = [r for r in rows if start <= r["date"] <= end]
        sub_sorted = sorted(sub, key=lambda r: r["uvai_mean"])
        n = len(sub)
        n_lt_03 = sum(1 for r in sub if r["uvai_mean"] < 0.3)
        n_lt_0 = sum(1 for r in sub if r["uvai_mean"] < 0.0)
        print(f"\n=== {label} ===")
        print(f"  scenes in window: {n}")
        print(f"  uvai_mean < 0.3:  {n_lt_03}")
        print(f"  uvai_mean < 0.0:  {n_lt_0}")
        print(f"  TOP 5:")
        print(
            f"  {'rk':>2} {'date':10} {'cloud%':>7} {'n':>2} "
            f"{'uvai_mean':>10} {'uvai_max':>10}  product_id"
        )
        for i, r in enumerate(sub_sorted[:5]):
            print(
                f"  {i+1:>2} {r['date']:10} {r['cloud_pct']:>7.2f} "
                f"{r['tropomi_n_images']:>2} {r['uvai_mean']:>10.4f} "
                f"{r['uvai_max']:>10.4f}  {r['l1c_product_id']}"
            )


if __name__ == "__main__":
    main()

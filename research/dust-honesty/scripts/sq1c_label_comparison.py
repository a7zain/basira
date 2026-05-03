"""
SQ1C label comparison + UVAI audit.

Reads the three sq1c_<aoi>_relabel.csv files after the researcher confirmation
pass (sq1c_label_review.py). Reports:

  - Per AOI and overall: n confirmed, AI-researcher agreement rate.
  - Disagreement table: scene_id, date, AI label, confirmed label,
    UVAI value, review_protocol, reviewer_notes.
  - Cold-protocol block: for the 6 bias_exposed rows, did cold-labeling
    agree with AI pre-label? Print all 6 explicitly. This is the
    contamination-broke-or-not signal.
  - UVAI audit (post-labeling, fine to print here):
      * mean + 25/50/75 percentile UVAI per (AOI, confirmed_label).
      * flags: confirmed='clean' with UVAI > +2.0, or
               confirmed='heavy_dust' with UVAI < +1.0.

Output: stdout summary + sq1c_confirmation_audit.csv with one row per scene.

UVAI is first surfaced HERE, never at labeling time. (Locked 2026-04-30.)

Usage:
    python sq1c_label_comparison.py
    python sq1c_label_comparison.py --strict   # exit nonzero on any unconfirmed row
"""
from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path
from statistics import mean

ROOT = Path(__file__).resolve().parents[3]
DATA = ROOT / "research/dust-honesty/data"

AOIS = [
    ("king_salman_park", "KSP"),
    ("qiddiya_core",     "Qiddiya"),
    ("diriyah_gate",     "Diriyah"),
]

OUT_CSV = DATA / "calibration" / "confirmation_audit_sq1c.csv"

AOI_ABBREV = {
    "king_salman_park": "ksp",
    "qiddiya_core": "qiddiya",
    "diriyah_gate": "diriyah",
}

CLEAN_UVAI_FLAG = 2.0   # confirmed clean but UVAI > this is interesting
HEAVY_UVAI_FLAG = 1.0   # confirmed heavy_dust but UVAI < this is interesting


def load_aoi(aoi: str):
    path = DATA / "calibration" / f"relabel_{AOI_ABBREV[aoi]}_sq1c.csv"
    with open(path) as f:
        return list(csv.DictReader(f))


def is_bias(r) -> bool:
    return str(r.get("bias_exposed_during_ai_labeling", "False")).strip().lower() == "true"


def is_confirmed(r) -> bool:
    return bool(str(r.get("confirmed_label", "")).strip())


def parse_uvai(r) -> float | None:
    raw = r.get("candidate_uvai", "").strip()
    if not raw:
        return None
    try:
        return float(raw)
    except ValueError:
        return None


def percentile(sorted_vals, p):
    if not sorted_vals:
        return float("nan")
    if len(sorted_vals) == 1:
        return sorted_vals[0]
    k = (len(sorted_vals) - 1) * p
    f = int(k)
    c = min(f + 1, len(sorted_vals) - 1)
    if f == c:
        return sorted_vals[f]
    return sorted_vals[f] + (sorted_vals[c] - sorted_vals[f]) * (k - f)


def report_aoi(aoi: str, label: str, rows):
    print(f"\n--- {label} ({aoi}) ---")
    n = len(rows)
    confirmed = [r for r in rows if is_confirmed(r)]
    unconfirmed = [r for r in rows if not is_confirmed(r)]
    print(f"  n total      : {n}")
    print(f"  n confirmed  : {len(confirmed)}")
    if unconfirmed:
        print(f"  n unconfirmed: {len(unconfirmed)}  -> dates: "
              f"{', '.join(r.get('date', '?') for r in unconfirmed)}")
    if not confirmed:
        return

    agree = sum(1 for r in confirmed
                if r["confirmed_label"].strip() == r["ai_prelabel"].strip())
    overrides = len(confirmed) - agree
    rate = agree / len(confirmed) if confirmed else float("nan")
    print(f"  agreement    : {agree}/{len(confirmed)} = {rate:.3f}")
    print(f"  overrides    : {overrides}")


def report_disagreements(all_rows):
    print("\n=== Disagreement table (AI != confirmed) ===")
    disagreements = [r for r in all_rows
                     if is_confirmed(r)
                     and r["confirmed_label"].strip() != r["ai_prelabel"].strip()]
    if not disagreements:
        print("  (none)")
        return
    print(f"{'AOI':<18s} {'Date':<11s} {'AI':<11s} {'Confirmed':<11s} "
          f"{'UVAI':>6s} {'Proto':<9s} Notes")
    for r in disagreements:
        uvai = parse_uvai(r)
        uvai_s = f"{uvai:+.2f}" if uvai is not None else "  NaN"
        print(f"{r['sub_aoi']:<18s} {r['date']:<11s} "
              f"{r['ai_prelabel']:<11s} {r['confirmed_label']:<11s} "
              f"{uvai_s:>6s} {r.get('review_protocol', ''):<9s} "
              f"{r.get('reviewer_notes', '')}")


def report_cold_protocol(all_rows):
    print("\n=== Cold-protocol block (6 bias_exposed rows) ===")
    cold = [r for r in all_rows if is_bias(r)]
    if not cold:
        print("  (no bias_exposed rows found — unexpected; check schema)")
        return
    print(f"{'AOI':<18s} {'Date':<11s} {'AI':<11s} {'Cold':<11s} "
          f"{'agree?':<7s} {'UVAI':>6s} Notes")
    n_agree = 0
    n_disagree = 0
    n_unconfirmed = 0
    for r in cold:
        ai = r["ai_prelabel"].strip()
        cl = r.get("confirmed_label", "").strip()
        if not cl:
            n_unconfirmed += 1
            tag = "PEND"
        elif cl == ai:
            n_agree += 1
            tag = "yes"
        else:
            n_disagree += 1
            tag = "NO"
        uvai = parse_uvai(r)
        uvai_s = f"{uvai:+.2f}" if uvai is not None else "  NaN"
        print(f"{r['sub_aoi']:<18s} {r['date']:<11s} "
              f"{ai:<11s} {cl or '(pending)':<11s} {tag:<7s} {uvai_s:>6s} "
              f"{r.get('reviewer_notes', '')}")
    print(f"\n  cold rows agreement: {n_agree} agree / {n_disagree} disagree "
          f"/ {n_unconfirmed} pending. Disagreements here ARE the "
          f"contamination-broke signal.")


def report_uvai_audit(all_rows):
    print("\n=== UVAI audit per (AOI, confirmed_label) ===")
    print(f"{'AOI':<18s} {'Label':<11s} {'n':>3s} {'mean':>7s} "
          f"{'p25':>7s} {'p50':>7s} {'p75':>7s}")
    by_cell = {}
    for r in all_rows:
        if not is_confirmed(r):
            continue
        u = parse_uvai(r)
        if u is None:
            continue
        key = (r["sub_aoi"], r["confirmed_label"])
        by_cell.setdefault(key, []).append(u)
    for (aoi, label) in sorted(by_cell.keys()):
        vals = sorted(by_cell[(aoi, label)])
        m = mean(vals)
        p25 = percentile(vals, 0.25)
        p50 = percentile(vals, 0.50)
        p75 = percentile(vals, 0.75)
        print(f"{aoi:<18s} {label:<11s} {len(vals):>3d} "
              f"{m:>+7.3f} {p25:>+7.3f} {p50:>+7.3f} {p75:>+7.3f}")


def report_uvai_anomalies(all_rows):
    print(f"\n=== UVAI anomalies (clean & UVAI > {CLEAN_UVAI_FLAG}, "
          f"heavy_dust & UVAI < {HEAVY_UVAI_FLAG}) ===")
    anomalies = []
    for r in all_rows:
        if not is_confirmed(r):
            continue
        u = parse_uvai(r)
        if u is None:
            continue
        cl = r["confirmed_label"]
        if cl == "clean" and u > CLEAN_UVAI_FLAG:
            anomalies.append((r, u, "clean_high_uvai"))
        elif cl == "heavy_dust" and u < HEAVY_UVAI_FLAG:
            anomalies.append((r, u, "heavy_low_uvai"))
    if not anomalies:
        print("  (none)")
        return
    print(f"{'AOI':<18s} {'Date':<11s} {'Label':<11s} {'UVAI':>7s} {'flag':<18s} "
          f"Notes")
    for r, u, flag in anomalies:
        print(f"{r['sub_aoi']:<18s} {r['date']:<11s} "
              f"{r['confirmed_label']:<11s} {u:>+7.3f} {flag:<18s} "
              f"{r.get('reviewer_notes', '')}")
    print("\n  Anomalies are piece B discussion-section candidates "
          "(visual-vs-aerosol decoupling).")


def write_audit_csv(all_rows):
    fields = [
        "aoi", "date", "s2_system_index",
        "ai_prelabel", "confirmed_label", "agreement",
        "candidate_uvai", "review_protocol",
        "bias_exposed_during_ai_labeling", "reviewer_notes",
    ]
    with open(OUT_CSV, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in all_rows:
            ai = r.get("ai_prelabel", "").strip()
            cl = r.get("confirmed_label", "").strip()
            agree = "" if not cl else str(cl == ai)
            w.writerow({
                "aoi": r.get("sub_aoi", ""),
                "date": r.get("date", ""),
                "s2_system_index": r.get("s2_system_index", ""),
                "ai_prelabel": ai,
                "confirmed_label": cl,
                "agreement": agree,
                "candidate_uvai": r.get("candidate_uvai", ""),
                "review_protocol": r.get("review_protocol", ""),
                "bias_exposed_during_ai_labeling": r.get(
                    "bias_exposed_during_ai_labeling", ""),
                "reviewer_notes": r.get("reviewer_notes", ""),
            })
    print(f"\nWrote audit CSV: {OUT_CSV}")


def main():
    p = argparse.ArgumentParser(
        description="SQ1C label comparison + UVAI audit. Run AFTER "
                    "sq1c_label_review.py confirmation passes complete.",
    )
    p.add_argument(
        "--strict", action="store_true",
        help="Exit nonzero if any row across the 3 AOIs is unconfirmed.",
    )
    args = p.parse_args()

    all_rows = []
    for aoi, label in AOIS:
        rows = load_aoi(aoi)
        report_aoi(aoi, label, rows)
        all_rows.extend(rows)

    print("\n" + "=" * 72)
    print(f"OVERALL: n total = {len(all_rows)}")
    confirmed_total = sum(1 for r in all_rows if is_confirmed(r))
    print(f"OVERALL: n confirmed = {confirmed_total}")
    if confirmed_total:
        agree_total = sum(
            1 for r in all_rows
            if is_confirmed(r)
            and r["confirmed_label"].strip() == r["ai_prelabel"].strip()
        )
        print(f"OVERALL: AI agreement = {agree_total}/{confirmed_total} "
              f"= {agree_total / confirmed_total:.3f}")

    report_disagreements(all_rows)
    report_cold_protocol(all_rows)
    report_uvai_audit(all_rows)
    report_uvai_anomalies(all_rows)
    write_audit_csv(all_rows)

    n_unconfirmed = sum(1 for r in all_rows if not is_confirmed(r))
    if args.strict and n_unconfirmed > 0:
        print(f"\nSTRICT mode: {n_unconfirmed} row(s) unconfirmed; exit 1.",
              file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

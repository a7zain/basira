"""
SQ2 — summary statistics over the operational DBB CSV.

Reads sq2_dbb_operational.csv. Emits sq2_summary_stats.md with:
  1. Headline numbers per AOI (months, usable, V4 fires %, V3 fires %, cloud %)
  2. Temporal pattern: peak DBB scene + top 5 + monthly histogram of V4 fires.
  3. Cross-check status (overlap rows / pass / fail).
  4. Self-reference test status (restated).

Usage:
    python sq2_summary_stats.py
"""
from __future__ import annotations

import csv
import math
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
DATA = ROOT / "research/dust-honesty/data"
IN_CSV = DATA / "sq2_dbb_operational.csv"
FAILURES_CSV = DATA / "sq2_cross_check_failures.csv"
COMBINED_CAL_CSV = DATA / "sq1bc_combined_calibration_confirmed.csv"
OUT_MD = DATA / "sq2_summary_stats.md"

AOI_ORDER = ["king_salman_park", "qiddiya_core", "diriyah_gate"]
AOI_TITLE = {
    "king_salman_park": "King Salman Park",
    "qiddiya_core":     "Qiddiya core",
    "diriyah_gate":     "Diriyah Gate",
}

THRESH_V4 = 0.034
THRESH_V3 = 0.053

MONTH_NAMES = ["", "Jan", "Feb", "Mar", "Apr", "May", "Jun",
               "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def to_bool(s):
    return str(s).strip().lower() == "true"


def to_float(s):
    s = str(s).strip()
    if s == "" or s.lower() == "nan":
        return float("nan")
    return float(s)


def load_rows():
    rows = []
    with open(IN_CSV) as f:
        for r in csv.DictReader(f):
            rows.append({
                "aoi": r["aoi"],
                "year": int(r["year"]),
                "month": int(r["month"]),
                "system_index": r["system_index"],
                "scene_date": r["scene_date"],
                "dbb": to_float(r["dbb"]),
                "flag_v4": to_bool(r["flag_v4"]),
                "flag_v3": (None if r["flag_v3_ksp_only"] in ("", None)
                            else to_bool(r["flag_v3_ksp_only"])),
                "cloud_pct_aoi": to_float(r["cloud_pct_aoi"]),
                "cloud_flag_present": to_bool(r["cloud_flag_present"]),
                "no_usable_scene": to_bool(r["no_usable_scene"]),
                "calibration_subset_match":
                    to_bool(r["calibration_subset_match"]),
            })
    return rows


def section_headline(rows_by_aoi):
    lines = ["## 1. Headline numbers", ""]
    lines.append("| AOI | months | usable | V4 fires | V4 % of usable | "
                 "V3 fires (KSP only) | V3 % | AOI cloud > 30% | cloud % |")
    lines.append("|---|---:|---:|---:|---:|---:|---:|---:|---:|")
    for aoi in AOI_ORDER:
        rs = rows_by_aoi.get(aoi, [])
        n = len(rs)
        usable = sum(1 for r in rs if not r["no_usable_scene"])
        v4 = sum(1 for r in rs if r["flag_v4"])
        v4_pct = (100.0 * v4 / usable) if usable else float("nan")
        cloudy = sum(1 for r in rs if r["cloud_flag_present"])
        cloud_pct = (100.0 * cloudy / n) if n else float("nan")
        if aoi == "king_salman_park":
            v3 = sum(1 for r in rs if r["flag_v3"] is True)
            v3_pct = (100.0 * v3 / usable) if usable else float("nan")
            v3_str = f"{v3}"
            v3_pct_str = f"{v3_pct:.1f}%"
        else:
            v3_str = "—"
            v3_pct_str = "—"
        lines.append(
            f"| {AOI_TITLE[aoi]} | {n} | {usable} | {v4} | "
            f"{v4_pct:.1f}% | {v3_str} | {v3_pct_str} | {cloudy} | "
            f"{cloud_pct:.1f}% |"
        )
    lines.append("")
    return lines


def section_temporal(rows_by_aoi):
    lines = ["## 2. Temporal pattern", ""]
    for aoi in AOI_ORDER:
        rs = [r for r in rows_by_aoi.get(aoi, [])
              if not math.isnan(r["dbb"])]
        if not rs:
            lines.append(f"### {AOI_TITLE[aoi]}\n\nno usable rows\n")
            continue
        rs_sorted = sorted(rs, key=lambda r: r["dbb"], reverse=True)
        peak = rs_sorted[0]
        top5 = rs_sorted[:5]
        lines.append(f"### {AOI_TITLE[aoi]}")
        lines.append("")
        lines.append(
            f"**Peak DBB:** {peak['dbb']:+.4f} on {peak['scene_date']} "
            f"(`{peak['system_index']}`)"
        )
        lines.append("")
        lines.append("**Top 5 highest DBB:**")
        lines.append("")
        lines.append("| rank | scene_date | DBB | V4 | cloud_aoi% | system_index |")
        lines.append("|---:|---|---:|:-:|---:|---|")
        for i, r in enumerate(top5, 1):
            cstr = ("NaN" if math.isnan(r["cloud_pct_aoi"])
                    else f"{r['cloud_pct_aoi']:.2f}")
            lines.append(
                f"| {i} | {r['scene_date']} | {r['dbb']:+.4f} | "
                f"{'✓' if r['flag_v4'] else '✗'} | {cstr} | "
                f"`{r['system_index']}` |"
            )
        lines.append("")

        # Monthly histogram of V4 fires.
        hist = Counter(
            r["month"] for r in rows_by_aoi.get(aoi, []) if r["flag_v4"]
        )
        lines.append("**Monthly distribution of V4 fires (by calendar month):**")
        lines.append("")
        lines.append("| " + " | ".join(MONTH_NAMES[1:]) + " |")
        lines.append("|" + "---:|" * 12)
        lines.append("| " + " | ".join(str(hist.get(m, 0)) for m in range(1, 13)) + " |")
        lines.append("")
    return lines


def section_cross_check(rows):
    lines = ["## 3. Cross-check vs sq1bc_combined_calibration_confirmed.csv", ""]
    overlap_rows = [r for r in rows if r["calibration_subset_match"]]
    n_overlap = len(overlap_rows)
    n_fail = 0
    failures_listed = []
    if FAILURES_CSV.exists():
        with open(FAILURES_CSV) as f:
            for r in csv.DictReader(f):
                n_fail += 1
                failures_listed.append(r)
    n_pass = n_overlap - n_fail
    lines.append(f"- Overlap rows (calibration_subset_match=True): **{n_overlap}**")
    lines.append(f"- Passes (|sq2_dbb − cal_dbb| < 1e-4): **{n_pass}**")
    lines.append(f"- Failures: **{n_fail}**")
    if failures_listed:
        lines.append("")
        lines.append("| aoi | year-month | system_index | sq2_dbb | cal_dbb | delta |")
        lines.append("|---|---|---|---:|---:|---:|")
        for fa in failures_listed:
            lines.append(
                f"| {fa['aoi']} | {fa['year']}-{int(fa['month']):02d} | "
                f"`{fa['system_index']}` | {fa['sq2_dbb']} | "
                f"{fa['calibration_dbb']} | {fa['delta']} |"
            )
    lines.append("")
    return lines


def section_self_reference():
    return [
        "## 4. Self-reference test",
        "",
        "Performed at start of `sq2_apply_flag.py` run: pick KSP, set "
        "`test_scene = ref_scene`, compute DBB, assert `|DBB| < 1e-9`.",
        "Run aborts if the test fails. Successful completion of the operational "
        "sweep implies the test passed.",
        "",
    ]


def main():
    rows = load_rows()
    by_aoi = defaultdict(list)
    for r in rows:
        by_aoi[r["aoi"]].append(r)

    out = []
    out.append("# SQ2 summary stats — operational 228-scene set")
    out.append("")
    out.append(f"**Input:** `{IN_CSV.name}`  ")
    out.append(f"**Thresholds:** V4 = +{THRESH_V4:.3f} (all AOIs), "
               f"V3 = +{THRESH_V3:.3f} (KSP only).  ")
    out.append(f"**Coverage:** {len(rows)} (aoi, year, month) rows = "
               f"3 AOIs × 76 months (2020-01 … 2026-04).")
    out.append("")
    out += section_headline(by_aoi)
    out += section_temporal(by_aoi)
    out += section_cross_check(rows)
    out += section_self_reference()

    OUT_MD.write_text("\n".join(out))
    print(f"wrote {OUT_MD}")


if __name__ == "__main__":
    main()

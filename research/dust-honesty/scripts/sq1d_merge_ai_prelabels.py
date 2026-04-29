"""
SQ1D — merge AI pre-labels into KSP and Qiddiya relabel CSVs, write
canonical sq1d_references.json, and cross-check the JSON UVAI values
against the committed all-months CSVs.

Researcher reviewed both test montages at full resolution on 2026-04-29
and confirmed all 24 AI pre-labels — final_label = ai_prelabel for
every row in this commit.
"""
import csv
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
DATA = ROOT / "research/dust-honesty/data"

KSP_CSV = DATA / "sq1d_ksp_relabel.csv"
QIDDIYA_CSV = DATA / "sq1d_qiddiya_relabel.csv"
KSP_UVAI_CSV = DATA / "sq1d_ksp_uvai_all.csv"
QIDDIYA_UVAI_CSV = DATA / "sq1d_qiddiya_uvai_all.csv"
REFS_JSON = DATA / "sq1d_references.json"

KSP_PRELABELS = {
    "2021-02": ("clean", "high",
        "Sharp roads and runway features; deep contrast in airfield; urban grid crisp; clean colors throughout."),
    "2021-07": ("clean", "medium",
        "Slight warm cast on airfield consistent with surface (pre-demolition prep) not atmosphere; urban edges remain sharp and bright runway features crisp."),
    "2022-04": ("light_haze", "low",
        "Subtle uniform warm cast extends across urban areas not just airfield; edges still readable but scene contrast slightly compressed."),
    "2022-06": ("light_haze", "medium",
        "Stronger uniform yellow-warm cast; reduced overall scene contrast; urban features at bottom slightly washed."),
    "2022-07": ("light_haze", "low",
        "Bright wash across airfield with reduced contrast bleeding into urban grid; could be reflective bare ground but wash extends beyond surface area."),
    "2023-01": ("clean", "high",
        "Sharp building edges; distinct construction substrate colors orange and tan; clean shadows in surrounding urban grid."),
    "2024-01": ("clean", "high",
        "Sharp earthworks; distinct red and orange exposed soil; urban grid crisp throughout."),
    "2024-08": ("heavy_dust", "high",
        "Scene strongly washed with low overall contrast and slight warm tint; urban features at edges noticeably softened; consistent with August dust season in Riyadh."),
    "2025-02": ("clean", "medium",
        "Sharp building edges and good contrast; warm tone in construction zone is localized surface not atmospheric."),
    "2025-12": ("clean", "high",
        "Sharp construction details; good contrast across full scene."),
    "2026-01": ("clean", "high",
        "Sharp details and high contrast similar to 2025-12."),
}

QIDDIYA_PRELABELS = {
    "2020-01": ("clean", "high",
        "Deep canyon shadows; sharp bright cliffs; high scene contrast."),
    "2020-07": ("clean", "high",
        "Sharp canyon shadows; warm tones on upper plateau are localized surface (early construction) not atmospheric."),
    "2021-03": ("clean", "medium",
        "Slightly washed bright cliffs but canyon shadows still sharp; marginal call."),
    "2021-08": ("clean", "high",
        "Sharp shadows and bright cliffs; high contrast."),
    "2022-03": ("clean", "high",
        "Sharp canyon shadows; good scene contrast."),
    "2022-04": ("light_haze", "low",
        "Slight softening vs 2022-03; subtle warm cast across scene; canyon shadows marginally less deep."),
    "2022-09": ("light_haze", "medium",
        "More pronounced softening; lower scene contrast; bright cliffs noticeably dimmer than neighboring months."),
    "2023-09": ("clean", "high",
        "Sharp canyon shadows; new construction visible; high contrast."),
    "2024-02": ("clean", "high",
        "Sharp shadows; heavy construction visible; high contrast."),
    "2024-11": ("clean", "high",
        "Very deep dark canyon shadows; crisp bright cliffs; very high contrast."),
    "2025-04": ("clean", "high",
        "Heavy construction; sharp edges; high contrast."),
    "2025-07": ("clean", "high",
        "Sharp shadows and edges; high contrast."),
    "2026-03": ("clean", "high",
        "Sharp shadows and edges; high contrast."),
}

REFS = {
    "schema_version": 1,
    "locked_through": "2026-04-29",
    "selection_rule": "Cleanest UVAI from a date with surface-state representative of test scenes (not pure UVAI minimization).",
    "aois": {
        "qiddiya_core": {
            "primary": {
                "date": "2024-01-20",
                "uvai_mean": 0.310,
                "cloud_pct": 4.21,
                "cloud_note": "off-AOI",
                "rationale": "Post-construction-active surface; matches test-scene surface state at construction-active AOI.",
            },
            "sensitivity": {
                "date": "2021-01-10",
                "uvai_mean": -1.166,
                "rationale": "Atmosphere-cleanest pre-construction-surge.",
            },
            "locked_in_session": "2026-04-28",
        },
        "king_salman_park": {
            "primary": {
                "date": "2023-10-27",
                "uvai_mean": -0.067,
                "cloud_pct": 0.32,
                "rationale": "Pool B rank 1; midway through KSP construction evolution; matches surface state of post-demolition test scenes (10 of 11). Pool A candidates (2020-2021) show pre-demolition Riyadh Air Base — surface state matches only 1 test scene.",
            },
            "sensitivity": {
                "date": "2024-12-05",
                "uvai_mean": 0.336,
                "rationale": "More developed surface; catches threshold sensitivity to surface evolution within KSP construction window.",
            },
            "bbox_note": "References computed on tightened 16.6 km² bbox (committed 119db1b). Earlier 29.93 km² bbox candidates superseded.",
            "locked_in_session": "2026-04-29",
        },
        "diriyah_gate": {
            "primary": {
                "date": "2020-04-25",
                "uvai_mean": 0.082,
                "cloud_pct": 0.02,
                "rationale": "Surface-stable AOI; cleanest UVAI suffices.",
            },
            "sensitivity": None,
            "sensitivity_note": "None needed — AOI is surface-stable across study window.",
            "locked_in_session": "2026-04-28",
        },
    },
}

UVAI_TOLERANCE = 0.005


def merge(csv_path, prelabels):
    rows = list(csv.DictReader(open(csv_path)))
    expected_dates = set(r["date"] for r in rows)
    missing = expected_dates - set(prelabels.keys())
    extra = set(prelabels.keys()) - expected_dates
    if missing or extra:
        print(f"STOP: {csv_path.name} date mismatch — missing={sorted(missing)} extra={sorted(extra)}")
        sys.exit(2)
    for r in rows:
        ai_label, ai_conf, ai_reason = prelabels[r["date"]]
        r["ai_prelabel"] = ai_label
        r["ai_confidence"] = ai_conf
        r["ai_reasoning"] = ai_reason
        r["final_label"] = ai_label
    fields = list(rows[0].keys())
    with open(csv_path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, quoting=csv.QUOTE_MINIMAL)
        w.writeheader()
        w.writerows(rows)
    return rows


def report(name, rows):
    n = len(rows)
    final_dist = Counter(r["final_label"] for r in rows)
    nan_count = sum(
        1 for r in rows for k in ("ai_prelabel", "ai_confidence", "ai_reasoning", "final_label")
        if r[k] in ("", None) or str(r[k]).lower() == "nan"
    )
    disagree = [r for r in rows if r["ai_prelabel"] != r["old_label"]]
    print(f"\n=== {name} ===")
    print(f"  rows: {n}")
    print(f"  final_label distribution: {dict(final_dist)}")
    print(f"  empty/nan cells in ai_* + final_label: {nan_count}")
    print(f"  disagreements (ai_prelabel != old_label): {len(disagree)}")
    for r in disagree:
        print(f"    {r['date']}: old={r['old_label']} → ai={r['ai_prelabel']}")


def find_uvai(csv_path, target_date):
    with open(csv_path) as f:
        for row in csv.DictReader(f):
            if row["date"] == target_date:
                return float(row["uvai_mean"])
    return None


def cross_check():
    print("\n=== Cross-check JSON UVAI vs committed CSVs ===")
    failures = []

    qd = REFS["aois"]["qiddiya_core"]["primary"]
    actual_q = find_uvai(QIDDIYA_UVAI_CSV, qd["date"])
    if actual_q is None:
        print(f"  qiddiya_core {qd['date']}: NOT FOUND in {QIDDIYA_UVAI_CSV.name}")
        failures.append("qiddiya_core primary")
    else:
        diff = abs(actual_q - qd["uvai_mean"])
        ok = diff <= UVAI_TOLERANCE
        flag = "OK" if ok else "FAIL"
        print(f"  qiddiya_core {qd['date']}: json={qd['uvai_mean']:.4f} csv={actual_q:.4f} diff={diff:.4f} [{flag}]")
        if not ok:
            failures.append(f"qiddiya_core diff {diff:.4f}")

    kd = REFS["aois"]["king_salman_park"]["primary"]
    actual_k = find_uvai(KSP_UVAI_CSV, kd["date"])
    if actual_k is None:
        print(f"  king_salman_park {kd['date']}: NOT FOUND in {KSP_UVAI_CSV.name}")
        failures.append("ksp primary")
    else:
        diff = abs(actual_k - kd["uvai_mean"])
        ok = diff <= UVAI_TOLERANCE
        flag = "OK" if ok else "FAIL"
        print(f"  king_salman_park {kd['date']}: json={kd['uvai_mean']:.4f} csv={actual_k:.4f} diff={diff:.4f} [{flag}]")
        if not ok:
            failures.append(f"ksp diff {diff:.4f}")

    print("  diriyah_gate: no all-months UVAI CSV yet — skipped (next-session work).")
    return failures


def main():
    ksp_rows = merge(KSP_CSV, KSP_PRELABELS)
    qiddiya_rows = merge(QIDDIYA_CSV, QIDDIYA_PRELABELS)

    report("king_salman_park", ksp_rows)
    report("qiddiya_core", qiddiya_rows)

    REFS_JSON.write_text(json.dumps(REFS, indent=2, ensure_ascii=False))
    print(f"\nWrote {REFS_JSON}")

    failures = cross_check()
    if failures:
        print(f"\nSTOP: cross-check failures: {failures}")
        sys.exit(3)
    print("\nAll cross-checks passed.")


if __name__ == "__main__":
    main()

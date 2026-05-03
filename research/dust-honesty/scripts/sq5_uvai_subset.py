"""
SQ5 — UVAI quartile labels + UVAI × V4 contingency table.

Inputs:
  research/dust-honesty/data/operational/manifest_operational_sq2.csv (228 rows, AOI/date)
  research/dust-honesty/data/operational/dbb_operational_sq2.csv (V4 flag per row)
  research/dust-honesty/data/sq3_ndvi_per_scene.csv (NDVI per scene; for
    SQ5 candidate filter — must have NDVI to be a candidate)
  research/dust-honesty/data/calibration/uvai_ksp_sq1d.csv      (KSP UVAI)
  research/dust-honesty/data/calibration/uvai_qiddiya_sq1d.csv  (Qiddiya UVAI)
  research/dust-honesty/data/calibration/uvai_diriyah_sq1d.csv  (Diriyah UVAI)

Outputs:
  research/dust-honesty/data/sq5_uvai_labels.csv
    columns: aoi, acquisition_date, uvai_mean, uvai_quartile, v4_flag
  research/dust-honesty/data/sq5_uvai_v4_contingency.csv
    columns: aoi, in_q4, v4_fired, n

Schema asymmetry note (also surfaced in §2 of sq5_findings.md):
  The per-AOI UVAI CSVs do NOT carry an `aoi` column — AOI is implicit
  from the filename. Diriyah's CSV additionally has a `data_source` column
  (GEE_OFFL_L3 marker). This script injects AOI on load from a filename
  map. Per CLAUDE.md "infrastructure descriptions can drift from scripts"
  guardrail, this is documented in code as well as findings.

Quartile method:
  Per AOI, on the joined manifest+UVAI+NDVI candidate set, compute
  statistics.quantiles(uvai_mean, n=4) → [Q1_threshold, Q2_threshold,
  Q3_threshold]. Label scenes:
    uvai_mean ≤ Q1_threshold → 'Q1'
    uvai_mean ≥ Q3_threshold → 'Q4'
    otherwise                → 'Q2_Q3'

Sanity test:
  Re-running the quartile computation on the same input twice must
  produce identical labels (quartile boundaries are deterministic on
  sorted input). HALT on fail.

Note: this script does NOT proceed to pair-and-diff — the SQ5 paired
Q4-vs-Q1 design halted on R2 retention floor. See sq5_findings.md and
sq5_pair_retention_probe.csv for the halt receipt.
"""
from __future__ import annotations

import csv
import statistics
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
DATA = ROOT / "research/dust-honesty/data"

MANIFEST = DATA / "operational" / "manifest_operational_sq2.csv"
DBB_CSV = DATA / "operational" / "dbb_operational_sq2.csv"
NDVI_CSV = DATA / "ndvi_bias" / "ndvi_per_scene_sq3.csv"
UVAI_FILES = {
    "king_salman_park": DATA / "calibration" / "uvai_ksp_sq1d.csv",
    "qiddiya_core":     DATA / "calibration" / "uvai_qiddiya_sq1d.csv",
    "diriyah_gate":     DATA / "calibration" / "uvai_diriyah_sq1d.csv",
}
OUT_LABELS = DATA / "sq5_uvai_labels.csv"
OUT_CONTINGENCY = DATA / "sq5_uvai_v4_contingency.csv"

AOIS = ["king_salman_park", "qiddiya_core", "diriyah_gate"]


def load_v4_flags():
    """Return dict[(aoi, scene_date)] -> bool (V4 fired)."""
    out = {}
    with open(DBB_CSV) as f:
        for r in csv.DictReader(f):
            out[(r["aoi"], r["scene_date"])] = (r["flag_v4"] == "True")
    return out


def load_ndvi_dates():
    """Return set of (aoi, date) tuples that have a usable NDVI value."""
    out = set()
    with open(NDVI_CSV) as f:
        for r in csv.DictReader(f):
            if r["ndvi_aoi_mean"] != "":
                out.add((r["aoi"], r["scene_date"]))
    return out


def load_uvai_per_aoi():
    """Return dict[(aoi, date)] -> float uvai_mean.

    Per-AOI CSV does NOT have an `aoi` column — injected from filename
    map. Documented schema asymmetry per §2 of findings note.
    """
    out = {}
    for aoi, fpath in UVAI_FILES.items():
        with open(fpath) as f:
            for r in csv.DictReader(f):
                v = r.get("uvai_mean", "")
                if v == "":
                    continue
                out[(aoi, r["date"])] = float(v)
    return out


def quartile_labels(values):
    """Return (q1_threshold, q3_threshold, label_fn) for values list.

    label_fn(v) -> 'Q1' if v <= q1; 'Q4' if v >= q3; else 'Q2_Q3'.
    """
    qs = statistics.quantiles(values, n=4)
    q1_t, _, q3_t = qs

    def label_fn(v):
        if v <= q1_t:
            return "Q1"
        if v >= q3_t:
            return "Q4"
        return "Q2_Q3"
    return q1_t, q3_t, label_fn


def build_candidates():
    """Join manifest + ndvi + uvai + v4. Return list of dicts:
    {aoi, acquisition_date, uvai_mean, v4_flag}.
    """
    v4 = load_v4_flags()
    ndvi_dates = load_ndvi_dates()
    uvai = load_uvai_per_aoi()

    out = []
    with open(MANIFEST) as f:
        for r in csv.DictReader(f):
            if r["no_usable_scene"] == "True":
                continue
            aoi = r["aoi"]
            d = r["acquisition_date"]
            if (aoi, d) not in ndvi_dates:
                continue
            u = uvai.get((aoi, d))
            if u is None:
                continue
            out.append({
                "aoi": aoi,
                "acquisition_date": d,
                "uvai_mean": u,
                "v4_flag": v4.get((aoi, d), False),
            })
    return out


def assign_quartiles(candidates):
    """Mutate candidates in place to add 'uvai_quartile'. Return per-AOI
    threshold dict for receipt."""
    thresholds = {}
    for aoi in AOIS:
        sub = [c for c in candidates if c["aoi"] == aoi]
        vals = [c["uvai_mean"] for c in sub]
        if len(vals) < 4:
            raise RuntimeError(f"sanity-fail: {aoi} has {len(vals)} "
                               f"candidates, < 4 needed for quartiles")
        q1_t, q3_t, lab = quartile_labels(vals)
        thresholds[aoi] = (q1_t, q3_t, len(vals))
        for c in sub:
            c["uvai_quartile"] = lab(c["uvai_mean"])
    return thresholds


def sanity_test(candidates_a, candidates_b):
    """Assert two independent quartile assignments on the same candidate
    set produce identical labels. Determinism check."""
    if len(candidates_a) != len(candidates_b):
        raise RuntimeError(f"sanity-test FAILED: candidate count drift "
                           f"{len(candidates_a)} vs {len(candidates_b)}")
    diffs = []
    for a, b in zip(candidates_a, candidates_b):
        if (a["aoi"], a["acquisition_date"]) != (b["aoi"], b["acquisition_date"]):
            raise RuntimeError("sanity-test FAILED: row order drift")
        if a["uvai_quartile"] != b["uvai_quartile"]:
            diffs.append((a["aoi"], a["acquisition_date"],
                          a["uvai_quartile"], b["uvai_quartile"]))
    if diffs:
        raise RuntimeError(f"sanity-test FAILED: {len(diffs)} quartile "
                           f"label mismatches; first: {diffs[0]}")
    print(f"sanity-test PASSED ({len(candidates_a)} candidates, "
          f"identical quartile labels on twice-computed assignment)")


def write_labels(candidates):
    fields = ["aoi", "acquisition_date", "uvai_mean",
              "uvai_quartile", "v4_flag"]
    candidates = sorted(candidates, key=lambda r: (r["aoi"], r["acquisition_date"]))
    with open(OUT_LABELS, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for c in candidates:
            w.writerow({
                "aoi": c["aoi"],
                "acquisition_date": c["acquisition_date"],
                "uvai_mean": f"{c['uvai_mean']:+.6f}",
                "uvai_quartile": c["uvai_quartile"],
                "v4_flag": "True" if c["v4_flag"] else "False",
            })
    print(f"Wrote {OUT_LABELS} ({len(candidates)} rows)")


def write_contingency(candidates):
    """Per AOI x (in_q4 yes/no) x (v4 yes/no) cell count."""
    cells = defaultdict(int)
    for c in candidates:
        in_q4 = (c["uvai_quartile"] == "Q4")
        cells[(c["aoi"], in_q4, c["v4_flag"])] += 1
    fields = ["aoi", "in_q4", "v4_fired", "n"]
    with open(OUT_CONTINGENCY, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for aoi in AOIS:
            for in_q4 in (True, False):
                for v4 in (True, False):
                    n = cells[(aoi, in_q4, v4)]
                    w.writerow({
                        "aoi": aoi,
                        "in_q4": "True" if in_q4 else "False",
                        "v4_fired": "True" if v4 else "False",
                        "n": n,
                    })
    print(f"Wrote {OUT_CONTINGENCY}")


def main():
    print("SQ5 — UVAI quartile labels + UVAI × V4 contingency")
    print("  (halt-with-receipt: no pair-and-diff after this script)")
    print()

    candidates = build_candidates()
    print(f"Candidates with NDVI + UVAI: {len(candidates)}")

    thresholds = assign_quartiles(candidates)
    print()
    print("Per-AOI quartile thresholds:")
    print(f"  {'aoi':<22s} {'n':>4s} {'Q1_thresh':>10s} {'Q3_thresh':>10s}")
    for aoi in AOIS:
        q1, q3, n = thresholds[aoi]
        print(f"  {aoi:<22s} {n:>4d} {q1:>+10.3f} {q3:>+10.3f}")
    print()

    # Sanity: re-run independently
    candidates_b = build_candidates()
    assign_quartiles(candidates_b)
    candidates_b_sorted = sorted(candidates_b,
                                 key=lambda r: (r["aoi"], r["acquisition_date"]))
    candidates_a_sorted = sorted(candidates,
                                 key=lambda r: (r["aoi"], r["acquisition_date"]))
    sanity_test(candidates_a_sorted, candidates_b_sorted)
    print()

    write_labels(candidates)
    write_contingency(candidates)


if __name__ == "__main__":
    main()

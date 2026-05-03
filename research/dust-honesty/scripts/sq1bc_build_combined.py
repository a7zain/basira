"""
SQ1B re-re-run — build combined 73-scene calibration dataset.

Joins:
  - SQ1D 30-scene faithful DBB (sq1d_dbb_faithful.csv) with
    sq1d_<aoi>_relabel.csv (KSP, Qiddiya) and sq1_manual_labels.csv
    (Diriyah) for final_label.
  - SQ1C 43-scene faithful DBB (sq1c_dbb_faithful.csv) with the three
    sq1c_<aoi>_relabel.csv files for final_label, ai_confidence,
    bias_exposed_during_ai_labeling.

Output: research/dust-honesty/data/calibration/_archive/combined_calibration_preliminary.csv
Schema: row_id, source, aoi, date, sub_aoi, dbb_faithful,
        n_valid_pixels, n_total_pixels, final_label, ai_confidence,
        bias_exposed_during_ai_labeling, in_v3_scope, in_v4_scope
"""
import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
DATA = ROOT / "research/dust-honesty/data"

SQ1D_DBB = DATA / "dbb_compute" / "dbb_calibration_sq1d.csv"
SQ1C_DBB = DATA / "dbb_compute" / "dbb_calibration_sq1c.csv"

SQ1D_LABELS = {
    "king_salman_park": (DATA / "calibration" / "relabel_ksp_sq1d.csv", "date", "final_label"),
    "qiddiya_core":     (DATA / "calibration" / "relabel_qiddiya_sq1d.csv", "date", "final_label"),
    "diriyah_gate":     (DATA / "calibration" / "manual_labels_sq1.csv", "date", "label"),  # AOI col
}

SQ1C_RELABEL = {
    "king_salman_park": DATA / "calibration" / "relabel_ksp_sq1c.csv",
    "qiddiya_core":     DATA / "calibration" / "relabel_qiddiya_sq1c.csv",
    "diriyah_gate":     DATA / "calibration" / "relabel_diriyah_sq1c.csv",
}

OUT_CSV = DATA / "calibration" / "_archive" / "combined_calibration_preliminary.csv"

FIELDS = [
    "row_id", "source", "aoi", "date", "sub_aoi",
    "dbb_faithful", "n_valid_pixels", "n_total_pixels",
    "final_label", "ai_confidence", "bias_exposed_during_ai_labeling",
    "in_v3_scope", "in_v4_scope",
]


def load_sq1d_labels():
    """Return {(aoi, date_yyyy_mm): final_label}."""
    out = {}
    for aoi, (path, date_col, label_col) in SQ1D_LABELS.items():
        for r in csv.DictReader(open(path)):
            if aoi == "diriyah_gate" and r.get("AOI") != "diriyah_gate":
                continue
            d = r[date_col]
            out[(aoi, d)] = r[label_col]
    return out


def load_sq1c_relabel():
    """Return {(aoi, date_yyyy_mm_dd): {final_label, ai_confidence, bias}}."""
    out = {}
    for aoi, path in SQ1C_RELABEL.items():
        for r in csv.DictReader(open(path)):
            out[(aoi, r["date"])] = {
                "final_label": r["final_label"],
                "ai_confidence": r["ai_confidence"],
                "bias": r["bias_exposed_during_ai_labeling"],
            }
    return out


def main():
    sq1d_labels = load_sq1d_labels()
    sq1c_meta = load_sq1c_relabel()

    rows = []

    # --- SQ1D rows ---
    for r in csv.DictReader(open(SQ1D_DBB)):
        if not r.get("dbb_faithful"):
            continue
        aoi = r["sub_aoi"]
        date = r["date"]   # YYYY-MM
        # final_label is already in the SQ1D dbb CSV; keep it as authoritative.
        final_label = r.get("final_label") or sq1d_labels.get((aoi, date), "")
        rows.append({
            "source": "SQ1D",
            "aoi": aoi,
            "date": date,
            "sub_aoi": aoi,
            "dbb_faithful": float(r["dbb_faithful"]),
            "n_valid_pixels": int(r["n_valid_pixels"]),
            "n_total_pixels": int(r["n_total_pixels"]),
            "final_label": final_label,
            "ai_confidence": "",   # NaN equivalent for SQ1D
            "bias_exposed_during_ai_labeling": "False",
            "in_v3_scope": str(aoi == "king_salman_park"),
            "in_v4_scope": str(aoi in ("king_salman_park", "diriyah_gate")),
        })

    # --- SQ1C rows ---
    for r in csv.DictReader(open(SQ1C_DBB)):
        if not r.get("dbb_faithful"):
            continue
        aoi = r["sub_aoi"]
        date = r["date"]   # YYYY-MM-DD
        meta = sq1c_meta.get((aoi, date), {})
        rows.append({
            "source": "SQ1C",
            "aoi": aoi,
            "date": date,
            "sub_aoi": aoi,
            "dbb_faithful": float(r["dbb_faithful"]),
            "n_valid_pixels": int(r["n_valid_pixels"]),
            "n_total_pixels": int(r["n_total_pixels"]),
            "final_label": meta.get("final_label") or r.get("final_label", ""),
            "ai_confidence": meta.get("ai_confidence", ""),
            "bias_exposed_during_ai_labeling": meta.get("bias", "False"),
            "in_v3_scope": str(aoi == "king_salman_park"),
            "in_v4_scope": str(aoi in ("king_salman_park", "diriyah_gate")),
        })

    # assign row_id
    for i, r in enumerate(rows, 1):
        r["row_id"] = i

    # --- validate ---
    print(f"Total rows: {len(rows)}")
    assert len(rows) == 73, f"expected 73 rows, got {len(rows)}"
    no_dbb = [r for r in rows if r["dbb_faithful"] is None]
    assert not no_dbb, f"NaN dbb_faithful in {len(no_dbb)} rows"
    no_label = [r for r in rows if not r["final_label"]]
    assert not no_label, f"empty final_label in {len(no_label)} rows: {no_label[:3]}"
    n_bias = sum(1 for r in rows if r["bias_exposed_during_ai_labeling"] == "True")
    print(f"bias_exposed=True rows: {n_bias} (expected 6)")
    assert n_bias == 6
    # source split
    n_sq1d = sum(1 for r in rows if r["source"] == "SQ1D")
    n_sq1c = sum(1 for r in rows if r["source"] == "SQ1C")
    print(f"SQ1D rows: {n_sq1d} (expected 30)")
    print(f"SQ1C rows: {n_sq1c} (expected 43)")
    assert n_sq1d == 30 and n_sq1c == 43

    # --- write ---
    with open(OUT_CSV, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in FIELDS})
    print(f"Wrote {OUT_CSV}")

    # --- per-(aoi,source) label dist ---
    from collections import Counter
    print("\nLabel distribution per (aoi, source):")
    for aoi in ["king_salman_park", "qiddiya_core", "diriyah_gate"]:
        for src in ["SQ1D", "SQ1C"]:
            sub = [r for r in rows if r["aoi"] == aoi and r["source"] == src]
            c = Counter(r["final_label"] for r in sub)
            print(f"  {aoi:<20s} {src:<5s} n={len(sub):>3d}  {dict(c)}")


if __name__ == "__main__":
    main()

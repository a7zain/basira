"""
SQ1D — write blank relabel templates for KSP and Qiddiya.

Schema: date, sub_aoi, old_label, ai_prelabel, ai_confidence,
ai_reasoning, final_label.

Reads manual_labels_sq1.csv. Populates date, sub_aoi (from AOI),
old_label (from label). Leaves ai_* and final_label blank for the
post-render AI pre-label step + researcher review.

Outputs:
  research/dust-honesty/data/calibration/relabel_ksp_sq1d.csv      (overwrites a5ea00a)
  research/dust-honesty/data/calibration/relabel_qiddiya_sq1d.csv  (new)
"""
import csv
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
LABELS_CSV = ROOT / "research/dust-honesty/data/calibration/manual_labels_sq1.csv"
OUTPUTS = {
    "king_salman_park": ROOT / "research/dust-honesty/data/calibration/relabel_ksp_sq1d.csv",
    "qiddiya_core": ROOT / "research/dust-honesty/data/calibration/relabel_qiddiya_sq1d.csv",
}
FIELDS = [
    "date",
    "sub_aoi",
    "old_label",
    "ai_prelabel",
    "ai_confidence",
    "ai_reasoning",
    "final_label",
]


def main():
    rows_by_aoi = {aoi: [] for aoi in OUTPUTS}
    with open(LABELS_CSV) as f:
        for row in csv.DictReader(f):
            aoi = row["AOI"]
            if aoi not in rows_by_aoi:
                continue
            rows_by_aoi[aoi].append(
                {
                    "date": row["date"],
                    "sub_aoi": aoi,
                    "old_label": row["label"],
                    "ai_prelabel": "",
                    "ai_confidence": "",
                    "ai_reasoning": "",
                    "final_label": "",
                }
            )

    for aoi, out_path in OUTPUTS.items():
        rows = sorted(rows_by_aoi[aoi], key=lambda r: r["date"])
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=FIELDS)
            w.writeheader()
            w.writerows(rows)
        dist = Counter(r["old_label"] for r in rows)
        print(f"\n{aoi}: {len(rows)} rows → {out_path}")
        for k in sorted(dist):
            print(f"  {k}: {dist[k]}")

    print("\nCombined distribution (KSP + Qiddiya):")
    combined = Counter()
    for aoi in OUTPUTS:
        for r in rows_by_aoi[aoi]:
            combined[r["old_label"]] += 1
    for k in sorted(combined):
        print(f"  {k}: {combined[k]}")
    print(f"  TOTAL: {sum(combined.values())}")


if __name__ == "__main__":
    main()

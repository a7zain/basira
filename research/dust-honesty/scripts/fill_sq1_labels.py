#!/usr/bin/env python3
"""
fill_sq1_labels.py

Writes the reviewed SQ1 manual labels into
research/dust-honesty/data/calibration/manual_labels_sq1.csv.

Labels were produced by AI pre-labeling against a written rubric, then
reviewed and finalized by the researcher (Ahmed) on 2026-04-27 against
the full-resolution sq1_thumbnails.png.

Run from the basira repo root:
    python research/dust-honesty/scripts/fill_sq1_labels.py
"""

import csv
import sys
from pathlib import Path

CSV_PATH = Path("research/dust-honesty/data/calibration/manual_labels_sq1.csv")

# scene_id -> label
LABELS = {
    "qiddiya_core/2020-01":      "clean",
    "diriyah_gate/2020-04":      "clean",
    "qiddiya_core/2020-07":      "clean",
    "king_salman_park/2021-02":  "clean",
    "qiddiya_core/2021-03":      "clean",
    "king_salman_park/2021-07":  "clean",
    "qiddiya_core/2021-08":      "clean",
    "diriyah_gate/2021-11":      "cloud",
    "qiddiya_core/2022-03":      "light_haze",
    "king_salman_park/2022-04":  "heavy_dust",
    "qiddiya_core/2022-04":      "heavy_dust",
    "king_salman_park/2022-06":  "clean",
    "king_salman_park/2022-07":  "clean",
    "qiddiya_core/2022-09":      "clean",
    "diriyah_gate/2022-12":      "clean",
    "king_salman_park/2023-01":  "clean",
    "diriyah_gate/2023-05":      "clean",
    "qiddiya_core/2023-09":      "light_haze",
    "king_salman_park/2024-01":  "light_haze",
    "qiddiya_core/2024-02":      "clean",
    "diriyah_gate/2024-08":      "clean",
    "king_salman_park/2024-08":  "clean",
    "qiddiya_core/2024-11":      "clean",
    "diriyah_gate/2025-02":      "clean",
    "king_salman_park/2025-02":  "clean",
    "qiddiya_core/2025-04":      "clean",
    "qiddiya_core/2025-07":      "clean",
    "king_salman_park/2025-12":  "clean",
    "king_salman_park/2026-01":  "clean",
    "qiddiya_core/2026-03":      "light_haze",
}

VALID_LABELS = {"clean", "light_haze", "heavy_dust", "cloud", "mixed"}


def main() -> int:
    if not CSV_PATH.exists():
        print(f"ERROR: {CSV_PATH} not found. Run from basira repo root.",
              file=sys.stderr)
        return 1

    # Sanity check labels
    bad = [v for v in LABELS.values() if v not in VALID_LABELS]
    if bad:
        print(f"ERROR: invalid labels in script: {bad}", file=sys.stderr)
        return 1

    with CSV_PATH.open("r", newline="") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        rows = list(reader)

    if fieldnames is None or "scene_id" not in fieldnames or "label" not in fieldnames:
        print(f"ERROR: unexpected CSV schema. Got: {fieldnames}", file=sys.stderr)
        return 1

    matched = 0
    missing = []
    for row in rows:
        scene_id = row["scene_id"]
        if scene_id in LABELS:
            row["label"] = LABELS[scene_id]
            matched += 1
        else:
            missing.append(scene_id)

    if missing:
        print(f"WARNING: {len(missing)} CSV rows had no label in script:",
              file=sys.stderr)
        for s in missing:
            print(f"  {s}", file=sys.stderr)

    extra = set(LABELS) - {row["scene_id"] for row in rows}
    if extra:
        print(f"WARNING: {len(extra)} script labels had no CSV row:",
              file=sys.stderr)
        for s in extra:
            print(f"  {s}", file=sys.stderr)

    with CSV_PATH.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"OK: filled {matched}/{len(rows)} rows in {CSV_PATH}")

    # Distribution summary
    counts: dict[str, int] = {}
    for row in rows:
        lbl = row["label"] or "(empty)"
        counts[lbl] = counts.get(lbl, 0) + 1
    print("\nLabel distribution:")
    for lbl in sorted(counts):
        print(f"  {counts[lbl]:3d}  {lbl}")

    return 0


if __name__ == "__main__":
    sys.exit(main())

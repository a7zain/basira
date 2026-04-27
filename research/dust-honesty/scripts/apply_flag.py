"""
Apply the DBB index across the Phase 1 corpus, writing a flag table.

For SQ1 this produces the per-scene DBB mean. The threshold and
clean/haze/dust label assignment happen after Ahmed's manual labeling
in the SQ1 calibration notebook.

Usage:
    python apply_flag.py --out research/dust-honesty/data/dbb_corpus.csv
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

from dbb_index import dbb_scene_mean

REPO = Path(__file__).resolve().parents[3]
PHASE1 = REPO / "data" / "phase1"
AOIS = ["qiddiya_core", "king_salman_park", "diriyah_gate"]


def iter_scenes():
    for aoi in AOIS:
        for tif in sorted((PHASE1 / aoi).glob("*.tif")):
            yield aoi, tif.stem, tif  # stem = "YYYY-MM"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    rows = []
    for aoi, date, tif in iter_scenes():
        dbb = dbb_scene_mean(tif)
        rows.append({"date": date, "AOI": aoi, "scene_id": f"{aoi}/{date}", "dbb_mean": dbb})
        print(f"{aoi:20s} {date}  dbb_mean={dbb:+.4f}")

    with out_path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["date", "AOI", "scene_id", "dbb_mean"])
        w.writeheader()
        w.writerows(rows)
    print(f"\nWrote {len(rows)} rows -> {out_path}")


if __name__ == "__main__":
    main()

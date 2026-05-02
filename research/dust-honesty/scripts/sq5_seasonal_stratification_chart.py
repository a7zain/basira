"""
SQ5 — seasonal stratification chart (load-bearing visual halt receipt).

Input:
  research/dust-honesty/data/sq5_seasonal_stratification.csv

Output:
  research/dust-honesty/figures/sq5/sq5_seasonal_stratification.png

Per-AOI side-by-side calendar-month bars: Q1 (low UVAI, cool color)
vs Q4 (high UVAI, warm color). Visual proof of the halt cause —
high and low UVAI scenes live in different seasons; the ±60-day
paired temporal-neighbor design cannot bridge them at this site.
"""
from __future__ import annotations

import csv
from collections import defaultdict
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[3]
DATA = ROOT / "research/dust-honesty/data"
FIG = ROOT / "research/dust-honesty/figures/sq5"
FIG.mkdir(parents=True, exist_ok=True)

SRC = DATA / "sq5_seasonal_stratification.csv"
OUT = FIG / "sq5_seasonal_stratification.png"

AOIS = ["king_salman_park", "qiddiya_core", "diriyah_gate"]
AOI_LABELS = {
    "king_salman_park": "King Salman Park",
    "qiddiya_core": "Qiddiya core",
    "diriyah_gate": "Diriyah Gate",
}
MONTH_NAMES = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
               "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

Q1_COLOR = "#4a90d9"  # cool blue
Q4_COLOR = "#e07a3f"  # warm orange


def load_seasonal():
    out = defaultdict(lambda: {"q1": [0]*12, "q4": [0]*12})
    with open(SRC) as f:
        for r in csv.DictReader(f):
            m = int(r["calendar_month"])
            out[r["aoi"]]["q1"][m-1] = int(r["n_q1_scenes"])
            out[r["aoi"]]["q4"][m-1] = int(r["n_q4_scenes"])
    return out


def main():
    data = load_seasonal()
    fig, axes = plt.subplots(3, 1, figsize=(10, 9), sharex=True)

    x = np.arange(12)
    width = 0.4
    max_y = 0
    for ax, aoi in zip(axes, AOIS):
        q1 = data[aoi]["q1"]
        q4 = data[aoi]["q4"]
        max_y = max(max_y, max(q1 + q4))
        ax.bar(x - width/2, q1, width, color=Q1_COLOR,
               label="Q1 (low UVAI)", edgecolor="white", linewidth=0.6)
        ax.bar(x + width/2, q4, width, color=Q4_COLOR,
               label="Q4 (high UVAI)", edgecolor="white", linewidth=0.6)
        ax.set_title(AOI_LABELS[aoi], fontsize=11, loc="left")
        ax.set_ylabel("scene count")
        ax.grid(axis="y", alpha=0.3)
        ax.set_axisbelow(True)
        if ax is axes[0]:
            ax.legend(loc="upper right", fontsize=9, frameon=False)

    for ax in axes:
        ax.set_ylim(0, max_y + 1)
    axes[-1].set_xticks(x)
    axes[-1].set_xticklabels(MONTH_NAMES)
    axes[-1].set_xlabel("calendar month")

    fig.suptitle("Why Q4-vs-Q1 paired temporal-neighbor design halts at "
                 "Riyadh:\nseasonal stratification of UVAI",
                 fontsize=12, y=0.995)
    fig.text(0.5, 0.01,
             "Q1 scenes cluster in winter (Nov–Feb); Q4 scenes cluster in "
             "spring/summer (Mar–Aug).\nThe ±60-day pair window cannot "
             "bridge the seasonal gap. Pre-registered SQ5 retention "
             "halted at 0.0% / 11.1% / 11.1% (KSP / Qiddiya / Diriyah).",
             ha="center", fontsize=9, style="italic")
    fig.tight_layout(rect=[0, 0.04, 1, 0.97])
    fig.savefig(OUT, dpi=150)
    plt.close(fig)
    print(f"Wrote {OUT}")


if __name__ == "__main__":
    main()

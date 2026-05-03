"""
SQ2 — DBB time-series plots over the operational 228-scene set.

Reads sq2_dbb_operational.csv. Emits:
  - data/sq2_dbb_timeseries_king_salman_park.png
  - data/sq2_dbb_timeseries_qiddiya_core.png
  - data/sq2_dbb_timeseries_diriyah_gate.png
  - data/sq2_dbb_timeseries_combined.png  (3 stacked subplots)

Marker convention:
  filled circle = flag_v4 = True
  open circle   = flag_v4 = False
  X mark        = cloud_flag_present = True (overlay)
  gray dot      = no_usable_scene = True
Dashed horizontals: V4 +0.034 (all panels), V3 +0.053 (KSP only).
Light-grey vertical bands: Jun–Sep each year (visual season reference).

Usage:
    python sq2_plot_timeseries.py
"""
from __future__ import annotations

import csv
import math
from datetime import date
from pathlib import Path

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
DATA = ROOT / "research/dust-honesty/data"
FIGS = ROOT / "research/dust-honesty/figures"
IN_CSV = DATA / "operational" / "dbb_operational_sq2.csv"

OUT_PER_AOI = {
    "king_salman_park": FIGS / "operational" / "dbb_timeseries_king_salman_park_sq2.png",
    "qiddiya_core":     FIGS / "operational" / "dbb_timeseries_qiddiya_core_sq2.png",
    "diriyah_gate":     FIGS / "operational" / "dbb_timeseries_diriyah_gate_sq2.png",
}
OUT_COMBINED = FIGS / "operational" / "dbb_timeseries_combined_sq2.png"

THRESH_V4 = 0.034
THRESH_V3_KSP = 0.053

AOI_TITLE = {
    "king_salman_park": "King Salman Park",
    "qiddiya_core":     "Qiddiya core",
    "diriyah_gate":     "Diriyah Gate",
}

YEAR_MIN = 2020
YEAR_MAX = 2026

COLOR_FILLED = "#3b82a4"
COLOR_OPEN_EDGE = "#3b82a4"
COLOR_THRESH_V4 = "#c0392b"
COLOR_THRESH_V3 = "#7f6d92"
COLOR_NO_DATA = "#a0a0a0"
COLOR_CLOUD_X = "#000000"


def parse_date(s: str) -> date | None:
    s = (s or "").strip()
    if not s:
        return None
    try:
        return date.fromisoformat(s)
    except ValueError:
        return None


def to_bool(s) -> bool:
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
                "scene_date": parse_date(r["scene_date"]),
                "month_first": date(int(r["year"]), int(r["month"]), 1),
                "dbb": to_float(r["dbb"]),
                "flag_v4": to_bool(r["flag_v4"]),
                "flag_v3": to_bool(r["flag_v3_ksp_only"]) if r["flag_v3_ksp_only"] not in ("", None) else None,
                "cloud_flag_present": to_bool(r["cloud_flag_present"]),
                "no_usable_scene": to_bool(r["no_usable_scene"]),
            })
    return rows


def shade_summer_bands(ax):
    for year in range(YEAR_MIN, YEAR_MAX + 1):
        start = date(year, 6, 1)
        end = date(year, 9, 30)
        ax.axvspan(start, end, color="#f0f0f0", alpha=0.6, zorder=0)


def plot_one(ax, rows, aoi, show_v3=False):
    # X axis bounds: first day of YEAR_MIN..YEAR_MAX+1
    x_lo = date(YEAR_MIN, 1, 1)
    x_hi = date(YEAR_MAX, 5, 1)  # April 2026 cap + small margin

    # Compute y range from non-nan dbb values; include thresholds.
    vals = [r["dbb"] for r in rows if not math.isnan(r["dbb"])]
    if vals:
        y_lo = min(min(vals), -0.05) - 0.02
        y_hi = max(max(vals), THRESH_V4 + 0.02) + 0.02
        if show_v3:
            y_hi = max(y_hi, THRESH_V3_KSP + 0.02)
    else:
        y_lo, y_hi = -0.4, 0.4

    shade_summer_bands(ax)

    # Threshold lines.
    ax.axhline(THRESH_V4, color=COLOR_THRESH_V4, linestyle="--", lw=1.0,
               label=f"V4 threshold (+{THRESH_V4:.3f})")
    if show_v3:
        ax.axhline(THRESH_V3_KSP, color=COLOR_THRESH_V3, linestyle="--", lw=1.0,
                   label=f"V3 KSP threshold (+{THRESH_V3_KSP:.3f})")
    ax.axhline(0.0, color="grey", linestyle=":", lw=0.6, alpha=0.4)

    # Scatter points: choose x by scene_date if available, else month-first.
    fired = [r for r in rows if r["flag_v4"] and not r["no_usable_scene"]]
    not_fired = [r for r in rows if not r["flag_v4"] and not r["no_usable_scene"]]
    no_data = [r for r in rows if r["no_usable_scene"]]
    cloudy = [r for r in rows if r["cloud_flag_present"] and not r["no_usable_scene"]]

    def xs(rs):
        return [r["scene_date"] or r["month_first"] for r in rs]

    def ys(rs):
        return [r["dbb"] for r in rs]

    if not_fired:
        ax.scatter(xs(not_fired), ys(not_fired), s=42,
                   facecolors="none", edgecolors=COLOR_OPEN_EDGE, linewidths=1.2,
                   label="DBB ≤ +0.034 (V4 not fired)", zorder=3)
    if fired:
        ax.scatter(xs(fired), ys(fired), s=42,
                   c=COLOR_FILLED, edgecolors="black", linewidths=0.4,
                   label="DBB > +0.034 (V4 fired)", zorder=4)
    if cloudy:
        # Place X marks at the same y as the dbb scatter point.
        ax.scatter(xs(cloudy), ys(cloudy), s=70,
                   c=COLOR_CLOUD_X, marker="x", linewidths=1.4,
                   label="cloud_flag_present (AOI cloud > 30%)", zorder=5)
    if no_data:
        # Place gray dots at y=0 (no DBB available).
        ax.scatter([r["month_first"] for r in no_data],
                   [0.0] * len(no_data), s=20,
                   c=COLOR_NO_DATA, marker=".",
                   label="no usable scene", zorder=2)

    ax.set_xlim(x_lo, x_hi)
    ax.set_ylim(y_lo, y_hi)
    ax.xaxis.set_major_locator(mdates.MonthLocator(bymonth=(1, 7)))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
    ax.xaxis.set_minor_locator(mdates.MonthLocator())
    ax.tick_params(axis="x", labelrotation=45)
    ax.grid(axis="y", alpha=0.3, linestyle=":")
    ax.set_ylabel("DBB")


def per_aoi(rows_by_aoi):
    for aoi, rows in rows_by_aoi.items():
        rows = sorted(rows, key=lambda r: (r["year"], r["month"]))
        fig, ax = plt.subplots(1, 1, figsize=(11, 4))
        show_v3 = aoi == "king_salman_park"
        plot_one(ax, rows, aoi, show_v3=show_v3)
        ax.set_title(f"SQ2 — DBB time-series — {AOI_TITLE[aoi]} (n={len(rows)} months)",
                     fontsize=11)
        ax.legend(fontsize=8, loc="upper left", framealpha=0.9, ncol=2)
        fig.tight_layout()
        out = OUT_PER_AOI[aoi]
        fig.savefig(out, dpi=150, bbox_inches="tight")
        plt.close(fig)
        print(f"wrote {out}")


def combined(rows_by_aoi):
    aois = ["king_salman_park", "qiddiya_core", "diriyah_gate"]
    fig, axes = plt.subplots(3, 1, figsize=(11, 10), sharex=True)
    for ax, aoi in zip(axes, aois):
        rows = sorted(rows_by_aoi[aoi], key=lambda r: (r["year"], r["month"]))
        show_v3 = aoi == "king_salman_park"
        plot_one(ax, rows, aoi, show_v3=show_v3)
        ax.set_title(f"{AOI_TITLE[aoi]} (n={len(rows)} months)", fontsize=10)
    # Single shared legend (drawn from KSP panel, which carries the V3 line).
    h, l = axes[0].get_legend_handles_labels()
    fig.legend(h, l, loc="lower center", ncol=3, fontsize=9,
               bbox_to_anchor=(0.5, -0.02))
    fig.suptitle("SQ2 — DBB time-series across operational 228-scene set "
                 "(76 months × 3 AOIs)", fontsize=12, y=1.0)
    fig.tight_layout(rect=(0, 0.02, 1, 0.99))
    fig.savefig(OUT_COMBINED, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"wrote {OUT_COMBINED}")


def main():
    rows = load_rows()
    print(f"loaded {len(rows)} rows from {IN_CSV.name}")
    by_aoi = {}
    for r in rows:
        by_aoi.setdefault(r["aoi"], []).append(r)
    print(f"AOI counts: {dict((a, len(v)) for a, v in by_aoi.items())}")
    per_aoi(by_aoi)
    combined(by_aoi)


if __name__ == "__main__":
    main()

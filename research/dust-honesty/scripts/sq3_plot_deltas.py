"""
SQ3 — figures.

Inputs:
  research/dust-honesty/data/sq3_ndvi_bias.csv
  research/dust-honesty/data/sq3_pairing_audit.csv

Outputs (under research/dust-honesty/figures/sq3/):
  sq3_delta_hist_<aoi>.png         (3 PNGs, one per AOI)
  sq3_forest_plot.png              (combined forest plot)
  sq3_retention.png                (per-AOI pairing retention bar chart)
"""
from __future__ import annotations

import csv
import math
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[3]
DATA = ROOT / "research/dust-honesty/data"
FIGDIR = ROOT / "research/dust-honesty/figures/sq3"

BIAS_CSV = DATA / "sq3_ndvi_bias.csv"
AUDIT_CSV = DATA / "sq3_pairing_audit.csv"

AOI_ORDER = ["king_salman_park", "qiddiya_core", "diriyah_gate"]
AOI_LABEL = {
    "king_salman_park": "King Salman Park",
    "qiddiya_core": "Qiddiya core",
    "diriyah_gate": "Diriyah Gate",
}
AOI_SHORT = {
    "king_salman_park": "ksp",
    "qiddiya_core": "qiddiya",
    "diriyah_gate": "diriyah",
}


def load_bias():
    by_aoi = {a: [] for a in AOI_ORDER}
    with open(BIAS_CSV) as f:
        for r in csv.DictReader(f):
            by_aoi[r["aoi"]].append(float(r["delta_ndvi"]))
    return by_aoi


def load_audit():
    rows = []
    with open(AUDIT_CSV) as f:
        for r in csv.DictReader(f):
            rows.append({
                "aoi": r["aoi"],
                "n_fired_total": int(r["n_fired_total"]),
                "n_paired": int(r["n_paired"]),
                "retention_pct": float(r["retention_pct"]),
                "mean_delta": float(r["mean_delta"]) if r["mean_delta"] else float("nan"),
                "ci_lo_95": float(r["ci_lo_95"]) if r["ci_lo_95"] else float("nan"),
                "ci_hi_95": float(r["ci_hi_95"]) if r["ci_hi_95"] else float("nan"),
                "ci_halfwidth": float(r["ci_halfwidth"]) if r["ci_halfwidth"] else float("nan"),
                "signal_class": r["signal_class"],
            })
    return {r["aoi"]: r for r in rows}


def plot_aoi_hist(aoi, deltas, audit_row):
    FIGDIR.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(7, 4.5))
    if deltas:
        # Bin width: ~0.01 NDVI is a small but visible step; clamp range.
        lo = min(deltas) - 0.005
        hi = max(deltas) + 0.005
        nbins = max(8, min(30, int(round((hi - lo) / 0.01))))
        ax.hist(deltas, bins=nbins, color="#4477aa", edgecolor="black",
                alpha=0.85)
    ax.axvline(0, color="red", linewidth=1.5, label="Δ = 0")
    if not math.isnan(audit_row["mean_delta"]):
        ax.axvline(audit_row["mean_delta"], color="black", linewidth=2,
                   label=f"mean Δ = {audit_row['mean_delta']:+.4f}")
    if not math.isnan(audit_row["ci_lo_95"]):
        ax.axvline(audit_row["ci_lo_95"], color="black", linestyle="--",
                   linewidth=1.2, label=f"95% CI [{audit_row['ci_lo_95']:+.4f}, "
                                       f"{audit_row['ci_hi_95']:+.4f}]")
        ax.axvline(audit_row["ci_hi_95"], color="black", linestyle="--",
                   linewidth=1.2)
    ax.set_xlabel("Δ NDVI = NDVI(fired) − NDVI(neighbor)")
    ax.set_ylabel("count of pairs")
    ax.set_title(f"{AOI_LABEL[aoi]} — NDVI bias on V4-fired vs unflagged "
                 f"neighbor\n"
                 f"n_paired = {audit_row['n_paired']} / "
                 f"n_fired = {audit_row['n_fired_total']} "
                 f"({audit_row['retention_pct']:.1f}% retention) — "
                 f"signal: {audit_row['signal_class']}")
    ax.legend(loc="upper left", fontsize=9)
    ax.grid(True, alpha=0.3)
    out = FIGDIR / f"sq3_delta_hist_{AOI_SHORT[aoi]}.png"
    fig.tight_layout()
    fig.savefig(out, dpi=150)
    plt.close(fig)
    print(f"wrote {out}")


def plot_forest(audit):
    fig, ax = plt.subplots(figsize=(8, 4))
    aoi_sorted = sorted(AOI_ORDER, key=lambda a: audit[a]["mean_delta"]
                        if not math.isnan(audit[a]["mean_delta"]) else 0)
    y = np.arange(len(aoi_sorted))
    means = [audit[a]["mean_delta"] for a in aoi_sorted]
    los = [audit[a]["ci_lo_95"] for a in aoi_sorted]
    his = [audit[a]["ci_hi_95"] for a in aoi_sorted]
    err_lo = [m - lo if not math.isnan(lo) else 0 for m, lo in zip(means, los)]
    err_hi = [hi - m if not math.isnan(hi) else 0 for m, hi in zip(means, his)]

    color_for = {
        "signal_negative": "#cc3333",
        "signal_positive": "#3366cc",
        "tight_null": "#22aa55",
        "wide_inconclusive": "#888888",
    }
    colors = [color_for.get(audit[a]["signal_class"], "#888888")
              for a in aoi_sorted]

    ax.errorbar(means, y, xerr=[err_lo, err_hi], fmt="o", capsize=5,
                ecolor="black", elinewidth=1.5,
                markersize=10, markerfacecolor="white",
                markeredgewidth=2)
    # color the markers by signal class
    for yi, mi, ci in zip(y, means, colors):
        ax.plot(mi, yi, "o", markersize=10, markerfacecolor=ci,
                markeredgecolor="black", markeredgewidth=1.5)

    ax.axvline(0, color="black", linewidth=1, alpha=0.5)
    labels = []
    for a in aoi_sorted:
        ar = audit[a]
        labels.append(f"{AOI_LABEL[a]}  (n={ar['n_paired']}; "
                      f"{ar['signal_class']})")
    ax.set_yticks(y)
    ax.set_yticklabels(labels)
    ax.set_xlabel("Mean Δ NDVI = NDVI(fired) − NDVI(neighbor),  "
                  "bars = 95% bootstrap CI")
    ax.set_title("SQ3 forest plot — paired-temporal-neighbor NDVI bias on "
                 "V4-fired scenes")
    ax.grid(True, alpha=0.3, axis="x")
    out = FIGDIR / "sq3_forest_plot.png"
    fig.tight_layout()
    fig.savefig(out, dpi=150)
    plt.close(fig)
    print(f"wrote {out}")


def plot_retention(audit):
    fig, ax = plt.subplots(figsize=(7, 4))
    aois = AOI_ORDER
    pcts = [audit[a]["retention_pct"] for a in aois]
    n_paired = [audit[a]["n_paired"] for a in aois]
    n_fired = [audit[a]["n_fired_total"] for a in aois]
    bar_colors = ["#3366cc" if p >= 70 else "#cc6633" for p in pcts]
    bars = ax.bar([AOI_LABEL[a] for a in aois], pcts,
                  color=bar_colors, edgecolor="black")
    for b, p, np_, nf in zip(bars, pcts, n_paired, n_fired):
        ax.text(b.get_x() + b.get_width() / 2, p + 1.5,
                f"{np_}/{nf}\n{p:.1f}%",
                ha="center", va="bottom", fontsize=10)
    ax.axhline(70, color="grey", linestyle="--", linewidth=1,
               label="reference: 70%")
    ax.set_ylim(0, max(pcts + [100]) + 10)
    ax.set_ylabel("Pairing retention (%)")
    ax.set_title("SQ3 — fraction of V4-fired scenes paired to an unflagged "
                 "neighbor (|Δt| ≤ 60 d)")
    ax.legend(loc="lower right")
    ax.grid(True, alpha=0.3, axis="y")
    out = FIGDIR / "sq3_retention.png"
    fig.tight_layout()
    fig.savefig(out, dpi=150)
    plt.close(fig)
    print(f"wrote {out}")


def main():
    by_aoi = load_bias()
    audit = load_audit()
    for aoi in AOI_ORDER:
        plot_aoi_hist(aoi, by_aoi[aoi], audit[aoi])
    plot_forest(audit)
    plot_retention(audit)
    print()
    print(f"Figures dir: {FIGDIR}")


if __name__ == "__main__":
    main()

"""
SQ4 — summary tables + figures.

Outputs (under research/dust-honesty/figures/sq4/):
  sq4_forest_diff_of_diffs.png  — per-AOI mean ± 95% CI on diff_of_diffs
  sq4_scatter_<aoi>.png × 3     — Δ Sen2Cor (x) vs Δ HLS (y), 1:1 line
  sq4_coverage_chart.png        — HLS coverage % per AOI vs SQ3 pair count

Also writes research/dust-honesty/data/sq4_summary_stats.md (1-page table)
"""
from __future__ import annotations

import csv
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[3]
DATA = ROOT / "research/dust-honesty/data"
FIG = ROOT / "research/dust-honesty/figures/cross_correction"
FIG.mkdir(parents=True, exist_ok=True)

DIFF_CSV = DATA / "cross_correction" / "diff_of_diffs_lasrc_sq4.csv"
CLASS_CSV = DATA / "cross_correction" / "signal_class_sq4.csv"
COVERAGE_CSV = DATA / "cross_correction" / "coverage_probe_sq4.csv"
HLS_CSV = DATA / "cross_correction" / "ndvi_hls_s30_b8a_sq4.csv"
PAIRS_CSV = DATA / "ndvi_bias" / "paired_sen2cor_sq3.csv"
OUT_MD = DATA / "cross_correction" / "summary_stats_sq4.md"

AOIS = ["king_salman_park", "qiddiya_core", "diriyah_gate"]
AOI_LABELS = {
    "king_salman_park": "King Salman Park",
    "qiddiya_core": "Qiddiya core",
    "diriyah_gate": "Diriyah Gate",
}
AOI_COLORS = {
    "king_salman_park": "#2a9d8f",
    "qiddiya_core": "#e76f51",
    "diriyah_gate": "#264653",
}


def load_class():
    rows = []
    with open(CLASS_CSV) as f:
        for r in csv.DictReader(f):
            for k in ("mean_diff", "ci_lo_95", "ci_hi_95", "ci_halfwidth"):
                r[k] = float(r[k]) if r[k] != "" else float("nan")
            r["n_sq3_pairs"] = int(r["n_sq3_pairs"])
            r["n_pairs_with_hls"] = int(r["n_pairs_with_hls"])
            rows.append(r)
    return rows


def load_diffs():
    rows = []
    with open(DIFF_CSV) as f:
        for r in csv.DictReader(f):
            for k in ("delta_sen2cor", "delta_hls", "diff_of_diffs"):
                r[k] = float(r[k])
            rows.append(r)
    return rows


def forest_plot(class_rows):
    fig, ax = plt.subplots(figsize=(8, 4))
    y_positions = list(range(len(class_rows)))
    for y, r in zip(y_positions, class_rows):
        c = AOI_COLORS[r["aoi"]]
        ax.errorbar(
            r["mean_diff"], y,
            xerr=[[r["mean_diff"] - r["ci_lo_95"]],
                  [r["ci_hi_95"] - r["mean_diff"]]],
            fmt="o", color=c, ecolor=c, elinewidth=2, capsize=6,
            markersize=10,
        )
        ax.text(r["mean_diff"], y + 0.18,
                f"n={r['n_pairs_with_hls']}/{r['n_sq3_pairs']}  "
                f"{r['signal_class']}",
                ha="center", va="bottom", fontsize=9, color=c)
    ax.axvline(0, color="gray", lw=0.8, ls="--")
    ax.set_yticks(y_positions)
    ax.set_yticklabels([AOI_LABELS[r["aoi"]] for r in class_rows])
    ax.set_xlabel("diff_of_diffs  =  Δ NDVI (HLS LaSRC) − Δ NDVI (S2 Sen2Cor)")
    ax.set_title("SQ4 — HLS vs Sen2Cor Δ NDVI on V4-flagged pairs\n"
                 "(per-AOI mean ± bootstrap 95% CI; pairs from SQ3)")
    ax.set_xlim(-0.025, 0.025)
    ax.invert_yaxis()
    ax.grid(axis="x", alpha=0.3)
    fig.tight_layout()
    out = FIG / "forest_diff_of_diffs_sq4.png"
    fig.savefig(out, dpi=150)
    plt.close(fig)
    print(f"  Wrote {out}")


def scatter_plot(diff_rows, aoi):
    sub = [r for r in diff_rows if r["aoi"] == aoi]
    if not sub:
        print(f"  SKIP scatter {aoi}: no rows")
        return
    fig, ax = plt.subplots(figsize=(5.5, 5.5))
    xs = [r["delta_sen2cor"] for r in sub]
    ys = [r["delta_hls"] for r in sub]
    ax.scatter(xs, ys, color=AOI_COLORS[aoi], s=60, alpha=0.85,
               edgecolor="white", linewidth=1.2)
    lo = min(min(xs), min(ys)) - 0.01
    hi = max(max(xs), max(ys)) + 0.01
    ax.plot([lo, hi], [lo, hi], color="gray", ls="--", lw=1, label="1:1")
    ax.set_xlim(lo, hi)
    ax.set_ylim(lo, hi)
    ax.set_xlabel("Δ NDVI  (Sen2Cor L2A, SQ3)")
    ax.set_ylabel("Δ NDVI  (HLS S30 LaSRC, SQ4)")
    ax.set_title(f"SQ4 — {AOI_LABELS[aoi]}\n"
                 f"per-pair Δ HLS vs Δ Sen2Cor  (n={len(sub)})")
    ax.axhline(0, color="gray", lw=0.5, alpha=0.5)
    ax.axvline(0, color="gray", lw=0.5, alpha=0.5)
    ax.legend(loc="upper left", fontsize=9)
    ax.grid(alpha=0.3)
    fig.tight_layout()
    out = FIG / f"scatter_{aoi}_sq4.png"
    fig.savefig(out, dpi=150)
    plt.close(fig)
    print(f"  Wrote {out}")


def coverage_chart(class_rows):
    """Bar chart of HLS coverage % per AOI vs SQ3 pair count.
    coverage = pairs_with_hls / sq3_pairs.
    """
    fig, ax = plt.subplots(figsize=(7, 4))
    aois = [r["aoi"] for r in class_rows]
    n_sq3 = np.array([r["n_sq3_pairs"] for r in class_rows])
    n_kept = np.array([r["n_pairs_with_hls"] for r in class_rows])
    coverage_pct = 100.0 * n_kept / n_sq3
    x = np.arange(len(aois))
    ax.bar(x - 0.2, n_sq3, width=0.4,
           color=[AOI_COLORS[a] for a in aois], alpha=0.4,
           label="SQ3 pairs")
    ax.bar(x + 0.2, n_kept, width=0.4,
           color=[AOI_COLORS[a] for a in aois], alpha=0.95,
           label="SQ4 pairs (HLS-covered)")
    for xi, n3, nk, pct in zip(x, n_sq3, n_kept, coverage_pct):
        ax.text(xi + 0.2, nk + 0.2, f"{pct:.0f}%",
                ha="center", va="bottom", fontsize=9)
        ax.text(xi - 0.2, n3 + 0.2, f"{n3}",
                ha="center", va="bottom", fontsize=8, color="gray")
    ax.set_xticks(x)
    ax.set_xticklabels([AOI_LABELS[a] for a in aois])
    ax.set_ylabel("pair count")
    ax.set_title("SQ4 — HLS-pair retention vs SQ3 pair count")
    ax.legend(loc="upper right", fontsize=9)
    ax.grid(axis="y", alpha=0.3)
    fig.tight_layout()
    out = FIG / "coverage_chart_sq4.png"
    fig.savefig(out, dpi=150)
    plt.close(fig)
    print(f"  Wrote {out}")


def write_md(class_rows):
    """Per-AOI 1-page table to sq4_summary_stats.md."""
    lines = [
        "# SQ4 — HLS vs Sen2Cor Δ NDVI: per-AOI summary",
        "",
        f"Pairs from SQ3 (n=38). HLS NDVI computed at AOI mean, native 30 m, ",
        "Fmask bits 1-4 masked (cloud, adj, shadow, snow). NIR band: HLS B8A ",
        "(narrow ~865 nm); Red: HLS B4 ~665 nm. SQ3 Sen2Cor used B8 broad ",
        "NIR ~833 nm — see §5 of sq4_findings.md for the band-shift caveat.",
        "",
        "diff_of_diffs = Δ NDVI (HLS LaSRC) − Δ NDVI (S2 Sen2Cor)  per pair.",
        "Bootstrap: 1000 resamples on pairs (seed 42).",
        "",
        "| AOI | n_kept / n_sq3 | mean diff | 95% CI | halfwidth | signal_class |",
        "|---|---:|---:|---|---:|---|",
    ]
    for r in class_rows:
        ci = f"[{r['ci_lo_95']:+.4f}, {r['ci_hi_95']:+.4f}]"
        lines.append(
            f"| {AOI_LABELS[r['aoi']]} | "
            f"{r['n_pairs_with_hls']}/{r['n_sq3_pairs']} | "
            f"{r['mean_diff']:+.4f} | {ci} | "
            f"{r['ci_halfwidth']:.4f} | `{r['signal_class']}` |"
        )
    lines.append("")
    lines.append("Per-AOI scope-conditional reads:")
    for r in class_rows:
        sc = r["signal_class"]
        if sc == "tight_null":
            lines.append(
                f"- **{AOI_LABELS[r['aoi']]}**: tight null. HLS LaSRC and "
                f"Sen2Cor agree on Δ NDVI to within "
                f"halfwidth {r['ci_halfwidth']:.4f}. The SQ3 conditional null "
                f"is not Sen2Cor-specific at this AOI."
            )
        elif sc == "wide_inconclusive":
            lines.append(
                f"- **{AOI_LABELS[r['aoi']]}**: wide-inconclusive on n alone "
                f"(n={r['n_pairs_with_hls']}). CI halfwidth "
                f"{r['ci_halfwidth']:.4f} is above the {0.01:.2f} tight-null "
                f"threshold — same SQ8 AERONET hook as SQ3."
            )
        elif sc == "correction_chains_disagree":
            lines.append(
                f"- **{AOI_LABELS[r['aoi']]}**: CI excludes zero "
                f"(mean {r['mean_diff']:+.4f}). HLS LaSRC and Sen2Cor "
                f"disagree on Δ NDVI direction — bias localizes to one "
                f"correction chain at this AOI."
            )
    OUT_MD.write_text("\n".join(lines) + "\n")
    print(f"  Wrote {OUT_MD}")


def main():
    class_rows = load_class()
    diff_rows = load_diffs()
    print(f"Loaded {len(class_rows)} AOI summary rows, "
          f"{len(diff_rows)} pair diff rows")
    print()
    print("Figures:")
    forest_plot(class_rows)
    for aoi in AOIS:
        scatter_plot(diff_rows, aoi)
    coverage_chart(class_rows)
    print()
    print("Summary table:")
    write_md(class_rows)


if __name__ == "__main__":
    main()

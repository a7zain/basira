"""
piece B §4: Qiddiya construction-substrate convergence panel.

Six independent lines of evidence that the satellite-detected "atmospheric"
signal at Qiddiya is dominated by construction-substrate confusion rather
than by atmosphere. Qiddiya is rendered in warm orange against KSP teal
and Diriyah dark-navy (the project AOI palette per sq8_summary.py) —
Qiddiya sits at the extreme position in all six panels and the warm-vs-cool
contrast carries the convergence story.

Panels (2x3, horizontal bars):
  P1 SQ1D blind relabel    : % AI pre-labels overridden to "clean"
  P2 SQ1D Part B sensitivity: Spearman rho between primary and alt DBB
  P3 SQ1B threshold-fit AUC : pool-with-Qiddiya (V2) vs pool-without (V4)
  P4 SQ2 operational DBB    : median DBB minus V4 threshold (+0.034)
  P5 SQ3 paired retention   : % V4-flagged scenes successfully paired
  P6 SQ5 Q4 cap V4 contingency: % of highest-UVAI-quartile that fired V4

Notes on data:
- P1: SQ1D omitted Diriyah by design. KSP and Qiddiya use sq1d_*_relabel.csv
  and the metric is `old_label != "clean" AND final_label == "clean"`
  (the AI prior label is the SQ1B label that SQ1D's visually-blind pass
  overrode). Diriyah uses relabel_diriyah_sq1c.csv with the
  analogous `ai_prelabel != "clean" AND final_label == "clean"`
  (SQ1C's relabel structure has ai_prelabel as the prior AI label).
  "Toward clean" is strict: heavy_dust -> light_haze does NOT count.
- P2: dbb_calibration_alt_sq1d.csv excluded Diriyah by design (Part B was
  per-AOI on KSP+Qiddiya only). Diriyah cell renders as N/A.

Output: research/dust-honesty/figures/qiddiya_convergence_panel.png (300 dpi)
"""
import sys
from pathlib import Path
import numpy as np
import pandas as pd

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from scipy.stats import spearmanr


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
OUT  = ROOT / "figures" / "qiddiya_convergence_panel.png"

AOI_ORDER = ["king_salman_park", "qiddiya_core", "diriyah_gate"]
AOI_LABEL = {
    "king_salman_park": "KSP",
    "qiddiya_core":     "Qiddiya",
    "diriyah_gate":     "Diriyah",
}
COLOR = {
    "king_salman_park": "#2a9d8f",
    "qiddiya_core":     "#e76f51",
    "diriyah_gate":     "#264653",
}

V4_THRESHOLD = 0.034
HALT_PCT = 30.0


def panel1_override_to_clean():
    out = {}
    df = pd.read_csv(DATA / "calibration" / "relabel_ksp_sq1d.csv")
    n = len(df)
    k = int(((df["old_label"] != "clean") & (df["final_label"] == "clean")).sum())
    out["king_salman_park"] = (k / n * 100.0, k, n, "SQ1D old->final")

    df = pd.read_csv(DATA / "calibration" / "relabel_qiddiya_sq1d.csv")
    n = len(df)
    k = int(((df["old_label"] != "clean") & (df["final_label"] == "clean")).sum())
    out["qiddiya_core"] = (k / n * 100.0, k, n, "SQ1D old->final")

    df = pd.read_csv(DATA / "calibration" / "relabel_diriyah_sq1c.csv")
    n = len(df)
    k = int(((df["ai_prelabel"] != "clean") & (df["final_label"] == "clean")).sum())
    out["diriyah_gate"] = (k / n * 100.0, k, n, "SQ1C ai_pre->final")
    return out


def panel2_spearman():
    p = pd.read_csv(DATA / "dbb_compute" / "dbb_calibration_sq1d.csv")
    a = pd.read_csv(DATA / "dbb_compute" / "dbb_calibration_alt_sq1d.csv")
    out = {}
    for aoi in AOI_ORDER:
        pa = p[p["sub_aoi"] == aoi].copy()
        aa = a[a["sub_aoi"] == aoi].copy()
        if len(aa) == 0:
            out[aoi] = (None, 0)
            continue
        merged = pa.merge(aa, on=["date", "sub_aoi"], suffixes=("_p", "_a"))
        if len(merged) < 3:
            out[aoi] = (None, len(merged))
            continue
        rho, _ = spearmanr(merged["dbb_faithful_p"], merged["dbb_faithful_a"])
        out[aoi] = (float(rho), len(merged))
    return out


def panel3_auc():
    df = pd.read_csv(DATA / "threshold_fits" / "threshold_v4_confirmed_sq1b.csv")
    v2 = float(df.loc[df["variant"] == "V2", "auc"].iloc[0])
    v4 = float(df.loc[df["variant"] == "V4", "auc"].iloc[0])
    return {"with_qiddiya": v2, "without_qiddiya": v4}


def panel4_above_threshold():
    df = pd.read_csv(DATA / "operational" / "dbb_operational_sq2.csv")
    df = df[(~df["no_usable_scene"]) & (df["dbb"].notna())]
    out = {}
    for aoi in AOI_ORDER:
        sub = df[df["aoi"] == aoi]
        med = float(sub["dbb"].median())
        out[aoi] = (med - V4_THRESHOLD, med, len(sub))
    return out


def panel5_retention():
    df = pd.read_csv(DATA / "ndvi_bias" / "pairing_audit_sq3.csv")
    out = {}
    for aoi in AOI_ORDER:
        out[aoi] = float(df.loc[df["aoi"] == aoi, "retention_pct"].iloc[0])
    return out


def panel6_q4_v4():
    df = pd.read_csv(DATA / "halts" / "uvai_sq5" / "uvai_v4_contingency.csv")
    out = {}
    for aoi in AOI_ORDER:
        sub = df[df["aoi"] == aoi]
        q4 = sub[sub["in_q4"]]
        n_q4 = int(q4["n"].sum())
        n_q4_v4 = int(q4.loc[q4["v4_fired"], "n"].sum())
        out[aoi] = (n_q4_v4 / n_q4 * 100.0, n_q4_v4, n_q4)
    return out


def hbar(ax, values, labels, colors, value_fmt, xlabel,
         xlim=None, vline=None, vline_text=None, na_text="N/A"):
    y = np.arange(len(labels))
    plot_vals = [(v if v is not None else 0.0) for v in values]
    bars = ax.barh(y, plot_vals, color=colors, edgecolor="black",
                   linewidth=0.6, height=0.65, zorder=2)
    ax.set_yticks(y)
    ax.set_yticklabels(labels, fontsize=10)
    ax.invert_yaxis()
    if xlim is not None:
        ax.set_xlim(*xlim)
    xl = ax.get_xlim()
    span = xl[1] - xl[0]
    pad = span * 0.014
    if vline is not None:
        ax.axvline(vline, color="black", ls="--", lw=1.2, alpha=0.7, zorder=1)
        if vline_text is not None:
            ax.text(vline + pad, len(values) - 0.55, vline_text, fontsize=8,
                    color="black", ha="left", va="top")
    for i, (v, b) in enumerate(zip(values, bars)):
        if v is None:
            ax.text(xl[0] + pad, i, na_text, va="center", ha="left",
                    fontsize=8.5, color="#666666", style="italic",
                    clip_on=True)
        else:
            x = b.get_width()
            if x >= 0:
                ax.text(x + pad, i, value_fmt(v), va="center", ha="left",
                        fontsize=9)
            else:
                ax.text(x - pad, i, value_fmt(v), va="center", ha="right",
                        fontsize=9)
    ax.set_xlabel(xlabel, fontsize=9)
    ax.tick_params(axis="x", labelsize=8.5)
    ax.grid(axis="x", alpha=0.25, linestyle=":", zorder=0)
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)


def add_subtitle(ax, title, subtitle):
    ax.set_title(title, fontsize=10.5, fontweight="bold",
                 loc="left", pad=22)
    ax.text(0, 1.02, subtitle, fontsize=8.5, color="#555555",
            transform=ax.transAxes, va="bottom")


def build():
    p1 = panel1_override_to_clean()
    p2 = panel2_spearman()
    p3 = panel3_auc()
    p4 = panel4_above_threshold()
    p5 = panel5_retention()
    p6 = panel6_q4_v4()

    aois = AOI_ORDER
    labels = [AOI_LABEL[a] for a in aois]
    cols = [COLOR[a] for a in aois]

    fig, axes = plt.subplots(2, 3, figsize=(10.0, 6.25),
                             gridspec_kw={"hspace": 0.85, "wspace": 0.55})

    handles = [
        plt.Rectangle((0, 0), 1, 1, color=COLOR["qiddiya_core"],
                      ec="black", lw=0.6, label="Qiddiya"),
        plt.Rectangle((0, 0), 1, 1, color=COLOR["king_salman_park"],
                      ec="black", lw=0.6, label="KSP"),
        plt.Rectangle((0, 0), 1, 1, color=COLOR["diriyah_gate"],
                      ec="black", lw=0.6, label="Diriyah"),
    ]
    fig.legend(handles=handles, loc="upper center", ncol=3,
               frameon=False, fontsize=10, bbox_to_anchor=(0.5, 0.96))
    fig.suptitle(
        "Qiddiya construction-substrate convergence — six independent lines of evidence",
        fontsize=12, fontweight="bold", y=0.995,
    )

    # P1
    ax = axes[0, 0]
    vals = [p1[a][0] for a in aois]
    vmax = max(vals)
    hbar(ax, vals, labels, cols,
         value_fmt=lambda v: f"{v:.1f}%",
         xlabel="% AI labels overridden -> clean",
         xlim=(0, max(vmax * 1.45, 1.0)))
    add_subtitle(ax, "SQ1D blind relabel",
                 "% AI pre-labels overridden to 'clean'")

    # P2
    ax = axes[0, 1]
    vals = [p2[a][0] for a in aois]
    hbar(ax, vals, labels, cols,
         value_fmt=lambda v: f"{v:.3f}",
         xlabel="Spearman rho (primary vs alt DBB)",
         xlim=(0.85, 1.005),
         na_text="N/A (alt set excludes Diriyah)")
    add_subtitle(ax, "SQ1D Part B sensitivity",
                 "Spearman rho across reference change")

    # P3
    ax = axes[0, 2]
    p3_labels = ["With Qiddiya\n(V2)", "Without Qiddiya\n(V4)"]
    p3_vals = [p3["with_qiddiya"], p3["without_qiddiya"]]
    p3_cols = [COLOR["qiddiya_core"], COLOR["king_salman_park"]]
    hbar(ax, p3_vals, p3_labels, p3_cols,
         value_fmt=lambda v: f"{v:.3f}",
         xlabel="AUC",
         xlim=(0.5, 0.95))
    add_subtitle(ax, "SQ1B threshold-fit AUC",
                 "Pool with vs without Qiddiya")

    # P4
    ax = axes[1, 0]
    vals = [p4[a][0] for a in aois]
    vmin = min(vals)
    vmax = max(vals)
    span = vmax - vmin
    hbar(ax, vals, labels, cols,
         value_fmt=lambda v: f"{v:+.3f}",
         xlabel="median DBB - 0.034",
         xlim=(vmin - 0.30 * span, vmax + 0.22 * span),
         vline=0.0)
    add_subtitle(ax, "SQ2 operational DBB",
                 "Median DBB above V4 threshold (+0.034)")

    # P5
    ax = axes[1, 1]
    vals = [p5[a] for a in aois]
    hbar(ax, vals, labels, cols,
         value_fmt=lambda v: f"{v:.1f}%",
         xlabel="paired retention %",
         xlim=(0, 100),
         vline=HALT_PCT, vline_text="30% halt")
    add_subtitle(ax, "SQ3 paired retention",
                 "% V4-flagged scenes paired (+/-60d)")

    # P6
    ax = axes[1, 2]
    vals = [p6[a][0] for a in aois]
    hbar(ax, vals, labels, cols,
         value_fmt=lambda v: f"{v:.1f}%",
         xlabel="% Q4 scenes that fired V4",
         xlim=(0, 100))
    add_subtitle(ax, "SQ5 Q4 cap V4 contingency",
                 "% of highest-UVAI-quartile that fired V4")

    fig.subplots_adjust(left=0.07, right=0.98, top=0.86, bottom=0.09,
                        hspace=0.85, wspace=0.55)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(OUT, dpi=300)
    print(f"saved: {OUT}")

    print("\n=== panel summary ===")
    for a in aois:
        v, k, n, src = p1[a]
        print(f"  P1 {AOI_LABEL[a]:<8} {v:5.1f}%  ({k}/{n}, {src})")
    for a in aois:
        rho, n = p2[a]
        s = f"{rho:.3f}" if rho is not None else "N/A"
        print(f"  P2 {AOI_LABEL[a]:<8} rho={s:>6}  (n={n})")
    print(f"  P3 with Qiddiya (V2)    AUC={p3['with_qiddiya']:.4f}")
    print(f"  P3 without Qiddiya (V4) AUC={p3['without_qiddiya']:.4f}")
    for a in aois:
        d, m, n = p4[a]
        print(f"  P4 {AOI_LABEL[a]:<8} median DBB - 0.034 = {d:+.4f}  "
              f"(median {m:+.4f}, n={n})")
    for a in aois:
        print(f"  P5 {AOI_LABEL[a]:<8} retention = {p5[a]:.2f}%")
    for a in aois:
        v, k, n = p6[a]
        print(f"  P6 {AOI_LABEL[a]:<8} Q4 cap V4 = {v:.1f}%  ({k}/{n})")


if __name__ == "__main__":
    build()

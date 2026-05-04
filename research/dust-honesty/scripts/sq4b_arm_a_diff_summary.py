"""
SQ4B Arm A — pair difference-of-differences + two-by-two summary + figures.

Inputs:
  research/dust-honesty/data/ndvi_bias/paired_sen2cor_sq3.csv       (38 SQ3 pairs)
  research/dust-honesty/data/cross_correction/ndvi_hls_s30_b8_sq4b.csv    (65 (aoi, date) NDVI)
  research/dust-honesty/data/cross_correction/diff_of_diffs_lasrc_sq4.csv   (SQ4 B8A pair results)
  research/dust-honesty/data/cross_correction/signal_class_sq4.csv    (SQ4 B8A AOI summary)

Outputs:
  research/dust-honesty/data/cross_correction/arm_a_b8_sensitivity_sq4b.csv   (per kept pair)
  research/dust-honesty/data/cross_correction/arm_a_signal_class_sq4b.csv     (per AOI)
  research/dust-honesty/data/cross_correction/two_by_two_summary_sq4b.csv     (per AOI x cell)
  research/dust-honesty/data/cross_correction/summary_stats_sq4b.md           (1-page table)

Figures (research/dust-honesty/figures/cross_correction/):
  arm_a_forest_sq4b.png            — per-AOI mean ± 95% CI on arm_a_diff
  two_by_two_forest_sq4b.png       — per-AOI: Sen2Cor B8 (SQ3 mean Δ),
                                     LaSRC B8 (this run mean Δ),
                                     LaSRC B8A (SQ4 mean Δ)  with 95% CIs
  b8_vs_b8a_scatter_sq4b.png       — per-AOI scatter of B8 NDVI (x) vs
                                     B8A NDVI (y), 1:1 line

Math:
  delta_b8_s30 = b8_s30_ndvi(fired) - b8_s30_ndvi(neighbor)
  delta_sen2cor = sq3 delta_ndvi (alias from SQ3)
  arm_a_diff = delta_b8_s30 - delta_sen2cor

Bootstrap: 1000 resamples on pairs (seed 42), per AOI.
Signal classification:
  CI excludes zero          -> 'nir_band_sensitive'
  CI includes zero, hw<0.01 -> 'tight_null'
  else                      -> 'wide_inconclusive'

Note: this script is read-only on SQ4 outputs (diff_of_diffs_lasrc_sq4.csv,
signal_class_sq4.csv, ndvi_hls_s30_b8a_sq4.csv) and SQ3 outputs (paired_sen2cor_sq3.csv,
pairing_audit_sq3.csv). It writes only sq4b_* artifacts.
"""
from __future__ import annotations

import csv
import math
from collections import defaultdict
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[3]
DATA = ROOT / "research/dust-honesty/data"
FIG = ROOT / "research/dust-honesty/figures/cross_correction"
FIG.mkdir(parents=True, exist_ok=True)

PAIRS_CSV = DATA / "ndvi_bias" / "paired_sen2cor_sq3.csv"
B8_CSV = DATA / "cross_correction" / "ndvi_hls_s30_b8_sq4b.csv"
SQ4_DIFF_CSV = DATA / "cross_correction" / "diff_of_diffs_lasrc_sq4.csv"     # SQ4 B8A per-pair
SQ4_CLASS_CSV = DATA / "cross_correction" / "signal_class_sq4.csv"           # SQ4 B8A AOI summary
SQ4_NDVI_CSV = DATA / "cross_correction" / "ndvi_hls_s30_b8a_sq4.csv"        # SQ4 B8A per (aoi, date)
SQ3_AUDIT_CSV = DATA / "ndvi_bias" / "pairing_audit_sq3.csv"                 # SQ3 Sen2Cor B8 AOI summary

OUT_PAIRS = DATA / "cross_correction" / "arm_a_b8_sensitivity_sq4b.csv"
OUT_CLASS = DATA / "cross_correction" / "arm_a_signal_class_sq4b.csv"
OUT_2X2 = DATA / "cross_correction" / "two_by_two_summary_sq4b.csv"
OUT_MD = DATA / "cross_correction" / "summary_stats_sq4b.md"

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
N_BOOT = 1000
BOOT_SEED = 42
TIGHT_NULL_HW = 0.01


# ---------- I/O ----------

def load_b8_lookup():
    out = {}
    with open(B8_CSV) as f:
        for r in csv.DictReader(f):
            v = r["b8_s30_ndvi"]
            out[(r["aoi"], r["date"])] = (
                float(v) if v != "" else None,
                r["qa_flag"], int(r["n_valid_pixels"])
            )
    return out


def load_b8a_lookup():
    out = {}
    with open(SQ4_NDVI_CSV) as f:
        for r in csv.DictReader(f):
            v = r["hls_ndvi"]
            out[(r["aoi"], r["date"])] = (
                float(v) if v != "" else None
            )
    return out


def load_sq3_pairs():
    with open(PAIRS_CSV) as f:
        for r in csv.DictReader(f):
            yield {
                "aoi": r["aoi"],
                "fired_date": r["fired_date"],
                "neighbor_date": r["neighbor_date"],
                "fired_sen2cor": float(r["fired_ndvi"]),
                "neighbor_sen2cor": float(r["neighbor_ndvi"]),
                "delta_sen2cor": float(r["delta_ndvi"]),
                "dt_days": int(r["dt_days"]),
            }


def load_sq3_audit():
    """Per-AOI Sen2Cor B8 summary (mean Δ, CI, halfwidth, n_paired)."""
    out = {}
    with open(SQ3_AUDIT_CSV) as f:
        for r in csv.DictReader(f):
            out[r["aoi"]] = {
                "mean": float(r["mean_delta"]) if r["mean_delta"] != "" else float("nan"),
                "ci_lo": float(r["ci_lo_95"]) if r["ci_lo_95"] != "" else float("nan"),
                "ci_hi": float(r["ci_hi_95"]) if r["ci_hi_95"] != "" else float("nan"),
                "hw": float(r["ci_halfwidth"]) if r["ci_halfwidth"] != "" else float("nan"),
                "n_paired": int(r["n_paired"]),
            }
    return out


def load_sq4_class():
    """Per-AOI LaSRC B8A summary (mean Δ HLS, CI, halfwidth) — wait, sq4_signal_class
    holds DIFF-OF-DIFFS not raw delta_hls. We need raw delta_hls per AOI for
    the two-by-two table. Compute from diff_of_diffs_lasrc_sq4.csv directly."""
    raise NotImplementedError("use compute_sq4_b8a_summary instead")


def compute_sq4_b8a_summary():
    """Per-AOI mean Δ NDVI under HLS LaSRC B8A (SQ4), bootstrapped from
    diff_of_diffs_lasrc_sq4.csv columns delta_hls."""
    per_aoi = defaultdict(list)
    with open(SQ4_DIFF_CSV) as f:
        for r in csv.DictReader(f):
            per_aoi[r["aoi"]].append(float(r["delta_hls"]))
    out = {}
    for aoi, deltas in per_aoi.items():
        m, lo, hi = bootstrap_ci(deltas)
        hw = (hi - lo) / 2.0 if not math.isnan(lo) else float("nan")
        out[aoi] = {"mean": m, "ci_lo": lo, "ci_hi": hi, "hw": hw,
                    "n": len(deltas)}
    return out


def bootstrap_ci(deltas, n_boot=N_BOOT, seed=BOOT_SEED):
    deltas = np.asarray(deltas, dtype=float)
    n = len(deltas)
    if n == 0:
        return float("nan"), float("nan"), float("nan")
    mean = float(deltas.mean())
    rng = np.random.default_rng(seed)
    boot_means = np.empty(n_boot)
    for i in range(n_boot):
        sample = rng.choice(deltas, size=n, replace=True)
        boot_means[i] = sample.mean()
    return mean, float(np.percentile(boot_means, 2.5)), \
           float(np.percentile(boot_means, 97.5))


def signal_class_of(mean, ci_lo, ci_hi):
    if math.isnan(mean) or math.isnan(ci_lo) or math.isnan(ci_hi):
        return "wide_inconclusive"
    hw = (ci_hi - ci_lo) / 2.0
    excludes_zero = (ci_lo > 0) or (ci_hi < 0)
    if excludes_zero:
        return "nir_band_sensitive"
    if hw < TIGHT_NULL_HW:
        return "tight_null"
    return "wide_inconclusive"


# ---------- main computations ----------

def build_arm_a_pairs():
    """Build per-pair Arm A rows. Returns (kept_pairs, drop_log)."""
    b8 = load_b8_lookup()
    kept = []
    drops = []
    for p in load_sq3_pairs():
        aoi = p["aoi"]
        f_key = (aoi, p["fired_date"])
        n_key = (aoi, p["neighbor_date"])
        if f_key not in b8 or n_key not in b8:
            drops.append((aoi, p["fired_date"], p["neighbor_date"], "missing_in_lookup"))
            continue
        f_ndvi, f_qa, _ = b8[f_key]
        n_ndvi, n_qa, _ = b8[n_key]
        if f_ndvi is None or n_ndvi is None:
            why = []
            if f_ndvi is None:
                why.append(f"fired_nan({f_qa})")
            if n_ndvi is None:
                why.append(f"neighbor_nan({n_qa})")
            drops.append((aoi, p["fired_date"], p["neighbor_date"], ";".join(why)))
            continue
        delta_b8 = f_ndvi - n_ndvi
        arm_a_diff = delta_b8 - p["delta_sen2cor"]
        kept.append({
            **p,
            "fired_b8": f_ndvi,
            "neighbor_b8": n_ndvi,
            "delta_b8_s30": delta_b8,
            "arm_a_diff": arm_a_diff,
            "fired_qa": f_qa,
            "neighbor_qa": n_qa,
        })
    return kept, drops


def write_pair_rows(kept):
    fields = ["aoi", "fired_date", "neighbor_date", "dt_days",
              "fired_sen2cor", "neighbor_sen2cor", "delta_sen2cor",
              "fired_b8", "neighbor_b8", "delta_b8_s30",
              "arm_a_diff", "fired_qa", "neighbor_qa"]
    with open(OUT_PAIRS, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for p in kept:
            w.writerow({
                "aoi": p["aoi"],
                "fired_date": p["fired_date"],
                "neighbor_date": p["neighbor_date"],
                "dt_days": p["dt_days"],
                "fired_sen2cor": f"{p['fired_sen2cor']:.6f}",
                "neighbor_sen2cor": f"{p['neighbor_sen2cor']:.6f}",
                "delta_sen2cor": f"{p['delta_sen2cor']:.6f}",
                "fired_b8": f"{p['fired_b8']:.6f}",
                "neighbor_b8": f"{p['neighbor_b8']:.6f}",
                "delta_b8_s30": f"{p['delta_b8_s30']:.6f}",
                "arm_a_diff": f"{p['arm_a_diff']:.6f}",
                "fired_qa": p["fired_qa"],
                "neighbor_qa": p["neighbor_qa"],
            })


def per_aoi_arm_a(kept_pairs):
    n_seen = defaultdict(int)
    for p in load_sq3_pairs():
        n_seen[p["aoi"]] += 1
    summary = []
    for aoi in AOIS:
        sub = [p for p in kept_pairs if p["aoi"] == aoi]
        diffs = [p["arm_a_diff"] for p in sub]
        m, lo, hi = bootstrap_ci(diffs)
        hw = (hi - lo) / 2.0 if not math.isnan(lo) else float("nan")
        sig = signal_class_of(m, lo, hi)
        summary.append({
            "aoi": aoi, "n_sq3_pairs": n_seen[aoi],
            "n_pairs_with_b8": len(sub),
            "mean_diff": m, "ci_lo_95": lo, "ci_hi_95": hi,
            "ci_halfwidth": hw, "signal_class": sig,
        })
    return summary


def write_class_csv(arm_a):
    fields = ["aoi", "n_sq3_pairs", "n_pairs_with_b8",
              "mean_diff", "ci_lo_95", "ci_hi_95", "ci_halfwidth",
              "signal_class"]
    with open(OUT_CLASS, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for a in arm_a:
            row = {"aoi": a["aoi"], "n_sq3_pairs": a["n_sq3_pairs"],
                   "n_pairs_with_b8": a["n_pairs_with_b8"],
                   "signal_class": a["signal_class"]}
            for k in ("mean_diff", "ci_lo_95", "ci_hi_95", "ci_halfwidth"):
                v = a[k]
                row[k] = "" if (v is None or
                                (isinstance(v, float) and math.isnan(v))) \
                    else f"{v:+.6f}"
            w.writerow(row)


def build_two_by_two(arm_a_kept):
    """Build per-AOI per-cell summary.
    Cells:
      - Sen2Cor B8 (from SQ3 audit): raw mean Δ NDVI, halfwidth, n_paired.
      - LaSRC B8 (this run): raw mean Δ NDVI from delta_b8_s30 column.
      - LaSRC B8A (from SQ4): raw mean Δ NDVI from sq4_diff_of_diffs delta_hls.
      - Sen2Cor B8A: not in scope; placeholder cell.
    """
    sq3 = load_sq3_audit()
    sq4_b8a = compute_sq4_b8a_summary()
    rows = []
    for aoi in AOIS:
        # LaSRC B8 raw delta from kept pairs
        lasrc_b8_deltas = [p["delta_b8_s30"]
                           for p in arm_a_kept if p["aoi"] == aoi]
        m, lo, hi = bootstrap_ci(lasrc_b8_deltas)
        hw = (hi - lo) / 2.0 if not math.isnan(lo) else float("nan")
        # Append cells
        rows.append({"aoi": aoi, "chain": "Sen2Cor",
                     "nir": "B8 (broad ~833nm)",
                     "n": sq3[aoi]["n_paired"],
                     "mean_delta": sq3[aoi]["mean"],
                     "ci_halfwidth": sq3[aoi]["hw"],
                     "in_scope": "yes (from SQ3)"})
        rows.append({"aoi": aoi, "chain": "Sen2Cor",
                     "nir": "B8A (narrow ~865nm)",
                     "n": "", "mean_delta": float("nan"),
                     "ci_halfwidth": float("nan"),
                     "in_scope": "no (S2 L2A delivers B8 as primary "
                                 "NIR; B8A is supplementary, not "
                                 "exercised in SQ3)"})
        rows.append({"aoi": aoi, "chain": "LaSRC (HLS S30)",
                     "nir": "B8 (broad ~833nm)",
                     "n": len(lasrc_b8_deltas),
                     "mean_delta": m,
                     "ci_halfwidth": hw,
                     "in_scope": "yes (this run, SQ4B Arm A)"})
        rows.append({"aoi": aoi, "chain": "LaSRC (HLS S30)",
                     "nir": "B8A (narrow ~865nm)",
                     "n": sq4_b8a[aoi]["n"],
                     "mean_delta": sq4_b8a[aoi]["mean"],
                     "ci_halfwidth": sq4_b8a[aoi]["hw"],
                     "in_scope": "yes (from SQ4)"})
    return rows


def write_two_by_two(rows):
    fields = ["aoi", "chain", "nir", "n", "mean_delta", "ci_halfwidth",
              "in_scope"]
    with open(OUT_2X2, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in rows:
            w.writerow({
                "aoi": r["aoi"], "chain": r["chain"], "nir": r["nir"],
                "n": r["n"],
                "mean_delta": ("" if math.isnan(r["mean_delta"])
                               else f"{r['mean_delta']:+.6f}"),
                "ci_halfwidth": ("" if math.isnan(r["ci_halfwidth"])
                                 else f"{r['ci_halfwidth']:.6f}"),
                "in_scope": r["in_scope"],
            })


# ---------- figures ----------

def fig_arm_a_forest(arm_a):
    fig, ax = plt.subplots(figsize=(8, 4))
    ys = list(range(len(arm_a)))
    for y, r in zip(ys, arm_a):
        c = AOI_COLORS[r["aoi"]]
        ax.errorbar(
            r["mean_diff"], y,
            xerr=[[r["mean_diff"] - r["ci_lo_95"]],
                  [r["ci_hi_95"] - r["mean_diff"]]],
            fmt="o", color=c, ecolor=c, elinewidth=2, capsize=6,
            markersize=10,
        )
        ax.text(r["mean_diff"], y + 0.18,
                f"n={r['n_pairs_with_b8']}/{r['n_sq3_pairs']}  "
                f"{r['signal_class']}",
                ha="center", va="bottom", fontsize=9, color=c)
    ax.axvline(0, color="gray", lw=0.8, ls="--")
    ax.set_yticks(ys)
    ax.set_yticklabels([AOI_LABELS[r["aoi"]] for r in arm_a])
    ax.set_xlabel("arm_a_diff  =  Δ NDVI (LaSRC B8 broad) − Δ NDVI (Sen2Cor B8)")
    ax.set_title("SQ4B Arm A — B8 broad-NIR sensitivity on HLS S30\n"
                 "(per-AOI mean ± bootstrap 95% CI; pairs from SQ3)")
    ax.set_xlim(-0.025, 0.025)
    ax.invert_yaxis()
    ax.grid(axis="x", alpha=0.3)
    fig.tight_layout()
    out = FIG / "arm_a_forest_sq4b.png"
    fig.savefig(out, dpi=150)
    plt.close(fig)
    print(f"  Wrote {out}")


def fig_two_by_two_forest(two_by_two):
    """For each AOI, plot mean Δ NDVI for the three filled cells side by side."""
    cells = [
        ("Sen2Cor B8\n(SQ3)", "Sen2Cor", "B8 (broad ~833nm)", "#5c6b73"),
        ("LaSRC B8\n(SQ4B)", "LaSRC (HLS S30)", "B8 (broad ~833nm)", "#9c6644"),
        ("LaSRC B8A\n(SQ4)", "LaSRC (HLS S30)", "B8A (narrow ~865nm)", "#264653"),
    ]
    cell_lookup = {(r["aoi"], r["chain"], r["nir"]): r for r in two_by_two}
    fig, axes = plt.subplots(1, 3, figsize=(13, 4.5), sharey=False)
    for ax, aoi in zip(axes, AOIS):
        xs = []
        means = []
        hws = []
        colors = []
        labels = []
        for label, chain, nir, color in cells:
            r = cell_lookup.get((aoi, chain, nir))
            if r is None or math.isnan(r["mean_delta"]):
                continue
            xs.append(len(xs))
            means.append(r["mean_delta"])
            hws.append(r["ci_halfwidth"])
            colors.append(color)
            labels.append(label)
        for x, m, hw, c in zip(xs, means, hws, colors):
            ax.errorbar(x, m, yerr=hw, fmt="o", color=c, ecolor=c,
                        elinewidth=2, capsize=6, markersize=10)
            ax.text(x, m + hw + 0.002, f"{m:+.4f}\n±{hw:.4f}",
                    ha="center", va="bottom", fontsize=8, color=c)
        ax.axhline(0, color="gray", lw=0.8, ls="--")
        ax.set_xticks(xs)
        ax.set_xticklabels(labels, fontsize=9)
        ax.set_title(AOI_LABELS[aoi])
        ax.set_ylim(-0.06, 0.06)
        ax.grid(axis="y", alpha=0.3)
    axes[0].set_ylabel("mean Δ NDVI (paired V4-fired vs unflagged)")
    fig.suptitle("SQ4B — two-by-two: correction chain × NIR band\n"
                 "(per-AOI mean Δ NDVI ± bootstrap CI halfwidth)")
    fig.tight_layout()
    out = FIG / "two_by_two_forest_sq4b.png"
    fig.savefig(out, dpi=150)
    plt.close(fig)
    print(f"  Wrote {out}")


def fig_b8_vs_b8a_scatter():
    """Per-AOI scatter of B8 (this run) vs B8A (SQ4) NDVI on shared dates."""
    b8 = load_b8_lookup()
    b8a = load_b8a_lookup()
    fig, axes = plt.subplots(1, 3, figsize=(13, 4.5))
    for ax, aoi in zip(axes, AOIS):
        xs = []
        ys = []
        for k, (v_b8, _, _) in b8.items():
            if k[0] != aoi or v_b8 is None:
                continue
            v_b8a = b8a.get(k)
            if v_b8a is None:
                continue
            xs.append(v_b8)
            ys.append(v_b8a)
        c = AOI_COLORS[aoi]
        ax.scatter(xs, ys, color=c, s=50, alpha=0.85,
                   edgecolor="white", linewidth=1.2)
        if xs and ys:
            lo = min(min(xs), min(ys)) - 0.01
            hi = max(max(xs), max(ys)) + 0.01
        else:
            lo, hi = 0, 0.2
        ax.plot([lo, hi], [lo, hi], color="gray", ls="--", lw=1, label="1:1")
        ax.set_xlim(lo, hi)
        ax.set_ylim(lo, hi)
        ax.set_xlabel("S30 B8 (broad ~833nm) NDVI")
        ax.set_ylabel("S30 B8A (narrow ~865nm) NDVI")
        ax.set_title(f"{AOI_LABELS[aoi]}  (n={len(xs)})")
        ax.legend(loc="upper left", fontsize=9)
        ax.grid(alpha=0.3)
    fig.suptitle("SQ4B — broad vs narrow NIR on HLS S30 (per-scene NDVI)")
    fig.tight_layout()
    out = FIG / "b8_vs_b8a_scatter_sq4b.png"
    fig.savefig(out, dpi=150)
    plt.close(fig)
    print(f"  Wrote {out}")


# ---------- markdown summary ----------

def write_md(arm_a, two_by_two, n_kept, n_dropped):
    sq3 = load_sq3_audit()
    sq4_b8a = compute_sq4_b8a_summary()

    lines = [
        "# SQ4B Arm A — B8 broad-NIR sensitivity on HLS S30",
        "",
        "Pairs from SQ3 (n=38). Arm A reruns SQ4's compute pipeline on",
        "HLS S30 v2.0 with broad NIR (B8 ~833nm) instead of narrow NIR",
        "(B8A ~865nm) used in SQ4. Same correction chain (LaSRC), same",
        "AOI mean / native 30m / single-image single-reducer / mosaic()",
        "across MGRS tiles. Fmask bits 1–4 masked. Bootstrap 1000 on",
        "pairs (seed 42).",
        "",
        f"Pair retention: {n_kept}/{n_kept + n_dropped} = "
        f"{100*n_kept/(n_kept+n_dropped):.1f}% "
        f"({n_dropped} dropped, parity with SQ4 single-loss).",
        "",
        "## §3 Arm A per-AOI signal classification",
        "",
        "| AOI | n_kept / n_sq3 | mean diff | 95% CI | halfwidth | signal_class |",
        "|---|---:|---:|---|---:|---|",
    ]
    for r in arm_a:
        ci = f"[{r['ci_lo_95']:+.4f}, {r['ci_hi_95']:+.4f}]"
        lines.append(
            f"| {AOI_LABELS[r['aoi']]} | "
            f"{r['n_pairs_with_b8']}/{r['n_sq3_pairs']} | "
            f"{r['mean_diff']:+.4f} | {ci} | "
            f"{r['ci_halfwidth']:.4f} | `{r['signal_class']}` |"
        )
    lines.append("")
    lines.append("## §3.1 Two-by-two summary (correction chain × NIR band)")
    lines.append("")
    lines.append("Cells: raw mean Δ NDVI per pair (paired V4-fired minus")
    lines.append("unflagged neighbor), bootstrap halfwidth on the same")
    lines.append("pair set used for that cell.")
    lines.append("")
    lines.append("| AOI | chain | NIR | n | mean Δ NDVI | halfwidth | scope |")
    lines.append("|---|---|---|---:|---:|---:|---|")
    for r in two_by_two:
        if math.isnan(r["mean_delta"]):
            mean_s = "—"; hw_s = "—"
        else:
            mean_s = f"{r['mean_delta']:+.4f}"
            hw_s = f"{r['ci_halfwidth']:.4f}"
        n_s = "—" if r["n"] == "" else str(r["n"])
        lines.append(
            f"| {AOI_LABELS[r['aoi']]} | {r['chain']} | {r['nir']} | "
            f"{n_s} | {mean_s} | {hw_s} | {r['in_scope']} |"
        )
    OUT_MD.write_text("\n".join(lines) + "\n")
    print(f"  Wrote {OUT_MD}")


# ---------- main ----------

def main():
    print("SQ4B Arm A — pair diff + summary")
    print()

    kept, drops = build_arm_a_pairs()
    print(f"Pairs kept: {len(kept)}; dropped: {len(drops)}")
    for aoi, fd, nd, why in drops:
        print(f"  DROP {aoi} fired={fd} neighbor={nd} why={why}")
    print()
    write_pair_rows(kept)
    print(f"Wrote {OUT_PAIRS} ({len(kept)} rows)")

    arm_a = per_aoi_arm_a(kept)
    write_class_csv(arm_a)
    print(f"Wrote {OUT_CLASS} ({len(arm_a)} rows)")

    two_by_two = build_two_by_two(kept)
    write_two_by_two(two_by_two)
    print(f"Wrote {OUT_2X2} ({len(two_by_two)} rows)")
    print()

    print("Per-AOI Arm A summary (arm_a_diff = LaSRC B8 Δ − Sen2Cor B8 Δ):")
    print(f"{'aoi':<22s} {'pairs':>10s} {'mean':>10s} "
          f"{'ci_lo':>10s} {'ci_hi':>10s} {'hw':>8s} {'class':<22s}")
    for a in arm_a:
        pairs_str = f"{a['n_pairs_with_b8']}/{a['n_sq3_pairs']}"
        if math.isnan(a["mean_diff"]):
            print(f"{a['aoi']:<22s} {pairs_str:>10s} (insufficient)")
            continue
        print(f"{a['aoi']:<22s} {pairs_str:>10s} "
              f"{a['mean_diff']:>+10.4f} "
              f"{a['ci_lo_95']:>+10.4f} {a['ci_hi_95']:>+10.4f} "
              f"{a['ci_halfwidth']:>8.4f} {a['signal_class']:<22s}")
    print()

    print("Figures:")
    fig_arm_a_forest(arm_a)
    fig_two_by_two_forest(two_by_two)
    fig_b8_vs_b8a_scatter()
    print()

    print("Summary table:")
    write_md(arm_a, two_by_two, len(kept), len(drops))


if __name__ == "__main__":
    main()

"""
SQ1B re-re-run on combined 73-scene calibration set (SQ1D + SQ1C primary refs).

Same 4 binary task variants and stop rule as sq1b_rerun.py, but the
input is sq1bc_combined_calibration.csv. No alt-ref sensitivity check
in v2 (the alternate-ref CSV from Part B' covers only the 24 SQ1D KSP+
Qiddiya scenes; the 43-scene SQ1C set has no parallel alt-ref pull yet —
queued as deferred work).

Stop rule reused verbatim from sq1b_rerun.py (commit 3d3b511 lineage):
ship a threshold IFF bootstrap 95% CI half-width < 0.020 AND AUC > 0.75.

Outputs:
  data/sq1b_rerun_v2_threshold_results.csv
  data/sq1b_rerun_v2_threshold_spec.md
  data/sq1b_rerun_v2_roc_curves.png
  data/sq1b_rerun_v2_bootstrap_thresholds.png
"""
from __future__ import annotations

import csv
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
DATA = ROOT / "research/dust-honesty/data"

# Reuse helpers from sq1b_rerun.py — identical statistics, identical
# variant_filter, identical stop rule.
sys.path.insert(0, str(ROOT / "research/dust-honesty/scripts"))
from sq1b_rerun import (  # noqa: E402
    CI_HALFWIDTH_TARGET, AUC_TARGET, N_BOOT, SEED, N_SWEEP,
    variant_filter, sweep_thresholds, roc, trapz_auc,
    youden_threshold, bootstrap_thresholds,
)

INPUT_CSV = DATA / "sq1bc_combined_calibration.csv"
OUT_RESULTS_CSV = DATA / "sq1b_rerun_v2_threshold_results.csv"
OUT_ROC_PNG = DATA / "sq1b_rerun_v2_roc_curves.png"
OUT_BOOT_PNG = DATA / "sq1b_rerun_v2_bootstrap_thresholds.png"
OUT_SPEC_MD = DATA / "sq1b_rerun_v2_threshold_spec.md"


def load_combined():
    df = pd.read_csv(INPUT_CSV)
    df = df.rename(columns={"dbb_faithful": "dbb"})
    return df


def run_variant(name, df_full, source_tag="combined_73"):
    sub, y = variant_filter(df_full, name)
    values = sub["dbb"].to_numpy(dtype=float)
    n_pos = int((y == 1).sum())
    n_neg = int((y == 0).sum())

    if n_pos == 0 or n_neg == 0:
        return {
            "variant": name, "source": source_tag,
            "n_pos": n_pos, "n_neg": n_neg,
            "auc": float("nan"), "threshold_youden": float("nan"),
            "ci_low": float("nan"), "ci_high": float("nan"),
            "ci_halfwidth": float("nan"),
            "ci_passes": False, "auc_passes": False, "ships": False,
            "boots": np.array([]), "fpr": np.array([0, 1]), "tpr": np.array([0, 1]),
            "notes": "degenerate (one class missing)",
        }

    thresh = sweep_thresholds(values)
    fpr, tpr, _ = roc(values, y, thresh)
    auc = trapz_auc(fpr, tpr)
    t_hat = youden_threshold(values, y, thresh)
    boots, skipped = bootstrap_thresholds(values, y, thresh)

    if len(boots) > 0:
        ci_lo, ci_hi = np.percentile(boots, [2.5, 97.5])
        ci_hw = (ci_hi - ci_lo) / 2.0
    else:
        ci_lo = ci_hi = ci_hw = float("nan")

    ci_passes = bool(ci_hw < CI_HALFWIDTH_TARGET) if not np.isnan(ci_hw) else False
    auc_passes = bool(auc > AUC_TARGET) if not np.isnan(auc) else False
    ships = ci_passes and auc_passes
    note_bits = []
    if n_pos < 5:
        note_bits.append(f"n_pos={n_pos}<5_unstable_bootstrap")
    if skipped > 0:
        note_bits.append(f"degenerate_boot_iters={skipped}")

    return {
        "variant": name, "source": source_tag,
        "n_pos": n_pos, "n_neg": n_neg,
        "auc": auc, "threshold_youden": t_hat,
        "ci_low": float(ci_lo), "ci_high": float(ci_hi),
        "ci_halfwidth": float(ci_hw),
        "ci_passes": ci_passes, "auc_passes": auc_passes, "ships": ships,
        "boots": boots, "fpr": fpr, "tpr": tpr,
        "notes": ";".join(note_bits) if note_bits else "",
    }


def plot_roc_grid(results, out_path):
    fig, axes = plt.subplots(2, 2, figsize=(9, 9))
    for ax, (name, r) in zip(axes.flatten(), results.items()):
        ax.plot(r["fpr"], r["tpr"], "-", lw=2, color="#b4793b")
        ax.plot([0, 1], [0, 1], "--", color="grey", alpha=0.5)
        ax.set_xlim(-0.02, 1.02); ax.set_ylim(-0.02, 1.02)
        title = (f"{name}  AUC={r['auc']:.3f}\n"
                 f"n_pos={r['n_pos']} n_neg={r['n_neg']}  "
                 f"t={r['threshold_youden']:+.4f}")
        ax.set_title(title, fontsize=10)
        ax.set_xlabel("FPR"); ax.set_ylabel("TPR")
    fig.suptitle("SQ1B re-re-run on combined 73-scene set — ROC curves", y=1.0)
    fig.tight_layout()
    fig.savefig(out_path, dpi=120, bbox_inches="tight")
    plt.close(fig)


def plot_boot_grid(results, out_path):
    fig, axes = plt.subplots(2, 2, figsize=(10, 8))
    for ax, (name, r) in zip(axes.flatten(), results.items()):
        if len(r["boots"]) == 0:
            ax.text(0.5, 0.5, f"{name}: degenerate (no boots)",
                    ha="center", va="center", transform=ax.transAxes)
            ax.set_title(name); continue
        ax.hist(r["boots"], bins=40, color="#b4793b", edgecolor="black", alpha=0.7)
        ax.axvspan(r["ci_low"], r["ci_high"], color="grey", alpha=0.25,
                   label=f"95% CI [{r['ci_low']:+.3f}, {r['ci_high']:+.3f}]")
        ax.axvline(r["threshold_youden"], color="black", lw=2,
                   label=f"point t={r['threshold_youden']:+.4f}")
        ax.set_title(f"{name}  CI half-width={r['ci_halfwidth']:.4f}  "
                     f"({'PASS' if r['ci_passes'] else 'STOP'} CI, "
                     f"{'PASS' if r['auc_passes'] else 'STOP'} AUC)",
                     fontsize=10)
        ax.set_xlabel("bootstrap Youden threshold")
        ax.legend(fontsize=8, loc="upper right")
    fig.suptitle(f"SQ1B re-re-run — bootstrap threshold distributions "
                 f"({N_BOOT} iters, seed={SEED})", y=1.0)
    fig.tight_layout()
    fig.savefig(out_path, dpi=120, bbox_inches="tight")
    plt.close(fig)


def write_results_csv(rows_for_csv, out_path):
    fields = ["variant", "source", "n_pos", "n_neg", "auc",
              "threshold_youden", "ci_low", "ci_high", "ci_halfwidth",
              "ci_passes", "auc_passes", "ships", "notes"]
    with open(out_path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in rows_for_csv:
            w.writerow({k: r.get(k) for k in fields})


def write_spec(results, out_path):
    lines = [
        "# SQ1B re-re-run — threshold spec on combined 73-scene set",
        "",
        f"**Input:** `{INPUT_CSV.name}` (30 SQ1D + 43 SQ1C, primary references).",
        f"**Stop rule:** CI half-width < {CI_HALFWIDTH_TARGET} AND AUC > {AUC_TARGET}.",
        f"**Bootstrap:** {N_BOOT} iters, seed={SEED}; ROC sweep {N_SWEEP} thresholds.",
        "",
        "**Status:** PRELIMINARY. SQ1C labels are AI-only (researcher confirmation",
        "deferred per 2026-04-30 session 3 decision); 6 SQ1C rows had partial UVAI",
        "exposure during AI pre-labeling and are flagged via",
        "`bias_exposed_during_ai_labeling=True` in the source CSVs. Do not propagate",
        "results to external communication before researcher review.",
        "",
        "## Per-variant results",
        "",
        "| variant | n_pos | n_neg | AUC | t_youden | CI [lo, hi] | CI half-width | ships |",
        "|---|---:|---:|---:|---:|---|---:|:-:|",
    ]
    for v in ("V1", "V2", "V3", "V4"):
        r = results[v]
        if np.isnan(r["auc"]):
            lines.append(f"| {v} | {r['n_pos']} | {r['n_neg']} | NaN | NaN | NaN | NaN | — |")
            continue
        lines.append(
            f"| {v} | {r['n_pos']} | {r['n_neg']} | {r['auc']:.4f} | "
            f"{r['threshold_youden']:+.4f} | "
            f"[{r['ci_low']:+.4f}, {r['ci_high']:+.4f}] | "
            f"{r['ci_halfwidth']:.4f} | "
            f"{'✓' if r['ships'] else '✗'} |"
        )
    lines += ["",
              "## Variant scopes",
              "",
              "- V1: heavy_dust vs clean, all AOIs.",
              "- V2: any-non-clean vs clean, all AOIs (HEADLINE).",
              "- V3: KSP-only any-non-clean vs clean.",
              "- V4: KSP + Diriyah any-non-clean vs clean (Qiddiya excluded).",
              ""]
    out_path.write_text("\n".join(lines))


def main():
    print(f"Stop rule: CI half-width < {CI_HALFWIDTH_TARGET}  AND  AUC > {AUC_TARGET}")
    print(f"Bootstrap: {N_BOOT} iters, seed={SEED}")
    print(f"ROC sweep: {N_SWEEP} thresholds\n")

    df = load_combined()
    print(f"Loaded {INPUT_CSV.name}: {len(df)} rows. Label dist: "
          f"{df['final_label'].value_counts().to_dict()}\n")
    print(f"Source split: {df['source'].value_counts().to_dict()}")
    print(f"bias_exposed=True: {(df['bias_exposed_during_ai_labeling']==True).sum() + (df['bias_exposed_during_ai_labeling']=='True').sum()}\n")

    variants = ["V1", "V2", "V3", "V4"]
    results = {v: run_variant(v, df) for v in variants}

    # Print
    print(f"{'variant':<8s} {'n_pos':>6s} {'n_neg':>6s} {'AUC':>7s} "
          f"{'t_youden':>10s} {'CI_hw':>8s}  ships")
    for v in variants:
        r = results[v]
        if np.isnan(r["auc"]):
            print(f"{v:<8s} {r['n_pos']:>6d} {r['n_neg']:>6d}    NaN       NaN     NaN  —")
            continue
        print(f"{v:<8s} {r['n_pos']:>6d} {r['n_neg']:>6d} "
              f"{r['auc']:>7.4f} {r['threshold_youden']:>+10.4f} "
              f"{r['ci_halfwidth']:>8.4f}  {'YES' if r['ships'] else 'no'}")
        if r["notes"]:
            print(f"  notes: {r['notes']}")

    # Headlines
    v2 = results["V2"]
    print()
    if v2["ships"]:
        print("V2 SHIPS — piece B headline result is preliminary-shippable on AI-only labels.")
    else:
        print(f"V2 does not ship: AUC={v2['auc']:.4f} (target>{AUC_TARGET}), "
              f"CI_hw={v2['ci_halfwidth']:.4f} (target<{CI_HALFWIDTH_TARGET}).")
    v3 = results["V3"]; v4 = results["V4"]
    print(f"V3 (KSP-only): CI_hw={v3['ci_halfwidth']:.4f} vs original 0.060")
    print(f"V4 (KSP+Diriyah): CI_hw={v4['ci_halfwidth']:.4f} vs original 0.046")

    # Write outputs
    write_results_csv([results[v] for v in variants], OUT_RESULTS_CSV)
    print(f"\nWrote {OUT_RESULTS_CSV}")
    plot_roc_grid(results, OUT_ROC_PNG)
    print(f"Wrote {OUT_ROC_PNG}")
    plot_boot_grid(results, OUT_BOOT_PNG)
    print(f"Wrote {OUT_BOOT_PNG}")
    write_spec(results, OUT_SPEC_MD)
    print(f"Wrote {OUT_SPEC_MD}")


if __name__ == "__main__":
    main()

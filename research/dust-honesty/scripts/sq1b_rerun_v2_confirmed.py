"""
SQ1B re-re-run on confirmed SQ1C labels (researcher-reviewed).

Same 4 binary task variants and same stop rule as sq1b_rerun_v2.py, but
SQ1C rows draw their label from `confirmed_label` instead of `final_label`.
SQ1D rows continue to use their existing labels (already researcher-confirmed
in SQ1D Pass 5).

This script is the post-confirmation entrypoint after the researcher has
walked all 43 SQ1C scenes through `sq1c_label_review.py`. Outputs go to a
parallel set of files prefixed `sq1b_rerun_v2_confirmed_*` and
`combined_calibration_confirmed.csv` so the preliminary results from
2026-04-30 session 3 stay untouched on disk for audit.

Stop rule (unchanged): CI half-width < 0.020 AND AUC > 0.75.

Usage:
    python sq1b_rerun_v2_confirmed.py
    python sq1b_rerun_v2_confirmed.py --allow-unconfirmed   # debug only

Outputs:
    data/calibration/combined_calibration_confirmed.csv
    data/threshold_fits/threshold_v4_confirmed_sq1b.csv
    data/threshold_fits/threshold_v4_confirmed_spec_sq1b.md
    data/threshold_fits/_archive/sq1b_rerun_v2_confirmed_roc_curves.png
    data/threshold_fits/_archive/sq1b_rerun_v2_confirmed_bootstrap_thresholds.png
"""
from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
DATA = ROOT / "research/dust-honesty/data"

# Reuse helpers from sq1b_rerun.py.
sys.path.insert(0, str(ROOT / "research/dust-honesty/scripts"))
from sq1b_rerun import (  # noqa: E402
    CI_HALFWIDTH_TARGET, AUC_TARGET, N_BOOT, SEED, N_SWEEP,
    variant_filter, sweep_thresholds, roc, trapz_auc,
    youden_threshold, bootstrap_thresholds,
)

SQ1D_DBB = DATA / "dbb_compute" / "dbb_calibration_sq1d.csv"
SQ1C_DBB = DATA / "dbb_compute" / "dbb_calibration_sq1c.csv"

SQ1D_LABELS = {
    "king_salman_park": (DATA / "calibration" / "relabel_ksp_sq1d.csv", "date", "final_label"),
    "qiddiya_core":     (DATA / "calibration" / "relabel_qiddiya_sq1d.csv", "date", "final_label"),
    "diriyah_gate":     (DATA / "calibration" / "manual_labels_sq1.csv", "date", "label"),
}

SQ1C_RELABEL = {
    "king_salman_park": DATA / "calibration" / "relabel_ksp_sq1c.csv",
    "qiddiya_core":     DATA / "calibration" / "relabel_qiddiya_sq1c.csv",
    "diriyah_gate":     DATA / "calibration" / "relabel_diriyah_sq1c.csv",
}

OUT_COMBINED = DATA / "calibration" / "combined_calibration_confirmed.csv"
OUT_RESULTS = DATA / "threshold_fits" / "threshold_v4_confirmed_sq1b.csv"
OUT_ROC = DATA / "threshold_fits" / "_archive" / "sq1b_rerun_v2_confirmed_roc_curves.png"
OUT_BOOT = DATA / "threshold_fits" / "_archive" / "sq1b_rerun_v2_confirmed_bootstrap_thresholds.png"
OUT_SPEC = DATA / "threshold_fits" / "threshold_v4_confirmed_spec_sq1b.md"

PRELIM_RESULTS = DATA / "threshold_fits" / "_archive" / "sq1b_rerun_v2_threshold_results.csv"

COMBINED_FIELDS = [
    "row_id", "source", "aoi", "date", "sub_aoi",
    "dbb_faithful", "n_valid_pixels", "n_total_pixels",
    "final_label",                 # the LABEL USED for this run (confirmed for SQ1C)
    "ai_prelabel",                 # the SQ1C AI pre-label (empty for SQ1D)
    "ai_confidence",
    "bias_exposed_during_ai_labeling",
    "review_protocol",             # 'standard' | 'cold' | '' for SQ1D
    "in_v3_scope", "in_v4_scope",
]


def load_sq1d_labels():
    out = {}
    for aoi, (path, date_col, label_col) in SQ1D_LABELS.items():
        for r in csv.DictReader(open(path)):
            if aoi == "diriyah_gate" and r.get("AOI") != "diriyah_gate":
                continue
            out[(aoi, r[date_col])] = r[label_col]
    return out


def load_sq1c_relabel():
    """Return {(aoi, date): row_dict}."""
    out = {}
    for aoi, path in SQ1C_RELABEL.items():
        for r in csv.DictReader(open(path)):
            out[(aoi, r["date"])] = r
    return out


def build_combined(allow_unconfirmed: bool):
    sq1d_labels = load_sq1d_labels()
    sq1c_meta = load_sq1c_relabel()

    rows = []
    n_unconfirmed = 0

    for r in csv.DictReader(open(SQ1D_DBB)):
        if not r.get("dbb_faithful"):
            continue
        aoi = r["sub_aoi"]
        date = r["date"]
        final_label = r.get("final_label") or sq1d_labels.get((aoi, date), "")
        rows.append({
            "source": "SQ1D",
            "aoi": aoi,
            "date": date,
            "sub_aoi": aoi,
            "dbb_faithful": float(r["dbb_faithful"]),
            "n_valid_pixels": int(r["n_valid_pixels"]),
            "n_total_pixels": int(r["n_total_pixels"]),
            "final_label": final_label,
            "ai_prelabel": "",
            "ai_confidence": "",
            "bias_exposed_during_ai_labeling": "False",
            "review_protocol": "",
            "in_v3_scope": str(aoi == "king_salman_park"),
            "in_v4_scope": str(aoi in ("king_salman_park", "diriyah_gate")),
        })

    for r in csv.DictReader(open(SQ1C_DBB)):
        if not r.get("dbb_faithful"):
            continue
        aoi = r["sub_aoi"]
        date = r["date"]
        meta = sq1c_meta.get((aoi, date), {})
        confirmed = (meta.get("confirmed_label") or "").strip()
        ai = (meta.get("ai_prelabel") or "").strip()
        if confirmed:
            label_for_run = confirmed
        else:
            n_unconfirmed += 1
            if not allow_unconfirmed:
                label_for_run = ""    # surfaces in the assert below
            else:
                label_for_run = ai     # debug fallback
        rows.append({
            "source": "SQ1C",
            "aoi": aoi,
            "date": date,
            "sub_aoi": aoi,
            "dbb_faithful": float(r["dbb_faithful"]),
            "n_valid_pixels": int(r["n_valid_pixels"]),
            "n_total_pixels": int(r["n_total_pixels"]),
            "final_label": label_for_run,
            "ai_prelabel": ai,
            "ai_confidence": meta.get("ai_confidence", ""),
            "bias_exposed_during_ai_labeling":
                meta.get("bias_exposed_during_ai_labeling", "False"),
            "review_protocol": meta.get("review_protocol", ""),
            "in_v3_scope": str(aoi == "king_salman_park"),
            "in_v4_scope": str(aoi in ("king_salman_park", "diriyah_gate")),
        })

    for i, r in enumerate(rows, 1):
        r["row_id"] = i

    return rows, n_unconfirmed


def write_combined(rows):
    with open(OUT_COMBINED, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COMBINED_FIELDS)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in COMBINED_FIELDS})


def run_variant(name, df_full, source_tag="combined_73_confirmed"):
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
            "boots": np.array([]),
            "fpr": np.array([0, 1]), "tpr": np.array([0, 1]),
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
        ax.plot(r["fpr"], r["tpr"], "-", lw=2, color="#3b82a4")
        ax.plot([0, 1], [0, 1], "--", color="grey", alpha=0.5)
        ax.set_xlim(-0.02, 1.02); ax.set_ylim(-0.02, 1.02)
        title = (f"{name}  AUC={r['auc']:.3f}\n"
                 f"n_pos={r['n_pos']} n_neg={r['n_neg']}  "
                 f"t={r['threshold_youden']:+.4f}")
        ax.set_title(title, fontsize=10)
        ax.set_xlabel("FPR"); ax.set_ylabel("TPR")
    fig.suptitle("SQ1B re-re-run on CONFIRMED labels — ROC curves", y=1.0)
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
        ax.hist(r["boots"], bins=40, color="#3b82a4", edgecolor="black", alpha=0.7)
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
    fig.suptitle(f"SQ1B re-re-run on CONFIRMED labels — bootstrap "
                 f"threshold distributions ({N_BOOT} iters, seed={SEED})",
                 y=1.0)
    fig.tight_layout()
    fig.savefig(out_path, dpi=120, bbox_inches="tight")
    plt.close(fig)


def write_results_csv(results_list, out_path):
    fields = ["variant", "source", "n_pos", "n_neg", "auc",
              "threshold_youden", "ci_low", "ci_high", "ci_halfwidth",
              "ci_passes", "auc_passes", "ships", "notes"]
    with open(out_path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in results_list:
            w.writerow({k: r.get(k) for k in fields})


def load_preliminary_results():
    """Read sq1b_rerun_v2_threshold_results.csv (session 3) for spec comparison.
    Returns {variant: row_dict} or {} if not present."""
    if not PRELIM_RESULTS.exists():
        return {}
    out = {}
    for r in csv.DictReader(open(PRELIM_RESULTS)):
        out[r["variant"]] = r
    return out


def write_spec(results, prelim, out_path):
    lines = [
        "# SQ1B re-re-run — threshold spec on CONFIRMED labels",
        "",
        f"**Input:** `{OUT_COMBINED.name}` (30 SQ1D + 43 SQ1C, primary refs, "
        "SQ1C labels = `confirmed_label` post-researcher-review).",
        f"**Stop rule:** CI half-width < {CI_HALFWIDTH_TARGET} AND AUC > {AUC_TARGET}.",
        f"**Bootstrap:** {N_BOOT} iters, seed={SEED}; ROC sweep {N_SWEEP} thresholds.",
        "",
        "**Status:** Non-preliminary IFF the 6 cold-protocol rows "
        "(`bias_exposed_during_ai_labeling=True`) and all 37 standard-protocol "
        "rows have been researcher-confirmed via `sq1c_label_review.py`. The "
        "bias_exposed flag remains True in the data even after cold-labeling — "
        "the cold protocol is the audit, not an erasure.",
        "",
        "## Per-variant results (confirmed labels)",
        "",
        "| variant | n_pos | n_neg | AUC | t_youden | CI [lo, hi] | CI hw | ships |",
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

    if prelim:
        lines += [
            "",
            "## Confirmed vs preliminary (session 3) comparison",
            "",
            "Preliminary source: `sq1b_rerun_v2_threshold_results.csv` (AI-only labels for SQ1C).",
            "",
            "| variant | n_pos prelim | n_pos conf | AUC prelim | AUC conf | t_youden prelim | t_youden conf | CI hw prelim | CI hw conf | ships prelim | ships conf | changed? |",
            "|---|---:|---:|---:|---:|---:|---:|---:|---:|:-:|:-:|:-:|",
        ]
        for v in ("V1", "V2", "V3", "V4"):
            r = results[v]
            p = prelim.get(v, {})

            def fmt(s, kind):
                if s is None or s == "":
                    return "?"
                try:
                    f = float(s)
                except (TypeError, ValueError):
                    return str(s)
                if np.isnan(f):
                    return "NaN"
                return f"{f:+.4f}" if kind == "thr" else f"{f:.4f}"

            ships_p = str(p.get("ships", "")).lower() == "true"
            ships_c = bool(r["ships"])
            changed = "yes" if ships_p != ships_c else "no"
            lines.append(
                f"| {v} | "
                f"{p.get('n_pos', '?')} | {r['n_pos']} | "
                f"{fmt(p.get('auc', ''), 'auc')} | {fmt(r['auc'], 'auc')} | "
                f"{fmt(p.get('threshold_youden', ''), 'thr')} | {fmt(r['threshold_youden'], 'thr')} | "
                f"{fmt(p.get('ci_halfwidth', ''), 'auc')} | {fmt(r['ci_halfwidth'], 'auc')} | "
                f"{'✓' if ships_p else '✗'} | "
                f"{'✓' if ships_c else '✗'} | "
                f"**{changed}** |"
            )
        lines += [
            "",
            "**Stop-rule changes** are the load-bearing diff. Any 'yes' in "
            "the `changed?` column needs prose explanation in the methodology "
            "footnote update.",
        ]
    else:
        lines += [
            "",
            "## Confirmed vs preliminary",
            "",
            f"Preliminary results CSV `{PRELIM_RESULTS.name}` not found; "
            "comparison table omitted.",
        ]

    lines += [
        "",
        "## Variant scopes",
        "",
        "- V1: heavy_dust vs clean, all AOIs.",
        "- V2: any-non-clean vs clean, all AOIs (HEADLINE attempt).",
        "- V3: KSP-only any-non-clean vs clean.",
        "- V4: KSP + Diriyah any-non-clean vs clean (Qiddiya excluded for "
        "construction-substrate label contamination — V2 failure on this "
        "scope is the third independent line of evidence for that effect).",
        "",
    ]
    out_path.write_text("\n".join(lines))


def main():
    p = argparse.ArgumentParser(
        description="SQ1B re-re-run on CONFIRMED SQ1C labels. Run AFTER "
                    "sq1c_label_review.py confirmation passes complete.",
    )
    p.add_argument(
        "--allow-unconfirmed", action="store_true",
        help="DEBUG ONLY: fall back to ai_prelabel for any unconfirmed SQ1C "
             "row instead of failing. Do not use for ship results.",
    )
    args = p.parse_args()

    print(f"Stop rule: CI half-width < {CI_HALFWIDTH_TARGET}  AND  AUC > {AUC_TARGET}")
    print(f"Bootstrap: {N_BOOT} iters, seed={SEED}")
    print(f"ROC sweep: {N_SWEEP} thresholds\n")

    rows, n_unconfirmed = build_combined(args.allow_unconfirmed)
    n_total = len(rows)
    if n_total != 73:
        print(f"WARNING: expected 73 rows in combined dataset, got {n_total}",
              file=sys.stderr)

    if n_unconfirmed > 0 and not args.allow_unconfirmed:
        print(f"ERROR: {n_unconfirmed} SQ1C row(s) not yet confirmed.",
              file=sys.stderr)
        print("Run `python sq1c_label_review.py --aoi {ksp,qiddiya,diriyah}` "
              "to complete the researcher pass first.", file=sys.stderr)
        return 1
    if n_unconfirmed > 0:
        print(f"WARN: --allow-unconfirmed set; {n_unconfirmed} SQ1C row(s) "
              "fell back to ai_prelabel. Results are NOT shippable.")

    write_combined(rows)
    print(f"Wrote {OUT_COMBINED}")

    df = pd.read_csv(OUT_COMBINED).rename(columns={"dbb_faithful": "dbb"})
    print(f"\nLoaded combined dataset: {len(df)} rows. "
          f"Label dist: {df['final_label'].value_counts().to_dict()}")
    print(f"Source split: {df['source'].value_counts().to_dict()}")
    print(f"bias_exposed=True: "
          f"{(df['bias_exposed_during_ai_labeling'].astype(str)=='True').sum()}\n")

    variants = ["V1", "V2", "V3", "V4"]
    results = {v: run_variant(v, df) for v in variants}

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

    prelim = load_preliminary_results()
    if prelim:
        print(f"\nLoaded preliminary results from {PRELIM_RESULTS.name} for spec comparison.")
    else:
        print(f"\nNote: {PRELIM_RESULTS.name} not found; spec will omit the comparison table.")

    write_results_csv([results[v] for v in variants], OUT_RESULTS)
    print(f"Wrote {OUT_RESULTS}")
    plot_roc_grid(results, OUT_ROC)
    print(f"Wrote {OUT_ROC}")
    plot_boot_grid(results, OUT_BOOT)
    print(f"Wrote {OUT_BOOT}")
    write_spec(results, prelim, OUT_SPEC)
    print(f"Wrote {OUT_SPEC}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

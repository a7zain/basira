"""
SQ1B re-run on faithful Lolli DBB output.

Four binary task variants on sq1d_dbb_faithful.csv:
  V1 — heavy_dust vs clean, all AOIs (1 vs 23).
  V2 — any-non-clean (light_haze + heavy_dust) vs clean, all AOIs.
  V3 — KSP-only any-non-clean vs clean.
  V4 — KSP + Diriyah any-non-clean vs clean (Qiddiya excluded for label
       contamination from construction substrate).

Stop rule (reused verbatim from commit 3d3b511 / SQ1B_RESULTS.md):
  ship a threshold IFF bootstrap 95% CI half-width < 0.02 AND AUC > 0.75.

For each variant:
  - Drop cloud-labeled rows (cloud is a different physical phenomenon).
  - 1000-point fine ROC sweep over the observed DBB range.
  - AUC via trapezoidal integration of TPR vs FPR.
  - Youden-optimal threshold = argmax(TPR − FPR).
  - 2000 bootstrap iterations (seed 42) → 95% CI on Youden threshold.

Sensitivity check: re-run the largest variant that passes (or, if none,
the highest-AUC variant) on sq1d_dbb_faithful_alt.csv.

Outputs:
  data/threshold_fits/_archive/sq1b_threshold_results.csv
  data/threshold_fits/_archive/sq1b_roc_curves.png
  data/threshold_fits/_archive/sq1b_bootstrap_thresholds.png
"""
from __future__ import annotations

import csv
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[3]
DATA = REPO / "research" / "dust-honesty" / "data"

PRIMARY_CSV = DATA / "dbb_compute" / "dbb_calibration_sq1d.csv"
ALT_CSV = DATA / "dbb_compute" / "dbb_calibration_alt_sq1d.csv"

OUT_RESULTS_CSV = DATA / "threshold_fits" / "_archive" / "sq1b_threshold_results.csv"
OUT_ROC_PNG = DATA / "threshold_fits" / "_archive" / "sq1b_roc_curves.png"
OUT_BOOT_PNG = DATA / "threshold_fits" / "_archive" / "sq1b_bootstrap_thresholds.png"

# Stop rule (commit 3d3b511 / SQ1B_RESULTS.md):
CI_HALFWIDTH_TARGET = 0.02   # precision target on bootstrap 95% CI half-width
AUC_TARGET = 0.75            # AUC must exceed this

N_BOOT = 2000
SEED = 42
N_SWEEP = 1000


def load_primary() -> pd.DataFrame:
    df = pd.read_csv(PRIMARY_CSV)
    df = df.rename(columns={"dbb_faithful": "dbb"})
    return df


def load_alt() -> pd.DataFrame:
    df = pd.read_csv(ALT_CSV)
    df = df.rename(columns={"dbb_faithful": "dbb"})
    return df


# ---- variant filters ----------------------------------------------------

def variant_filter(df: pd.DataFrame, variant: str) -> tuple[pd.DataFrame, np.ndarray]:
    """Return (sub_df, y_binary) for the variant."""
    df = df[df["final_label"] != "cloud"].copy()
    if variant == "V1":
        sub = df[df["final_label"].isin(["heavy_dust", "clean"])].copy()
        y = (sub["final_label"] == "heavy_dust").astype(int).to_numpy()
    elif variant == "V2":
        sub = df[df["final_label"].isin(["light_haze", "heavy_dust", "clean"])].copy()
        y = sub["final_label"].isin(["light_haze", "heavy_dust"]).astype(int).to_numpy()
    elif variant == "V3":
        sub = df[df["sub_aoi"] == "king_salman_park"].copy()
        sub = sub[sub["final_label"].isin(["light_haze", "heavy_dust", "clean"])].copy()
        y = sub["final_label"].isin(["light_haze", "heavy_dust"]).astype(int).to_numpy()
    elif variant == "V4":
        sub = df[df["sub_aoi"].isin(["king_salman_park", "diriyah_gate"])].copy()
        sub = sub[sub["final_label"].isin(["light_haze", "heavy_dust", "clean"])].copy()
        y = sub["final_label"].isin(["light_haze", "heavy_dust"]).astype(int).to_numpy()
    else:
        raise ValueError(variant)
    return sub.reset_index(drop=True), y


# ---- core stats ---------------------------------------------------------

def sweep_thresholds(values: np.ndarray, n: int = N_SWEEP) -> np.ndarray:
    lo, hi = float(np.min(values)), float(np.max(values))
    pad = max(1e-6, (hi - lo) * 1e-3)
    return np.linspace(lo - pad, hi + pad, n)


def roc(values: np.ndarray, y: np.ndarray, thresholds: np.ndarray):
    """Return (fpr, tpr, thresh) sorted by fpr ascending."""
    tprs = np.zeros_like(thresholds)
    fprs = np.zeros_like(thresholds)
    p = (y == 1).sum()
    n = (y == 0).sum()
    for i, t in enumerate(thresholds):
        pred = (values > t).astype(int)
        tp = ((y == 1) & (pred == 1)).sum()
        fp = ((y == 0) & (pred == 1)).sum()
        tprs[i] = tp / p if p else 0.0
        fprs[i] = fp / n if n else 0.0
    order = np.argsort(fprs)
    return fprs[order], tprs[order], thresholds[order]


def trapz_auc(fpr: np.ndarray, tpr: np.ndarray) -> float:
    return float(np.trapz(tpr, fpr))


def youden_threshold(values: np.ndarray, y: np.ndarray, thresholds: np.ndarray) -> float:
    """argmax(TPR − FPR). Tie-break: midmost threshold."""
    p = (y == 1).sum()
    n = (y == 0).sum()
    if p == 0 or n == 0:
        return float(np.median(thresholds))
    j_scores = np.zeros_like(thresholds)
    for i, t in enumerate(thresholds):
        pred = (values > t).astype(int)
        tp = ((y == 1) & (pred == 1)).sum()
        fp = ((y == 0) & (pred == 1)).sum()
        tpr = tp / p
        fpr = fp / n
        j_scores[i] = tpr - fpr
    best = j_scores.max()
    idxs = np.where(j_scores == best)[0]
    midrange = thresholds.mean()
    return float(thresholds[idxs[np.argmin(np.abs(thresholds[idxs] - midrange))]])


def bootstrap_thresholds(values, y, thresholds, n_boot=N_BOOT, seed=SEED):
    rng = np.random.default_rng(seed)
    n = len(values)
    out = []
    skipped = 0
    for _ in range(n_boot):
        idx = rng.integers(0, n, n)
        v = values[idx]
        yy = y[idx]
        if (yy == 1).sum() == 0 or (yy == 0).sum() == 0:
            skipped += 1
            continue
        out.append(youden_threshold(v, yy, thresholds))
    return np.array(out), skipped


# ---- per-variant runner -------------------------------------------------

def run_variant(name: str, df_full: pd.DataFrame, variant_label: str = None,
                source_tag: str = "primary") -> dict:
    sub, y = variant_filter(df_full, name)
    values = sub["dbb"].to_numpy(dtype=float)
    n_pos = int((y == 1).sum())
    n_neg = int((y == 0).sum())

    if n_pos == 0 or n_neg == 0:
        return {
            "variant": variant_label or name,
            "source": source_tag,
            "n_pos": n_pos, "n_neg": n_neg,
            "auc": float("nan"),
            "threshold_youden": float("nan"),
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
        "variant": variant_label or name,
        "source": source_tag,
        "n_pos": n_pos, "n_neg": n_neg,
        "auc": auc,
        "threshold_youden": t_hat,
        "ci_low": float(ci_lo), "ci_high": float(ci_hi),
        "ci_halfwidth": float(ci_hw),
        "ci_passes": ci_passes, "auc_passes": auc_passes, "ships": ships,
        "boots": boots,
        "fpr": fpr, "tpr": tpr,
        "notes": ";".join(note_bits) if note_bits else "",
    }


# ---- plotting -----------------------------------------------------------

def plot_roc_grid(results: dict, out_path: Path):
    fig, axes = plt.subplots(2, 2, figsize=(9, 9))
    for ax, (name, r) in zip(axes.flatten(), results.items()):
        ax.plot(r["fpr"], r["tpr"], "-", lw=2, color="#b4793b")
        ax.plot([0, 1], [0, 1], "--", color="grey", alpha=0.5)
        # Youden point (find idx whose threshold is the Youden threshold)
        # Reproject via current ROC sweep:
        if not np.isnan(r["auc"]):
            # Mark by computing TPR/FPR at exactly the Youden threshold
            # — recompute against the original variant's values:
            pass
        ax.set_xlim(-0.02, 1.02); ax.set_ylim(-0.02, 1.02)
        title = (f"{name}  AUC={r['auc']:.3f}\n"
                 f"n_pos={r['n_pos']} n_neg={r['n_neg']}  "
                 f"t={r['threshold_youden']:+.4f}")
        ax.set_title(title, fontsize=10)
        ax.set_xlabel("FPR"); ax.set_ylabel("TPR")
    fig.suptitle("SQ1B re-run on faithful Lolli DBB — ROC curves", y=1.0)
    fig.tight_layout()
    fig.savefig(out_path, dpi=120, bbox_inches="tight")
    plt.close(fig)


def plot_youden_point(ax, values, y, t_hat):
    p = (y == 1).sum(); n = (y == 0).sum()
    pred = (values > t_hat).astype(int)
    tp = ((y == 1) & (pred == 1)).sum()
    fp = ((y == 0) & (pred == 1)).sum()
    tpr = tp / p if p else 0
    fpr = fp / n if n else 0
    ax.plot(fpr, tpr, marker="o", color="black", markersize=10, mfc="none", mew=2)


def plot_boot_grid(results: dict, out_path: Path):
    fig, axes = plt.subplots(2, 2, figsize=(10, 8))
    for ax, (name, r) in zip(axes.flatten(), results.items()):
        if len(r["boots"]) == 0:
            ax.text(0.5, 0.5, f"{name}: degenerate (no boots)",
                    ha="center", va="center", transform=ax.transAxes)
            ax.set_title(name)
            continue
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
    fig.suptitle("SQ1B re-run — bootstrap threshold distributions (2000 iters, seed=42)",
                 y=1.0)
    fig.tight_layout()
    fig.savefig(out_path, dpi=120, bbox_inches="tight")
    plt.close(fig)


# ---- main ---------------------------------------------------------------

def write_results_csv(results_list: list[dict], out_path: Path):
    fields = ["variant", "source", "n_pos", "n_neg", "auc",
              "threshold_youden", "ci_low", "ci_high", "ci_halfwidth",
              "ci_passes", "auc_passes", "ships", "notes"]
    with open(out_path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in results_list:
            w.writerow({k: r.get(k) for k in fields})


def main():
    print(f"Stop rule: CI half-width < {CI_HALFWIDTH_TARGET}  AND  AUC > {AUC_TARGET}")
    print(f"Bootstrap: {N_BOOT} iters, seed={SEED}")
    print(f"ROC sweep: {N_SWEEP} thresholds")
    print()

    df = load_primary()
    print(f"Loaded primary: {len(df)} rows. Label dist: "
          f"{df['final_label'].value_counts().to_dict()}\n")

    variants = ["V1", "V2", "V3", "V4"]
    results = {}
    for v in variants:
        r = run_variant(v, df, variant_label=v, source_tag="primary")
        results[v] = r
        print(f"=== {v} (primary) ===")
        print(f"  n_pos={r['n_pos']}  n_neg={r['n_neg']}")
        print(f"  AUC={r['auc']:.4f}  t_youden={r['threshold_youden']:+.4f}")
        print(f"  95% CI: [{r['ci_low']:+.4f}, {r['ci_high']:+.4f}]  "
              f"halfwidth={r['ci_halfwidth']:.4f}")
        print(f"  ships={r['ships']}  (CI {'pass' if r['ci_passes'] else 'STOP'}, "
              f"AUC {'pass' if r['auc_passes'] else 'STOP'})")
        if r["notes"]:
            print(f"  notes: {r['notes']}")
        print()

    # --- sensitivity check ---
    shippers = [v for v in variants if results[v]["ships"]]
    if shippers:
        # largest n_pos+n_neg among shippers
        chosen = max(shippers, key=lambda v: results[v]["n_pos"] + results[v]["n_neg"])
        rationale = "largest passing variant"
    else:
        # highest AUC (NaN-safe)
        valid_auc = {v: results[v]["auc"] for v in variants
                     if not np.isnan(results[v]["auc"])}
        chosen = max(valid_auc, key=valid_auc.get) if valid_auc else "V2"
        rationale = "no shippers; highest-AUC variant"
    print(f"Sensitivity-check variant: {chosen} ({rationale})")

    # If chosen is V4: alt has no Diriyah → falls back to KSP-only = V3 scope
    df_alt = load_alt()
    if chosen == "V4":
        sens_variant_for_alt = "V3"
        sens_label = "V4_alt (=V3 scope: Diriyah has no alternate ref)"
    else:
        sens_variant_for_alt = chosen
        sens_label = f"{chosen}_alt"

    r_alt = run_variant(sens_variant_for_alt, df_alt, variant_label=sens_label,
                        source_tag="alternate")
    print(f"=== {sens_label} ===")
    print(f"  n_pos={r_alt['n_pos']}  n_neg={r_alt['n_neg']}")
    print(f"  AUC={r_alt['auc']:.4f}  t_youden={r_alt['threshold_youden']:+.4f}")
    print(f"  95% CI: [{r_alt['ci_low']:+.4f}, {r_alt['ci_high']:+.4f}]  "
          f"halfwidth={r_alt['ci_halfwidth']:.4f}")
    print(f"  ships={r_alt['ships']}")

    # --- write results CSV ---
    rows_for_csv = [results[v] for v in variants] + [r_alt]
    write_results_csv(rows_for_csv, OUT_RESULTS_CSV)
    print(f"\nWrote {OUT_RESULTS_CSV}")

    # --- plots ---
    plot_roc_grid(results, OUT_ROC_PNG)
    print(f"Wrote {OUT_ROC_PNG}")
    plot_boot_grid(results, OUT_BOOT_PNG)
    print(f"Wrote {OUT_BOOT_PNG}")

    # Also stash sensitivity result + chosen for the spec doc:
    print()
    print(f"SENSITIVITY: variant={sens_label}  ships={r_alt['ships']}")
    if not np.isnan(results[chosen if chosen != 'V4' else 'V3']["threshold_youden"]) and \
       not np.isnan(r_alt["threshold_youden"]):
        prim_t = results[chosen if chosen != "V4" else "V3"]["threshold_youden"]
        delta_t = r_alt["threshold_youden"] - prim_t
        agree = (results[chosen if chosen != "V4" else "V3"]["ships"] == r_alt["ships"])
        print(f"  threshold(prim)={prim_t:+.4f}  threshold(alt)={r_alt['threshold_youden']:+.4f}  "
              f"delta={delta_t:+.4f}  stop-rule_agreement={agree}")


if __name__ == "__main__":
    main()

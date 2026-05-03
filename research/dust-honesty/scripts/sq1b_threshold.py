"""
SQ1B — threshold tuning for the DBB dust flag with bootstrap CI.

Two label mappings (per the SQ1B brief):
  CONSERVATIVE: clean, light_haze, cloud -> 0 ; heavy_dust, mixed -> 1
  AGGRESSIVE:   clean, cloud -> 0 ; light_haze, heavy_dust, mixed -> 1

For each mapping:
  - sweep all dbb_mean values, find the threshold maximizing balanced accuracy
  - 1000 bootstrap resamples -> 95% CI on the threshold
  - report sens / spec / bal-acc / F1 at the chosen threshold
  - save ROC curve and confusion matrix figures

Outputs:
  figures/sq1b_roc_<mapping>.png
  figures/sq1b_confusion_<mapping>.png
  figures/threshold_fits/threshold_bootstrap_sq1b.png
  data/threshold_fits/_archive/sq1b_summary.json
"""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[3]
DATA = REPO / "research" / "dust-honesty" / "data"
FIGS = REPO / "research" / "dust-honesty" / "figures"

MAPPINGS = {
    "conservative": {
        "positive": {"heavy_dust", "mixed"},
        "negative": {"clean", "light_haze", "cloud"},
    },
    "aggressive": {
        "positive": {"light_haze", "heavy_dust", "mixed"},
        "negative": {"clean", "cloud"},
    },
}

N_BOOT = 1000
SEED = 20260427


def load_joined() -> pd.DataFrame:
    labels = pd.read_csv(DATA / "calibration" / "manual_labels_sq1.csv")
    values = pd.read_csv(DATA / "calibration" / "_archive" / "dbb_values_sq1.csv")
    df = labels.merge(values[["scene_id", "dbb_mean"]], on="scene_id")
    return df


def to_binary(df: pd.DataFrame, mapping: dict) -> pd.DataFrame:
    pos, neg = mapping["positive"], mapping["negative"]
    out = df.copy()
    out["y"] = out["label"].map(lambda x: 1 if x in pos else (0 if x in neg else np.nan))
    return out.dropna(subset=["y"]).astype({"y": int}).reset_index(drop=True)


def balanced_accuracy(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    tp = ((y_true == 1) & (y_pred == 1)).sum()
    tn = ((y_true == 0) & (y_pred == 0)).sum()
    p = (y_true == 1).sum()
    n = (y_true == 0).sum()
    sens = tp / p if p else 0.0
    spec = tn / n if n else 0.0
    return 0.5 * (sens + spec)


def best_threshold(values: np.ndarray, y: np.ndarray) -> tuple[float, float]:
    """Threshold maximizing balanced accuracy. Rule: dbb_mean > t => positive.

    Candidate thresholds: midpoints between sorted unique values, plus extremes.
    Ties broken by preferring the threshold closest to the midrange (more
    parsimonious / less overfit to the boundary point)."""
    s = np.sort(np.unique(values))
    if len(s) < 2:
        return float(s[0]), 0.5
    cands = np.concatenate([[s[0] - 1e-6], (s[:-1] + s[1:]) / 2.0, [s[-1] + 1e-6]])
    scores = np.array([balanced_accuracy(y, (values > t).astype(int)) for t in cands])
    best_score = scores.max()
    best_idx = np.where(scores == best_score)[0]
    midrange = (s[0] + s[-1]) / 2.0
    chosen = best_idx[np.argmin(np.abs(cands[best_idx] - midrange))]
    return float(cands[chosen]), float(best_score)


def metrics_at(values, y, t) -> dict:
    pred = (values > t).astype(int)
    tp = int(((y == 1) & (pred == 1)).sum())
    tn = int(((y == 0) & (pred == 0)).sum())
    fp = int(((y == 0) & (pred == 1)).sum())
    fn = int(((y == 1) & (pred == 0)).sum())
    sens = tp / (tp + fn) if (tp + fn) else 0.0
    spec = tn / (tn + fp) if (tn + fp) else 0.0
    bal = 0.5 * (sens + spec)
    prec = tp / (tp + fp) if (tp + fp) else 0.0
    f1 = 2 * prec * sens / (prec + sens) if (prec + sens) else 0.0
    return {
        "threshold": t,
        "tp": tp, "tn": tn, "fp": fp, "fn": fn,
        "sensitivity": sens, "specificity": spec,
        "balanced_accuracy": bal, "f1": f1, "precision": prec,
    }


def bootstrap_thresholds(values, y, n_boot=N_BOOT, seed=SEED) -> np.ndarray:
    rng = np.random.default_rng(seed)
    n = len(values)
    out = []
    for _ in range(n_boot):
        idx = rng.integers(0, n, n)
        v = values[idx]; yy = y[idx]
        if (yy == 1).sum() == 0 or (yy == 0).sum() == 0:
            continue  # degenerate sample
        t, _ = best_threshold(v, yy)
        out.append(t)
    return np.array(out)


def roc_curve(values, y) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    s = np.sort(np.unique(values))
    cands = np.concatenate([[s[0] - 1e-6], (s[:-1] + s[1:]) / 2.0, [s[-1] + 1e-6]])
    tprs, fprs = [], []
    for t in cands:
        pred = (values > t).astype(int)
        tp = ((y == 1) & (pred == 1)).sum()
        fn = ((y == 1) & (pred == 0)).sum()
        fp = ((y == 0) & (pred == 1)).sum()
        tn = ((y == 0) & (pred == 0)).sum()
        tprs.append(tp / (tp + fn) if (tp + fn) else 0)
        fprs.append(fp / (fp + tn) if (fp + tn) else 0)
    fprs, tprs = np.array(fprs), np.array(tprs)
    order = np.argsort(fprs)
    return fprs[order], tprs[order], cands[order]


def plot_roc(fpr, tpr, mapping_name, auc, out_path):
    fig, ax = plt.subplots(figsize=(5, 5))
    ax.plot(fpr, tpr, "o-", color="#b4793b")
    ax.plot([0, 1], [0, 1], "--", color="grey", alpha=0.6)
    ax.set_xlabel("False positive rate")
    ax.set_ylabel("True positive rate")
    ax.set_title(f"ROC ({mapping_name})  AUC={auc:.3f}")
    ax.set_xlim(-0.02, 1.02); ax.set_ylim(-0.02, 1.02)
    fig.tight_layout()
    fig.savefig(out_path, dpi=120)
    plt.close(fig)


def plot_confusion(m, mapping_name, out_path):
    cm = np.array([[m["tn"], m["fp"]], [m["fn"], m["tp"]]])
    fig, ax = plt.subplots(figsize=(4.5, 4))
    im = ax.imshow(cm, cmap="Oranges")
    ax.set_xticks([0, 1]); ax.set_yticks([0, 1])
    ax.set_xticklabels(["pred clean", "pred dust"])
    ax.set_yticklabels(["true clean", "true dust"])
    for i in range(2):
        for j in range(2):
            ax.text(j, i, str(cm[i, j]), ha="center", va="center",
                    color="black", fontsize=14)
    ax.set_title(f"Confusion ({mapping_name})\nt={m['threshold']:+.4f}  bal_acc={m['balanced_accuracy']:.2f}")
    fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    fig.tight_layout()
    fig.savefig(out_path, dpi=120)
    plt.close(fig)


def trapz_auc(fpr, tpr) -> float:
    return float(np.trapz(tpr, fpr))


def main():
    df = load_joined()
    print(f"Joined: {len(df)} scenes, label counts:\n{df['label'].value_counts().to_dict()}\n")

    summary = {}
    boot_dist = {}

    for name, mapping in MAPPINGS.items():
        b = to_binary(df, mapping)
        v = b["dbb_mean"].to_numpy()
        y = b["y"].to_numpy()
        n_pos = int((y == 1).sum()); n_neg = int((y == 0).sum())
        print(f"=== {name} ===")
        print(f"  scenes: {len(b)}  positives: {n_pos}  negatives: {n_neg}")
        if n_pos == 0 or n_neg == 0:
            print("  degenerate mapping, skipping")
            continue

        t_hat, ba = best_threshold(v, y)
        m = metrics_at(v, y, t_hat)

        boots = bootstrap_thresholds(v, y)
        ci_lo, ci_hi = np.percentile(boots, [2.5, 97.5])
        boot_dist[name] = boots

        fpr, tpr, _ = roc_curve(v, y)
        auc = trapz_auc(fpr, tpr)

        plot_roc(fpr, tpr, name, auc, FIGS / "threshold_fits" / "_archive" / f"roc_{name}_sq1b.png")
        plot_confusion(m, name, FIGS / "threshold_fits" / "_archive" / f"confusion_{name}_sq1b.png")

        ci_halfwidth = (ci_hi - ci_lo) / 2.0
        print(f"  best threshold: {t_hat:+.4f}  bal_acc={ba:.3f}")
        print(f"  bootstrap 95% CI: [{ci_lo:+.4f}, {ci_hi:+.4f}]  half-width={ci_halfwidth:.4f}")
        print(f"  metrics: sens={m['sensitivity']:.2f} spec={m['specificity']:.2f} "
              f"f1={m['f1']:.2f} prec={m['precision']:.2f}")
        print(f"  AUC: {auc:.3f}\n")

        summary[name] = {
            "n_scenes": int(len(b)),
            "n_positives": n_pos,
            "n_negatives": n_neg,
            "threshold": t_hat,
            "ci_low": float(ci_lo), "ci_high": float(ci_hi),
            "ci_halfwidth": float(ci_halfwidth),
            "auc": auc,
            **m,
        }

    # bootstrap histogram (both mappings overlaid)
    fig, ax = plt.subplots(figsize=(7, 4))
    colors = {"conservative": "#7a3b3b", "aggressive": "#b4793b"}
    for name, boots in boot_dist.items():
        ax.hist(boots, bins=30, alpha=0.55, label=f"{name} (n={len(boots)})",
                color=colors[name], edgecolor="black")
        s = summary[name]
        ax.axvline(s["threshold"], color=colors[name], ls="-", lw=2)
        ax.axvline(s["ci_low"], color=colors[name], ls="--", lw=1)
        ax.axvline(s["ci_high"], color=colors[name], ls="--", lw=1)
    ax.set_xlabel("Bootstrap threshold")
    ax.set_ylabel("count")
    ax.set_title("Bootstrap distribution of best DBB threshold")
    ax.legend()
    fig.tight_layout()
    fig.savefig(FIGS / "threshold_fits" / "threshold_bootstrap_sq1b.png", dpi=120)
    plt.close(fig)

    (DATA / "threshold_fits" / "_archive" / "sq1b_summary.json").write_text(json.dumps(summary, indent=2))
    print(f"Wrote summary -> {DATA / 'threshold_fits' / '_archive' / 'sq1b_summary.json'}")
    return summary


if __name__ == "__main__":
    main()

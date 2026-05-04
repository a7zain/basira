"""
SQ4 — pair difference-of-differences + bootstrap.

Inputs:
  research/dust-honesty/data/ndvi_bias/paired_sen2cor_sq3.csv (38 SQ3 pairs)
  research/dust-honesty/data/cross_correction/ndvi_hls_s30_b8a_sq4.csv  (65 (aoi, date) NDVI rows)

Outputs:
  research/dust-honesty/data/cross_correction/diff_of_diffs_lasrc_sq4.csv   (one row per kept pair)
  research/dust-honesty/data/cross_correction/signal_class_sq4.csv    (one row per AOI)

Math:
  delta_hls = hls_ndvi(fired) - hls_ndvi(neighbor)
  delta_sen2cor = sq3 delta_ndvi (renamed for clarity)
  diff_of_diffs = delta_hls - delta_sen2cor

Bootstrap:
  1000 resamples of pairs with replacement (seed 42), per AOI.
  Statistic: mean of diff_of_diffs.
  95% CI = (2.5, 97.5) percentiles of bootstrap means.

Signal classification:
  CI excludes zero          -> 'correction_chains_disagree'
  CI includes zero, hw<0.01 -> 'tight_null'
  else                      -> 'wide_inconclusive'

A pair is kept iff both fired_date AND neighbor_date have a non-empty
hls_ndvi in ndvi_hls_s30_b8a_sq4.csv. Pairs where either side is missing
(Fmask wipeout) are dropped and counted in the AOI summary.

Note: SQ3 column is `delta_ndvi`. We alias it as delta_sen2cor in
this script's outputs for clarity vs delta_hls.
"""
from __future__ import annotations

import csv
import math
from collections import defaultdict
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
DATA = ROOT / "research/dust-honesty/data"

PAIRS_CSV = DATA / "ndvi_bias" / "paired_sen2cor_sq3.csv"
HLS_CSV = DATA / "cross_correction" / "ndvi_hls_s30_b8a_sq4.csv"
OUT_DIFF = DATA / "cross_correction" / "diff_of_diffs_lasrc_sq4.csv"
OUT_CLASS = DATA / "cross_correction" / "signal_class_sq4.csv"

AOIS = ["king_salman_park", "qiddiya_core", "diriyah_gate"]
N_BOOT = 1000
BOOT_SEED = 42
TIGHT_NULL_HALFWIDTH = 0.01


def load_hls_lookup():
    """Return dict[(aoi, date)] -> (hls_ndvi or None, qa_flag, n_valid)."""
    out = {}
    with open(HLS_CSV) as f:
        for r in csv.DictReader(f):
            v = r["hls_ndvi"]
            ndvi = float(v) if v != "" else None
            out[(r["aoi"], r["date"])] = (
                ndvi, r["qa_flag"], int(r["n_valid_pixels"])
            )
    return out


def load_sq3_pairs():
    """Yield dicts with aoi, fired_date, neighbor_date, fired_ndvi,
    neighbor_ndvi, delta_ndvi (Sen2Cor), dt_days."""
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
    halfwidth = (ci_hi - ci_lo) / 2.0
    excludes_zero = (ci_lo > 0) or (ci_hi < 0)
    if excludes_zero:
        return "correction_chains_disagree"
    if halfwidth < TIGHT_NULL_HALFWIDTH:
        return "tight_null"
    return "wide_inconclusive"


def main():
    hls = load_hls_lookup()
    print(f"HLS lookup loaded: {len(hls)} (aoi, date) entries")

    kept_pairs = []
    drop_log = []
    n_seen_per_aoi = defaultdict(int)

    for p in load_sq3_pairs():
        aoi = p["aoi"]
        n_seen_per_aoi[aoi] += 1
        f_key = (aoi, p["fired_date"])
        n_key = (aoi, p["neighbor_date"])
        if f_key not in hls or n_key not in hls:
            drop_log.append((aoi, p["fired_date"], p["neighbor_date"],
                             "missing_in_lookup"))
            continue
        f_ndvi, f_qa, f_n = hls[f_key]
        n_ndvi, n_qa, n_n = hls[n_key]
        if f_ndvi is None or n_ndvi is None:
            why = []
            if f_ndvi is None:
                why.append(f"fired_nan({f_qa})")
            if n_ndvi is None:
                why.append(f"neighbor_nan({n_qa})")
            drop_log.append((aoi, p["fired_date"], p["neighbor_date"],
                             ";".join(why)))
            continue
        delta_hls = f_ndvi - n_ndvi
        diff_of_diffs = delta_hls - p["delta_sen2cor"]
        kept_pairs.append({
            **p,
            "fired_hls": f_ndvi,
            "neighbor_hls": n_ndvi,
            "delta_hls": delta_hls,
            "diff_of_diffs": diff_of_diffs,
            "fired_qa": f_qa,
            "neighbor_qa": n_qa,
        })

    print(f"Pairs seen: {sum(n_seen_per_aoi.values())}")
    print(f"Pairs kept: {len(kept_pairs)}")
    print(f"Pairs dropped: {len(drop_log)}")
    for aoi, fd, nd, why in drop_log:
        print(f"  DROP {aoi} fired={fd} neighbor={nd} why={why}")
    print()

    # Per-pair output
    fields_diff = ["aoi", "fired_date", "neighbor_date", "dt_days",
                   "fired_sen2cor", "neighbor_sen2cor", "delta_sen2cor",
                   "fired_hls", "neighbor_hls", "delta_hls",
                   "diff_of_diffs", "fired_qa", "neighbor_qa"]
    with open(OUT_DIFF, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields_diff)
        w.writeheader()
        for p in kept_pairs:
            w.writerow({
                "aoi": p["aoi"],
                "fired_date": p["fired_date"],
                "neighbor_date": p["neighbor_date"],
                "dt_days": p["dt_days"],
                "fired_sen2cor": f"{p['fired_sen2cor']:.6f}",
                "neighbor_sen2cor": f"{p['neighbor_sen2cor']:.6f}",
                "delta_sen2cor": f"{p['delta_sen2cor']:.6f}",
                "fired_hls": f"{p['fired_hls']:.6f}",
                "neighbor_hls": f"{p['neighbor_hls']:.6f}",
                "delta_hls": f"{p['delta_hls']:.6f}",
                "diff_of_diffs": f"{p['diff_of_diffs']:.6f}",
                "fired_qa": p["fired_qa"],
                "neighbor_qa": p["neighbor_qa"],
            })
    print(f"Wrote {OUT_DIFF} ({len(kept_pairs)} rows)")

    # Per-AOI signal classification
    aoi_summary = []
    for aoi in AOIS:
        n_seen = n_seen_per_aoi[aoi]
        aoi_pairs = [p for p in kept_pairs if p["aoi"] == aoi]
        n_kept = len(aoi_pairs)
        diffs = [p["diff_of_diffs"] for p in aoi_pairs]
        mean, ci_lo, ci_hi = bootstrap_ci(diffs)
        if not math.isnan(ci_lo):
            halfwidth = (ci_hi - ci_lo) / 2.0
        else:
            halfwidth = float("nan")
        sig = signal_class_of(mean, ci_lo, ci_hi)
        aoi_summary.append({
            "aoi": aoi,
            "n_sq3_pairs": n_seen,
            "n_pairs_with_hls": n_kept,
            "mean_diff": mean,
            "ci_lo_95": ci_lo,
            "ci_hi_95": ci_hi,
            "ci_halfwidth": halfwidth,
            "signal_class": sig,
        })

    fields_class = ["aoi", "n_sq3_pairs", "n_pairs_with_hls",
                    "mean_diff", "ci_lo_95", "ci_hi_95",
                    "ci_halfwidth", "signal_class"]
    with open(OUT_CLASS, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields_class)
        w.writeheader()
        for a in aoi_summary:
            row = {"aoi": a["aoi"],
                   "n_sq3_pairs": a["n_sq3_pairs"],
                   "n_pairs_with_hls": a["n_pairs_with_hls"],
                   "signal_class": a["signal_class"]}
            for k in ("mean_diff", "ci_lo_95", "ci_hi_95", "ci_halfwidth"):
                v = a[k]
                row[k] = "" if (v is None or
                                (isinstance(v, float) and math.isnan(v))) \
                    else f"{v:+.6f}"
            w.writerow(row)
    print(f"Wrote {OUT_CLASS} ({len(aoi_summary)} rows)")
    print()

    print("Per-AOI summary (diff_of_diffs = HLS Δ − Sen2Cor Δ):")
    print(f"{'aoi':<22s} {'pairs':>10s} {'mean':>10s} "
          f"{'ci_lo':>10s} {'ci_hi':>10s} {'hw':>8s} {'class':<28s}")
    for a in aoi_summary:
        pairs_str = f"{a['n_pairs_with_hls']}/{a['n_sq3_pairs']}"
        if math.isnan(a["mean_diff"]):
            print(f"{a['aoi']:<22s} {pairs_str:>10s} (insufficient data)")
            continue
        print(f"{a['aoi']:<22s} {pairs_str:>10s} "
              f"{a['mean_diff']:>+10.4f} "
              f"{a['ci_lo_95']:>+10.4f} {a['ci_hi_95']:>+10.4f} "
              f"{a['ci_halfwidth']:>8.4f} {a['signal_class']:<28s}")


if __name__ == "__main__":
    main()

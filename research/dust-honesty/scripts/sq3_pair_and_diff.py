"""
SQ3 — pair V4-fired scenes to nearest unflagged neighbor in same AOI,
compute Δ NDVI = NDVI(fired) − NDVI(neighbor), bootstrap mean and 95%
CI per AOI.

Inputs:
  research/dust-honesty/data/sq2_dbb_operational.csv (228 rows)
  research/dust-honesty/data/sq3_ndvi_per_scene.csv  (228 rows)

Pairing rules:
  For each V4-fired scene at (AOI, date) with valid NDVI:
    - Restrict candidates to same AOI.
    - Restrict to flag_v4=False, cloud_flag_present=False,
      no_usable_scene=False, NDVI present.
    - |Δt| ≤ 60 days.
    - Sort by (abs_dt, neighbor_date_asc); take first.
      → ties broken by EARLIER neighbor date (deterministic).
  If no qualifying neighbor, fired scene is dropped from the bias CSV
  but counted as `n_unpairable` in the audit.

  Unflagged neighbors may be reused across pairings — the bootstrap
  resamples PAIRS (not scenes), so within-AOI dependence shows up at
  inference time as wider CIs.

Bootstrap:
  - 1000 resamples of pairs with replacement (random seed 42).
  - Per resample: mean of delta_ndvi. Take 2.5 / 97.5 percentiles for
    the 95% CI. ci_halfwidth = (ci_hi − ci_lo) / 2.

Decision rule:
  - 95% CI excludes zero, mean Δ < 0      → 'signal_negative'
  - 95% CI excludes zero, mean Δ > 0      → 'signal_positive'
  - CI includes zero, ci_halfwidth < 0.01 → 'tight_null'
  - else                                   → 'wide_inconclusive'
  - n_paired = 0 also classed 'wide_inconclusive' (CI fields blank).

V4 is uniform across all three AOIs. V3-KSP-only is not exercised in
this script — sensitivity goes in the findings note (S3), not the
headline pairing.

Outputs:
  research/dust-honesty/data/sq3_ndvi_bias.csv    (one row per pair)
  research/dust-honesty/data/sq3_pairing_audit.csv (one row per AOI)
"""
from __future__ import annotations

import csv
import math
from datetime import date
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
DATA = ROOT / "research/dust-honesty/data"

DBB_CSV = DATA / "operational" / "dbb_operational_sq2.csv"
NDVI_CSV = DATA / "ndvi_bias" / "ndvi_per_scene_sq3.csv"
OUT_BIAS = DATA / "ndvi_bias" / "paired_sen2cor_sq3.csv"
OUT_AUDIT = DATA / "ndvi_bias" / "pairing_audit_sq3.csv"

AOIS = ["king_salman_park", "qiddiya_core", "diriyah_gate"]
WINDOW_DAYS = 60
N_BOOT = 1000
BOOT_SEED = 42
TIGHT_NULL_HALFWIDTH = 0.01


def parse_date(s):
    return date.fromisoformat(s)


def load_joined():
    """Read DBB + NDVI, join on (aoi, system_index). Returns list of dicts:
        aoi, year, month, scene_date(date), system_index,
        dbb(float|None), flag_v4(bool), cloud_flag(bool), no_usable(bool),
        ndvi(float|None)
    """
    ndvi_lookup = {}
    with open(NDVI_CSV) as f:
        for r in csv.DictReader(f):
            key = (r["aoi"], r["system_index"])
            v = r["ndvi_aoi_mean"]
            ndvi_lookup[key] = (float(v) if v != "" else None)

    rows = []
    with open(DBB_CSV) as f:
        for r in csv.DictReader(f):
            sd = r["scene_date"]
            scene_date = parse_date(sd) if sd else None
            dbb_str = r["dbb"]
            dbb = float(dbb_str) if dbb_str != "" else None
            ndvi = ndvi_lookup.get((r["aoi"], r["system_index"]))
            rows.append({
                "aoi": r["aoi"],
                "year": int(r["year"]),
                "month": int(r["month"]),
                "scene_date": scene_date,
                "system_index": r["system_index"],
                "dbb": dbb,
                "flag_v4": (r["flag_v4"] == "True"),
                "cloud_flag": (r["cloud_flag_present"] == "True"),
                "no_usable": (r["no_usable_scene"] == "True"),
                "ndvi": ndvi,
            })
    return rows


def fired_pool(rows, aoi):
    """V4-fired rows in this AOI with usable date and NDVI present.

    Cloud-flagged fired scenes are kept (per spec — only neighbors are
    cloud-filtered). They appear in the bias CSV with a flag in the
    audit CSV's `n_fired_cloudy` count for transparency.
    """
    out = []
    for r in rows:
        if r["aoi"] != aoi:
            continue
        if not r["flag_v4"]:
            continue
        if r["no_usable"]:  # defensive — apply script forces flag_v4=False on these
            continue
        if r["scene_date"] is None or r["ndvi"] is None:
            continue
        out.append(r)
    return out


def neighbor_pool(rows, aoi):
    """V4-unflagged, cloud-clean, usable rows in this AOI with NDVI present."""
    out = []
    for r in rows:
        if r["aoi"] != aoi:
            continue
        if r["flag_v4"]:
            continue
        if r["cloud_flag"]:
            continue
        if r["no_usable"]:
            continue
        if r["scene_date"] is None or r["ndvi"] is None:
            continue
        out.append(r)
    return out


def find_nearest(fired, candidates, max_days=WINDOW_DAYS):
    """Return (neighbor_row, signed_dt_days) or (None, None).

    Sort key: (abs_dt, neighbor_date_asc). EARLIER neighbor wins ties.
    """
    eligible = []
    for c in candidates:
        dt = (c["scene_date"] - fired["scene_date"]).days
        abs_dt = abs(dt)
        if abs_dt > max_days:
            continue
        eligible.append((abs_dt, c["scene_date"], c))
    if not eligible:
        return None, None
    eligible.sort(key=lambda x: (x[0], x[1]))
    _, _, n = eligible[0]
    dt_signed = (n["scene_date"] - fired["scene_date"]).days
    return n, dt_signed


def bootstrap_ci(deltas, n_boot=N_BOOT, seed=BOOT_SEED):
    """Return (mean, ci_lo, ci_hi). Mean is sample mean (point estimate);
    ci is from bootstrap resampling of pairs with replacement.

    Empty deltas → (nan, nan, nan).
    """
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
    ci_lo = float(np.percentile(boot_means, 2.5))
    ci_hi = float(np.percentile(boot_means, 97.5))
    return mean, ci_lo, ci_hi


def signal_class_of(mean, ci_lo, ci_hi):
    if math.isnan(mean) or math.isnan(ci_lo) or math.isnan(ci_hi):
        return "wide_inconclusive"
    halfwidth = (ci_hi - ci_lo) / 2.0
    excludes_zero = (ci_lo > 0) or (ci_hi < 0)
    if excludes_zero and mean < 0:
        return "signal_negative"
    if excludes_zero and mean > 0:
        return "signal_positive"
    if (not excludes_zero) and halfwidth < TIGHT_NULL_HALFWIDTH:
        return "tight_null"
    return "wide_inconclusive"


def write_bias_csv(pairs):
    fields = ["aoi", "fired_date", "fired_ndvi", "fired_v4",
              "neighbor_date", "neighbor_ndvi", "neighbor_v4",
              "delta_ndvi", "dt_days"]
    with open(OUT_BIAS, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for p in pairs:
            w.writerow({
                "aoi": p["aoi"],
                "fired_date": p["fired"]["scene_date"].isoformat(),
                "fired_ndvi": f"{p['fired']['ndvi']:.6f}",
                "fired_v4": "True",
                "neighbor_date": p["neighbor"]["scene_date"].isoformat(),
                "neighbor_ndvi": f"{p['neighbor']['ndvi']:.6f}",
                "neighbor_v4": "False",
                "delta_ndvi": f"{p['delta']:.6f}",
                "dt_days": p["dt_days"],
            })


def write_audit_csv(audit):
    fields = ["aoi", "n_fired_total", "n_paired", "n_unpairable",
              "retention_pct", "mean_delta",
              "ci_lo_95", "ci_hi_95", "ci_halfwidth", "signal_class"]
    with open(OUT_AUDIT, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for a in audit:
            row = {"aoi": a["aoi"],
                   "n_fired_total": a["n_fired_total"],
                   "n_paired": a["n_paired"],
                   "n_unpairable": a["n_unpairable"],
                   "retention_pct": f"{a['retention_pct']:.2f}",
                   "signal_class": a["signal_class"]}
            for k in ("mean_delta", "ci_lo_95", "ci_hi_95", "ci_halfwidth"):
                v = a[k]
                row[k] = "" if (v is None or
                                (isinstance(v, float) and math.isnan(v))) \
                    else f"{v:+.6f}"
            w.writerow(row)


def main():
    rows = load_joined()
    print(f"Joined rows: {len(rows)}")
    n_with_ndvi = sum(1 for r in rows if r["ndvi"] is not None)
    print(f"  with NDVI present: {n_with_ndvi}")
    print()

    pairs = []
    audit = []

    for aoi in AOIS:
        fired = fired_pool(rows, aoi)
        neighbors = neighbor_pool(rows, aoi)
        # n_fired_total here counts V4=True rows that are usable + have NDVI;
        # apply script forces flag_v4=False on no_usable rows so the only
        # exclusion above the V4 column is "missing NDVI."
        n_fired_total_raw = sum(1 for r in rows
                                if r["aoi"] == aoi and r["flag_v4"])
        n_fired_total = len(fired)
        n_fired_no_ndvi = n_fired_total_raw - n_fired_total
        if n_fired_no_ndvi:
            print(f"WARN: {aoi} has {n_fired_no_ndvi} fired row(s) without "
                  f"NDVI — excluded from pairing")

        print(f"AOI: {aoi}")
        print(f"  fired_with_ndvi : {n_fired_total}")
        print(f"  neighbor pool   : {len(neighbors)}")

        aoi_pairs = []
        n_unpairable = 0
        for fr in sorted(fired, key=lambda r: r["scene_date"]):
            nbr, dt = find_nearest(fr, neighbors)
            if nbr is None:
                n_unpairable += 1
                print(f"  UNPAIRABLE: {fr['scene_date']} (no neighbor "
                      f"within ±{WINDOW_DAYS}d)")
                continue
            delta = fr["ndvi"] - nbr["ndvi"]
            aoi_pairs.append({
                "aoi": aoi,
                "fired": fr,
                "neighbor": nbr,
                "delta": delta,
                "dt_days": dt,
            })
        n_paired = len(aoi_pairs)
        retention_pct = (100.0 * n_paired / n_fired_total) if n_fired_total else 0.0
        print(f"  paired          : {n_paired} / {n_fired_total} "
              f"({retention_pct:.1f}%)")
        print(f"  unpairable      : {n_unpairable}")

        deltas = [p["delta"] for p in aoi_pairs]
        mean, ci_lo, ci_hi = bootstrap_ci(deltas)
        if not math.isnan(ci_lo):
            ci_halfwidth = (ci_hi - ci_lo) / 2.0
        else:
            ci_halfwidth = float("nan")
        sig = signal_class_of(mean, ci_lo, ci_hi)

        print(f"  mean Δ NDVI     : {mean:+.6f}" if not math.isnan(mean)
              else "  mean Δ NDVI     : NaN")
        print(f"  95% CI          : [{ci_lo:+.6f}, {ci_hi:+.6f}] "
              f"halfwidth={ci_halfwidth:.6f}" if not math.isnan(ci_lo)
              else "  95% CI          : (insufficient data)")
        print(f"  signal_class    : {sig}")
        print()

        pairs.extend(aoi_pairs)
        audit.append({
            "aoi": aoi,
            "n_fired_total": n_fired_total,
            "n_paired": n_paired,
            "n_unpairable": n_unpairable,
            "retention_pct": retention_pct,
            "mean_delta": mean,
            "ci_lo_95": ci_lo,
            "ci_hi_95": ci_hi,
            "ci_halfwidth": ci_halfwidth,
            "signal_class": sig,
        })

    write_bias_csv(pairs)
    write_audit_csv(audit)
    print(f"Wrote {OUT_BIAS}  ({len(pairs)} pair rows)")
    print(f"Wrote {OUT_AUDIT} ({len(audit)} AOI rows)")
    print()
    print("Per-AOI summary:")
    print(f"{'aoi':<22s} {'n_fired':>7s} {'n_paired':>8s} {'ret%':>6s} "
          f"{'mean_Δ':>10s} {'ci_lo':>10s} {'ci_hi':>10s} {'class':<22s}")
    for a in audit:
        print(f"{a['aoi']:<22s} {a['n_fired_total']:>7d} "
              f"{a['n_paired']:>8d} {a['retention_pct']:>6.1f} "
              f"{a['mean_delta']:>+10.4f} {a['ci_lo_95']:>+10.4f} "
              f"{a['ci_hi_95']:>+10.4f} {a['signal_class']:<22s}")


if __name__ == "__main__":
    main()

"""
SA4 — L30 coverage probe (pre-registered halt mechanism, §SA4).

Pure date math over SA1 CSVs already on disk. No EE, no Sentinel Hub.
Sub-minute runtime. This is the SA4 halt-floor probe per pre-reg, not a
separate sub-question — runs without sa4_implementation.md because the
halt mechanism itself is fully specified at pre-reg level.

Probe spec
----------
Per AOI:
  denominator = count of S30 scenes with cloud_fraction < 0.10
  numerator   = count of those S30 dates that have at least one L30 scene
                (cloud_fraction < 0.10) within +/- 1 day
  coverage    = numerator / denominator
  halt        = coverage < 0.50  (pre-reg §SA4 50% L30 coverage floor)

Cloud filter parity: SA1 strict 0.10. Any SA4 regression downstream would
consume cf<0.10 scenes (label-quality parity with SA1 bare_epoch_flag).
SA4 NDVI compute, if it happens, would inherit the same filter.

Tie-breaking on multiple L30 within +/- 1 day is irrelevant to the probe:
we count S30 dates with at-least-one match, not pair uniqueness. Pair
construction is an SA4 implementation question, not a halt question.

Outputs
-------
  data/sa4_coverage_probe/coverage_summary.csv
    aoi, s30_total_unfiltered, s30_cf_filtered, l30_cf_filtered,
    paired_within_1d, coverage_rate, halt_status
  data/halts/sa4_coverage/{aoi}.md
    Per-AOI receipt (parity with sa2_variance/ format). Even AOIs that
    CLEAR get a receipt for grep parity; the file frames cleared vs halted.
"""

from __future__ import annotations

import csv
import datetime as dt
import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
SA1_DIR = REPO_ROOT / "research/construction-substrate-by-site/data/sa1_bsi_baseline"
OUT_DATA_DIR = REPO_ROOT / "research/construction-substrate-by-site/data/sa4_coverage_probe"
OUT_HALT_DIR = REPO_ROOT / "research/construction-substrate-by-site/data/halts/sa4_coverage"

CLOUD_MAX = 0.10
PAIR_DAYS = 1
HALT_FLOOR = 0.50

AOIS = [
    ("qiddiya", "Qiddiya"),
    ("ksp", "King Salman Park"),
    ("diriyah", "Diriyah Gate"),
]


def load_dates(csv_path: Path) -> tuple[int, set[dt.date]]:
    """Return (total scene rows, set of unique cf<0.10 scene dates)."""
    total = 0
    kept: set[dt.date] = set()
    with open(csv_path, newline="") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            total += 1
            cf_raw = row.get("cloud_fraction", "")
            if cf_raw == "" or cf_raw is None:
                continue
            try:
                cf = float(cf_raw)
            except ValueError:
                continue
            if cf >= CLOUD_MAX:
                continue
            try:
                d = dt.date.fromisoformat(row["scene_date"])
            except (KeyError, ValueError):
                continue
            kept.add(d)
    return total, kept


def coverage_rate(s30_dates: set[dt.date], l30_dates: set[dt.date]) -> tuple[int, float]:
    if not s30_dates:
        return 0, 0.0
    paired = 0
    for s in s30_dates:
        for offset in range(-PAIR_DAYS, PAIR_DAYS + 1):
            if (s + dt.timedelta(days=offset)) in l30_dates:
                paired += 1
                break
    return paired, paired / len(s30_dates)


def write_halt_receipt(
    out_path: Path,
    aoi_label: str,
    s30_filtered: int,
    l30_filtered: int,
    paired: int,
    rate: float,
    halted: bool,
) -> None:
    decision = "HALT" if halted else "CLEAR"
    relation = "<" if halted else ">="
    if halted:
        downstream = (
            "L30+S30 paired-design SA4 cannot proceed at this AOI under the "
            "pre-registered +/- 1-day pairing rule. SA4C (native L30 pair "
            "construction without S30 +/- 1-day requirement) is pre-scoped "
            "but does NOT auto-invoke; it requires its own pre-registration "
            "before execution per pre-reg §SA4 and locked decisions in "
            "CLAUDE.md. SA4 ships this halt receipt and the AOI does not "
            "contribute a divergence-by-stratum result."
        )
    else:
        downstream = (
            "AOI cleared the L30 coverage floor. SA4 paired-design analysis "
            "(per-pair Δ(NDVI_S30) vs Δ(NDVI_L30), stratified by SA1 "
            "bare_epoch_flag per Amendment 01) can proceed at this AOI once "
            "sa4_implementation.md locks the under-specified items "
            "(Δ definition, L30 NDVI compute pipeline, bootstrap target, "
            "pairing tie-breaking)."
        )
    body = f"""# SA4 coverage probe -- {aoi_label} ({decision})

**Pre-registered halt rule (piece A §SA4):** at least 50% of cloud-filtered S30 scene dates per AOI must have a cloud-filtered L30 scene within +/- 1 day. AOIs below the floor halt the SA4 paired design at that site; SA4C (native L30 pairing) is pre-scoped but requires its own pre-registration before execution.

## Numbers

- AOI: {aoi_label}
- S30 scenes (cloud_fraction < {CLOUD_MAX:.2f}): {s30_filtered}
- L30 scenes (cloud_fraction < {CLOUD_MAX:.2f}): {l30_filtered}
- S30 dates with >= 1 L30 within +/- {PAIR_DAYS} day: {paired}
- Coverage rate (paired / S30 cf-filtered): {rate:.4f}
- Halt threshold: {HALT_FLOOR:.2f}
- Decision: {decision} (rate {relation} threshold)

## Effect on outputs

{downstream}

## Why a halt and not a workaround

Per piece B stop-rule philosophy carried into piece A: when a halt fires, the cheapest possible scope review is the one happening mid-run. Switching to native L30 pairing post-hoc (without re-registering it as SA4C) would conflate "this AOI doesn't have S30+L30 cadence overlap" with "we should answer a different question." The halt is the finding. The cross-sensor coverage gap at +/- 1 day is itself diagnostic information about HLS scheduling at MGRS tile 38RPN.
"""
    out_path.write_text(body)


def main() -> None:
    OUT_DATA_DIR.mkdir(parents=True, exist_ok=True)
    OUT_HALT_DIR.mkdir(parents=True, exist_ok=True)

    summary_path = OUT_DATA_DIR / "coverage_summary.csv"
    rows = []
    for slug, label in AOIS:
        s30_csv = SA1_DIR / f"{slug}_s30_bsi_per_scene.csv"
        l30_csv = SA1_DIR / f"{slug}_l30_bsi_per_scene.csv"
        s30_total, s30_dates = load_dates(s30_csv)
        l30_total, l30_dates = load_dates(l30_csv)
        paired, rate = coverage_rate(s30_dates, l30_dates)
        halted = rate < HALT_FLOOR
        status = "HALT" if halted else "CLEAR"
        rows.append({
            "aoi": slug,
            "s30_total_unfiltered": s30_total,
            "s30_cf_filtered": len(s30_dates),
            "l30_cf_filtered": len(l30_dates),
            "paired_within_1d": paired,
            "coverage_rate": f"{rate:.4f}",
            "halt_status": status,
        })
        receipt_path = OUT_HALT_DIR / f"{slug}.md"
        write_halt_receipt(
            receipt_path,
            label,
            s30_filtered=len(s30_dates),
            l30_filtered=len(l30_dates),
            paired=paired,
            rate=rate,
            halted=halted,
        )
        print(
            f"{label:20s}  S30 cf<{CLOUD_MAX} = {len(s30_dates):4d}  "
            f"L30 cf<{CLOUD_MAX} = {len(l30_dates):4d}  "
            f"paired = {paired:4d}  rate = {rate:.4f}  -> {status}"
        )

    tmp_path = summary_path.with_suffix(".csv.tmp")
    with open(tmp_path, "w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    os.replace(tmp_path, summary_path)
    print(f"\nWrote {summary_path}")
    print(f"Wrote per-AOI receipts under {OUT_HALT_DIR}")


if __name__ == "__main__":
    main()

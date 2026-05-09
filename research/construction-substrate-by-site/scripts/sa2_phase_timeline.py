"""
SA2 — Construction-phase timeline from BSI quartile breaks.

Per-AOI: pool cloud-filtered (cloud_fraction < 0.10) S30 + L30 BSI from
SA1 outputs across the 76-month DBB-operational window. Compute Q1, Q2,
Q3 mechanically. Assign phases 1..4 by quartile. Cross-reference phase
labels against piece B SQ2's DBB-operational fire flag (flag_v4)
aggregated by (AOI, year-month).

Halt rule (pre-registered): per-AOI cloud-filtered BSI variance < 0.005
=> site is not phase-structured. All cloud-filtered scenes flagged
"halted" in that AOI's CSV; halt receipt under data/halts/sa2_variance/.

Inputs
------
SA1 CSVs (6 files; commit 38d1fc3 schema, one per AOI x sensor):
  data/sa1_bsi_baseline/{qiddiya,ksp,diriyah}_{s30,l30}_bsi_per_scene.csv

Piece B SQ2 DBB-operational table (per AOI x year x month):
  research/dust-honesty/data/operational/dbb_operational_sq2.csv

Outputs
-------
data/sa2_phase_timeline/{qiddiya,ksp,diriyah}_phase_assignments.csv
data/sa2_phase_timeline/SA2_summary.md
data/halts/sa2_variance/{aoi}.md   (only if halt fires)

Notes
-----
- SA1's 75th-percentile bare-epoch cut is the same threshold as SA2's
  Q3. SA2 just resolves the lower tail (Q1, Q2) too — the upper-tail
  flag from SA1 is preserved by construction.
- Pooling S30 + L30 follows SA1's locked decision (B8A vs L30 OLI 5
  spectrally matched). Documented in SA1_summary.md band-choice
  rationale.
- Cloud filter < 0.10 inherits SA1's strict label-quality cut. The
  pre-reg's SA3 cloud-filter (< 0.30) is for the regression downstream;
  SA2 is label-producing (phase labels), so the strict cut applies here.
- Non-cloud-filtered rows and rows with NaN BSI are dropped from the
  output CSV. The per-AOI CSV contains only scenes with assigned
  phases (or "halted" for halted AOIs).

Run
---
$ /opt/anaconda3/envs/sarsat/bin/python \\
    research/construction-substrate-by-site/scripts/sa2_phase_timeline.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]

PIECE_DIR = ROOT / "research/construction-substrate-by-site"
DATA = PIECE_DIR / "data"
SA1_DIR = DATA / "sa1_bsi_baseline"
OUT_DIR = DATA / "sa2_phase_timeline"
HALT_DIR = DATA / "halts/sa2_variance"

PIECE_B_DBB = ROOT / "research/dust-honesty/data/operational/dbb_operational_sq2.csv"

CLOUD_FILTER = 0.10
HALT_VARIANCE = 0.005

# (sa1 stem, sa2 output stem, dbb-operational aoi key, display name)
AOIS = [
    ("qiddiya", "qiddiya", "qiddiya_core", "Qiddiya"),
    ("ksp", "ksp", "king_salman_park", "King Salman Park"),
    ("diriyah", "diriyah", "diriyah_gate", "Diriyah Gate"),
]


def load_pooled(sa1_stem: str) -> pd.DataFrame:
    """Concat S30 + L30 SA1 outputs for one AOI; return all rows."""
    s30 = pd.read_csv(SA1_DIR / f"{sa1_stem}_s30_bsi_per_scene.csv")
    l30 = pd.read_csv(SA1_DIR / f"{sa1_stem}_l30_bsi_per_scene.csv")
    df = pd.concat([s30, l30], ignore_index=True)
    return df


def cloud_filtered_view(df: pd.DataFrame) -> pd.DataFrame:
    """Drop rows with NaN BSI or cloud_fraction >= CLOUD_FILTER."""
    out = df.dropna(subset=["bsi", "cloud_fraction"]).copy()
    out = out[out["cloud_fraction"] < CLOUD_FILTER]
    return out


def assign_phase(bsi: float, q1: float, q2: float, q3: float) -> int:
    """Quartile -> phase. BSI ascending = vegetation -> bare earth."""
    if bsi <= q1:
        return 1   # landscaped / vegetated
    if bsi <= q2:
        return 2   # partial vegetation
    if bsi <= q3:
        return 3   # active fill / grading
    return 4       # bare earthworks


def write_halt_receipt(aoi_name: str, sa2_stem: str, var_bsi: float,
                       n_cloudfilt: int) -> None:
    HALT_DIR.mkdir(parents=True, exist_ok=True)
    path = HALT_DIR / f"{sa2_stem}.md"
    lines = [
        f"# SA2 halt -- {aoi_name} (var(BSI) < {HALT_VARIANCE})",
        "",
        "**Pre-registered halt rule (piece A SA2):** if per-AOI BSI "
        f"variance over the 76-month window (cloud-filtered, pooled "
        f"S30+L30) falls below {HALT_VARIANCE}, the site is not "
        "phase-structured. Surface as finding (expected for Diriyah, "
        "informative if KSP), continue site into SA3+ as control "
        "rather than test.",
        "",
        "## Numbers",
        "",
        f"- AOI: {aoi_name}",
        f"- Cloud-filtered scene count (cf < {CLOUD_FILTER}, pooled "
        f"S30+L30): {n_cloudfilt}",
        f"- BSI variance: {var_bsi:.6f}",
        f"- Halt threshold: {HALT_VARIANCE}",
        f"- Decision: HALT (var < threshold)",
        "",
        "## Effect on outputs",
        "",
        f"- All cloud-filtered scenes for {aoi_name} are flagged "
        '`phase = "halted"` in the per-AOI CSV.',
        "- The per-AOI CSV still ships (does not block SA3+).",
        "- Quartile breakpoints not computed — there is no real phase "
        "structure to recover.",
        "",
        "## Why a halt and not a workaround",
        "",
        "Per piece B stop-rule philosophy carried into piece A: when a "
        "halt fires, the cheapest possible scope review is the one "
        "happening mid-run. Tightening the variance threshold or "
        "switching to a different phase-recovery method post-hoc would "
        "conflate \"this site doesn't have phases\" with \"this method "
        "doesn't see phases.\" The halt is the finding.",
        "",
    ]
    path.write_text("\n".join(lines))
    print(f"  halt receipt: {path}")


def cross_tab_phase_vs_dbb(cf: pd.DataFrame, dbb_aoi: pd.DataFrame
                           ) -> pd.DataFrame:
    """Match cf rows to DBB rows by (year-month) and tabulate
    (phase, n, n_with_dbb, fire_rate)."""
    cf = cf.copy()
    cf["ym"] = cf["scene_date"].astype(str).str[:7]
    dbb_aoi = dbb_aoi.copy()
    dbb_aoi["ym"] = (
        dbb_aoi["year"].astype(int).astype(str).str.zfill(4)
        + "-"
        + dbb_aoi["month"].astype(int).astype(str).str.zfill(2)
    )
    dbb_aoi["flag_v4_bool"] = (
        dbb_aoi["flag_v4"].astype(str).str.strip().str.lower() == "true"
    )
    # When piece B couldn't get a usable scene that month, flag_v4 is
    # NaN-ish; we keep those as missing in the cross-tab so fire_rate
    # reflects only months with usable DBB coverage.
    dbb_aoi.loc[dbb_aoi["no_usable_scene"].astype(str).str.lower() == "true",
                "flag_v4_bool"] = pd.NA
    merged = cf.merge(
        dbb_aoi[["ym", "flag_v4_bool"]], on="ym", how="left"
    )

    rows = []
    for phase in (1, 2, 3, 4):
        sub = merged[merged["phase"] == phase]
        n = len(sub)
        n_with_dbb = sub["flag_v4_bool"].notna().sum()
        fire_rate = (
            float(sub["flag_v4_bool"].dropna().mean())
            if n_with_dbb > 0 else float("nan")
        )
        rows.append({
            "phase": phase, "n": n, "n_with_dbb": int(n_with_dbb),
            "fire_rate": fire_rate,
        })
    return pd.DataFrame(rows)


def main():
    sys.stdout.reconfigure(line_buffering=True)
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    print("SA2 -- BSI phase timeline + DBB cross-reference")
    print(f"  Cloud filter: cloud_fraction < {CLOUD_FILTER}")
    print(f"  Halt variance threshold: {HALT_VARIANCE}")
    print(f"  Inputs: {SA1_DIR}/")
    print(f"  Piece B DBB: {PIECE_B_DBB}")
    print()

    dbb_all = pd.read_csv(PIECE_B_DBB)

    summary_rows = []   # for the variance + quartile table
    phase_count_rows = []
    crosstab_blocks = []
    halts = []

    for sa1_stem, sa2_stem, dbb_aoi_key, name in AOIS:
        print(f"--- {name} ({sa2_stem}) ---")
        df = load_pooled(sa1_stem)
        n_total = len(df)
        cf = cloud_filtered_view(df)
        n_cf = len(cf)
        var_bsi = float(cf["bsi"].var(ddof=1)) if n_cf > 1 else float("nan")

        halted = (not np.isnan(var_bsi)) and var_bsi < HALT_VARIANCE
        if halted:
            print(f"  HALT: var(BSI) = {var_bsi:.6f} < {HALT_VARIANCE}")
            halts.append(sa2_stem)
            cf_out = cf.copy()
            cf_out["phase"] = "halted"
            q1 = q2 = q3 = float("nan")
            write_halt_receipt(name, sa2_stem, var_bsi, n_cf)
        else:
            q1, q2, q3 = (float(cf["bsi"].quantile(q))
                          for q in (0.25, 0.50, 0.75))
            cf_out = cf.copy()
            cf_out["phase"] = cf_out["bsi"].apply(
                lambda b: assign_phase(b, q1, q2, q3)
            )
            print(f"  n_cloud_filtered={n_cf}  var(BSI)={var_bsi:.6f}  "
                  f"Q1={q1:+.4f}  Q2={q2:+.4f}  Q3={q3:+.4f}")

        # Output CSV: scene_date, sensor, bsi, cloud_fraction, phase
        out_cols = ["scene_date", "sensor", "bsi", "cloud_fraction", "phase"]
        cf_out_sorted = cf_out.sort_values(["scene_date", "sensor"])[out_cols]
        out_path = OUT_DIR / f"{sa2_stem}_phase_assignments.csv"
        cf_out_sorted.to_csv(out_path, index=False)
        print(f"  wrote {out_path} ({len(cf_out_sorted)} rows)")

        # Phase counts
        if halted:
            phase_count_rows.append({
                "aoi": name, "phase": "halted", "n": n_cf,
            })
        else:
            for phase in (1, 2, 3, 4):
                phase_count_rows.append({
                    "aoi": name, "phase": str(phase),
                    "n": int((cf_out["phase"] == phase).sum()),
                })

        # DBB cross-tab (per-AOI), only if not halted
        if halted:
            crosstab_blocks.append((name, None))
        else:
            dbb_aoi = dbb_all[dbb_all["aoi"] == dbb_aoi_key].copy()
            ct = cross_tab_phase_vs_dbb(cf_out, dbb_aoi)
            crosstab_blocks.append((name, ct))

        summary_rows.append({
            "aoi": name, "n_total": n_total, "n_cloud_filtered": n_cf,
            "var_bsi": var_bsi, "Q1": q1, "Q2": q2, "Q3": q3,
            "halted": halted,
        })
        print()

    # SA2_summary.md
    write_summary(summary_rows, phase_count_rows, crosstab_blocks, halts)
    print("SA2 done.")


def write_summary(summary_rows, phase_count_rows, crosstab_blocks, halts):
    path = OUT_DIR / "SA2_summary.md"
    lines = [
        "# SA2 -- BSI phase timeline summary",
        "",
        "**Goal:** map each AOI into construction phases (bare "
        "earthworks, active fill/grading, partial vegetation, "
        "landscaped) using BSI quartile breaks across the full "
        "76-month DBB-operational window. Cross-reference against "
        "piece B SQ2's DBB-operational fire flag to confirm the "
        "phase structure tracks an independent signal, not noise.",
        "",
        "## Pooling + cloud filter",
        "",
        "Per-AOI BSI is pooled across S30 and L30 within the AOI "
        "(SA1's locked decision: S30 B8A and L30 OLI Band 5 are "
        "spectrally matched at ~865nm, so cross-sensor BSI is "
        "comparable). Cloud filter inherits SA1's strict cut "
        f"(cloud_fraction < {CLOUD_FILTER}); rows with NaN BSI or "
        "fully cloudy scenes are dropped before quartile computation.",
        "",
        "Note: SA1's 75th-percentile bare-epoch threshold and SA2's "
        "Q3 are the same value by construction (both computed on the "
        "same cloud-filtered pooled distribution). SA2 just resolves "
        "the lower tail (Q1, Q2) on top.",
        "",
        "## Per-AOI scene counts, variance, quartile breakpoints",
        "",
        "| AOI | n total | n cloud-filtered | var(BSI) | Q1 | Q2 (median) | Q3 | halt? |",
        "|-----|--------:|-----------------:|---------:|---:|------------:|---:|:-----:|",
    ]
    for r in summary_rows:
        var_disp = (f"{r['var_bsi']:.6f}" if not np.isnan(r["var_bsi"])
                    else "n/a")
        if r["halted"]:
            q_disp = ["n/a", "n/a", "n/a"]
        else:
            q_disp = [f"{r['Q1']:+.4f}", f"{r['Q2']:+.4f}", f"{r['Q3']:+.4f}"]
        lines.append(
            f"| {r['aoi']} | {r['n_total']} | {r['n_cloud_filtered']} | "
            f"{var_disp} | {q_disp[0]} | {q_disp[1]} | {q_disp[2]} | "
            f"{'**HALT**' if r['halted'] else 'no'} |"
        )

    lines += [
        "",
        f"**Halt threshold:** var(BSI) < {HALT_VARIANCE}.",
        "",
    ]
    if halts:
        lines.append(f"**Halt fired in:** {', '.join(halts)}. Halt "
                     "receipts under `data/halts/sa2_variance/`. "
                     "Halted AOIs ship `phase = \"halted\"` for all "
                     "cloud-filtered scenes; SA3+ continues with those "
                     "AOIs as controls per pre-reg.")
    else:
        lines.append("**Halt rule did not fire.** All AOIs have "
                     "phase-structured BSI distributions.")

    lines += [
        "",
        "## Per-AOI phase scene counts",
        "",
        "Phase semantics: 1 = landscaped / vegetated, 2 = partial "
        "vegetation, 3 = active fill / grading, 4 = bare earthworks. "
        "Quartile breaks are mechanical -- no visual inspection or "
        "manual tuning per pre-reg.",
        "",
        "| AOI | phase 1 | phase 2 | phase 3 | phase 4 | halted |",
        "|-----|--------:|--------:|--------:|--------:|-------:|",
    ]
    by_aoi = {}
    for r in phase_count_rows:
        by_aoi.setdefault(r["aoi"], {})[str(r["phase"])] = r["n"]
    for r in summary_rows:
        d = by_aoi.get(r["aoi"], {})
        lines.append(
            f"| {r['aoi']} | "
            f"{d.get('1', '-' if r['halted'] else 0)} | "
            f"{d.get('2', '-' if r['halted'] else 0)} | "
            f"{d.get('3', '-' if r['halted'] else 0)} | "
            f"{d.get('4', '-' if r['halted'] else 0)} | "
            f"{d.get('halted', '-')} |"
        )

    lines += [
        "",
        "## Per-AOI phase x DBB-fire-rate cross-tab",
        "",
        "Cross-reference: for each cloud-filtered scene, look up "
        "piece B SQ2's DBB-operational `flag_v4` (V4 fire) by "
        "(AOI, year-month). `fire_rate` = mean(flag_v4) within phase, "
        "computed only over months where piece B had a usable scene "
        "(`no_usable_scene = False`). The phase signal is real (not "
        "noise) if higher-BSI phases (3, 4) carry materially higher "
        "fire rates than lower phases (1, 2).",
        "",
    ]
    for name, ct in crosstab_blocks:
        lines.append(f"### {name}")
        lines.append("")
        if ct is None:
            lines.append("Halted -- no quartile breakpoints to cross-tab.")
            lines.append("")
            continue
        lines.append("| phase | n scenes | n with DBB flag | fire rate |")
        lines.append("|------:|---------:|----------------:|----------:|")
        for _, row in ct.iterrows():
            fr = row["fire_rate"]
            fr_disp = f"{fr:.3f}" if not np.isnan(fr) else "n/a"
            lines.append(
                f"| {int(row['phase'])} | {int(row['n'])} | "
                f"{int(row['n_with_dbb'])} | {fr_disp} |"
            )
        lines.append("")

    # Interpretation paragraph (data-driven, generated from crosstabs)
    lines += [
        "## Interpretation",
        "",
        _interpretation_paragraph(crosstab_blocks, halts),
        "",
        "## Outputs",
        "",
        "- `data/sa2_phase_timeline/qiddiya_phase_assignments.csv`",
        "- `data/sa2_phase_timeline/ksp_phase_assignments.csv`",
        "- `data/sa2_phase_timeline/diriyah_phase_assignments.csv`",
        "- `data/sa2_phase_timeline/SA2_summary.md` (this file)",
    ]
    if halts:
        lines.append("- `data/halts/sa2_variance/{aoi}.md` "
                     "(one per halted AOI)")
    lines.append("")
    lines.append("CSV schema: `scene_date, sensor, bsi, cloud_fraction, "
                 "phase`. Phase values: `1`, `2`, `3`, `4`, or `halted`.")
    lines.append("")

    path.write_text("\n".join(lines))
    print(f"wrote {path}")


def _interpretation_paragraph(crosstab_blocks, halts) -> str:
    """One-paragraph data-driven read of the phase x fire-rate signal.
    Pre-reg-style: do phases 3+4 carry higher fire rate than 1+2 within
    each AOI? No overclaim. Flag halts."""
    bits = []
    for name, ct in crosstab_blocks:
        if ct is None:
            bits.append(
                f"{name} is halted on the variance rule; no phase "
                "signal to cross-check there."
            )
            continue
        # mean fire rate phases 1+2 vs 3+4, weighted by n_with_dbb
        low = ct[ct["phase"].isin([1, 2])]
        high = ct[ct["phase"].isin([3, 4])]
        low_n = int(low["n_with_dbb"].sum())
        high_n = int(high["n_with_dbb"].sum())
        if low_n == 0 or high_n == 0:
            bits.append(
                f"{name}: insufficient overlap with piece B usable-"
                "scene months for a meaningful fire-rate aggregation."
            )
            continue
        low_fr = (low["fire_rate"] * low["n_with_dbb"]).sum() / low_n
        high_fr = (high["fire_rate"] * high["n_with_dbb"]).sum() / high_n
        delta = high_fr - low_fr
        if delta > 0.05:
            verdict = ("higher-BSI phases carry a materially higher "
                       "fire rate, consistent with phase structure "
                       "tracking an independent signal")
        elif delta > 0:
            verdict = ("higher-BSI phases carry a slightly higher "
                       "fire rate; the signal is in the predicted "
                       "direction but small")
        elif delta == 0:
            verdict = ("higher- and lower-BSI phases carry the same "
                       "fire rate; the cross-reference is silent on "
                       "phase structure here")
        else:
            verdict = ("higher-BSI phases carry a *lower* fire rate "
                       "than lower-BSI phases -- unexpected; flag as "
                       "caveat for SA3+")
        bits.append(
            f"{name}: phase 1+2 fire rate = {low_fr:.3f} "
            f"(n={low_n} months), phase 3+4 = {high_fr:.3f} "
            f"(n={high_n}), Δ = {delta:+.3f}. {verdict}."
        )

    if halts:
        bits.append(
            "Halts ride into prose as findings per piece B stop-rule "
            "philosophy carried into piece A."
        )

    return " ".join(bits)


if __name__ == "__main__":
    main()

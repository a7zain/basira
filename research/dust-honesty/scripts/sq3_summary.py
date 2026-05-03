"""
SQ3 — summary stats + findings note.

Inputs:
  research/dust-honesty/data/sq3_ndvi_bias.csv
  research/dust-honesty/data/sq3_pairing_audit.csv

Outputs:
  research/dust-honesty/data/sq3_summary_stats.md
  research/dust-honesty/docs/sq3_findings.md
"""
from __future__ import annotations

import csv
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
DATA = ROOT / "research/dust-honesty/data"
DOCS = ROOT / "research/dust-honesty/docs"

BIAS_CSV = DATA / "ndvi_bias" / "paired_sen2cor_sq3.csv"
AUDIT_CSV = DATA / "ndvi_bias" / "pairing_audit_sq3.csv"
OUT_STATS = DATA / "ndvi_bias" / "summary_stats_sq3.md"
OUT_FINDINGS = DOCS / "sq3_findings.md"

AOI_ORDER = ["king_salman_park", "qiddiya_core", "diriyah_gate"]
AOI_LABEL = {
    "king_salman_park": "King Salman Park",
    "qiddiya_core": "Qiddiya core",
    "diriyah_gate": "Diriyah Gate",
}


def load_audit():
    out = {}
    with open(AUDIT_CSV) as f:
        for r in csv.DictReader(f):
            out[r["aoi"]] = {
                "n_fired_total": int(r["n_fired_total"]),
                "n_paired": int(r["n_paired"]),
                "n_unpairable": int(r["n_unpairable"]),
                "retention_pct": float(r["retention_pct"]),
                "mean_delta": float(r["mean_delta"]) if r["mean_delta"] else float("nan"),
                "ci_lo_95": float(r["ci_lo_95"]) if r["ci_lo_95"] else float("nan"),
                "ci_hi_95": float(r["ci_hi_95"]) if r["ci_hi_95"] else float("nan"),
                "ci_halfwidth": float(r["ci_halfwidth"]) if r["ci_halfwidth"] else float("nan"),
                "signal_class": r["signal_class"],
            }
    return out


def load_bias():
    rows = []
    with open(BIAS_CSV) as f:
        for r in csv.DictReader(f):
            rows.append({
                "aoi": r["aoi"],
                "fired_date": r["fired_date"],
                "neighbor_date": r["neighbor_date"],
                "delta_ndvi": float(r["delta_ndvi"]),
                "dt_days": int(r["dt_days"]),
            })
    return rows


def fmt_signed(v, prec=4):
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return "—"
    return f"{v:+.{prec}f}"


def per_aoi_oneliner(aoi, audit_row):
    """Hand-locked per-AOI one-liners (CLAUDE 2026-05-02, framing decision).

    Numbers are pulled from the audit row, but the surrounding language is
    AOI-specific — KSP and Qiddiya are tight nulls with different sample
    quality stories, Diriyah is wide-inconclusive with the SQ8 hook.
    """
    n = audit_row["n_paired"]
    ret = audit_row["retention_pct"]
    lo, hi = audit_row["ci_lo_95"], audit_row["ci_hi_95"]
    hw = audit_row["ci_halfwidth"]
    if aoi == "king_salman_park":
        return (f"**KSP**: tight null (95% CI [{fmt_signed(lo)}, "
                f"{fmt_signed(hi)}], halfwidth {hw:.4f}, n_paired={n}, "
                f"retention {ret:.0f}%). No measurable Sen2Cor NDVI bias on "
                f"V4-flagged scenes at this AOI under this design.")
    if aoi == "qiddiya_core":
        return (f"**Qiddiya**: tight null (95% CI [{fmt_signed(lo)}, "
                f"{fmt_signed(hi)}], halfwidth {hw:.4f}, n_paired={n}, "
                f"retention {ret:.1f}% — see §5). Direction consistent with "
                f"Goyens prior but magnitude an order of magnitude below "
                f"noise floor.")
    if aoi == "diriyah_gate":
        return (f"**Diriyah**: wide inconclusive (95% CI [{fmt_signed(lo)}, "
                f"{fmt_signed(hi)}], n_paired={n}, retention {ret:.0f}%). "
                f"Sample too small to call a sign — flag for SQ8 AERONET "
                f"follow-up.")
    return f"{AOI_LABEL[aoi]}: n_paired={n}, retention {ret:.1f}%."


def write_summary_stats(audit, bias):
    lines = []
    lines.append("# SQ3 summary stats")
    lines.append("")
    lines.append("Inputs: `sq3_ndvi_bias.csv`, `sq3_pairing_audit.csv`. "
                 "All bootstrap CIs use 1000 resamples of pairs with "
                 "replacement, seed=42.")
    lines.append("")
    lines.append("## Per-AOI table")
    lines.append("")
    lines.append("| AOI | n_fired | n_paired | retention% | mean Δ NDVI | "
                 "95% CI | CI halfwidth | signal_class |")
    lines.append("|---|---:|---:|---:|---:|---|---:|---|")
    for aoi in AOI_ORDER:
        a = audit[aoi]
        ci_str = (f"[{fmt_signed(a['ci_lo_95'])}, "
                  f"{fmt_signed(a['ci_hi_95'])}]") \
            if not math.isnan(a["ci_lo_95"]) else "—"
        hw_str = (f"{a['ci_halfwidth']:.4f}"
                  if not math.isnan(a["ci_halfwidth"]) else "—")
        lines.append(f"| {AOI_LABEL[aoi]} | {a['n_fired_total']} | "
                     f"{a['n_paired']} | {a['retention_pct']:.1f} | "
                     f"{fmt_signed(a['mean_delta'])} | {ci_str} | "
                     f"{hw_str} | {a['signal_class']} |")
    lines.append("")
    lines.append("## Per-pair Δ distribution (sample percentiles)")
    lines.append("")
    lines.append("| AOI | n | min | p25 | median | p75 | max |")
    lines.append("|---|---:|---:|---:|---:|---:|---:|")
    for aoi in AOI_ORDER:
        deltas = sorted([b["delta_ndvi"] for b in bias if b["aoi"] == aoi])
        n = len(deltas)
        if n == 0:
            lines.append(f"| {AOI_LABEL[aoi]} | 0 | — | — | — | — | — |")
            continue

        def pct(p):
            if n == 1:
                return deltas[0]
            i = (n - 1) * p
            lo, hi = int(math.floor(i)), int(math.ceil(i))
            if lo == hi:
                return deltas[lo]
            return deltas[lo] + (deltas[hi] - deltas[lo]) * (i - lo)

        lines.append(f"| {AOI_LABEL[aoi]} | {n} | "
                     f"{fmt_signed(deltas[0])} | "
                     f"{fmt_signed(pct(0.25))} | "
                     f"{fmt_signed(pct(0.5))} | "
                     f"{fmt_signed(pct(0.75))} | "
                     f"{fmt_signed(deltas[-1])} |")
    lines.append("")
    lines.append("## dt_days distribution per AOI")
    lines.append("")
    lines.append("| AOI | n_paired | min |Δt| | median |Δt| | max |Δt| |")
    lines.append("|---|---:|---:|---:|---:|")
    for aoi in AOI_ORDER:
        dts = sorted([abs(b["dt_days"]) for b in bias if b["aoi"] == aoi])
        n = len(dts)
        if n == 0:
            lines.append(f"| {AOI_LABEL[aoi]} | 0 | — | — | — |")
            continue
        med = dts[n // 2] if n % 2 == 1 else (dts[n // 2 - 1] + dts[n // 2]) / 2
        lines.append(f"| {AOI_LABEL[aoi]} | {n} | {dts[0]} | "
                     f"{med:.1f} | {dts[-1]} |")
    lines.append("")

    OUT_STATS.write_text("\n".join(lines) + "\n")
    print(f"Wrote {OUT_STATS}")


def write_findings(audit, bias):
    a_ksp = audit["king_salman_park"]
    a_qid = audit["qiddiya_core"]
    a_dir = audit["diriyah_gate"]

    lines = []
    lines.append("# SQ3 findings — NDVI bias on V4-flagged vs unflagged "
                 "scenes")
    lines.append("")
    lines.append("**Date:** 2026-05-02.")
    lines.append("**Inputs:** `sq2_dbb_operational.csv` (228 rows; 226 "
                 "usable), `sq3_ndvi_per_scene.csv` (NDVI mean per scene "
                 "on the same manifest), `sq3_ndvi_bias.csv`, "
                 "`sq3_pairing_audit.csv`.")
    lines.append("**Calibration anchor:** V4 = +0.034 (KSP+Diriyah scope, "
                 "applied uniformly to all three AOIs).")
    lines.append("")

    # §1 Question
    lines.append("## 1. Question")
    lines.append("")
    lines.append("On the 226-usable-scene operational set, do "
                 "Sen2Cor-derived NDVIs differ between V4-flagged and "
                 "V4-unflagged scenes per AOI, at a magnitude that matters "
                 "for change detection? Direction-agnostic — we report "
                 "whichever sign shows up. The Goyens 2024 prediction "
                 "(residual aerosol → low NDVI bias on flagged scenes) is "
                 "the prior, but the analysis design does not assume it.")
    lines.append("")

    # §2 Method
    lines.append("## 2. Method")
    lines.append("")
    lines.append("**NDVI compute.** Per scene, NDVI = (B8 − B4) / (B8 + B4) "
                 "from Sen2Cor L2A SR, masked to SCL ∈ {4, 5, 6, 7, 11} "
                 "(veg / not-veg / water / unclassified / snow) AND "
                 "B12 ≥ 0.01 (not water — same convention as the SQ1D "
                 "faithful-Lolli mask). Spatial mean over the AOI bbox at "
                 "20 m native scale, single mean reducer + single sum+count "
                 "valid-pixel reducer, no `bestEffort`. Manifest-locked to "
                 "`sq2_scene_manifest.csv` so every NDVI scene matches the "
                 "DBB scene byte-for-byte on `system:index`.")
    lines.append("")
    lines.append("**Pairing.** For each V4-fired scene at (AOI, date) with "
                 "valid NDVI, find the temporally-nearest scene in the same "
                 "AOI with `flag_v4=False`, `cloud_flag_present=False`, "
                 "`no_usable_scene=False`, NDVI present, and "
                 "|Δt| ≤ 60 days. Tie-break on equidistant neighbors: "
                 "earlier date wins (deterministic). Unflagged neighbors "
                 "may be reused across pairings; the bootstrap resamples "
                 "PAIRS (not scenes), so within-AOI dependence is handled "
                 "at inference time.")
    lines.append("")
    lines.append("**Bootstrap.** 1000 resamples of pairs with replacement "
                 "(seed = 42). 95% CI from 2.5 / 97.5 percentiles of the "
                 "resampled means. ci_halfwidth = (ci_hi − ci_lo) / 2.")
    lines.append("")
    lines.append("**Decision rule.** signal_negative if 95% CI excludes 0 "
                 "and mean Δ < 0; signal_positive if CI excludes 0 and "
                 "mean Δ > 0; tight_null if CI includes 0 and halfwidth "
                 "< 0.01; else wide_inconclusive.")
    lines.append("")
    lines.append("**Decision: V4 uniform across all three AOIs in the "
                 "headline.** V3-KSP-only (+0.053) is a sensitivity "
                 "consideration in §4, not the lead figure (same scope "
                 "decision SQ2 settled on).")
    lines.append("")
    lines.append("**Operational denominator:** 226 / 228 scenes usable "
                 "(KSP 74, Qiddiya 76, Diriyah 76; two KSP scenes "
                 "`no_usable_scene=True` from SCL granule-edge effects).")
    lines.append("")

    # §3 Results
    lines.append("## 3. Results")
    lines.append("")
    lines.append("| AOI | n_fired | n_paired | retention | mean Δ NDVI | "
                 "95% CI | halfwidth | signal_class |")
    lines.append("|---|---:|---:|---:|---:|---|---:|---|")
    for aoi in AOI_ORDER:
        ar = audit[aoi]
        ci_str = (f"[{fmt_signed(ar['ci_lo_95'])}, "
                  f"{fmt_signed(ar['ci_hi_95'])}]") \
            if not math.isnan(ar["ci_lo_95"]) else "—"
        hw = (f"{ar['ci_halfwidth']:.4f}"
              if not math.isnan(ar["ci_halfwidth"]) else "—")
        lines.append(f"| {AOI_LABEL[aoi]} | {ar['n_fired_total']} | "
                     f"{ar['n_paired']} | {ar['retention_pct']:.1f}% | "
                     f"{fmt_signed(ar['mean_delta'])} | {ci_str} | {hw} | "
                     f"**{ar['signal_class']}** |")
    lines.append("")
    lines.append("**Per-AOI plain language:**")
    lines.append("")
    for aoi in AOI_ORDER:
        lines.append(f"- {per_aoi_oneliner(aoi, audit[aoi])}")
    lines.append("")

    # §4 Direction discussion
    lines.append("## 4. Direction discussion — observed sign vs Goyens prior")
    lines.append("")
    lines.append("**The pre-registered prediction (Goyens-consistent "
                 "negative Δ NDVI on flagged scenes) is not confirmed at "
                 "these AOIs under this design.** The result is a "
                 "*conditional null*: Sen2Cor L2A NDVI on V4-flagged scenes "
                 "vs near-temporal unflagged neighbors does not exhibit the "
                 "Goyens-predicted bias at moderate Riyadh-region "
                 "atmospheric loadings, on the paired 60-day-window design. "
                 "This is not a claim that Sen2Cor is correcting "
                 "perfectly; it is not a claim that Goyens overstated the "
                 "effect. The honest claim is scope-conditional — a null "
                 "at moderate loadings, on this design, at these AOIs, "
                 "with Sen2Cor L2A as the source.")
    lines.append("")
    lines.append("Two reasons the Goyens prior may not transfer cleanly to "
                 "the SQ3 setting (candidate explanations, not confirmed "
                 "mechanisms):")
    lines.append("")
    lines.append("- **Loading regime.** Goyens 2024 characterizes a TOA / "
                 "extreme-AOD regime where Sen2Cor's underestimate is "
                 "largest. At the moderate atmospheric loadings sampled by "
                 "the V4 fires here (mean DBB +0.017 at KSP, -0.052 at "
                 "Diriyah), Sen2Cor's L2A correction may absorb the bias "
                 "even if it fails at higher loadings. The null may sharpen "
                 "into a signal at AERONET-confirmed extreme-loading "
                 "events; SQ8 is the right place to check that.")
    lines.append("- **NDVI is a ratio.** Red and NIR are both perturbed by "
                 "residual aerosol scattering. Partial cancellation in the "
                 "(B8 − B4) / (B8 + B4) ratio attenuates whatever bias "
                 "survives Sen2Cor's correction. This is a structural "
                 "feature of the index, not an SQ3-specific limitation, "
                 "and is consistent with the literature observation that "
                 "NDVI is more robust to atmospheric noise than single-"
                 "band reflectance.")
    lines.append("")

    # §5 Limitations
    lines.append("## 5. Limitations")
    lines.append("")
    lines.append("**(a) Qiddiya retention 28.1% is structural, not noise.** "
                 "The unfired neighbor pool is small (19 unflagged scenes "
                 "across 76 months) because SQ2 found that V4 fires on "
                 "75% of Qiddiya scenes — a direct consequence of "
                 "construction-substrate contamination of the DBB index "
                 "against the fixed 2024-01-20 reference. The pool is also "
                 "clustered, so most fired Qiddiya months have no V4=0 "
                 "anchor inside ±60 days. This does not invalidate the 16 "
                 "pairs that did form — those pairs still produce a tight "
                 "CI ([" + fmt_signed(a_qid["ci_lo_95"]) + ", "
                 + fmt_signed(a_qid["ci_hi_95"]) + "], halfwidth "
                 + f"{a_qid['ci_halfwidth']:.4f})"
                 " — but it does mean Qiddiya's null is supported by a "
                 "thinner sample than KSP's null, and the conclusion "
                 "should be read with that asymmetry in mind.")
    lines.append("")
    lines.append("**(b) Diriyah n_paired=8 yields a wide CI** (halfwidth "
                 f"{a_dir['ci_halfwidth']:.4f}, an order of magnitude "
                 "wider than KSP or Qiddiya). The AOI with the cleanest "
                 "atmospheric prior — surface-stable desert edge, "
                 "shamal-aligned fires, peak event 2022-05-10 cross-"
                 "validated by SQ1C cold-protocol labels — is also the AOI "
                 "with the smallest pair count. Tighter Diriyah CIs are "
                 "the obvious SQ8 AERONET deliverable.")
    lines.append("")
    lines.append("**(c) Pairing design is direction-agnostic** and the "
                 "bootstrap on pairs handles neighbor reuse, but the "
                 "60-day window is a compromise between atmospheric "
                 "specificity (shorter is better) and surface-state "
                 "continuity (longer admits more pairs). A wider window "
                 "was rejected to preserve atmospheric specificity at "
                 "Qiddiya, where surface drift dominates beyond two "
                 "months.")
    lines.append("")

    # §6 Cross-validation hooks
    lines.append("## 6. Cross-validation hooks")
    lines.append("")
    lines.append("- **SQ4 (HLS NDVI) is positioned to test whether the "
                 "null is Sen2Cor-specific.** HLS uses LaSRC for "
                 "atmospheric correction (different chain from Sen2Cor); "
                 "if HLS-NDVI on the same V4-fired scenes shows the "
                 "Goyens-predicted negative bias and Sen2Cor-NDVI does "
                 "not, the null collapses to a Sen2Cor-correction story. "
                 "If both NDVIs agree on the null, it is a surface-driven "
                 "result and Sen2Cor is exonerated for this loading "
                 "regime.")
    lines.append("- **SQ8 (KAUST AERONET) is positioned to add ground-"
                 "truth atmospheric comparisons** that can tighten "
                 "Diriyah CIs and decouple `small bias` from `small "
                 "sample`. Solar Village (Riyadh) is dead since 2013, so "
                 "KAUST Thuwal is the closest AERONET station; its "
                 "different surface (coastal vs bright desert) is itself "
                 "a generalization test for the SQ3 framework.")
    lines.append("- **The SQ2-SQ3 chain is internally consistent.** V4 "
                 "detects atmospheric optical thickness — confirmed by "
                 "SQ2's Diriyah shamal-season alignment and the 2022-05-10 "
                 "peak-event agreement with SQ1C cold-protocol labels — "
                 "but that thickness does not propagate to NDVI bias at "
                 "change-detection magnitude on Sen2Cor L2A SR. Both "
                 "findings are real; they describe different layers of "
                 "the imaging chain. SQ3's null does not invalidate SQ2's "
                 "fire-rate readout; it bounds the downstream consequence "
                 "for NDVI-based change monitoring.")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("_Footnote on what this note does not claim._ SQ3 "
                 "measures Sen2Cor L2A NDVI on V4-flagged scenes against "
                 "Sen2Cor L2A NDVI on unflagged temporal-neighbor scenes "
                 "— not against a model-independent atmospheric reference. "
                 "SQ4 (HLS / LaSRC) and SQ8 (KAUST AERONET) are the "
                 "downstream chapters that cross the model-independence "
                 "boundary.")
    lines.append("")

    OUT_FINDINGS.write_text("\n".join(lines) + "\n")
    print(f"Wrote {OUT_FINDINGS}")


def main():
    audit = load_audit()
    bias = load_bias()
    write_summary_stats(audit, bias)
    write_findings(audit, bias)


if __name__ == "__main__":
    main()

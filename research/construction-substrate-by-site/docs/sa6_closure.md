# SA6 Closure — Per-AOI Heterogeneity Discharged by SA3

**Status:** Locked closure. Not an amendment (no methodological substitution).
**Date:** 2026-05-10
**Cross-references:** pre-registration §SA6, sa3_implementation.md, commit a9a4f8e

## Rationale

Pre-registration §SA6 specifies: "Replicate SA1+SA3 at KSP and Diriyah using identical specs to produce per-AOI heterogeneity findings."

By the time of this closure, both inputs to SA6 already exist on disk:

- **SA1** ran at all three AOIs in this session (commits 38d1fc3, 092bb0e). KSP and Diriyah CSVs are the same shape and provenance as Qiddiya's.
- **SA3** ran with a per-AOI heterogeneity arm by design (sa3_implementation.md, locked 8468395). The heterogeneity arm produced regression results at KSP (halted on n=12) and Diriyah (β_bsi = -0.3767, 95% CI [-0.91, +0.15]).

The SA6 spec is content-identical to what SA3's heterogeneity arm already executed at non-Qiddiya AOIs. There is no remaining SA6 compute. Closure rather than amendment because no methodological substitution occurred — the work specified by SA6 was completed under SA3's dispatch.

## SA6 findings, by AOI

**KSP — halt receipt.** SA3 KSP arm halted on n=12 after NDVI⨝AOD inner join (pre-reg floor 20). Halt receipt at `data/halts/sa3_coverage/king_salman_park.md`. Discharges SA6 KSP. KSP halt drivers: KSP S30 cf<0.10 count = 49 (anomalously low for MGRS tile 38RPN), reduced further by AOD inner-join.

**Diriyah — inconclusive, opposite sign.** SA3 Diriyah arm: β_bsi = -0.3767, 95% CI [-0.91, +0.15], β × IQR = -0.0044. Does not pass dual criterion (CI crosses zero, magnitude below threshold). The negative point estimate is opposite-signed to Qiddiya's substrate_primary verdict. Mechanism note (carry to prose, not claim): Diriyah's substrate is plausibly post-construction landscaped surface, not active-construction churn — different surface physics, plausibly different BSI-NDVI coupling sign. Discharges SA6 Diriyah.

**Qiddiya — substrate_primary verdict.** SA3 Qiddiya arm: β_bsi = +0.6892, 95% CI [+0.34, +1.04], β × IQR = +0.0074. Passes dual criterion. Closes SA6 at Qiddiya (the heterogeneity arm at Qiddiya produced the same arithmetic that the SA3 headline reports).

## Status of SA6 sub-question

SA6 question: "Does the substrate-confound signal at Qiddiya replicate at KSP and Diriyah?"

Answer (from SA3 heterogeneity outputs, now relabeled as SA6 deliverable):
- KSP: not testable at the cell-count required by pre-reg.
- Diriyah: inconclusive, with opposite-signed point estimate consistent with mechanistic difference (post-construction vs active construction).
- Qiddiya: confirmed by dual criterion. Single-site result, not a generalization.

The piece A umbrella claim is correspondingly bounded: substrate-aware reasoning matters at active-construction Vision 2030 sites (Qiddiya). Whether it matters at post-construction or stalled-construction sites is not addressed by this work and is not claimed.

## Cumulative piece-A halt count

8 (SA2 ×3, SA3 ×1 KSP, SA4 ×3, SA5 ×1 Qiddiya). SA6 closure is not a halt — it documents work already discharged.

## Decisions locked by this closure

- No fresh SA6 dispatch. Engine work on piece A ends here.
- SA3's KSP halt receipt and Diriyah heterogeneity output are dual-purpose: they discharge both SA3 and SA6.
- Methods-memo prose carries the closure as a single short paragraph; does not require a dedicated SA6 chart or section.
- Multi-city expansion on `wip/phase5-multicity` remains parked (pre-reg out-of-scope).

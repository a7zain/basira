# Piece A — Prose Skeleton (Revised)

**Status:** Revised 2026-05-10 post-engine-close. Original locked 2026-05-05 at `18f5a76` (now superseded). Replaces original wholesale; original retained in git history.

## Why this revision

The original skeleton was written for a story that didn't happen. Six sub-questions executed; one substantive verdict (Qiddiya substrate_primary at SA3), eight halts (SA2 ×3, SA3 ×1 KSP, SA4 ×3, SA5 ×1 Qiddiya), one closure (SA6). The narrative compressed: less to claim, more independent corroboration of what we do claim.

Revision principles:
- Page budget 4–4.5 → 3–3.5 pages, hard cap 4. Halts compress in prose; receipts do the work.
- Halt-rides-into-prose table replaced with halt-locked mapping (which halt fired, where it lands).
- Site pieces re-scoped: Qiddiya 1500 words (substantive), KSP/Diriyah 400–500 words each (honest about non-findings).
- §3 (mechanism test) and §4 (cross-sensor halt + anchor-sparsity mechanism) carry the substantive load. §5 is a paragraph.

## Two-document structure (preserved)

Methods memo (3–3.5 pages, hard cap 4) + three site pieces (Qiddiya hero ~1500 words, KSP/Diriyah ~400–500 each, mirrored structure). Site pieces self-contained — a hiring reader landing cold on KSP leaves with the right takeaway in 400 words.

## Document 1: Technical Methods Memo

Length 3–3.5 pages. Hard cap 4.

- **§0 Problem framing (¼ p).** Vision 2030 surface change at desert-construction scale. S30 NDVI flags apparent vegetation gain at Qiddiya across 2020–2026 in a region receiving no new water. Question: real, atmospheric, or substrate? Piece B closed the atmospheric arm (NDVI-vs-AOD null). Piece A closes the substrate arm at Qiddiya. TPM-relevance frame: execution discipline visible in pre-registered halt receipts, not algorithmic novelty.

- **§1 Pre-registered design (¼ p).** Umbrella question verbatim. Six sub-questions, one line each. Halts as feature. Amendment 01 (SA2 halt substitution) and SA6 closure noted as in-scope methodological evolution under dated rules. Scope conditional: SA5's V4 + `bare_epoch_flag` framing — claim is "pipeline flags differently," not "this is real change." Bounded substantive verdict: single-AOI, active-construction sites only.

- **§2 Substrate signal at threshold level (½ p).** SA1 outputs. Per-AOI 75th-percentile BSI thresholds: Qiddiya +0.1834, KSP +0.1498, Diriyah +0.1432. Qiddiya threshold 28% higher than Diriyah's at the same percentile — substrate-confound signal visible at SA1 before any inferential test. SA2 triple-halt rides here as an anti-finding: phase structure not recoverable at AOI-bbox-mean (variance 0.0001 vs floor 0.005, ~50–96× below). Substrate signal exists at the threshold level but doesn't move temporally at this aggregation. Halt itself is the finding.

- **§3 Mechanism test — Qiddiya substrate_primary (1 p).** SA3 design: pooled-with-FE + per-AOI heterogeneity, by construction. Pooled inconclusive (β_bsi × IQR = +0.00131, dual criterion fails) — Diriyah cancels Qiddiya, exactly as the heterogeneity arm was designed to surface. Qiddiya per-AOI: β_bsi = +0.6892, 95% CI [+0.34, +1.04], β × IQR = +0.0074, **dual criterion fires substrate_primary**. Above piece B's SQ8 operational threshold of 0.005. **Two independent measurements** at Qiddiya now point the same direction: piece B's NDVI-vs-AOD null + SA3's NDVI-vs-BSI positive. Diriyah opposite-sign aside (β = -0.38, CI crosses zero) carried as mechanism hypothesis, not claim — post-construction landscaping plausibly different physics from active-construction churn. KSP n=12 halt noted; KSP discharged at SA6 closure.

- **§4 Cross-sensor halt + anchor-sparsity finding (½ p).** SA4 triple-halt on ±1-day L30 pairing floor (Qiddiya 16.4%, KSP 20.4%, Diriyah 18.8%; floor 50%). Side-finding worth one paragraph: HLS scheduling at MGRS 38RPN is structurally thin regardless of which sensor is denser — sensor-architecture diagnostic, not AOI-specific anomaly. SA5 Qiddiya halt at n=10 (V4 ∩ `bare_epoch_flag`, floor 15) carries the load-bearing mechanism prose: V4 ramp test fires on vegetation flush events, `bare_epoch_flag` fires on substrate-dominated scenes; at Qiddiya the substrate confound pushes apparent NDVI without piece B's V4 ramp test firing, so the joint distribution is sparse by construction. **The substrate signal ate the overlap** — third independent measurement at Qiddiya pointing the same direction.

- **§5 Closure and generalization (¼ p).** SA6 discharged by SA3 heterogeneity arm — KSP halt and Diriyah inconclusive opposite-sign both relabeled as SA6 outputs under closure. Bounded generalization: substrate verdict at Qiddiya holds; at KSP/Diriyah, untested or mechanistically distinct.

- **§6 What this can't claim (¼ p).** No external ground-truth label set. SA5 contamination labels are V4 + `bare_epoch_flag` (post-Amendment-01). Single-region single-cohort. SAR-optical fusion, substrate composition by mineralogy, multi-city expansion explicitly out of scope.

- **§7 Repo + reproducibility (¼ p).** GitHub URL, pre-reg commit hash + Amendment 01 hash + SA6 closure hash, sub-question commit hashes, halt receipts under `data/halts/` (gitignored, regenerated from locked HLS catalog snapshot). SA1 deterministic at ~7h; SA3+SA4+SA5 all sub-minute over SA1 outputs.

## Document 2: Three Site Pieces

### Qiddiya hero (~1500 words). Substantive site piece.

1. Site framing — Vision 2030 entertainment city, 2020 graded desert → 2026 active construction. Scale fact grounded in satellite data.
2. What the engine saw — apparent NDVI gain in a no-new-water region. The paradox piece B and piece A both opened on.
3. **Three independent measurements at Qiddiya** — piece B null on aerosol, SA3 substrate_primary, SA5 anchor sparsity ("substrate signal ate the overlap" mechanism prose lives here). The convergence is the verdict.
4. Halt receipts as evidence — SA1 BSI threshold 28% above Diriyah's at 75th percentile, SA2 variance halt, SA4 coverage halt, SA5 anchor halt. Pre-registered, dated, locked.
5. Operational implications — bounded claim, no over-reach. Substrate-aware reasoning matters at active-construction Vision 2030 sites; KSP/Diriyah explicitly not generalizable.
6. Methods footer — pre-reg hash, methods memo link, commit trail.

### KSP (~450 words). Honest-about-non-finding.

1. Site framing — King Salman Park, ~16km² central Riyadh urban park. Vision 2030 context.
2. What the engine saw first — anomalously low cloud-free S30 cadence (49 cf<0.10 vs Qiddiya's 128 and Diriyah's 282) on identical Sentinel cadence. First signal something was different.
3. Halt cascade — SA2 variance halt, SA3 n=12 halt after AOD inner-join, SA4 coverage halt at 20.4%, SA6 closure relabels SA3 KSP halt.
4. What didn't fire is the finding — substrate verdict in piece A is Qiddiya-loaded; KSP is a different problem (post-construction landscaped park ≠ active-construction churn) and the engine doesn't manufacture a verdict to fill space.
5. Methods footer.

### Diriyah Gate (~500 words). Honest-about-mechanism-hypothesis.

1. Site framing — Diriyah Gate heritage + entertainment district, Vision 2030 context.
2. What the engine saw — high cloud-free S30 cadence (282 cf<0.10), good baseline coverage. SA1 BSI threshold +0.1432, lowest of the three.
3. SA3 inconclusive opposite-sign — β_bsi = -0.3767, 95% CI [-0.91, +0.15], dual criterion does not fire. Mechanism hypothesis: post-construction landscaped surfaces present different BSI-NDVI coupling than Qiddiya's active-construction churn. Hypothesis, not claim.
4. SA2 + SA4 halts — coverage and variance both informative.
5. What this suggests — substrate-aware reasoning is site-stage-dependent. Active construction ≠ post-construction landscaping. Open question for follow-on work.
6. Methods footer.

## Halt-locked routing (replaces hypothetical table)

8 halts fired. Each pre-designated to a memo + site location:

| Halt | Rule fired | Memo location | Site-piece location |
|---|---|---|---|
| SA2 Qiddiya variance | var(BSI)=0.000099 < 0.005 | §2 (anti-finding) | Qiddiya §4 |
| SA2 KSP variance | var(BSI)=0.000052 < 0.005 | §2 (mention) | KSP §3 |
| SA2 Diriyah variance | var(BSI)=0.000055 < 0.005 | §2 (mention) | Diriyah §4 |
| SA3 KSP coverage | n=12 < 20 | §3 (mention) | KSP §3 |
| SA4 Qiddiya coverage | 16.4% < 50% | §4 (primary) | Qiddiya §4 |
| SA4 KSP coverage | 20.4% < 50% | §4 (HLS-thin diagnostic) | KSP §3 |
| SA4 Diriyah coverage | 18.8% < 50% | §4 (mention) | Diriyah §4 |
| SA5 Qiddiya anchors | n=10 < 15 | §4 (primary mechanism finding) | Qiddiya §3 |

SA6 closure (not a halt): §5 memo + each site piece footer.

## Open questions for draft-1 (preserved + tightened)

- **Voice/register single 200-word test on §0 before full memo draft.** Methods-memo voice is post-execution, halt-honest, dual-criterion-precise. Mismatch at §0 propagates to seven sections downstream. Lock register before proceeding.
- Figure list per section. Likely: SA1 BSI distribution per-AOI, SA3 per-AOI β_bsi caterpillar plot, SA4 coverage bar chart, SA5 anchor density at Qiddiya. Halt receipts ship as inset boxes, not dedicated figures.
- Word counts per section refined once §0 voice locks.

## Decisions locked by this revision

- §3 is the substantive section, 1 page, no expansion.
- §4 SA5 mechanism ("substrate signal ate the overlap") is primary, not caveat.
- KSP and Diriyah site pieces compressed to 400–500 words. Hiring readers see three pieces from the homepage; only Qiddiya carries substantive verdict.
- 8 halts + closure → memo IS the receipt. Page budget compresses accordingly.
- §0 voice test is gating: locks before full draft begins.

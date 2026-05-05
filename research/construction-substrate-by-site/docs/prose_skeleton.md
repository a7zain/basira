# Piece A — Prose Skeleton

**Status:** Locked 2026-05-05. Skeleton for the methods memo + three site-level research pieces. Resolves length budget, halt-prose routing, and section structure before sub-question execution lands prose.

## Two-document structure

Per pre-reg: one technical methods memo (3–5 pages, primary deliverable for the research-engine claim, SARsatX read) and three site-level research pieces (Qiddiya hero, KSP, Diriyah, supporting assets, primary deliverable for the get-noticed claim via the cinematic homepage).

Decision locked: site pieces are self-contained. A reader landing on the Qiddiya piece without reading the memo gets a complete artifact — site framing, methods sketch, results, caveats, methods-memo link in footer. Hiring readers don't follow links; each site piece is its own complete artifact.

## Document 1: Technical Methods Memo

Length target 4–4.5 pages at TPM-readable density. Hard cap 5.

- §0 Problem framing (½ p): Vision 2030 surface change at scale. S30-alone flags substrate as change. Question: does L30 + substrate index discriminate? Frame TPM-relevance as execution discipline, not algorithmic novelty.
- §1 Pre-registered design (½ p): umbrella question verbatim. Six sub-questions one-line each. Halt rules as feature. Scope conditional on SA5's V4+high-BSI label framing — acknowledged up front.
- §2 Substrate signal (1 p): SA1 BSI baselines + SA2 phase timeline + cross-reference vs piece B fire rates. SA2 halts ride here.
- §3 Mechanism test (1 p): SA3 pooled regression headline. Per-AOI heterogeneity. Dual criterion outcome. Qiddiya-loaded pattern reported as expected per pre-reg if it fires.
- §4 Cross-sensor + operational (1 p): SA4 + SA5. Halt-as-finding pattern carries from piece B. SA5 effect size + CI, null ships as null.
- §5 Generalization (½ p): SA6 three-AOI comparison. Pre-registered surprises reported primary if they fire.
- §6 What this can't claim (½ p): conditional on SA5 framing. No external ground-truth. Single-region single-cohort. SAR-optical, mineralogy, multi-city out of scope.
- §7 Repo + reproducibility (¼ p): URL, pre-reg hash, sub-question commit hashes, halt-receipt note.

## Document 2: Three Site-Level Research Pieces

Per-AOI structure (mirrored, ~1500 words Qiddiya hero, ~1000 KSP/Diriyah):

1. Site framing — Vision 2030 context, scale fact grounded in satellite data.
2. What the engine sees — SA2 phase timeline figure + piece B NDVI overlay, annotated.
3. Where substrate confounds — SA3 per-AOI β_bsi with CI + magnitude check.
4. What the substrate-aware pipeline does differently — SA5 at Qiddiya; SA6 generalization at KSP/Diriyah.
5. Caveats — site-specific halts, cloud-cadence gaps, pre-registered framing limits.
6. Methods footer — link to pre-reg, link to methods memo, commit hash.

Qiddiya is the hero: longest, most figure-heavy, lands first on the homepage. KSP and Diriyah are shorter and structured to read in parallel.

## Halt-rides-into-prose routing (locked)

Each halt has a pre-designated narrative location. Prevents post-execution scramble.

| Sub-question | Halt condition | Where it rides |
|---|---|---|
| SA1 | <5 bare-epoch scenes per AOI/sensor | Memo §2 + that AOI's site piece §2 |
| SA2 | BSI variance < 0.005 | Memo §2 + that AOI's site piece §2 |
| SA3 | Per-AOI n < 20 OR pooled n < 60 | Memo §3 (caveat) |
| SA4 | L30 coverage < 50% | Memo §4 (primary, halt-as-finding) |
| SA5 | V4-anchor cells < 15 at Qiddiya | Qiddiya piece §4 (primary) + memo §4 (caveat) |
| SA6 | L30 coverage < 40% at KSP/Diriyah | That AOI's site piece §5 + memo §5 |

If a halt fires somewhere unexpected, surface as primary finding in §3, not appendix.

## Open questions for execution time (not blockers)

- Word counts per memo section once SA results land — current allocation is byte-budget, not word-budget. Adjust at draft-1.
- Figure list per section — figures defined per sub-question output; figure→section mapping resolved at draft-1.
- Voice/register check needed at draft-1 of memo §0 — single 200-word test before committing to full draft.

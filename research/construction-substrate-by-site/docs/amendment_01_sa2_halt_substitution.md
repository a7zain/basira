# Amendment 01 — SA2 halt substitution (locked 2026-05-09)

## Trigger

SA2 triple halt at commit b838e9f. AOI-bbox-mean BSI variance fell 50–100× below the pre-registered 0.005 threshold at all three AOIs (Qiddiya 0.000099, KSP 0.000052, Diriyah 0.000055). Per SA2 halt rule, no quartile breakpoints computed. Phase structure not recoverable at AOI-bbox-mean spatial aggregation.

## Affected sub-questions

- SA4 §method: "Stratify by BSI quartile" requires SA2 quartiles.
- SA5 §method Pipeline B: "BSI is not in active-substrate-phase quartile (Q4 from SA2)" requires SA2 Q4.
- SA5 §method reference labels: "high-BSI (Q4 from SA2)" requires SA2 Q4.

SA3 unaffected (BSI is continuous regression covariate, not a phase label).
SA6 unaffected (re-runs SA1+SA3 at other sites; no phase dependency).

## Substitution

Replace "Q4 from SA2" with "bare_epoch_flag from SA1" in all SA4/SA5 references.

Justification: SA1's bare_epoch_flag is the per-AOI 75th-percentile BSI cut — mathematically the Q3/Q4 boundary of the same distribution SA2 attempted to subdivide further. SA2 added Q1/Q2/Q3 below the 75th-percentile line; SA2 halted on the lower three; the upper bound (75th-percentile = Q3 in quartile terms = "scenes in or above the top quartile" = Q4 stratum) is preserved verbatim by SA1's bare_epoch_flag column.

Pre-reg locked SA1 thresholds:
- Qiddiya: BSI ≥ +0.1834
- King Salman Park: BSI ≥ +0.1498
- Diriyah Gate: BSI ≥ +0.1432

Substitution is mechanical and content-equivalent for SA4 stratification (binary high-BSI vs not, instead of 4-bin quartile stratification — coarser but same direction) and content-identical for SA5 anchors and substrate mask (the same 75th-percentile cut SA2's Q4 would have produced).

## Loss

SA4 loses Q1/Q2/Q3 granularity in the stratified divergence test. The stratification becomes binary: bare_epoch_flag=True vs False. Reduces resolution of the divergence-by-stratum curve from 4 points to 2. Hypothesis preserved (substrate-dominated scenes diverge in S30 vs L30; non-substrate scenes converge).

## Not triggered

- SA4C is NOT triggered. SA4C is the fallback for L30 coverage halt (a different failure mode). SA4 has not halted on coverage; only on the phase-stratification mechanism, for which this substitution suffices.
- SA5B is NOT triggered. SA5B is the fallback for V4-anchor density halt. SA5 has not halted on anchor density; the V4-fire AND bare_epoch_flag intersection still produces anchors at the SA1 75th-percentile cut.

If SA4 subsequently halts on L30 coverage, SA4C still requires its own pre-registration before execution per the original pre-reg.
If SA5 subsequently halts on anchor density, SA5B still requires its own pre-registration before execution.

## Halt-rides-into-prose discipline

The SA2 halt and this substitution amendment ride into piece A prose as a methods finding, not appendix material. Story shape: "We tested for phase recovery at AOI-bbox-mean; three halts, including the one we did not expect (Qiddiya). The halt is part of the methods narrative — it tells the hire that BSI cannot resolve sub-AOI phase structure at this aggregation level. Downstream sub-questions retained their substrate signal via SA1's 75th-percentile cut, which is the same threshold SA2's Q4 would have produced anyway." Lock this story shape into the prose skeleton at piece-skeleton revision time.

## Locked

This amendment is locked at commit time. Subsequent SA4/SA5 dispatches reference this amendment, not the original pre-reg, for Q4-related operations.

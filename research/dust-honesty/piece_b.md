# Piece B — Dust honesty at Riyadh

## §0 — Abstract

We tested whether Sen2Cor's known underestimation of aerosols over bright deserts actually corrupts NDVI for change monitoring at Riyadh. It doesn't — not at any magnitude that matters operationally. Across five designs at three Vision 2030 AOIs over 76 months, the strongest detectable signal was −0.002 NDVI per IQR of dust optical depth, 95% CI lower bound −0.003.

The question came from Goyens 2024: Sen2Cor systematically underestimates aerosol over bright deserts, so what does that do to NDVI at Qiddiya, King Salman Park, and Diriyah Gate? We built a faithful port of the Lolli 2024 DBB index to flag dusty scenes and ran the question five ways — paired Sen2Cor, paired LaSRC, broad-versus-narrow NIR, a halt-with-receipt at the Q4 dust quartile (paired designs can't probe the highest loadings at this site), and a per-scene regression against reanalysis AOD. Four pre-registered stop rules fired during execution. Each produced a deferred sub-question rather than a mid-run design switch — the discipline held all four times.

The same chain turned up something the dust question wasn't asking about: six independent lines of evidence that Qiddiya is contaminated bidirectionally by construction substrate, not aerosol. For anyone monitoring change at that specific site, that side-finding matters more operationally than the dust answer does.

For change monitoring at Riyadh, the operational read is simple. NDVI's Red/NIR ratio cancels aerosol perturbations cleanly enough that correction-chain choice doesn't gate deployment.

## §1 — The question

Sentinel-2 is the workhorse of public-data change monitoring — 10m resolution, free, global, 5-day revisit. To make it usable, Copernicus ships a standard atmospheric correction called Sen2Cor that strips scattering and absorption from the air column and returns surface reflectance. For most users that's the entry point, and the assumption baked into every downstream pipeline is that Sen2Cor has done its job.

Goyens et al. 2024 looked at how well that assumption holds over bright desert surfaces. It doesn't, fully. Sen2Cor systematically underestimates aerosol optical depth over bright deserts at high loadings. The mechanism is well-described — bright surfaces confuse the dark-target retrieval Sen2Cor uses, the correction under-removes the aerosol signal, residual perturbation rides in the surface reflectance.

What we cared about isn't whether the underestimation exists — Goyens already established that — but whether it propagates into the metric people actually use. NDVI is the workhorse for vegetation and surface-disturbance monitoring. If Sen2Cor leaves residual aerosol in the bands, and that residual perturbs Red and NIR differently, NDVI gets corrupted on dusty scenes. A pipeline running on those scenes flags dust events as surface change, or misses real changes hiding under dust. Either way it breaks.

Riyadh is the place this question matters most. The surfaces around it sit at the bright end of the Sentinel-2 catalogue — exactly Goyens's failure regime. The atmosphere over it is dust-loaded for months at a time; the shamal season alone delivers Q4-quartile aerosol events on a regular cadence. The three AOIs we monitor — Qiddiya, King Salman Park, and Diriyah Gate — are megaprojects under active construction. Real change is happening on the ground while aerosol is potentially corrupting the measurement of it. If Sen2Cor has a Riyadh-shaped hole, this is where it shows up.

So the umbrella question, tightly: how does Sen2Cor's known aerosol underestimation translate into NDVI bias at Riyadh, and how often does it matter operationally? A "yes, often" answer would push us toward LaSRC, native L30, or a custom correction. A "no" answer means the operational pipeline can keep using Sen2Cor and treat the aerosol question as second-order.

## §2 — Method

The piece B method has two layers: a calibrated dust flag we built once, and a research engine we ran five times against it.

The dust flag. We needed a way to mark Sentinel-2 scenes as "dust-affected" without leaning on Sen2Cor's own aerosol product, which is the thing under test. The Lolli 2024 DBB index gives that — it's a TOA-reflectance ratio designed to be sensitive to aerosol load and insensitive to surface. We ported it faithfully to our three AOIs, calibrated thresholds against TROPOMI UVAI as ground truth, and validated through visually-blind researcher relabeling on a 73-scene calibration set. The final flag (V4) fires across KSP and Diriyah for any non-clean scene; operational fire rates land at 32% for KSP, 75% for Qiddiya, and 12% for Diriyah. The Qiddiya 75% is anomalously high and turns out to be load-bearing for a finding the dust question wasn't asking about — more on that in §4.

The research engine. Once V4 was calibrated, the umbrella question became tractable five different ways. SQ3 measures NDVI bias on V4-flagged versus unflagged scenes via paired temporal neighbors on Sen2Cor L2A — the most direct test of the Goyens claim's downstream consequence. SQ4 reruns the same paired design on HLS S30, which is LaSRC-corrected; if the SQ3 result is Sen2Cor-specific, SQ4 should diverge. SQ4B repeats SQ4 but swaps NIR bands (B8 broad vs B8A narrow) to rule out that any null we see is an artifact of which NIR is being differenced. SQ5 attempts the same paired design but stratified by TROPOMI UVAI quartile to probe specifically the Q4 high-loading regime where Goyens's claim is sharpest. SQ8 abandons paired design entirely and regresses per-scene NDVI residuals against reanalysis dust optical depth — the design that survives when paired pairing fails.

Five designs, one umbrella question, intentional redundancy. Any single design has gaps; the convergence across five tightens the answer until the gaps close.

Stop-rule discipline. Every sub-question entered execution with a pre-registered halt condition. Four of them fired. SQ3's Qiddiya retention came in at 28.1% against a 30% threshold — halted, surfaced, accepted with caveat because the cause was a structural consequence of the 75% V4 fire rate (itself a finding), not noise. SQ4B's Arm B (HLS L30 cross-correction) hit a 43% pre-registered coverage floor failure across two AOIs — halted, deferred to SQ4C, the L30 coverage probe shipped as receipt. SQ5's retention failed in all three AOIs because Riyadh's UVAI seasonality clusters Q1 in winter and Q4 in spring/summer; the quartiles don't temporally interleave at the ±60-day window paired designs need — halted, two methodology findings rode out as receipts, the high-loading question deferred to SQ8. SQ8's first attempt aimed at AERONET ground truth and found no operational station within 500 km of Riyadh during the SQ2 window — halted, retargeted to MERRA-2 reanalysis primary with CAMS NRT cross-check.

The pattern that held across all four: when a stop rule fires, the cheapest possible scope review is the one happening mid-run. The temptation in each case was to switch to a different design that bypassed the constraint — a temptation that conflates "this measurement got borderline retention" with "we should answer a different question." Pre-registration catches that. New questions become new sub-questions; the original ships or halts on its own terms.

A second pattern emerged: the diagnosis is often the finding. SQ3's Qiddiya retention failure is a downstream consequence of SQ2's construction-substrate finding. SQ4B's Arm B coverage failure is a structural Sentinel-2 vs Landsat cadence mismatch. SQ5's retention failure is Riyadh's UVAI seasonality. SQ8's AERONET halt is the absence of long-running ground stations in the eastern Saudi interior. Each halt diagnosis carries forward as either a finding or load-bearing methodology context for the next sub-question. The receipts aren't appendix material; they're piece B substance.

## §3 — The five-design answer chain

The umbrella question got hit five different ways. The first three subsections cover the clean part of the chain — V4's fire rates, the Sen2Cor paired test, the LaSRC cross-check. The next three cover the more interesting structural calls: the NIR-band sensitivity, the halt-with-receipt at high loadings, and the power-confirmed null at the high-AOD regime where the original Goyens claim is sharpest.

### §3.1 — SQ2: V4 fire rates and what they mean

V4 was calibrated on a 73-scene set and applied to 228 operational scenes spanning January 2020 through April 2026. Three numbers came back: KSP 32.4%, Qiddiya 75.0%, Diriyah Gate 11.8% (Figure 1).

Diriyah at 11.8% tracks independent shamal climatology — dust events at this site cluster in spring and early summer, the rest of the year is largely clean. KSP at 32% is the middle case: more atmospheric activity than Diriyah, less than Qiddiya. Both numbers are physically defensible.

Qiddiya at 75% is not. No atmospheric-only mechanism puts a fire rate this high at a site less than 50 km from KSP. Either V4 is broken at Qiddiya — which it can't be selectively, by construction — or something at Qiddiya is producing a DBB signal the calibration set didn't see. That something turns out to be the construction substrate itself: bidirectional contamination from active earthworks producing optical signatures V4 reads as dust. §4 unpacks it. What matters here for the umbrella question: Qiddiya carries a 75% V4 rate that's mostly not aerosol and partly is, and that asymmetry shapes the rest of §3.

### §3.2 — SQ3: Paired NDVI bias on Sen2Cor

The most direct test of the Goyens claim's downstream consequence: take V4-flagged scenes, find each one's nearest unflagged temporal neighbor at the same AOI within ±60 days, compute the per-pair NDVI difference, and bootstrap the resulting distribution against zero.

Three signal classifications came back:

- KSP: tight null, CI halfwidth 0.0076
- Qiddiya: tight null, CI halfwidth 0.0055, with caveat
- Diriyah: wide inconclusive at n=8

The Qiddiya caveat: pair retention landed at 28.1% against a pre-registered 30% floor. Halt rule fired. We accepted the result with the caveat documented because the diagnosis was the §3.1 finding — when 75% of operational scenes are flagged, you can't build many V4-vs-non-V4 pairs in the same temporal window. The cause was structural, not statistical.

Diriyah's wide-inconclusive isn't a halt — it's an artifact of V4's design at the cleanest atmospheric site. The smallest paired set (n=8) sits at the AOI with the lowest V4 fire rate; fewer dusty scenes means fewer pairs. The AOI most worth measuring is the AOI we can measure least precisely from satellite-only paired designs. SQ8 carries that test forward; SQ8B will eventually anchor it against ground truth.

At face value, SQ3 is a conditional null: no detectable aerosol-driven NDVI bias on Sen2Cor at moderate Riyadh-region loadings, on this design, given the Qiddiya retention caveat. The natural follow-up: is the null Sen2Cor-specific?

### §3.3 — SQ4: LaSRC cross-check

If SQ3's null is Sen2Cor-specific — Sen2Cor happens to produce no measurable bias despite its real aerosol underestimation — a different correction chain should diverge. NASA's HLS S30 applies LaSRC to Sentinel-2 surface reflectance: same input radiance, different correction. We reused SQ3's 38 pairs, computed Δ(HLS) − Δ(Sen2Cor) per pair, and ran the same bootstrap on the difference of differences.

Results tracked SQ3's shape:

- KSP: tight null, halfwidth 0.0071
- Qiddiya: tight null, halfwidth 0.0047
- Diriyah: wide inconclusive at n=8

The two correction chains agree at the per-pair level on what aerosol-flagged scenes do to NDVI, which is to say nothing operationally meaningful. The conditional null from SQ3 is not Sen2Cor-specific.

One in-build correction is worth naming. An early run silently lost 39 of 65 candidate tuples when `coll.first()` returned MGRS sliver-coverage tiles near AOI boundaries instead of the AOI-covering tile. We switched to `coll.mosaic()` and re-ran. The diff-of-diffs design absorbs absolute-level offsets between B8A LaSRC and B8A Sen2Cor — the per-pair Δ takes them out — but it can't absorb silently fetching the wrong pixel. The failure mode applies to any HLS query at AOI boundaries.

### §3.4 — SQ4B: NIR-band sensitivity

A subtle escape hatch for the SQ3/SQ4 null: both designs computed NDVI from B8A, the narrow-band NIR. If aerosol perturbs the broader B8 band differently than B8A — a plausible mechanism, since B8 covers a wider wavelength range with different aerosol scattering behavior — then SQ3 and SQ4 might be missing real bias hiding in the standard NDVI definition that most operational pipelines actually use.

SQ4B Arm A reran SQ4's design on HLS S30 with B8 instead of B8A. Same 38 pairs, same diff-of-diffs structure, same bootstrap. Three results:

- KSP: tight null, halfwidth 0.0028
- Qiddiya: tight null, halfwidth 0.0022
- Diriyah: wide inconclusive at n=8

The halfwidths are 3-4× tighter than SQ4. The SQ3/SQ4 null is not an artifact of which NIR band gets differenced.

Arm B (deferred). The original SQ4B plan had a second arm: cross-correction-chain test at high AOD using HLS L30 (LaSRC on Landsat). We pre-registered a 50% L30 coverage floor — at least half of SQ3's pair dates needed an L30 scene within ±1 day. Coverage came in at 33.3% at Qiddiya, 42.9% at Diriyah, 54.2% at KSP, 43.1% pooled. Halt fired in two of three AOIs.

The diagnosis: structural cadence mismatch between Sentinel-2 (S2A+B, ~5-day revisit) and Landsat (L8+L9, ~8-day revisit). The probability of an L30 scene falling within ±1 day of any S2 acquisition is about 37.5% by construction. Re-using SQ3's S2-anchored pairs forces a near-impossible coverage requirement on L30. Arm B got promoted to SQ4C — a future sub-question with native L30 pair construction (Landsat overpass dates as anchors, S2 matched via ±k-day window). SQ4C is deferred post-piece-B because SQ8's operational null obviates the urgency: a third correction chain doesn't change the headline.

The L30 coverage probe shipped as a committed receipt. The halt diagnosis — a known cadence mismatch between two satellite constellations — became methodology context rather than a missing data point.

### §3.5 — SQ5: Halt-with-receipt at the high-AOD regime

Goyens's claim is sharpest at high aerosol loadings. SQ3, SQ4, and SQ4B sampled the loading distribution as it arrived — mostly moderate, occasionally heavy. They found no operationally meaningful bias across that range, but they didn't isolate the high-AOD tail where the failure mode should be most visible. SQ5 was designed to do exactly that: stratify the V4 paired design by TROPOMI UVAI quartile and run the bias test specifically on Q4-vs-Q1 contrasts.

It didn't get to run.

The pre-registered retention floor was 30% across all three AOIs. We hit 0.0% at KSP, 11.1% at Qiddiya, 11.1% at Diriyah. None of the three came close.

The diagnosis took ten minutes once we looked at the date distributions. Riyadh's UVAI seasonality is structural: Q1 (lowest aerosol quartile) clusters in winter; Q4 (highest) clusters in spring and early summer with the shamal season. The two quartiles barely co-occur at any month of the year, much less within the ±60-day matching window paired designs require. The temporal-neighbor algorithm was being asked to find a clean Q1 reference scene within two months of a heavy Q4 scene at a site where those two regimes don't temporally interleave. Of course it failed.

This is where halt-with-receipt earns its place. The standard moves were (a) widen the matching window until retention rises — which conflates a high-AOD test with a between-season comparison and stops measuring what we said we'd measure — or (b) abandon SQ5 and call it a failed sub-question. We did neither. Two findings rode out of the halt as committed receipts:

The seasonal-stratification methodology finding. Paired temporal-neighbor designs cannot probe high-AOD vs low-AOD contrasts at moderate-aridity Saudi sites. The constraint isn't sample size and isn't fixable by tuning the matching window. It's a structural property of how UVAI loadings are distributed across the calendar at this latitude. Anyone running a similar design at Jeddah, Madinah, or any other Saudi site at similar aridity should expect the same retention failure and design accordingly. This is a methodology contribution piece B couldn't have produced if SQ5 had quietly produced an underpowered result and been buried.

The UVAI × V4 contingency table. The pair-retention probe ran a contingency analysis as part of the diagnostic block. Three results emerged that fed the rest of the piece. At Diriyah, the Q4 ∧ ¬V4 cell holds 12 scenes — high atmospheric loading without V4 firing. That cell is the cleanest available Goyens-regime test cell at this site, because it samples high-AOD events V4 itself didn't catch. SQ8 used it as a pre-registered headline anchor. At Qiddiya, the Q4 ∧ V4 cell holds 16 of 18 Q4 scenes (89%) — a sixth independent line of evidence for the construction-substrate finding §4 develops, independent of the optical-DBB calibration. At KSP, the Q4 cell splits roughly evenly between V4-fired and non-fired, confirming KSP's middle case structurally as well as operationally.

The halt that didn't ship a paired-design measurement shipped two findings instead. SQ8 inherited the high-AOD question with a regression design built specifically for the regime SQ5 couldn't reach.

### §3.6 — SQ8: Power-confirmed null at high reanalysis-AOD

SQ5 inherited the high-AOD question to SQ8 with the constraint that paired designs were off the table at this site. SQ8 abandoned pairing and went per-scene: regress NDVI residuals (each scene relative to its per-AOI per-month climatology) against reanalysis dust optical depth, with AOI fixed effects and HC3 robust standard errors. The design trades the within-pair noise control of SQ3/SQ4/SQ4B for the ability to actually sample the high-AOD tail.

The first attempt aimed at AERONET ground-truth AOD as the primary independent variable. Pre-registered station-survey halt: no operational AERONET station within 500 km of Riyadh during the SQ2 window. Solar Village, the only station inside the AOI ring, last reported 2015-10-12 — five years before the SQ2 window opens. Bahrain stopped reporting in 2007. The UAE cluster sits 750–800 km away. The halt fired before any regression code was written.

Retargeted to MERRA-2 DUEXTTAU (reanalysis dust extinction, mechanistically matched to TROPOMI UVAI) as primary, with CAMS NRT total AOD as cross-check at a different temporal cadence. Per-source matching windows — MERRA-2 ±60 minutes, CAMS ±120 minutes because CAMS is 3-hourly not hourly — were a mid-run correction surfaced when an early CAMS query returned almost no matches.

The regression on n=226 scenes returned this:

| Criterion | Test | Result | Classification |
|---|---|---|---|
| Significance | CI excludes zero, β<0, p=0.024; replicated by CAMS at p=0.017 | CI excludes zero | goyens_consistent_bias_detected |
| Magnitude | β × IQR(AOD) = −0.0018 NDVI | 2.8× below 0.005 operational threshold | tight_null |
| Per-AOI | KSP p=0.138, Qiddiya p=0.169, Diriyah p=0.208 | All individually null | — |
| Anchor cell | Diriyah Q4∧¬V4 prediction CI [−0.0046, +0.0011] | Straddles zero | — |

Both pre-registered classifiers fired. They disagreed (Figure 2).

The disagreement is itself a finding. At pooled n=226 with R²=0.028, a regression has enough statistical power to detect very small effects that lack operational meaning. The significance criterion catches the small effect. The magnitude criterion correctly says the effect is too small to matter for change monitoring. Pre-registering both surfaces the disagreement explicitly rather than letting whichever-criterion-fires-first define the result. Documenting the disagreement, rather than overriding one criterion with the other, is the load-bearing methodology move.

The framing decision: read SQ8 as power-confirmation of the SQ3/SQ4/SQ4B operational null, not as Goyens transfer. The Bayesian inverse holds — the test had the power to detect operationally relevant magnitudes at high loadings, and the magnitude it detected is sub-operational. A statistically significant effect 25× below the change-detection threshold is not evidence of bias; it's evidence the test would have caught bias if it existed. Operational magnitude is the load-bearing criterion because the umbrella question is operational.

What ships from §3 as a whole: across two correction chains (Sen2Cor + LaSRC), two NIR bands (B8A narrow + B8 broad), paired and per-scene regression designs, and reanalysis AOD up to Q4 dust loadings, AOD-dependent NDVI bias does not exist at operationally meaningful magnitude at Riyadh. The largest detectable effect is −0.002 NDVI per IQR of dust optical depth, 95% CI lower bound −0.003 — sub-operational across the loading regime (Figure 3). The five-design convergence is the answer; no single design carries it alone.

The mechanism that survives, by elimination: NDVI's Red/NIR ratio cancels aerosol perturbations cleanly. Sen2Cor's aerosol underestimation is real (Goyens 2024), and the residual aerosol does perturb the bands (SQ8's significance criterion confirms it), but the perturbation is correlated enough across Red and NIR that the ratio absorbs it. Change monitoring at Riyadh on Sen2Cor L2A is not gated by the aerosol question.

## §4 — What the methodology surfaced beyond the umbrella question

Piece B's umbrella question is about aerosol. Qiddiya kept showing up in the data with patterns no aerosol mechanism could explain. By the time the dust analysis closed, six independent lines of evidence had converged on a different finding entirely — one the research engine surfaced as a side effect, and one that matters more for anyone monitoring change at this specific site than the aerosol answer does.

The finding: Qiddiya's Sentinel-2 signal is contaminated bidirectionally by construction substrate, not aerosol. Active earthworks at the site produce optical signatures that look like dust to a dust flag, look like greenup or browndown to a vegetation index depending on the week, and create both false positives and false negatives in change-detection workflows that don't account for them.

Six lines, six different parts of the analysis, none of them the dust question:

1. Visually-blind relabeling direction. During the visually-blind relabeling pass, researchers relabeled scenes without seeing dates or AI pre-labels. Qiddiya scenes shifted systematically toward "clean" categories where the AI had pre-labeled them dusty — the human eye saw construction haze and substrate variability where the pre-labeler had pattern-matched to dust.
2. Sensitivity ρ=0.92. SQ1D's Part B sensitivity analysis on the alternate calibration set produced a Spearman correlation of 0.92 between Qiddiya's primary and alternate DBB values — high enough to confirm the calibration is internally consistent, low enough to indicate the site has substrate variability the index is partially reading as aerosol.
3. V2 → V4 AUC drop on Qiddiya inclusion. Calibration metrics dropped meaningfully when Qiddiya was included in the training pool. V4's final form (KSP+Diriyah any-non-clean vs clean) was chosen partly because Qiddiya was poisoning the calibration when included.
4. SQ2 baseline DBB above threshold. Qiddiya's mean operational DBB ran at +0.091, almost three times the V4 threshold of +0.034. This is what produced the 75% V4 fire rate. A site whose mean scene already exceeds the dust-flag threshold isn't a dusty site; it's a site whose substrate looks like dust to the flag.
5. SQ3 Qiddiya retention failure. The 28.1% pair retention that triggered SQ3's halt was a downstream consequence: when 75% of operational scenes are flagged, you can't form many V4-vs-non-V4 pairs in the same temporal window. The diagnosis carried back to the §3.1 finding.
6. SQ5 R5 contingency. The UVAI × V4 contingency table produced the cleanest line in the chain. Of 18 Q4 (highest UVAI quartile) scenes at Qiddiya, V4 fired on 16 — 89%. TROPOMI UVAI is an independent atmospheric instrument with no shared optical path with Sentinel-2's Red and NIR bands. Two independent dust signals agreeing 89% at high loadings would be expected behavior. But the 89% here isn't dust agreement: V4 fires whenever UVAI says it's high-aerosol, and V4 fires plenty of times when UVAI says aerosol is low. The asymmetry is the construction-substrate signal.

Figure 4 stacks the six lines into a single panel.

A seventh line landed at SQ8: the AOI fixed effects in the per-scene regression came in significantly different across the three sites, with Qiddiya's intercept distinct from KSP's and Diriyah's at confidence levels the regression structure should not produce from atmospheric variation alone. This validates the per-AOI baseline-difference reading at the regression level — the per-scene method, completely independent of the paired DBB index, sees the same site-level structural difference at Qiddiya.

What this means operationally: change monitoring at Qiddiya cannot use a dust mask alone. A workflow built on V4-style atmospheric flags will mis-classify construction-substrate variability as aerosol roughly 75% of the time, generating both false positives (construction phases flagged as dust events) and false negatives (real surface change hidden under "this is just dust again"). The fix isn't a better dust flag. The fix is a substrate-aware change detection layer that knows Qiddiya is under active earthworks and treats the site differently from KSP or Diriyah. SQ4C, when it eventually runs, may be able to distinguish the two via the L30 cadence; piece A is where this question lives in detail.

The methodology contribution generalizes. Any active-construction site monitored from satellite optical-only is vulnerable to the same contamination pattern. Vision 2030 has dozens. NEOM, Red Sea Project, Diriyah Gate (the parts under active build), King Salman Park's expansion zones — the same six-line convergence pattern is the diagnostic protocol for surfacing the contamination at any of them.

## §5 — Discussion

Three threads from §3 and §4 didn't get fully resolved inside the analysis. Naming them honestly belongs here, not in the limitations section, because each one is a live question the next phase of work has to answer rather than a caveat on what's already shipped.

Solar zenith angle dependency. Diriyah's wide-inconclusive halfwidth across SQ3, SQ4, and SQ4B isn't just a sample-size problem. The site's smaller paired sets cluster temporally around the dust season, which means V4-flagged and unflagged scenes are systematically separated by sun angle even when calendar dates fall inside the matching window. SZA differences between paired members can introduce path-length variation that compounds with aerosol perturbation, and the diff-of-diffs design absorbs absolute offsets but not regime shifts in path-length geometry. Two paths exist if piece A elevates the question: regress Diriyah residuals on 1/cos(SZA_test) − 1/cos(SZA_ref) and report the slope, or port the Lolli formula to L2A surface reflectance to bypass the TOA-path entirely. Neither belongs inside piece B.

Generalization across surface and coastal-vs-inland regimes. Piece B's answer is anchored at Riyadh — bright continental desert, structurally dust-loaded for months, sub-500 km from no operational aerosol ground station. SQ8B, the deferred KAUST Thuwal generalization test, would anchor the same question at a coastal Saudi site with a live AERONET station and a different aerosol regime (sea-salt and transported dust rather than locally-emitted shamal dust). The expected result there is convergence — the NDVI ratio cancellation mechanism is independent of which aerosol species perturbs the bands — but expectation isn't measurement. SQ8B is the cleanest available test of whether piece B's headline transfers to other Saudi geographies, and Diriyah is the cleanest atmospheric prior to anchor it against. Defer to post-piece-B; piece A's audience pressure may pull SQ8B forward.

Construction-substrate contamination at sites the dust question wasn't asked at. §4's six-line convergence at Qiddiya has a generalization claim attached: any active-construction Vision 2030 site is vulnerable to the same pattern. Piece B doesn't measure that claim; it asserts it on mechanism. NEOM, Red Sea Project, the active-build portions of Diriyah Gate, King Salman Park's expansion zones — each of these would produce a different six-line signature depending on substrate composition and construction phase, and each requires its own diagnostic protocol pass. The methodology to surface the contamination at any site is established; the contamination-by-site catalog is its own piece of work. That work is piece A's natural backbone.

What does not belong in this section: a recapitulation of the §3 chain, a softening of §0's locked headline, or any version of "more research is needed" that doesn't name a specific design. The umbrella question is answered. The discussion is about what the engine sees next.

## §6 — Limitations

Three real ones, named cleanly.

Riyadh-only. Every result in §3 is anchored at three AOIs inside ~50 km of each other in the eastern Saudi interior. The five-design convergence is internally robust; the geographic transfer is unmeasured. SQ8B is where transfer gets tested. Until it runs, piece B's headline applies to Riyadh.

Reanalysis-AOD instead of ground truth. SQ8 used MERRA-2 DUEXTTAU as primary independent variable because no operational AERONET station sits within 500 km of Riyadh during the SQ2 window. Reanalysis products are validated against ground-station networks elsewhere, but the validation density across the Saudi interior is structurally low — there are no stations to validate against. The CAMS NRT cross-check provides instrument-independent agreement on the regression result, which is the strongest available constraint at this site, but it's not the same constraint a co-located AERONET retrieval would provide. The Goyens-regime test is "well-powered using the best available reanalysis" rather than "well-powered using ground truth."

The mechanism claim is by elimination, not by direct measurement. §3 closes on the claim that NDVI's Red/NIR ratio cancels aerosol perturbations cleanly. The five-design convergence is consistent with that mechanism, and SQ8's significance result confirms the perturbation is real, but no design here isolated the per-band perturbations and demonstrated cancellation directly. A spectral residual analysis on AOI-mean Red and NIR separately, on V4-flagged versus unflagged scenes, would convert mechanism-by-elimination into mechanism-by-measurement. That's a piece A candidate, not a piece B gap.

What doesn't appear in this section: the Qiddiya retention caveat (already characterized in §3.2 with diagnosis), SQ4B Arm B's deferral (already characterized in §3.4 as scope decision, not limitation), SQ5's halt (already shipped as finding in §3.5). Stop-rule firings ride into the body as findings; they don't double-count as limitations.

## §7 — Methodology appendix

Full per-sub-question methodology, pre-registration documents, intermediate findings notes, and the calibration-set scene manifests live in `research/dust-honesty/docs/`. Data and figures organize by function under `research/dust-honesty/data/` (calibration, dbb_compute, threshold_fits, operational, ndvi_bias, cross_correction, high_aod_regression, halts) and the parallel `research/dust-honesty/figures/`. The repository at github.com/a7zain/basira ships every script that produced every number in this piece, every CSV the scripts emit, every figure-generation pipeline, and the session logs documenting each design decision and stop-rule firing. The piece B headline rides on six findings notes — `sq2_findings.md` through `sq8_findings.md` — that contain the technical detail this prose summarizes. The open methodology questions for piece A live at the bottom of `2026-05-02.md`.

Figure captions are at `research/dust-honesty/docs/figure_captions.md`.

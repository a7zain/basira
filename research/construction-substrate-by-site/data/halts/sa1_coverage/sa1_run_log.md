# SA1 — Run log (2026-05-05)

## Status

**Script:** `research/construction-substrate-by-site/scripts/sa1_compute_bsi.py` — written, smoke-tested, ready.

**Execution:** Blocked. Earth Engine project `basira-494617` is under heavy soft-throttle after several iterations of concurrent-getInfo abuse during this session. Per-batch `FeatureCollection.getInfo()` calls on the SA1 `.map(add_metrics_feature)` workload now hang past the 180s client-side hard timeout. Lightweight metadata calls (`.size().getInfo()`) return in 2 seconds, confirming the throttle is targeted at heavy compute requests, not project-wide outage.

**Outputs:** none yet (no successful per-AOI CSV produced).

## What was verified to work

- Bare-soil index math, band selection (S30 B11/B4/B8A/B2; L30 B6/B4/B5/B2), Fmask reject mask (bits 1–4) — all consistent with piece B `sq4_compute_hls_ndvi.py`.
- AOI mapping: all three AOIs (Qiddiya, KSP, Diriyah) sit inside MGRS tile **38RPN**. Verified by per-tile `reduceRegion(B4)` counts — 18.8k pixels for Qiddiya bbox, 19.2k for KSP, 8.0k for Diriyah, with zero pixels in any neighboring Riyadh-candidate tile (38RPP, 38RQN, 38RQP, 39RUH, 39RUJ).
- HLS `system:footprint` is broken on Earth Engine for both HLSS30 and HLSL30 (corners stored as ±Infinity); `filterBounds(geom)` returns the global collection. Workaround: `ee.Filter.stringContains('system:index', '38RPN')`. Documented in script docstring.
- Smoke test, single 1-month batch (Qiddiya S30 Jan 2024): 11 per-tile rows, 30s.
- Smoke test, single 3-month batch (Qiddiya S30 Q1 2024): 33 per-tile rows, 60–90s. **Stopped working after concurrent-getInfo abuse.**
- BSI values land in expected range (~0.16 over Qiddiya bare-substrate scenes); cloud_fraction tracks Fmask pixel rejection sensibly (0.04–0.25 on partly-clear scenes, 1.0 on fully-cloudy scenes).

## What broke

Iteration on parallelism settings:

1. **6-way `ThreadPoolExecutor` (one worker per AOI×sensor pair).** Initial 26 batches landed in ~10 minutes, then the run dead-stalled. Process alive but no new output for 5+ hours. EE was queueing new heavy-compute requests behind older ones without responding.
2. **3-way `ThreadPoolExecutor` (one worker per AOI).** First batch landed in ~90s, second batch never landed. Same hang shape.
3. **1-way serial, no inter-batch pacing.** First batch landed in ~30s, second batch hung past the 180s client hard timeout. Retry attempts also timed out.
4. **1-way serial with 3s inter-batch pause.** First 4 batches landed cleanly (~30s each). Batch 5 hung; retry path activated. Pacing helps but doesn't eliminate the throttle.
5. **Smoke test, post-cooldown.** A single 1-month fetch immediately after process restart still works (~30s). Subsequent fetches hang.

The pattern: the project has a heavy-compute soft quota. Every successful `FC.getInfo()` debits the quota. The first call after a cold start is usually fine; subsequent calls land in the throttle queue and stall.

## Resume instructions

1. **Wait for quota reset.** EE soft quotas typically reset on a sliding 24-hour window. Tomorrow morning is a safe target.
2. **Re-run unchanged:** `/opt/anaconda3/envs/sarsat/bin/python -u research/construction-substrate-by-site/scripts/sa1_compute_bsi.py`.
3. **If the throttle has cleared,** the serial run will take ~3 hours wall-clock (76 1-month batches × 6 (AOI × sensor) × ~25s/batch). Per-batch progress prints `[N/456=X.X%]` so resumption is observable.
4. **If the throttle is still active,** the script will retry each batch up to 4 times with exponential backoff (10s, 20s, 40s, 60s) before raising. If a batch fails terminally, kill, wait longer, retry.

## What to commit alongside this log

The SA1 script. Smoke tests confirm correctness; only execution is blocked. The script is the deliverable; the per-AOI CSVs and SA1_summary.md will be produced in the resume run.

## Note on stop-rule philosophy (carried from piece B)

This is **not** a pre-registered halt — pre-registered halts are about coverage gaps in the data (fewer than 5 cloud-free bare-epoch scenes per AOI/sensor). This is an environmental halt: the data is there, the methodology is sound, the execution environment is rate-limited. Surfacing it here so the resume run is unambiguous and the time-cost is auditable, not buried.

The lesson — concurrent `FC.getInfo()` on per-image `.map()`-with-reduceRegion workloads accumulates soft throttle that affects subsequent serial calls too — is documented in the script docstring under "Spatial filter" alongside the filterBounds workaround, so future SA-prefix scripts don't repeat it.

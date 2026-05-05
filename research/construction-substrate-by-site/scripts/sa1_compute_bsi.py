"""
SA1 — Per-AOI BSI baseline from cloud-free bare-epoch S30 + L30 scenes.

Computes BSI per scene per AOI per sensor over the 76-month
DBB-operational window (2020-01 .. 2026-04, parity with piece B SQ2),
then flags bare-epoch scenes via AOI-specific 75th percentile.

Math
----
BSI = ((SWIR + Red) - (NIR + Blue)) / ((SWIR + Red) + (NIR + Blue))

Bands locked
------------
S30: SWIR=B11, Red=B4, NIR=B8A (~865nm narrow), Blue=B2
L30: SWIR=B6,  Red=B4, NIR=B5  (~865nm),        Blue=B2

B8A locked for S30 because its ~855-875nm window overlaps L30 OLI
Band 5 (~845-885nm) almost exactly. S30 broad B8 (785-900nm) does
not overlap L30 OLI 5 in the same way; using B8 in SA1 would
introduce a band-mismatch confound in SA4's cross-sensor pair test.

Cloud filter
------------
SA1 uses Fmask cloud_fraction < 0.10 per scene (strict).
SA3 uses cloud_fraction < 0.30 (looser). Rationale: SA1 produces
threshold labels (the 75th percentile cut for bare-epoch); label
quality warrants tighter cloud-filtering. SA3 uses those labels in
regression where residual structure isn't in the clouds, so 0.30 is
defensible.

Fmask
-----
Bits 1..4 (cloud, adj-to-cloud, cloud-shadow, snow) define rejected
pixels. cloud_fraction = (n_total - n_valid) / n_total over the AOI
bbox. Bit 0 (cirrus) and bit 5 (water) NOT used in mask. Parity with
sq4_compute_hls_ndvi.py.

Spatial filter
--------------
HLS images on Earth Engine have broken `system:footprint` metadata
(corners reported as ±Infinity), so `filterBounds(geom)` returns
the entire global collection — every MGRS tile worldwide. Piece B's
SQ4 mosaic-then-reduceRegion pattern works around this: the mosaic
paints irrelevant tiles as no-data layers, and reduceRegion over the
AOI bbox correctly samples the Saudi tile's pixels at AOI grid
points.

For SA1's per-image throughput (we want per-scene BSI distribution,
not per-date mosaic averages), we filter on a known-good MGRS tile
prefix in `system:index` instead. All three Riyadh AOIs (Qiddiya,
KSP, Diriyah) sit inside MGRS tile 38RPN, verified by per-scene
reduceRegion(B4) counts: ~18.8k pixels for Qiddiya bbox, ~19.2k for
KSP, ~8.0k for Diriyah, with zero pixels in any neighboring Riyadh-
candidate tile (38RPP, 38RQN, 38RQP, 39RUH, 39RUJ). The filter is
`ee.Filter.stringContains('system:index', '38RPN')`, which works
identically for HLSS30 and HLSL30 (both use the `T<MGRS>_<datetime>`
system_index format; only S30 carries an `MGRS_TILE_ID` property,
so we use system_index for sensor parity).

Multi-tile same-date
--------------------
With the 38RPN single-tile filter, multi-MGRS-tile mosaic is
generally not needed (each acquisition contributes one tile per
sensor per day). When a date does carry multiple tile-rows (rare;
e.g., a sensor with overlapping orbit footprints in the same day),
they're collapsed to one row per (date, sensor) via valid-pixel-
weighted mean of per-tile BSI and summed (n_total - n_valid) for
cloud_fraction. Parity with piece B's locked one-row-per-(aoi, date)
HLS pattern.

Halt rule (pre-registered)
--------------------------
Per (AOI, sensor), count cloud-free (cloud_fraction < 0.10) bare-epoch
(BSI > AOI 75th percentile) scenes. Floor: 5. Below floor in either
sensor for any AOI -> halt SA1, write halt receipt under
data/halts/sa1_coverage/, fall back to the full DBB-operational window
as proxy bare-epoch (drop the BSI > 75th percentile filter for that
AOI; all cloud-filtered scenes flagged bare_epoch_flag=True). The
fallback still produces SA1 outputs and does not block SA2.

75th percentile pooling
-----------------------
Per AOI, the threshold is computed over the cloud-filtered S30 union
L30 BSI distribution within that AOI. Pooling across sensors is
defensible because S30 B8A and L30 B5 are spectrally matched (NIR
~865nm). NOT pooled across AOIs.

Outputs
-------
data/sa1_bsi_baseline/
  qiddiya_bsi_per_scene.csv
  ksp_bsi_per_scene.csv
  diriyah_bsi_per_scene.csv
  SA1_summary.md
data/halts/sa1_coverage/   (only if halt fires)

Run
---
$ /opt/anaconda3/envs/sarsat/bin/python \
    research/construction-substrate-by-site/scripts/sa1_compute_bsi.py
"""
from __future__ import annotations

import csv
import os
import sys
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import ee
import numpy as np
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from src.phase1_aois import get_bbox  # noqa: E402

# --- Constants --------------------------------------------------------------

PIECE_DIR = ROOT / "research/construction-substrate-by-site"
DATA = PIECE_DIR / "data"
OUT_DIR = DATA / "sa1_bsi_baseline"
HALT_DIR = DATA / "halts/sa1_coverage"

HLS_S30 = "NASA/HLS/HLSS30/v002"
HLS_L30 = "NASA/HLS/HLSL30/v002"

# All three AOIs (Qiddiya, KSP, Diriyah) sit inside MGRS tile 38RPN.
# We filter scenes by stringContains on system:index because (a) the
# canonical filterBounds is broken for HLS on GEE (footprints stored
# as ±Infinity → filterBounds returns the global collection) and (b)
# only S30 carries MGRS_TILE_ID; L30 doesn't, but its system_index
# follows the same T<MGRS>_<datetime> convention.
SAUDI_TILE = "38RPN"

# 76-month DBB-operational window, parity with piece B SQ2.
# Filter is start-inclusive, end-exclusive in GEE filterDate. End set to
# 2026-05-01 to cover all of April 2026.
WINDOW_START = "2020-01-01"
WINDOW_END = "2026-05-01"

# Fmask reject mask: bits 1..4 (cloud, adj-to-cloud, cloud-shadow, snow).
FMASK_REJECT = 0b00011110

SCALE_M = 30

SENSOR_CONFIG = {
    "S30": {
        "asset": HLS_S30,
        "swir": "B11",
        "red": "B4",
        "nir": "B8A",
        "blue": "B2",
    },
    "L30": {
        "asset": HLS_L30,
        "swir": "B6",
        "red": "B4",
        "nir": "B5",
        "blue": "B2",
    },
}

# AOI key (piece B convention) -> output filename stem and display name.
AOI_MAP = [
    {"key": "qiddiya_core", "stem": "qiddiya", "name": "Qiddiya"},
    {"key": "king_salman_park", "stem": "ksp", "name": "King Salman Park"},
    {"key": "diriyah_gate", "stem": "diriyah", "name": "Diriyah Gate"},
]

CLOUD_FILTER_SA1 = 0.10
BARE_EPOCH_PERCENTILE = 75
HALT_FLOOR = 5

# Process the window in 1-month batches. Earlier attempts at year-batches
# timed out on EE (5-min computation limit) and 3-month batches were
# unreliable under any concurrency (slow-queue / soft-throttle on the
# project after concurrent calls accumulated). 1-month batches are
# small enough (~10-30 scenes) that each FC.getInfo() lands in 20-60s
# reliably; the cost is more client round-trips (456 instead of 78)
# but those are network-bound and EE-friendly.
def _build_batches():
    out = []
    for y in range(2020, 2026):
        for m in range(1, 13):
            start = f"{y}-{m:02d}-01"
            if m == 12:
                end = f"{y + 1}-01-01"
            else:
                end = f"{y}-{m + 1:02d}-01"
            out.append((f"{y}-{m:02d}", start, end))
    # 2026 Jan-Apr.
    for m in range(1, 5):
        start = f"2026-{m:02d}-01"
        end = f"2026-{m + 1:02d}-01" if m < 12 else "2027-01-01"
        out.append((f"2026-{m:02d}", start, end))
    return out


BATCHES = _build_batches()
YEARS = list(range(2020, 2027))  # 2020..2026 for per-year summary aggregation


# --- Server-side metric attachment ------------------------------------------

def add_metrics_feature(img, sensor_cfg, geom):
    """Server-side: package per-image (bsi, n_valid, n_total, date,
    system_index) into a single ee.Feature.

    BSI computed at native 30m on AOI bbox as valid-pixel mean. Fmask
    rejection ('valid' band) and BSI mask share the same pixel
    population, so cloud_fraction (computed client-side from n_valid /
    n_total) refers to the same population BSI is averaged over.

    Two reduceRegion calls per image: one for bsi mean, one for
    valid sum+count. Tested an alternative single combined reducer
    over a 2-band stack — measured ~2x slower (53s vs 30s on the
    same 11-image batch); EE pays per (band × reducer-component) so
    the combine path does 6 reductions where we only need 3.

    We return a FEATURE rather than setting properties on the image
    because (a) one Feature == one record, fetched in a single
    getInfo() at the FeatureCollection level, and (b) aggregate_array
    drops null-property values, which would mis-align fully-cloudy
    scenes between bsi/date/n_valid arrays. Feature-level fetch
    preserves nulls in-place.
    """
    swir = img.select(sensor_cfg["swir"]).toFloat()
    red = img.select(sensor_cfg["red"]).toFloat()
    nir = img.select(sensor_cfg["nir"]).toFloat()
    blue = img.select(sensor_cfg["blue"]).toFloat()
    fmask = img.select("Fmask").toUint8()

    num = swir.add(red).subtract(nir.add(blue))
    den = swir.add(red).add(nir).add(blue)
    bsi = num.divide(den).rename("bsi").updateMask(den.gt(0))

    rejected = fmask.bitwiseAnd(FMASK_REJECT).gt(0)
    valid = rejected.Not().rename("valid")

    bsi_masked = bsi.updateMask(valid)
    bsi_stat = bsi_masked.reduceRegion(
        reducer=ee.Reducer.mean(),
        geometry=geom, scale=SCALE_M, maxPixels=1e9,
    )

    valid_stat = valid.unmask(0).reduceRegion(
        reducer=ee.Reducer.sum().combine(
            ee.Reducer.count(), sharedInputs=True
        ),
        geometry=geom, scale=SCALE_M, maxPixels=1e9,
    )

    return ee.Feature(None, {
        "system_index": img.get("system:index"),
        "scene_date": img.date().format("YYYY-MM-dd"),
        "bsi": bsi_stat.get("bsi"),
        "n_valid": valid_stat.get("valid_sum"),
        "n_total": valid_stat.get("valid_count"),
    })


def _getInfo_with_timeout(fc, timeout_sec):
    """Call fc.getInfo() with a hard timeout (seconds).

    EE getInfo lacks a client-side timeout; under soft-throttle the
    server can keep a connection open indefinitely. We run getInfo in
    a daemon thread and raise on timeout. The thread is abandoned (it
    will eventually return or be killed at process exit) but the
    caller can retry.
    """
    import threading
    result = [None]
    err = [None]

    def target():
        try:
            result[0] = fc.getInfo()
        except Exception as e:
            err[0] = e

    t = threading.Thread(target=target, daemon=True)
    t.start()
    t.join(timeout_sec)
    if t.is_alive():
        raise TimeoutError(f"getInfo exceeded {timeout_sec}s")
    if err[0] is not None:
        raise err[0]
    return result[0]


def fetch_aoi_sensor_year(aoi_key, sensor, ystart, yend,
                          max_retries=4, hard_timeout=180):
    """Return list of per-image dicts for one (aoi, sensor, batch).

    Filter chain: stringContains(system:index, '38RPN') → filterDate.
    See module docstring "Spatial filter" for why we don't use the
    canonical filterBounds with HLS on GEE.

    Single client round-trip via FeatureCollection.getInfo() on the
    mapped collection. Returns one dict per HLS scene; dedup_by_date()
    collapses any same-date duplicates to per-(date, sensor) downstream.

    Retries on transient EE errors (timeout, deadline) AND on
    client-side hard timeout (hard_timeout sec). The hard timeout
    catches EE soft-throttle hangs where the server holds the
    connection without responding; without it, a single hung call
    can stall the whole job. Backoff is exponential.
    """
    geom = ee.Geometry.Rectangle(list(get_bbox(aoi_key)))
    sensor_cfg = SENSOR_CONFIG[sensor]
    coll = (
        ee.ImageCollection(sensor_cfg["asset"])
        .filter(ee.Filter.stringContains("system:index", SAUDI_TILE))
        .filterDate(ystart, yend)
        .sort("system:index")
    )
    fc = ee.FeatureCollection(
        coll.map(lambda img: add_metrics_feature(img, sensor_cfg, geom))
    )
    info = None
    for attempt in range(1, max_retries + 1):
        try:
            info = _getInfo_with_timeout(fc, hard_timeout)
            break
        except (TimeoutError, ee.ee_exception.EEException) as exc:
            msg = str(exc)
            if attempt == max_retries:
                raise
            backoff = min(60, 10 * (2 ** (attempt - 1)))
            print(f"    retry {attempt}/{max_retries - 1} after error: "
                  f"{msg[:80]}  (sleeping {backoff}s)", flush=True)
            time.sleep(backoff)

    rows = []
    for feat in info["features"]:
        p = feat["properties"]
        nv = p.get("n_valid")
        nt = p.get("n_total")
        rows.append({
            "system_index": p.get("system_index"),
            "scene_date": p.get("scene_date"),
            "sensor": sensor,
            "bsi": p.get("bsi"),
            "n_valid": int(nv) if nv is not None else 0,
            "n_total": int(nt) if nt is not None else 0,
        })
    return rows


def dedup_by_date(rows):
    """Multi-tile same-date scenes -> one row per (date, sensor) via
    valid-pixel-weighted average. For non-overlapping MGRS tiles
    (the HLS norm) this equals the AOI-bbox mean of the mosaicked image.
    Parity with piece B's per-(aoi, date) HLS pattern.
    """
    grouped = defaultdict(list)
    for r in rows:
        grouped[(r["scene_date"], r["sensor"])].append(r)

    out = []
    for (ds, sensor), group in sorted(grouped.items()):
        if len(group) == 1:
            r = group[0]
            cf = (r["n_total"] - r["n_valid"]) / r["n_total"] if r["n_total"] > 0 else None
            out.append({
                "scene_date": ds,
                "sensor": sensor,
                "bsi": r["bsi"],
                "cloud_fraction": cf,
                "n_valid_pixels": r["n_valid"],
                "n_total_pixels": r["n_total"],
                "hls_system_index": r["system_index"],
            })
            continue

        n_valid_total = sum(r["n_valid"] for r in group)
        n_total_total = sum(r["n_total"] for r in group)
        weighted_sum = 0.0
        weight_total = 0
        for r in group:
            if r["bsi"] is None:
                continue
            w = r["n_valid"]
            weighted_sum += r["bsi"] * w
            weight_total += w
        bsi_combined = weighted_sum / weight_total if weight_total > 0 else None
        cf_combined = (
            (n_total_total - n_valid_total) / n_total_total
            if n_total_total > 0 else None
        )
        sys_idx_combined = "+".join(sorted(r["system_index"] for r in group))

        out.append({
            "scene_date": ds,
            "sensor": sensor,
            "bsi": bsi_combined,
            "cloud_fraction": cf_combined,
            "n_valid_pixels": n_valid_total,
            "n_total_pixels": n_total_total,
            "hls_system_index": sys_idx_combined,
        })
    return out


# --- I/O --------------------------------------------------------------------

def write_per_aoi_csv(path, rows):
    fields = [
        "scene_date", "sensor", "bsi", "cloud_fraction", "bare_epoch_flag",
        "hls_system_index", "n_valid_pixels", "n_total_pixels",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in rows:
            w.writerow({
                "scene_date": r["scene_date"],
                "sensor": r["sensor"],
                "bsi": ("" if r["bsi"] is None else f"{r['bsi']:.6f}"),
                "cloud_fraction": (
                    "" if r["cloud_fraction"] is None
                    else f"{r['cloud_fraction']:.4f}"
                ),
                "bare_epoch_flag": "True" if r["bare_epoch_flag"] else "False",
                "hls_system_index": r["hls_system_index"],
                "n_valid_pixels": r["n_valid_pixels"],
                "n_total_pixels": r["n_total_pixels"],
            })


def write_halt_receipt(aoi_meta, s30_n, l30_n, counts, threshold,
                       fallback_n_cloudfree):
    HALT_DIR.mkdir(parents=True, exist_ok=True)
    path = HALT_DIR / f"{aoi_meta['stem']}_sa1_halt.md"
    aoi_key = aoi_meta["key"]
    lines = [
        f"# SA1 halt — {aoi_meta['name']} ({aoi_key})",
        "",
        "**Pre-registered halt rule (piece A SA1):** per (AOI, sensor), "
        "fewer than 5 cloud-free bare-epoch scenes triggers halt for that "
        "AOI. Cloud-free = Fmask cloud_fraction < 0.10. Bare-epoch = BSI "
        "> AOI 75th percentile.",
        "",
        "## Counts (cloud-filtered)",
        "",
        "| sensor | total scenes | cloud-filtered (cf<0.10) | "
        "cloud-free bare-epoch | floor |",
        "|--------|-------------:|-------------------------:|"
        "----------------------:|------:|",
    ]
    for sensor in ("S30", "L30"):
        c = counts[(aoi_key, sensor)]
        lines.append(
            f"| {sensor} | {c['total']} | {c['cloud_filt']} | "
            f"{c['bare_epoch_cloudfree']} | {HALT_FLOOR} |"
        )
    threshold_disp = (
        f"{threshold:+.4f}" if threshold is not None else "n/a (no cloud-filtered scenes)"
    )
    lines += [
        "",
        f"**75th percentile BSI threshold (S30 ∪ L30 cloud-filtered):** "
        f"{threshold_disp}",
        "",
        f"**Halt counts:** S30 = {s30_n}, L30 = {l30_n}. "
        f"Below floor of {HALT_FLOOR} in "
        f"{'both sensors' if s30_n < HALT_FLOOR and l30_n < HALT_FLOOR else 'one sensor'}.",
        "",
        "## Fallback (pre-registered)",
        "",
        "Fall back to using the full DBB-operational window as proxy "
        "bare-epoch — drop the `BSI > 75th percentile` filter for this "
        "AOI. All cloud-filtered (cf<0.10) scenes are flagged "
        "`bare_epoch_flag=True` in the per-AOI CSV; the BSI threshold "
        "above is reported but NOT applied to this AOI's flag. The "
        "fallback still produces SA1 outputs; it does not block SA2.",
        "",
        f"**Fallback flagged (cloud-filtered) scenes for this AOI:** "
        f"{fallback_n_cloudfree}",
        "",
        "## Why a halt and not a workaround",
        "",
        "Per piece B stop-rule philosophy carried into piece A: when a "
        "halt fires, the cheapest possible scope review is the one "
        "happening mid-run. New designs that bypass the constraint "
        "become new sub-questions, not silent re-specifications. The "
        "fallback above is the pre-registered fallback, not a new "
        "design.",
        "",
    ]
    with open(path, "w") as f:
        f.write("\n".join(lines))
    print(f"  wrote halt receipt: {path}")


def write_summary(aoi_to_thresh, counts, halts, aoi_to_rows, n_per_year):
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUT_DIR / "SA1_summary.md"
    halted_keys = {h[0] for h in halts}

    lines = [
        "# SA1 — BSI baseline summary",
        "",
        "**Goal:** Build per-AOI BSI baseline from cloud-free bare-epoch "
        "S30 + L30 scenes for Qiddiya, KSP, Diriyah over the 76-month "
        "DBB-operational window (2020-01 .. 2026-04, parity with piece "
        "B SQ2). Output is per-AOI CSV with one row per (date, sensor) "
        "and a bare-epoch flag from the AOI's own 75th-percentile BSI "
        "cut.",
        "",
        "## Per-AOI per-sensor scene counts",
        "",
        "Counts after dedup-by-date (multi-MGRS-tile same-date scenes "
        "collapsed to one row per acquisition date via valid-pixel-"
        "weighted mean — parity with piece B's locked HLS pattern). "
        "`bare_epoch_cloudfree` is the count used by the halt rule.",
        "",
        "| AOI | sensor | total | cloud-filtered (cf<0.10) | "
        "cloud-free bare-epoch | halt? |",
        "|-----|--------|------:|-------------------------:|"
        "----------------------:|:-----:|",
    ]
    for aoi_meta in AOI_MAP:
        aoi_key = aoi_meta["key"]
        halted = "**YES**" if aoi_key in halted_keys else "no"
        for sensor in ("S30", "L30"):
            c = counts[(aoi_key, sensor)]
            lines.append(
                f"| {aoi_meta['name']} | {sensor} | {c['total']} | "
                f"{c['cloud_filt']} | {c['bare_epoch_cloudfree']} | "
                f"{halted if sensor == 'S30' else ''} |"
            )

    lines += [
        "",
        "## Halt rule",
        "",
        f"Per (AOI, sensor) cloud-free bare-epoch count must be ≥ "
        f"{HALT_FLOOR}. Below floor in either sensor for any AOI → "
        f"halt for that AOI.",
        "",
    ]
    if halts:
        lines.append("**Halt fired in:**")
        lines.append("")
        for (aoi_key, s30_n, l30_n) in halts:
            aoi_name = next(a["name"] for a in AOI_MAP if a["key"] == aoi_key)
            lines.append(
                f"- {aoi_name}: S30={s30_n}, L30={l30_n} (floor={HALT_FLOOR})."
            )
        lines += [
            "",
            "Per-AOI halt receipts: `data/halts/sa1_coverage/`. Fallback "
            "applied per pre-reg (drop BSI > 75th-pctile filter for "
            "halted AOIs; flag all cloud-filtered scenes as bare-epoch).",
        ]
    else:
        lines.append("**Halt rule did not fire.** All AOIs cleared the "
                     f"floor of {HALT_FLOOR} cloud-free bare-epoch scenes "
                     "in both S30 and L30.")

    lines += [
        "",
        "## Per-AOI 75th-percentile BSI thresholds",
        "",
        "Computed within each AOI's own cloud-filtered (cloud_fraction "
        "< 0.10) BSI distribution, S30 and L30 pooled. Pooling across "
        "sensors is defensible: S30 B8A (~865nm narrow) and L30 OLI "
        "Band 5 (~865nm) are spectrally matched. NOT pooled across AOIs.",
        "",
        "| AOI | n cloud-filtered scenes | 75th-percentile BSI |",
        "|-----|------------------------:|--------------------:|",
    ]
    for aoi_meta in AOI_MAP:
        aoi_key = aoi_meta["key"]
        n_cf = sum(1 for r in aoi_to_rows[aoi_key]
                   if r["bsi"] is not None
                   and r["cloud_fraction"] is not None
                   and r["cloud_fraction"] < CLOUD_FILTER_SA1)
        thresh = aoi_to_thresh[aoi_key]
        thresh_disp = (
            f"{thresh:+.4f}" if thresh is not None else "n/a"
        )
        lines.append(
            f"| {aoi_meta['name']} | {n_cf} | {thresh_disp} |"
        )

    lines += [
        "",
        "## Band-choice rationale",
        "",
        "S30 NIR locked at B8A (855–875nm narrow), not broad B8 "
        "(785–900nm). Reason: B8A's bandpass overlaps L30 OLI Band 5 "
        "(845–885nm) almost exactly, so S30-vs-L30 BSI comparisons in "
        "SA4 (cross-sensor pair test) measure substrate signal, not "
        "band-mismatch confound. SA1 inherits this lock so the bare-"
        "epoch labels carry through to SA4 in the same band geometry.",
        "",
        "S30: SWIR=B11, Red=B4, NIR=B8A, Blue=B2",
        "L30: SWIR=B6, Red=B4, NIR=B5, Blue=B2",
        "",
        "## Cloud-filter rationale",
        "",
        "SA1 uses Fmask cloud_fraction < 0.10 (strict). This is "
        "stricter than SA3's pre-registered cloud_fraction < 0.30 "
        "for the BSI–NDVI regression. The asymmetry is intentional:",
        "",
        "- **SA1 produces labels.** The 75th-percentile cut is the "
        "label that decides which scenes are \"bare earth\" downstream. "
        "If a residual cloud or cirrus haze inflates BSI on a "
        "marginal scene, that scene gets mislabeled as bare-epoch and "
        "the label set is corrupted. Strict cloud filtering protects "
        "the threshold.",
        "- **SA3 consumes labels in regression.** Residual cloud "
        "structure shows up in NDVI and AOD too, but SA3's regression "
        "controls for AOD (DUEXTTAU) and uses HC3 robust SE. The "
        "regression is robust to looser cloud filtering because the "
        "noise it introduces does not have the same residual structure "
        "as substrate. Tightening SA3 to 0.10 would shrink n past the "
        "halt floor at SA3 (n<20 per AOI) without buying coefficient "
        "stability.",
        "",
        "Documented per pre-reg requirement.",
        "",
        "## Fmask",
        "",
        "Bits 1..4 (cloud, adj-to-cloud, cloud-shadow, snow) define "
        "rejected pixels. cloud_fraction = (n_total − n_valid) / "
        "n_total over the AOI bbox at native 30m. Bit 0 (cirrus) and "
        "bit 5 (water) NOT used in mask. Parity with "
        "`sq4_compute_hls_ndvi.py`.",
        "",
        "## Multi-tile same-date handling",
        "",
        "HLS scenes are per-MGRS-tile. Same-date overlapping tiles "
        "for one AOI bbox are collapsed to one row per (date, sensor) "
        "via valid-pixel-weighted mean of per-tile BSI and summed "
        "(n_total − n_valid) for cloud_fraction. For non-overlapping "
        "MGRS tiles (the HLS norm) this is mathematically equivalent "
        "to the AOI-bbox mean of the mosaicked image. Parity with "
        "piece B's locked one-row-per-(aoi, date) HLS pattern.",
        "",
        "## Year-by-year per-tile scene counts (pre-dedup)",
        "",
        "Per-tile rows include partial-tile S2 acquisitions where the "
        "MGRS tile is in the catalog but the AOI bbox sits outside the "
        "actual data extent (n_total = 0). Those rows survive into the "
        "CSV with bsi=NULL and are filtered out at threshold and halt-"
        "count stages.",
        "",
        f"| AOI | sensor | {' | '.join(str(y) for y in YEARS)} | total |",
        "|-----|--------|"
        + "|".join(["------:"] * (len(YEARS) + 1))
        + "|",
    ]
    for aoi_meta in AOI_MAP:
        aoi_key = aoi_meta["key"]
        for sensor in ("S30", "L30"):
            yvals = [n_per_year.get((aoi_key, sensor, y), 0) for y in YEARS]
            total = sum(yvals)
            lines.append(
                f"| {aoi_meta['name']} | {sensor} | "
                + " | ".join(str(v) for v in yvals)
                + f" | {total} |"
            )

    lines += [
        "",
        "## Outputs",
        "",
        "- `data/sa1_bsi_baseline/qiddiya_bsi_per_scene.csv`",
        "- `data/sa1_bsi_baseline/ksp_bsi_per_scene.csv`",
        "- `data/sa1_bsi_baseline/diriyah_bsi_per_scene.csv`",
        "- `data/sa1_bsi_baseline/SA1_summary.md` (this file)",
    ]
    if halts:
        lines.append("- `data/halts/sa1_coverage/{aoi}_sa1_halt.md` "
                     "(one per halted AOI)")

    lines += [
        "",
        "CSV schema: `scene_date, sensor, bsi, cloud_fraction, "
        "bare_epoch_flag, hls_system_index, n_valid_pixels, "
        "n_total_pixels`. `bare_epoch_flag` is the union of (a) AOI 75th-"
        "percentile cut on BSI, or (b) for halted AOIs, the fallback "
        "of (cloud_fraction < 0.10).",
        "",
    ]

    with open(path, "w") as f:
        f.write("\n".join(lines))
    print(f"\nwrote {path}")


# --- Main -------------------------------------------------------------------

def main():
    # Unbuffered stdout so progress is visible when output is redirected.
    sys.stdout.reconfigure(line_buffering=True)
    load_dotenv(ROOT / ".env")
    project = os.environ.get("GEE_PROJECT", "basira-494617")
    ee.Initialize(project=project)

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    print("SA1 — BSI baseline per AOI per sensor (S30 + L30)")
    print(f"  Window: {WINDOW_START} .. {WINDOW_END} (exclusive)")
    print(f"  S30 asset: {HLS_S30}")
    print(f"  L30 asset: {HLS_L30}")
    print(f"  MGRS tile filter: stringContains(system:index, '{SAUDI_TILE}')")
    print(f"  Cloud filter: cloud_fraction < {CLOUD_FILTER_SA1} (strict)")
    print(f"  Bare-epoch percentile: {BARE_EPOCH_PERCENTILE}")
    print(f"  Halt floor: {HALT_FLOOR} cloud-free bare-epoch / (AOI, sensor)")
    print()

    # 1. Fetch per-image rows for each (aoi, sensor) over all 1-month
    # batches, serial. Empirical: any thread-pool concurrency on the
    # full per-image .map() workload accumulated soft throttle on
    # the project (EE queues new requests behind older ones; 6-way
    # dead-stalled, 3-way slowed to a crawl after the warm-up). 1-way
    # serial is the only reliably-stable mode under our quota. Total
    # wall-clock is high (~3-4h) but progress is visible per-batch.
    aoi_to_rows = {a["key"]: [] for a in AOI_MAP}
    n_per_year = {}

    n_total_batches = len(BATCHES) * len(AOI_MAP) * 2
    n_done = 0
    overall_t0 = time.time()
    INTER_BATCH_PAUSE_S = 3  # gentle pacing — empirical: hammering EE
                              # back-to-back accumulates soft throttle that
                              # later stalls the run. A few seconds between
                              # batches keeps the quota window cool.
    for aoi_meta in AOI_MAP:
        aoi_key = aoi_meta["key"]
        for sensor in ("S30", "L30"):
            sensor_pertile = []
            for (label, bstart, bend) in BATCHES:
                t0 = time.time()
                br_rows = fetch_aoi_sensor_year(aoi_key, sensor, bstart, bend)
                sensor_pertile.extend(br_rows)
                year = int(bstart[:4])
                n_per_year[(aoi_key, sensor, year)] = (
                    n_per_year.get((aoi_key, sensor, year), 0) + len(br_rows)
                )
                n_done += 1
                pct = 100.0 * n_done / n_total_batches
                print(f"  [{n_done:>3d}/{n_total_batches}={pct:4.1f}%] "
                      f"{aoi_meta['name']:<18s} {sensor} {label}: "
                      f"{len(br_rows):>3d} scenes in {time.time()-t0:5.1f}s "
                      f"(elapsed {(time.time()-overall_t0)/60:5.1f}m)",
                      flush=True)
                time.sleep(INTER_BATCH_PAUSE_S)
            sensor_dedup = dedup_by_date(sensor_pertile)
            aoi_to_rows[aoi_key].extend(sensor_dedup)
            print(f"  {aoi_meta['name']:<18s} {sensor} dedup-by-date: "
                  f"{len(sensor_dedup)} rows (from {len(sensor_pertile)} "
                  f"per-tile rows)", flush=True)
    print()

    # 2. Per AOI: 75th percentile on cloud-filtered BSI (S30 ∪ L30).
    aoi_to_thresh = {}
    for aoi_meta in AOI_MAP:
        aoi_key = aoi_meta["key"]
        cf_bsis = [
            r["bsi"] for r in aoi_to_rows[aoi_key]
            if r["bsi"] is not None
            and r["cloud_fraction"] is not None
            and r["cloud_fraction"] < CLOUD_FILTER_SA1
        ]
        if len(cf_bsis) == 0:
            aoi_to_thresh[aoi_key] = None
        else:
            aoi_to_thresh[aoi_key] = float(np.percentile(cf_bsis, BARE_EPOCH_PERCENTILE))

    # 3. Apply bare_epoch_flag per scene (pre-fallback).
    for aoi_meta in AOI_MAP:
        aoi_key = aoi_meta["key"]
        thresh = aoi_to_thresh[aoi_key]
        for r in aoi_to_rows[aoi_key]:
            if r["bsi"] is not None and thresh is not None:
                r["bare_epoch_flag"] = bool(r["bsi"] > thresh)
            else:
                r["bare_epoch_flag"] = False

    # 4. Halt-rule check per (aoi, sensor).
    halts = []
    counts = {}
    for aoi_meta in AOI_MAP:
        aoi_key = aoi_meta["key"]
        for sensor in ("S30", "L30"):
            n_total_scenes = sum(
                1 for r in aoi_to_rows[aoi_key] if r["sensor"] == sensor
            )
            n_cloudfilt = sum(
                1 for r in aoi_to_rows[aoi_key]
                if r["sensor"] == sensor
                and r["cloud_fraction"] is not None
                and r["cloud_fraction"] < CLOUD_FILTER_SA1
            )
            n_bareepoch = sum(
                1 for r in aoi_to_rows[aoi_key]
                if r["sensor"] == sensor
                and r["cloud_fraction"] is not None
                and r["cloud_fraction"] < CLOUD_FILTER_SA1
                and r["bare_epoch_flag"]
            )
            counts[(aoi_key, sensor)] = {
                "total": n_total_scenes,
                "cloud_filt": n_cloudfilt,
                "bare_epoch_cloudfree": n_bareepoch,
            }
        s30_n = counts[(aoi_key, "S30")]["bare_epoch_cloudfree"]
        l30_n = counts[(aoi_key, "L30")]["bare_epoch_cloudfree"]
        if s30_n < HALT_FLOOR or l30_n < HALT_FLOOR:
            halts.append((aoi_key, s30_n, l30_n))

    # 5. Apply fallback for halted AOIs and write halt receipts.
    if halts:
        print("=== HALTS ===")
        for (aoi_key, s30_n, l30_n) in halts:
            aoi_meta = next(a for a in AOI_MAP if a["key"] == aoi_key)
            print(f"  {aoi_meta['name']}: S30 cloud-free bare-epoch = {s30_n}, "
                  f"L30 = {l30_n} (floor = {HALT_FLOOR})")
            n_fb = 0
            for r in aoi_to_rows[aoi_key]:
                if (r["cloud_fraction"] is not None
                        and r["cloud_fraction"] < CLOUD_FILTER_SA1):
                    r["bare_epoch_flag"] = True
                    n_fb += 1
                else:
                    r["bare_epoch_flag"] = False
            write_halt_receipt(
                aoi_meta, s30_n, l30_n, counts, aoi_to_thresh[aoi_key], n_fb
            )
        print()
    else:
        print("=== NO HALTS — all AOIs cleared the floor ===\n")

    # 6. Write per-AOI CSVs.
    print("=== Writing per-AOI CSVs ===")
    for aoi_meta in AOI_MAP:
        aoi_key = aoi_meta["key"]
        rows = sorted(
            aoi_to_rows[aoi_key],
            key=lambda r: (r["scene_date"], r["sensor"]),
        )
        out_path = OUT_DIR / f"{aoi_meta['stem']}_bsi_per_scene.csv"
        write_per_aoi_csv(out_path, rows)
        print(f"  wrote {out_path} ({len(rows)} rows)")

    # 7. Write SA1 summary.
    write_summary(aoi_to_thresh, counts, halts, aoi_to_rows, n_per_year)

    print("\nSA1 done.")


if __name__ == "__main__":
    main()

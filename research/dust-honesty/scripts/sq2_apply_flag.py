"""
SQ2 — apply confirmed DBB thresholds to the operational 228-scene set.

Inputs:
  - 3 AOIs × 76 months (2020-01 .. 2026-04) = 228 (aoi, year, month) pairs.
  - Per-AOI reference scenes locked in sq1d_references.json.
  - Calibration thresholds (post-confirmation) from sq1b_rerun_v2_confirmed:
      flag_v4         : dbb > 0.034 (KSP + Diriyah scope, applied all AOIs)
      flag_v3_ksp_only: dbb > 0.053 (KSP only)

Math: identical to sq1d_lolli_faithful.compute_dbb (single-image,
single sum+count reducer, no bestEffort, native scale 20m).

Scene selection priority:
  (a) If (aoi, year, month) appears in sq1bc_combined_calibration_confirmed.csv
      use the manifest-locked system_index from sq1d/sq1c manifests.
  (b) Else, GEE deterministic pick: lowest CLOUDY_PIXEL_PERCENTAGE in the
      year-month window over the AOI bbox; date asc as tiebreaker.
  (c) Best-pick CLOUDY_PIXEL_PERCENTAGE > 60 → no_usable_scene=True, dbb=NaN.

Manifest:
  - On first run: write sq2_scene_manifest.csv at the start of the sweep.
  - On subsequent runs: read the manifest first; deterministic-pick is
    fallback only with WARNING.
  - Cross-check: SQ2's chosen system_index for any (aoi, year, month) that
    overlaps sq1c_scene_manifest.csv or sq1d_scene_manifest.csv MUST match
    the prior manifest. Mismatch → raise.

Outputs:
  data/sq2_scene_manifest.csv
  data/sq2_dbb_operational.csv  (force-add per 442d7b0 precedent)
  data/sq2_cross_check_failures.csv (only if any failure)

Usage:
  python sq2_apply_flag.py
"""
from __future__ import annotations

import csv
import json
import math
import os
import sys
from dataclasses import dataclass
from pathlib import Path

import ee
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[3]
SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(SCRIPT_DIR))

from src.phase1_aois import get_bbox  # noqa: E402
from sq1d_lolli_faithful import (  # noqa: E402
    BANDS, SCALE_M, SCALE_DIV, SCL_VALID, WATER_RHO12_THRESHOLD,
    best_l1c_image, matching_l2a, scl_valid_mask, reflectance,
    compute_dbb, day_bounds, month_bounds,
)

DATA = ROOT / "research/dust-honesty/data"
REFS_JSON = DATA / "calibration" / "references_sq1d.json"
COMBINED_CAL_CSV = DATA / "calibration" / "combined_calibration_confirmed.csv"
SQ1D_MANIFEST = DATA / "calibration" / "manifest_sq1d.csv"
SQ1C_MANIFEST = DATA / "calibration" / "manifest_sq1c.csv"

OUT_MANIFEST = DATA / "sq2_scene_manifest.csv"
OUT_DBB = DATA / "sq2_dbb_operational.csv"
OUT_FAILURES = DATA / "sq2_cross_check_failures.csv"

AOIS = ["king_salman_park", "qiddiya_core", "diriyah_gate"]
YEAR_MIN = 2020
YEAR_MAX = 2026
MONTH_MAX_2026 = 4   # Jan..Apr
THRESH_V4 = 0.034
THRESH_V3_KSP = 0.053
SCENE_CLOUD_MAX = 60.0   # if best-pick CLOUDY_PIXEL_PERCENTAGE > this → unusable
AOI_CLOUD_FLAG_PCT = 30.0
CROSS_CHECK_TOL = 1e-4


# ---- (aoi, year, month) iteration -------------------------------------------

def all_slots():
    out = []
    for aoi in AOIS:
        for year in range(YEAR_MIN, YEAR_MAX + 1):
            mmax = MONTH_MAX_2026 if year == YEAR_MAX else 12
            for m in range(1, mmax + 1):
                out.append((aoi, year, m))
    return out


def ym_str(year, month):
    return f"{year:04d}-{month:02d}"


# ---- calibration index ------------------------------------------------------

def load_combined_calibration():
    """Return list of dicts from sq1bc_combined_calibration_confirmed.csv."""
    rows = []
    with open(COMBINED_CAL_CSV) as f:
        for r in csv.DictReader(f):
            rows.append(r)
    return rows


def load_prior_manifests():
    """Return {(aoi, ym): [manifest_row, ...]} merged from sq1d and sq1c."""
    prior = {}
    for path, default_source in [(SQ1D_MANIFEST, "sq1d"), (SQ1C_MANIFEST, "sq1c")]:
        with open(path) as f:
            for r in csv.DictReader(f):
                aoi = r["aoi"]
                # SQ1D month_slot is YYYY-MM; SQ1C is YYYY-MM-DD.
                ym = r["month_slot"][:7]
                key = (aoi, ym)
                row = dict(r)
                row["_origin_manifest"] = default_source
                prior.setdefault(key, []).append(row)
    return prior


def calibration_overlap_set(cal_rows):
    """Set of (aoi, year, month) that have at least one calibration row.

    SQ1D rows: date='YYYY-MM'; SQ1C rows: date='YYYY-MM-DD'.
    """
    out = set()
    for r in cal_rows:
        aoi = r["aoi"]
        date = r["date"]
        ym = date[:7]
        out.add((aoi, ym))
    return out


def cal_dbb_by_system_index(cal_rows, prior):
    """Map (aoi, system_index) -> calibration_dbb_faithful.

    Uses prior manifests to translate calibration rows' (aoi, date) to
    system_index. SQ1D: date='YYYY-MM' matches manifest month_slot directly.
    SQ1C: date='YYYY-MM-DD' matches manifest acquisition_date directly.
    """
    out = {}
    # Index prior rows by (aoi, acquisition_date) AND by (aoi, month_slot).
    by_acq = {}
    by_month = {}
    for rows in prior.values():
        for r in rows:
            by_acq.setdefault((r["aoi"], r["acquisition_date"]), []).append(r)
            by_month.setdefault((r["aoi"], r["month_slot"]), []).append(r)

    for c in cal_rows:
        aoi = c["aoi"]
        date = c["date"]
        if c["source"] == "SQ1D":
            cands = by_month.get((aoi, date), [])
        else:  # SQ1C
            cands = by_acq.get((aoi, date), [])
        if not cands:
            continue
        # For SQ1D: 1:1 by month_slot.
        # For SQ1C: 1:1 by acquisition_date (each SQ1C scene is unique date).
        if len(cands) > 1:
            # Should not happen given how the manifests are built; surface it.
            print(f"WARN: multiple manifest rows for ({aoi}, {date}); "
                  f"taking first.", file=sys.stderr)
        m = cands[0]
        out[(aoi, m["system_index"])] = float(c["dbb_faithful"])
    return out


# ---- manifest building ------------------------------------------------------

@dataclass
class SceneSelection:
    aoi: str
    year: int
    month: int
    system_index: str
    acquisition_date: str
    cloudy_pct_scene: float
    source: str          # 'cal_lock_sq1d' | 'cal_lock_sq1c' | 'gee_pick' | 'no_scene' | 'too_cloudy'
    notes: str = ""
    no_usable_scene: bool = False


def select_via_calibration(aoi, year, month, prior, cal_overlap):
    """If (aoi, ym) is in calibration overlap, choose the lowest-cloud
    manifest row from prior (sq1d/sq1c) for this slot.

    Returns SceneSelection or None.
    """
    ym = ym_str(year, month)
    if (aoi, ym) not in cal_overlap:
        return None
    candidates = prior.get((aoi, ym), [])
    if not candidates:
        return None
    candidates_sorted = sorted(
        candidates,
        key=lambda r: (float(r["cloudy_pixel_pct"]), r["acquisition_date"]),
    )
    pick = candidates_sorted[0]
    origin = pick["_origin_manifest"]
    return SceneSelection(
        aoi=aoi, year=year, month=month,
        system_index=pick["system_index"],
        acquisition_date=pick["acquisition_date"],
        cloudy_pct_scene=float(pick["cloudy_pixel_pct"]),
        source=f"cal_lock_{origin}",
        notes=f"locked from {origin}_manifest among {len(candidates)} cand",
    )


def select_via_gee(aoi, year, month, geom):
    """Lowest-cloud L1C scene over geom in the year-month window.

    Returns SceneSelection. May set no_usable_scene=True if no scene or
    cloud > SCENE_CLOUD_MAX.
    """
    ym = ym_str(year, month)
    start, end = month_bounds(ym)
    coll = (
        ee.ImageCollection("COPERNICUS/S2_HARMONIZED")
        .filterBounds(geom)
        .filterDate(start, end)
        .sort("CLOUDY_PIXEL_PERCENTAGE")
        .sort("system:time_start")  # secondary sort (date asc as tiebreaker)
    )
    # Re-sort by CLOUDY_PIXEL_PERCENTAGE primary; secondary is implicit
    # (GEE sort is stable).
    coll = (
        ee.ImageCollection("COPERNICUS/S2_HARMONIZED")
        .filterBounds(geom)
        .filterDate(start, end)
        .sort("system:time_start")        # earlier date first
        .sort("CLOUDY_PIXEL_PERCENTAGE")  # lowest cloud wins (stable)
    )
    n = coll.size().getInfo()
    if n == 0:
        return SceneSelection(
            aoi=aoi, year=year, month=month,
            system_index="", acquisition_date="",
            cloudy_pct_scene=float("nan"),
            source="no_scene",
            notes=f"no S2 L1C scene in {ym}",
            no_usable_scene=True,
        )
    img = coll.first()
    sys_idx = img.get("system:index").getInfo()
    cloud = float(img.get("CLOUDY_PIXEL_PERCENTAGE").getInfo())
    acq_date = ee.Date(img.get("system:time_start")).format("YYYY-MM-dd").getInfo()
    if cloud > SCENE_CLOUD_MAX:
        return SceneSelection(
            aoi=aoi, year=year, month=month,
            system_index=sys_idx, acquisition_date=acq_date,
            cloudy_pct_scene=cloud,
            source="too_cloudy",
            notes=f"best pick cloud={cloud:.2f}% > {SCENE_CLOUD_MAX}",
            no_usable_scene=True,
        )
    return SceneSelection(
        aoi=aoi, year=year, month=month,
        system_index=sys_idx, acquisition_date=acq_date,
        cloudy_pct_scene=cloud,
        source="gee_pick",
        notes=f"deterministic-pick across {n} candidates",
    )


def assert_manifest_match(sel: SceneSelection, prior):
    """For (aoi, ym) overlapping sq1c/sq1d manifests, sel.system_index must
    appear among the prior manifest rows.

    Raises RuntimeError on mismatch. Logs WARNING when sel was a deterministic
    pick that happened to land on (aoi, ym) covered by prior manifests but
    chose a different system_index.
    """
    ym = ym_str(sel.year, sel.month)
    rows = prior.get((sel.aoi, ym), [])
    if not rows:
        return
    prior_indexes = [r["system_index"] for r in rows]
    if sel.system_index in prior_indexes:
        return
    raise RuntimeError(
        f"manifest drift: ({sel.aoi}, {ym}) — sq2 chose "
        f"{sel.system_index!r} via {sel.source!r}, but prior manifest(s) "
        f"hold {prior_indexes!r}. Refusing to silently overwrite."
    )


def write_manifest(selections):
    fields = [
        "aoi", "year", "month", "month_slot",
        "system_index", "acquisition_date",
        "cloudy_pct_scene", "source", "no_usable_scene", "notes",
    ]
    with open(OUT_MANIFEST, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for s in selections:
            w.writerow({
                "aoi": s.aoi,
                "year": s.year,
                "month": s.month,
                "month_slot": ym_str(s.year, s.month),
                "system_index": s.system_index,
                "acquisition_date": s.acquisition_date,
                "cloudy_pct_scene": ("" if math.isnan(s.cloudy_pct_scene)
                                     else f"{s.cloudy_pct_scene:.6f}"),
                "source": s.source,
                "no_usable_scene": "True" if s.no_usable_scene else "False",
                "notes": s.notes,
            })


def read_manifest():
    """Return list[SceneSelection] from existing manifest, or [] if missing."""
    if not OUT_MANIFEST.exists():
        return []
    out = []
    with open(OUT_MANIFEST) as f:
        for r in csv.DictReader(f):
            cloud_str = r["cloudy_pct_scene"]
            cloud = float("nan") if cloud_str == "" else float(cloud_str)
            out.append(SceneSelection(
                aoi=r["aoi"],
                year=int(r["year"]),
                month=int(r["month"]),
                system_index=r["system_index"],
                acquisition_date=r["acquisition_date"],
                cloudy_pct_scene=cloud,
                source=r["source"],
                notes=r["notes"],
                no_usable_scene=(r["no_usable_scene"] == "True"),
            ))
    return out


# ---- DBB compute ------------------------------------------------------------

def load_references():
    with open(REFS_JSON) as f:
        cfg = json.load(f)
    return {aoi: meta["primary"]["date"] for aoi, meta in cfg["aois"].items()}


def get_reference(aoi, ref_date, geom):
    """Fetch L1C + L2A reference scene + system_index for the AOI."""
    r_start, r_end = day_bounds(ref_date)
    ref_l1c = best_l1c_image(geom, r_start, r_end)
    if ref_l1c is None:
        raise RuntimeError(f"no L1C reference for {aoi} on {ref_date}")
    ref_l2a = matching_l2a(ref_l1c, geom)
    if ref_l2a is None:
        raise RuntimeError(f"no L2A reference for {aoi} on {ref_date}")
    ref_sys_idx = ref_l1c.get("system:index").getInfo()
    return ref_l1c, ref_l2a, ref_sys_idx


def fetch_test_pair(aoi, system_index, acquisition_date, geom):
    """Fetch (test_l1c, test_l2a) for the manifest-locked system_index.

    Strategy: filter L1C collection by system:index directly. Same for L2A
    using `matching_l2a` on the resolved L1C image.
    """
    coll = (
        ee.ImageCollection("COPERNICUS/S2_HARMONIZED")
        .filterBounds(geom)
        .filter(ee.Filter.eq("system:index", system_index))
    )
    n = coll.size().getInfo()
    if n == 0:
        return None, None
    test_l1c = coll.first()
    test_l2a = matching_l2a(test_l1c, geom)
    return test_l1c, test_l2a


def cloud_pct_aoi(test_l1c, geom):
    """Percentage of cloudy pixels in AOI from QA60 (bits 10 + 11) at 60m."""
    qa60 = test_l1c.select("QA60")
    cloud_mask = (qa60.bitwiseAnd(1 << 10).neq(0)
                  .Or(qa60.bitwiseAnd(1 << 11).neq(0))
                  .rename("cloud"))
    stat = cloud_mask.reduceRegion(
        reducer=ee.Reducer.mean(),
        geometry=geom,
        scale=60,
        maxPixels=1e9,
    ).getInfo()
    val = stat.get("cloud")
    if val is None:
        return float("nan")
    return float(val) * 100.0


# ---- self-reference unit test -----------------------------------------------

def self_reference_test(refs):
    """Pick KSP, set test_scene = ref_scene, compute DBB, assert |DBB| < 1e-9."""
    aoi = "king_salman_park"
    ref_date = refs[aoi]
    bbox = get_bbox(aoi)
    geom = ee.Geometry.Rectangle(list(bbox))
    ref_l1c, ref_l2a, ref_idx = get_reference(aoi, ref_date, geom)
    out = compute_dbb(ref_l1c, ref_l1c, ref_l2a, ref_l2a, geom)
    val = out["dbb_faithful"]
    if val is None or abs(val) > 1e-9:
        raise RuntimeError(
            f"self-reference test FAILED for {aoi} on {ref_date}: "
            f"DBB={val} (expected ~0). n_valid={out['n_valid_pixels']} "
            f"n_total={out['n_total_pixels']}"
        )
    print(f"self-reference test PASSED ({aoi} {ref_date}): "
          f"DBB={val:+.2e}, n_valid={out['n_valid_pixels']}, "
          f"n_total={out['n_total_pixels']}")


# ---- per-scene compute orchestration ----------------------------------------

@dataclass
class DBBResult:
    aoi: str
    year: int
    month: int
    system_index: str
    scene_date: str
    ref_system_index: str
    dbb: float
    flag_v4: bool
    flag_v3_ksp_only: object   # bool | None
    cloud_pct_aoi: float
    cloud_flag_present: bool
    no_usable_scene: bool
    calibration_subset_match: bool


def compute_one(sel: SceneSelection, refs, ref_cache, cal_overlap):
    aoi = sel.aoi
    ym = ym_str(sel.year, sel.month)
    cal_match = (aoi, ym) in cal_overlap
    bbox = get_bbox(aoi)
    geom = ee.Geometry.Rectangle(list(bbox))

    if aoi not in ref_cache:
        ref_l1c, ref_l2a, ref_idx = get_reference(aoi, refs[aoi], geom)
        ref_cache[aoi] = (ref_l1c, ref_l2a, ref_idx)
    ref_l1c, ref_l2a, ref_idx = ref_cache[aoi]

    if sel.no_usable_scene:
        v3 = (None if aoi != "king_salman_park" else False)
        return DBBResult(
            aoi=aoi, year=sel.year, month=sel.month,
            system_index=sel.system_index,
            scene_date=sel.acquisition_date,
            ref_system_index=ref_idx,
            dbb=float("nan"),
            flag_v4=False,
            flag_v3_ksp_only=v3,
            cloud_pct_aoi=float("nan"),
            cloud_flag_present=False,
            no_usable_scene=True,
            calibration_subset_match=cal_match,
        )

    test_l1c, test_l2a = fetch_test_pair(aoi, sel.system_index,
                                         sel.acquisition_date, geom)
    if test_l1c is None or test_l2a is None:
        v3 = (None if aoi != "king_salman_park" else False)
        return DBBResult(
            aoi=aoi, year=sel.year, month=sel.month,
            system_index=sel.system_index,
            scene_date=sel.acquisition_date,
            ref_system_index=ref_idx,
            dbb=float("nan"),
            flag_v4=False,
            flag_v3_ksp_only=v3,
            cloud_pct_aoi=float("nan"),
            cloud_flag_present=False,
            no_usable_scene=True,
            calibration_subset_match=cal_match,
        )

    out = compute_dbb(test_l1c, ref_l1c, ref_l2a, test_l2a, geom)
    dbb_val = out["dbb_faithful"]

    cpct = cloud_pct_aoi(test_l1c, geom)
    cloud_flag = (not math.isnan(cpct)) and (cpct > AOI_CLOUD_FLAG_PCT)

    if dbb_val is None or (isinstance(dbb_val, float) and math.isnan(dbb_val)):
        v3 = (None if aoi != "king_salman_park" else False)
        return DBBResult(
            aoi=aoi, year=sel.year, month=sel.month,
            system_index=sel.system_index,
            scene_date=sel.acquisition_date,
            ref_system_index=ref_idx,
            dbb=float("nan"),
            flag_v4=False,
            flag_v3_ksp_only=v3,
            cloud_pct_aoi=cpct,
            cloud_flag_present=cloud_flag,
            no_usable_scene=True,
            calibration_subset_match=cal_match,
        )

    flag_v4 = bool(dbb_val > THRESH_V4)
    if aoi == "king_salman_park":
        flag_v3 = bool(dbb_val > THRESH_V3_KSP)
    else:
        flag_v3 = None

    return DBBResult(
        aoi=aoi, year=sel.year, month=sel.month,
        system_index=sel.system_index,
        scene_date=sel.acquisition_date,
        ref_system_index=ref_idx,
        dbb=float(dbb_val),
        flag_v4=flag_v4,
        flag_v3_ksp_only=flag_v3,
        cloud_pct_aoi=cpct,
        cloud_flag_present=cloud_flag,
        no_usable_scene=False,
        calibration_subset_match=cal_match,
    )


def write_operational_csv(results):
    fields = [
        "aoi", "year", "month", "system_index", "scene_date",
        "ref_system_index", "dbb",
        "flag_v4", "flag_v3_ksp_only",
        "cloud_pct_aoi", "cloud_flag_present",
        "no_usable_scene", "calibration_subset_match",
    ]
    with open(OUT_DBB, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in results:
            w.writerow({
                "aoi": r.aoi,
                "year": r.year,
                "month": r.month,
                "system_index": r.system_index,
                "scene_date": r.scene_date,
                "ref_system_index": r.ref_system_index,
                "dbb": ("" if (isinstance(r.dbb, float) and math.isnan(r.dbb))
                        else f"{r.dbb:.10f}"),
                "flag_v4": "True" if r.flag_v4 else "False",
                "flag_v3_ksp_only": (""
                                     if r.flag_v3_ksp_only is None
                                     else ("True" if r.flag_v3_ksp_only
                                           else "False")),
                "cloud_pct_aoi": ("" if math.isnan(r.cloud_pct_aoi)
                                  else f"{r.cloud_pct_aoi:.4f}"),
                "cloud_flag_present": "True" if r.cloud_flag_present else "False",
                "no_usable_scene": "True" if r.no_usable_scene else "False",
                "calibration_subset_match": ("True"
                                             if r.calibration_subset_match
                                             else "False"),
            })


# ---- cross-check ------------------------------------------------------------

def cross_check(results, cal_dbb_index):
    """Compare SQ2 dbb against calibration dbb for any (aoi, system_index)
    pair found in cal_dbb_index. Returns list of failure dicts."""
    failures = []
    n_overlap = 0
    n_pass = 0
    for r in results:
        key = (r.aoi, r.system_index)
        if key not in cal_dbb_index:
            continue
        n_overlap += 1
        cal_v = cal_dbb_index[key]
        if isinstance(r.dbb, float) and math.isnan(r.dbb):
            failures.append({
                "aoi": r.aoi, "year": r.year, "month": r.month,
                "system_index": r.system_index,
                "scene_date": r.scene_date,
                "sq2_dbb": "NaN",
                "calibration_dbb": f"{cal_v:.10f}",
                "delta": "NaN",
                "reason": "sq2_dbb_is_nan_but_calibration_has_value",
            })
            continue
        delta = r.dbb - cal_v
        if abs(delta) < CROSS_CHECK_TOL:
            n_pass += 1
        else:
            failures.append({
                "aoi": r.aoi, "year": r.year, "month": r.month,
                "system_index": r.system_index,
                "scene_date": r.scene_date,
                "sq2_dbb": f"{r.dbb:.10f}",
                "calibration_dbb": f"{cal_v:.10f}",
                "delta": f"{delta:+.10f}",
                "reason": f"abs_delta {abs(delta):.6e} >= tol {CROSS_CHECK_TOL}",
            })
    return n_overlap, n_pass, failures


def write_cross_check_failures(failures):
    if not failures:
        if OUT_FAILURES.exists():
            OUT_FAILURES.unlink()
        return
    fields = ["aoi", "year", "month", "system_index", "scene_date",
              "sq2_dbb", "calibration_dbb", "delta", "reason"]
    with open(OUT_FAILURES, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in failures:
            w.writerow(r)


# ---- main -------------------------------------------------------------------

def main():
    load_dotenv(ROOT / ".env")
    ee.Initialize(project=os.environ["GEE_PROJECT"])

    print(f"SQ2 — apply confirmed DBB thresholds to operational set")
    print(f"  V4 threshold (all AOIs):     {THRESH_V4:+.4f}")
    print(f"  V3 threshold (KSP only):     {THRESH_V3_KSP:+.4f}")
    print(f"  Scene cloud max:             {SCENE_CLOUD_MAX:.0f}%")
    print(f"  AOI-local cloud flag at:     >{AOI_CLOUD_FLAG_PCT:.0f}%")
    print()

    refs = load_references()
    print(f"References: {refs}")
    print()

    print("Self-reference unit test ...")
    self_reference_test(refs)
    print()

    cal_rows = load_combined_calibration()
    cal_overlap = calibration_overlap_set(cal_rows)
    print(f"Calibration rows loaded: {len(cal_rows)}")
    print(f"Calibration (aoi, ym) overlap slots: {len(cal_overlap)}")

    prior = load_prior_manifests()
    cal_dbb_index = cal_dbb_by_system_index(cal_rows, prior)
    print(f"Calibration scenes indexed by (aoi, system_index): "
          f"{len(cal_dbb_index)}")
    print()

    # --- selection phase ---
    slots = all_slots()
    if len(slots) != 228:
        raise RuntimeError(f"expected 228 slots, got {len(slots)}")

    existing = read_manifest()
    if existing:
        print(f"Reading existing sq2_scene_manifest.csv "
              f"({len(existing)} rows). New picks WARN-logged.")
        manifest_lookup = {(s.aoi, s.year, s.month): s for s in existing}
    else:
        print("No existing sq2_scene_manifest.csv — building fresh.")
        manifest_lookup = {}

    selections = []
    n_cal_lock = n_gee = n_no_scene = n_too_cloudy = n_existing = 0
    for i, (aoi, year, month) in enumerate(slots, 1):
        key = (aoi, year, month)
        if key in manifest_lookup:
            sel = manifest_lookup[key]
            n_existing += 1
            print(f"[{i:3d}/228] {aoi} {ym_str(year, month)} "
                  f"existing-manifest {sel.system_index} ({sel.source})")
        else:
            sel = select_via_calibration(aoi, year, month, prior, cal_overlap)
            if sel is None:
                bbox = get_bbox(aoi)
                geom = ee.Geometry.Rectangle(list(bbox))
                if existing:
                    print(f"WARNING: ({aoi}, {ym_str(year, month)}) not in "
                          f"existing manifest, falling back to GEE pick")
                sel = select_via_gee(aoi, year, month, geom)
                if sel.source == "no_scene":
                    n_no_scene += 1
                elif sel.source == "too_cloudy":
                    n_too_cloudy += 1
                else:
                    n_gee += 1
            else:
                n_cal_lock += 1
            print(f"[{i:3d}/228] {aoi} {ym_str(year, month)} "
                  f"{sel.source} {sel.system_index} "
                  f"cloud={sel.cloudy_pct_scene if not math.isnan(sel.cloudy_pct_scene) else float('nan'):.2f}")
            assert_manifest_match(sel, prior)
        selections.append(sel)

    # Write/refresh manifest immediately so it's locked before compute.
    write_manifest(selections)
    print()
    print(f"Manifest written: {OUT_MANIFEST}")
    print(f"  cal_lock_sq1d/sq1c picks: {n_cal_lock}")
    print(f"  gee_pick                : {n_gee}")
    print(f"  too_cloudy              : {n_too_cloudy}")
    print(f"  no_scene                : {n_no_scene}")
    print(f"  reused from existing    : {n_existing}")
    print()

    # --- compute phase ---
    ref_cache = {}
    results = []
    for i, sel in enumerate(selections, 1):
        try:
            res = compute_one(sel, refs, ref_cache, cal_overlap)
        except Exception as e:
            print(f"[compute {i:3d}/228] ERROR {sel.aoi} {ym_str(sel.year, sel.month)}: {e}")
            res = DBBResult(
                aoi=sel.aoi, year=sel.year, month=sel.month,
                system_index=sel.system_index,
                scene_date=sel.acquisition_date,
                ref_system_index=ref_cache.get(sel.aoi, ("", "", ""))[2]
                                  if sel.aoi in ref_cache else "",
                dbb=float("nan"),
                flag_v4=False,
                flag_v3_ksp_only=(False if sel.aoi == "king_salman_park" else None),
                cloud_pct_aoi=float("nan"),
                cloud_flag_present=False,
                no_usable_scene=True,
                calibration_subset_match=(sel.aoi, ym_str(sel.year, sel.month)) in cal_overlap,
            )
        if res.no_usable_scene or (isinstance(res.dbb, float) and math.isnan(res.dbb)):
            tag = "UNUSABLE"
            dbb_str = "NaN"
        else:
            tag = "ok"
            dbb_str = f"{res.dbb:+.4f}"
        v3_str = ("—" if res.flag_v3_ksp_only is None
                  else ("V3+" if res.flag_v3_ksp_only else "V3-"))
        v4_str = "V4+" if res.flag_v4 else "V4-"
        cloud_str = ("NaN" if math.isnan(res.cloud_pct_aoi)
                     else f"{res.cloud_pct_aoi:5.2f}%")
        print(f"[compute {i:3d}/228] {res.aoi:20s} {ym_str(res.year, res.month)} "
              f"DBB={dbb_str} {v4_str} {v3_str} aoi_cloud={cloud_str} {tag}")
        results.append(res)

    write_operational_csv(results)
    print()
    print(f"Wrote {OUT_DBB}")

    # --- cross-check ---
    n_overlap, n_pass, failures = cross_check(results, cal_dbb_index)
    write_cross_check_failures(failures)
    print()
    print(f"Cross-check vs sq1bc_combined_calibration_confirmed.csv:")
    print(f"  overlap rows: {n_overlap}")
    print(f"  passes      : {n_pass}")
    print(f"  failures    : {len(failures)}")
    if failures:
        print(f"  → wrote {OUT_FAILURES}")
        for fa in failures[:10]:
            print(f"    {fa['aoi']} {fa['year']}-{fa['month']:02d} "
                  f"{fa['system_index']}: sq2={fa['sq2_dbb']} "
                  f"cal={fa['calibration_dbb']} delta={fa['delta']}")
        if len(failures) > 10:
            print(f"    ... ({len(failures) - 10} more in CSV)")
    else:
        print("  → no failures CSV written")

    # --- summary headline ---
    by_aoi = {a: [] for a in AOIS}
    for r in results:
        by_aoi[r.aoi].append(r)
    print()
    print("Headline by AOI:")
    print(f"{'aoi':<20s} {'months':>7s} {'usable':>7s} {'V4 fires':>9s} "
          f"{'V3 fires':>9s} {'cloud_aoi>30%':>14s}")
    for aoi in AOIS:
        rs = by_aoi[aoi]
        usable = sum(1 for r in rs if not r.no_usable_scene)
        v4_fires = sum(1 for r in rs if r.flag_v4)
        v3_fires = sum(1 for r in rs
                       if r.flag_v3_ksp_only is True)
        cloudy = sum(1 for r in rs if r.cloud_flag_present)
        v3_str = "—" if aoi != "king_salman_park" else f"{v3_fires}"
        print(f"{aoi:<20s} {len(rs):>7d} {usable:>7d} {v4_fires:>9d} "
              f"{v3_str:>9s} {cloudy:>14d}")

    return 0


if __name__ == "__main__":
    sys.exit(main())

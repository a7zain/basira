"""
Phase 4.11 — Hotspot Cell NDVI Time Series + Onset Detection
==============================================================
For each top-10 hotspot cell, computes monthly mean NDVI using windowed
rasterio reads, then detects the estimated onset of change via a
sustained-drop-below-baseline heuristic.

Outputs:
    webapp/data/phase4/hotspots.json           — augmented with onset fields
    webapp/data/phase4/hotspot_cell_timeseries.json — full per-cell series

Usage:
    python src/phase4_cell_timeseries.py
"""

import json
import os
import sys
import time

import numpy as np
import rasterio
import rasterio.windows

sys.path.insert(0, os.path.join(os.path.dirname(__file__)))
from phase4_ndvi_timeseries import (
    list_monthly_tifs,
    load_mask,
    compute_ndvi_from_bands,
    MONTHLY_DIR,
    BAND_RED,
    BAND_NIR,
)

# ── Config ──────────────────────────────────────────────────
HOTSPOTS_JSON = "webapp/data/phase4/hotspots.json"
OUT_TIMESERIES = "webapp/data/phase4/hotspot_cell_timeseries.json"
THUMB_SIZE = 256
IMG_H = 1687
IMG_W = 2002
MIN_VALID_PIXELS = 500
BASELINE_MONTHS = 18  # Jan 2020 – Jun 2021


def compute_cell_timeseries(scenes, mask, row, col):
    """Compute monthly mean NDVI for one grid cell using windowed reads."""
    y0 = row * THUMB_SIZE
    x0 = col * THUMB_SIZE
    y1 = min(y0 + THUMB_SIZE, IMG_H)
    x1 = min(x0 + THUMB_SIZE, IMG_W)
    ch = y1 - y0
    cw = x1 - x0

    cell_mask = mask[y0:y1, x0:x1]
    window = rasterio.windows.Window(x0, y0, cw, ch)

    series = []
    for year, month, path in scenes:
        with rasterio.open(path) as src:
            red = src.read(BAND_RED, window=window).astype(np.float32)
            nir = src.read(BAND_NIR, window=window).astype(np.float32)

        ndvi = compute_ndvi_from_bands(red, nir)

        # Mask nodata (both bands zero) and invalid-mask pixels
        nodata = (red == 0) & (nir == 0)
        valid = cell_mask & ~nodata
        n_valid = valid.sum()

        if n_valid < MIN_VALID_PIXELS:
            continue

        mean_ndvi = float(np.nanmean(ndvi[valid]))
        date_str = f"{year}-{month:02d}-15"
        series.append({"date": date_str, "mean_ndvi": round(mean_ndvi, 6)})

    return series


def detect_onset(series):
    """Detect earliest sustained NDVI drop below baseline.

    Returns (est_onset, delta_ndvi, baseline_ndvi) where est_onset is
    "YYYY-MM" or None.
    """
    if len(series) < BASELINE_MONTHS + 2:
        return None, None, None

    values = np.array([p["mean_ndvi"] for p in series])
    dates = [p["date"] for p in series]

    # Baseline: first 18 months
    baseline = values[:BASELINE_MONTHS].mean()
    baseline_std = values[:BASELINE_MONTHS].std()

    if baseline_std < 1e-6:
        baseline_std = 0.01  # prevent trivial threshold

    threshold = baseline - baseline_std

    # Walk forward from month 19, find sustained drop (>=2 consecutive)
    est_onset = None
    for i in range(BASELINE_MONTHS, len(values) - 1):
        if values[i] < threshold and values[i + 1] < threshold:
            est_onset = dates[i][:7]  # "YYYY-MM"
            break

    # Delta: mean of last 12 months minus baseline
    last_12 = values[-12:] if len(values) >= 12 else values
    delta_ndvi = float(last_12.mean() - baseline)

    return est_onset, round(delta_ndvi, 3), round(float(baseline), 3)


def main():
    t0 = time.time()
    print("Phase 4.11 — Hotspot Cell NDVI Time Series + Onset Detection")
    print("=" * 60)

    # ── Load prerequisites ────────────────────────────────
    with open(HOTSPOTS_JSON) as f:
        hotspot_data = json.load(f)
    hotspots = hotspot_data["hotspots"]
    print(f"  Hotspots: {len(hotspots)}")

    mask = load_mask()
    scenes = list_monthly_tifs(MONTHLY_DIR)
    print(f"  Monthly scenes: {len(scenes)}")

    # ── Compute per-cell time series ──────────────────────
    all_timeseries = {}

    print(f"\n  {'Cell':>5}  {'Points':>6}  {'Baseline':>8}  {'Onset':>10}  {'ΔNDVI':>7}")
    print(f"  {'-'*5}  {'-'*6}  {'-'*8}  {'-'*10}  {'-'*7}")

    for hs in hotspots:
        cell_id = hs["cell_id"]
        r, c = [int(x) for x in cell_id.split("_")]

        series = compute_cell_timeseries(scenes, mask, r, c)
        all_timeseries[cell_id] = series

        est_onset, delta_ndvi, baseline_ndvi = detect_onset(series)

        # Augment hotspot record
        hs["est_onset"] = est_onset
        hs["delta_ndvi"] = delta_ndvi
        hs["baseline_ndvi"] = baseline_ndvi

        onset_str = est_onset or "none"
        delta_str = f"{delta_ndvi:+.3f}" if delta_ndvi is not None else "n/a"
        base_str = f"{baseline_ndvi:.3f}" if baseline_ndvi is not None else "n/a"

        print(f"  {cell_id:>5}  {len(series):>6}  {base_str:>8}  {onset_str:>10}  {delta_str:>7}")

    # ── Save augmented hotspots ───────────────────────────
    with open(HOTSPOTS_JSON, "w") as f:
        json.dump(hotspot_data, f, indent=2)
    print(f"\n  Saved: {HOTSPOTS_JSON}")

    # ── Save cell timeseries ──────────────────────────────
    with open(OUT_TIMESERIES, "w") as f:
        json.dump(all_timeseries, f, indent=2)
    print(f"  Saved: {OUT_TIMESERIES} ({os.path.getsize(OUT_TIMESERIES) / 1024:.0f} KB)")

    elapsed = time.time() - t0
    print(f"\n  Runtime: {elapsed:.1f}s")
    print("=" * 60)


if __name__ == "__main__":
    main()

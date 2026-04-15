"""
Phase 4.7 — Pixel-Level Time-Series Classification
====================================================
Builds per-pixel NDVI feature vectors from 76 monthly scenes, then
clusters with KMeans (k=5) to identify distinct temporal behaviors.

Processes in row-strip chunks to avoid loading the full cube into RAM.

Outputs:
    outputs/phase4_pixel_classes.tif           — uint8 raster (0=nodata, 1-5=cluster)
    outputs/phase4_cluster_trajectories.json   — per-cluster mean NDVI trajectory

Usage:
    python src/phase4_pixel_classify.py
"""

import json
import os
import sys
import time

import numpy as np
import rasterio
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler

# Import reusable helpers from the existing NDVI timeseries module
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
OUT_DIR = "outputs"
CHUNK_ROWS = 200
N_CLUSTERS = 5
RANDOM_STATE = 42


def extract_features(ndvi_cube):
    """Compute 5 features per pixel from an NDVI time-series cube.

    Args:
        ndvi_cube: (n_times, n_pixels) float32, may contain NaN

    Returns:
        features: (n_pixels, 5) float32
    """
    n_times, n_pixels = ndvi_cube.shape
    features = np.full((n_pixels, 5), np.nan, dtype=np.float32)
    t = np.arange(n_times, dtype=np.float32)

    # a. mean NDVI
    features[:, 0] = np.nanmean(ndvi_cube, axis=0)

    # b. trend slope via least-squares (vectorized per-pixel)
    # For each pixel, fit y = a*t + b using only non-NaN timesteps
    # Vectorized approach: process all pixels where we have enough data
    mid = n_times // 2

    for px in range(n_pixels):
        series = ndvi_cube[:, px]
        valid = ~np.isnan(series)
        n_valid = valid.sum()
        if n_valid < 4:
            continue
        t_valid = t[valid]
        s_valid = series[valid]

        coeffs = np.polyfit(t_valid, s_valid, 1)
        features[px, 1] = coeffs[0]  # slope

        # c. seasonal amplitude: std of residuals from linear fit
        fitted = coeffs[0] * t_valid + coeffs[1]
        features[px, 2] = np.std(s_valid - fitted)

    # d. first half mean (months 0-37)
    features[:, 3] = np.nanmean(ndvi_cube[:mid, :], axis=0)

    # e. second half mean (months 38-75)
    features[:, 4] = np.nanmean(ndvi_cube[mid:, :], axis=0)

    return features


def main():
    t0 = time.time()
    print("Phase 4.7 — Pixel-Level Time-Series Classification")
    print("=" * 55)

    # ── Load prerequisites ─────────────────────────────────
    mask = load_mask()
    height, width = mask.shape
    print(f"  Raster: {height} x {width}")
    print(f"  Valid pixels: {mask.sum():,} / {mask.size:,} ({100*mask.sum()/mask.size:.1f}%)")

    scenes = list_monthly_tifs(MONTHLY_DIR)
    n_times = len(scenes)
    print(f"  Monthly scenes: {n_times}")
    if n_times == 0:
        print("ERROR: no monthly TIFFs found")
        return

    # Get CRS and transform from first scene (for output raster)
    with rasterio.open(scenes[0][2]) as src:
        profile = src.profile.copy()

    # ── Chunk processing ───────────────────────────────────
    all_features = []
    all_rows = []
    all_cols = []
    # Also accumulate per-pixel NDVI means per timestep for trajectory output
    # We'll store sum and count per cluster later; for now store raw trajectories
    # of valid pixels — but that's too large. Instead, accumulate per-chunk
    # trajectory sums and reconstruct per-cluster after labeling.
    # Strategy: store (row, col) -> we can re-read scenes per cluster.
    # Better: store the mean NDVI per timestep for each valid pixel alongside features.
    all_trajectories = []  # list of (n_valid_in_chunk, n_times) arrays

    n_chunks = (height + CHUNK_ROWS - 1) // CHUNK_ROWS
    print(f"\n  Processing {n_chunks} chunks of {CHUNK_ROWS} rows each...")

    for chunk_idx in range(n_chunks):
        r0 = chunk_idx * CHUNK_ROWS
        r1 = min(r0 + CHUNK_ROWS, height)
        chunk_h = r1 - r0
        chunk_mask = mask[r0:r1, :]

        n_valid = chunk_mask.sum()
        if n_valid == 0:
            continue

        # Build NDVI sub-cube: (n_times, chunk_h, width)
        ndvi_cube = np.full((n_times, chunk_h, width), np.nan, dtype=np.float32)

        for ti, (year, month, path) in enumerate(scenes):
            with rasterio.open(path) as src:
                red = src.read(BAND_RED, window=rasterio.windows.Window(0, r0, width, chunk_h)).astype(np.float32)
                nir = src.read(BAND_NIR, window=rasterio.windows.Window(0, r0, width, chunk_h)).astype(np.float32)
            ndvi = compute_ndvi_from_bands(red, nir)
            # Mask nodata: where both red and nir are 0 (sentinel for nodata)
            nodata = (red == 0) & (nir == 0)
            ndvi[nodata] = np.nan
            ndvi_cube[ti] = ndvi

        # Apply valid mask: set invalid pixels to NaN across all times
        invalid = ~chunk_mask
        ndvi_cube[:, invalid] = np.nan

        # Extract valid pixel positions
        valid_rows, valid_cols = np.where(chunk_mask)
        valid_rows += r0  # absolute row indices

        # Reshape to (n_times, n_valid_pixels) for feature extraction
        pixel_series = ndvi_cube[:, chunk_mask]  # (n_times, n_valid)

        # Compute features
        feats = extract_features(pixel_series)

        all_features.append(feats)
        all_rows.append(valid_rows)
        all_cols.append(valid_cols)
        all_trajectories.append(pixel_series)  # (n_times, n_valid)

        elapsed = time.time() - t0
        print(f"    Chunk {chunk_idx+1}/{n_chunks}: rows {r0}-{r1-1}, "
              f"{n_valid:,} valid pixels  [{elapsed:.0f}s]")

    # ── Assemble global arrays ─────────────────────────────
    features = np.concatenate(all_features, axis=0)
    rows = np.concatenate(all_rows)
    cols = np.concatenate(all_cols)
    trajectories = np.concatenate(all_trajectories, axis=1)  # (n_times, n_total_valid)

    n_total = features.shape[0]
    print(f"\n  Total valid pixels: {n_total:,}")
    print(f"  Feature matrix: {features.shape}")

    # Drop pixels with any NaN features (shouldn't be many)
    valid_feat = ~np.any(np.isnan(features), axis=1)
    n_dropped = n_total - valid_feat.sum()
    if n_dropped > 0:
        print(f"  Dropped {n_dropped:,} pixels with NaN features")
        features = features[valid_feat]
        rows = rows[valid_feat]
        cols = cols[valid_feat]
        trajectories = trajectories[:, valid_feat]
        n_total = features.shape[0]

    # ── Standardize and cluster ────────────────────────────
    print(f"\n  Standardizing features...")
    scaler = StandardScaler()
    features_scaled = scaler.fit_transform(features)

    print(f"  Running KMeans (k={N_CLUSTERS}, n_init=10)...")
    km = KMeans(n_clusters=N_CLUSTERS, random_state=RANDOM_STATE, n_init=10)
    labels = km.fit_predict(features_scaled)

    cluster_time = time.time() - t0
    print(f"  Clustering complete [{cluster_time:.0f}s]")

    # ── Build output raster ────────────────────────────────
    out_raster = np.zeros((height, width), dtype=np.uint8)
    out_raster[rows, cols] = labels + 1  # 1-indexed

    os.makedirs(OUT_DIR, exist_ok=True)
    out_path = os.path.join(OUT_DIR, "phase4_pixel_classes.tif")
    out_profile = profile.copy()
    out_profile.update(dtype="uint8", count=1, nodata=0, compress="lzw")
    with rasterio.open(out_path, "w", **out_profile) as dst:
        dst.write(out_raster, 1)
    print(f"\n  Saved: {out_path}")

    # ── Per-cluster diagnostics ────────────────────────────
    feature_names = ["mean_ndvi", "trend_slope", "seasonal_amp",
                     "first_half_mean", "second_half_mean"]
    cluster_trajectories = {}

    print(f"\n{'='*55}")
    print("  Per-Cluster Diagnostics")
    print(f"{'='*55}")

    for c in range(N_CLUSTERS):
        cmask = labels == c
        count = cmask.sum()
        pct = 100 * count / n_total

        print(f"\n  Cluster {c+1}  ({count:,} pixels, {pct:.1f}% of valid area)")
        print(f"  {'-'*45}")

        # Feature means
        feat_means = features[cmask].mean(axis=0)
        for i, name in enumerate(feature_names):
            print(f"    {name:20s}: {feat_means[i]:+.6f}")

        # Mean NDVI trajectory (76 months)
        traj = np.nanmean(trajectories[:, cmask], axis=1)
        cluster_trajectories[f"cluster_{c+1}"] = {
            "pixel_count": int(count),
            "pixel_pct": round(float(pct), 2),
            "feature_means": {name: round(float(feat_means[i]), 6)
                              for i, name in enumerate(feature_names)},
            "monthly_ndvi": [round(float(v), 4) if not np.isnan(v) else None
                             for v in traj],
        }

        # Print condensed trajectory (every 6th month for readability)
        dates = [f"{y}-{m:02d}" for y, m, _ in scenes]
        print(f"    {'trajectory (every 6 months)':20s}:")
        for j in range(0, n_times, 6):
            print(f"      {dates[j]}: {traj[j]:.4f}")

    # Add metadata
    cluster_trajectories["_meta"] = {
        "n_clusters": N_CLUSTERS,
        "n_valid_pixels": int(n_total),
        "n_times": n_times,
        "dates": [f"{y}-{m:02d}" for y, m, _ in scenes],
        "feature_names": feature_names,
    }

    traj_path = os.path.join(OUT_DIR, "phase4_cluster_trajectories.json")
    with open(traj_path, "w") as f:
        json.dump(cluster_trajectories, f, indent=2)
    print(f"\n  Saved: {traj_path}")

    total_time = time.time() - t0
    print(f"\n  Total runtime: {total_time:.1f}s")


if __name__ == "__main__":
    main()

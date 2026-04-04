"""
SAR Change Detection — ML-based Change Classification
======================================================
Clusters valid pixels using K-Means and GMM on a multi-band
feature stack, then interprets clusters by their radiometric
signatures.

Usage:
    python src/classify.py
"""

import numpy as np
import rasterio
from sklearn.cluster import KMeans
from sklearn.mixture import GaussianMixture
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import silhouette_score
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import os

from utils import TARGET_CRS

# ── Paths ───────────────────────────────────────────────────
PROC_DIR = "data/processed"
OUT_DIR  = "outputs"

AMP_2022_TIF  = f"{PROC_DIR}/amplitude_2022.tif"
AMP_2024_TIF  = f"{PROC_DIR}/amplitude_2024.tif"
DB_2022_TIF   = f"{PROC_DIR}/db_2022.tif"
DB_2024_TIF   = f"{PROC_DIR}/db_2024.tif"
CHANGE_TIF    = f"{OUT_DIR}/change_continuous.tif"
OUT_CLASS_TIF = f"{OUT_DIR}/ml_classification.tif"
OUT_PNG       = f"{OUT_DIR}/07_ml_classification.png"

K = 5  # number of clusters


# ── Class interpretation ────────────────────────────────────
def interpret_clusters(centroids):
    """
    Assign human-readable labels to clusters based on centroid
    feature values.

    Features: [db_2022, db_2024, |change|, signed_change]

    Logic:
      - High dB in both years + small change       → stable urban
      - Low dB in both years + small change         → stable desert
      - Large positive change (db_2024 >> db_2022)  → new construction
      - Large negative change (db_2022 >> db_2024)  → land clearing
      - Moderate change either direction             → seasonal variation
    """
    # Collect stable clusters and rank by mean dB to distinguish
    # high-reflectivity urban from low-reflectivity desert/open
    stable = []
    labels = [None] * len(centroids)

    for i, c in enumerate(centroids):
        db22, db24, abs_ch, signed_ch = c
        mean_db = (db22 + db24) / 2

        if abs_ch > 2.5 and signed_ch > 2.0:
            labels[i] = "New construction"
        elif abs_ch > 2.5 and signed_ch < -2.0:
            labels[i] = "Land clearing / demolition"
        else:
            stable.append((i, mean_db))

    # Sort stable clusters by mean dB and assign graded labels
    stable.sort(key=lambda x: -x[1])  # highest dB first
    stable_labels = ["Stable urban (dense)", "Stable urban (moderate)",
                     "Stable desert / open", "Stable desert / open",
                     "Stable desert / open"]
    for rank, (idx, _) in enumerate(stable):
        labels[idx] = stable_labels[min(rank, len(stable_labels) - 1)]

    return labels


# ── Colours for each semantic class (visually distinct) ────
CLASS_COLORS = {
    "Stable urban (dense)":       "#4A4A4A",  # dark grey
    "Stable urban (moderate)":    "#C4A882",  # tan / beige
    "Stable desert / open":       "#F0E068",  # sand yellow
    "New construction":           "#D32F2F",  # red
    "Land clearing / demolition": "#1565C0",  # blue
    "Seasonal / minor change":    "#66c2a5",  # teal (unused with k=5)
}
FALLBACK_PALETTE = ["#4A4A4A", "#C4A882", "#F0E068", "#D32F2F", "#1565C0"]


def main():
    os.makedirs(OUT_DIR, exist_ok=True)

    # ── Load data ──────────────────────────────────────────
    print("Loading rasters...")
    with rasterio.open(DB_2022_TIF) as src:
        db_2022   = src.read(1)
        transform = src.transform
        crs       = src.crs
    with rasterio.open(DB_2024_TIF) as src:
        db_2024 = src.read(1)
    with rasterio.open(CHANGE_TIF) as src:
        change = src.read(1)

    # Load amplitude rasters to detect true nodata (zero amplitude
    # pixels that the Lee filter may have smoothed to small values)
    with rasterio.open(AMP_2022_TIF) as src:
        amp_2022 = src.read(1)
    with rasterio.open(AMP_2024_TIF) as src:
        amp_2024 = src.read(1)

    h, w = db_2022.shape
    print(f"  Shape: {h} x {w}")

    # ── Build feature stack ────────────────────────────────
    print("\nBuilding feature stack...")
    # Robust nodata mask: exclude pixels where EITHER scene has
    # zero/near-zero amplitude (original nodata) OR extreme low dB.
    # The Lee filter (7x7) can smooth edge pixels, so amplitude
    # values near scene borders may be small but non-zero — catch
    # these with a conservative amplitude threshold.
    valid_mask = (
        np.isfinite(db_2022) & np.isfinite(db_2024) &
        (db_2022 > -30) & (db_2024 > -30) &
        (amp_2022 > 1.0) & (amp_2024 > 1.0)
    )
    n_valid = valid_mask.sum()
    n_total = h * w
    n_nodata = n_total - n_valid
    print(f"  Valid pixels: {n_valid:,} / {n_total:,} "
          f"({100*n_valid/n_total:.1f}%)")
    print(f"  Nodata pixels: {n_nodata:,} ({100*n_nodata/n_total:.1f}%)")

    abs_change = np.abs(change)

    features = np.column_stack([
        db_2022[valid_mask],
        db_2024[valid_mask],
        abs_change[valid_mask],
        change[valid_mask],       # signed change
    ])
    feature_names = ["dB 2022", "dB 2024", "|Change|", "Change (signed)"]
    print(f"  Feature matrix: {features.shape}")
    for i, name in enumerate(feature_names):
        col = features[:, i]
        print(f"    {name:>18}: mean={col.mean():+.2f}  std={col.std():.2f}  "
              f"range=[{col.min():.1f}, {col.max():.1f}]")

    # ── Standardise features ───────────────────────────────
    scaler = StandardScaler()
    features_scaled = scaler.fit_transform(features)

    # ── K-Means ────────────────────────────────────────────
    print(f"\nRunning K-Means (k={K})...")
    kmeans = KMeans(n_clusters=K, n_init=10, random_state=42, max_iter=300)
    km_labels = kmeans.fit_predict(features_scaled)
    km_centroids = scaler.inverse_transform(kmeans.cluster_centers_)
    print(f"  Inertia: {kmeans.inertia_:,.0f}")

    # ── GMM (fit on subsample, predict on full set) ──────
    print(f"\nRunning Gaussian Mixture Model (k={K})...")
    gmm_sample_n = min(500_000, len(features_scaled))
    rng_gmm = np.random.RandomState(42)
    gmm_idx = rng_gmm.choice(len(features_scaled), gmm_sample_n, replace=False)
    print(f"  Fitting on {gmm_sample_n:,} subsample...")

    gmm = GaussianMixture(
        n_components=K, covariance_type="full",
        n_init=3, random_state=42, max_iter=200,
        reg_covar=1e-3,
    )
    gmm.fit(features_scaled[gmm_idx])
    gmm_labels = gmm.predict(features_scaled)
    gmm_centroids = scaler.inverse_transform(gmm.means_)
    gmm_bic = gmm.bic(features_scaled[gmm_idx])
    gmm_aic = gmm.aic(features_scaled[gmm_idx])
    print(f"  BIC: {gmm_bic:,.0f}   AIC: {gmm_aic:,.0f}")

    # ── Compare via silhouette ─────────────────────────────
    rng = np.random.RandomState(42)
    sample_n = min(50_000, len(features_scaled))
    idx = rng.choice(len(features_scaled), sample_n, replace=False)

    km_sil  = silhouette_score(features_scaled[idx], km_labels[idx])
    gmm_sil = silhouette_score(features_scaled[idx], gmm_labels[idx])
    print(f"\nSilhouette scores (sampled {sample_n:,} pixels):")
    print(f"  K-Means: {km_sil:.4f}")
    print(f"  GMM:     {gmm_sil:.4f}")

    if gmm_sil > km_sil:
        best_name, best_labels, best_centroids = "GMM", gmm_labels, gmm_centroids
    else:
        best_name, best_labels, best_centroids = "K-Means", km_labels, km_centroids
    print(f"  Selected: {best_name}")

    # ── Interpret clusters ─────────────────────────────────
    print(f"\nInterpreting {best_name} clusters...")
    class_names = interpret_clusters(best_centroids)

    # Sort clusters by mean dB 2022 (descending) for consistency
    sort_order = np.argsort(-best_centroids[:, 0])
    label_remap = np.zeros(K, dtype=int)
    for new_id, old_id in enumerate(sort_order):
        label_remap[old_id] = new_id
    best_labels_sorted = label_remap[best_labels]
    sorted_centroids = best_centroids[sort_order]
    sorted_names = [class_names[i] for i in sort_order]

    # ── Summary table ──────────────────────────────────────
    print(f"\n{'='*100}")
    print(f"{'Class':>5}  {'Label':<30}  {'Pixels':>10}  {'%':>6}  "
          f"{'dB 2022':>8}  {'dB 2024':>8}  {'Mean dB':>8}  {'Mean Δ':>8}")
    print(f"{'-'*100}")
    for k in range(K):
        mask_k = best_labels_sorted == k
        count  = mask_k.sum()
        pct    = 100 * count / n_valid
        c      = sorted_centroids[k]
        mean_db = (c[0] + c[1]) / 2
        print(f"{k:>5}    {sorted_names[k]:<30}  {count:>10,}  "
              f"{pct:>5.1f}%  {c[0]:>+8.2f}  {c[1]:>+8.2f}  "
              f"{mean_db:>+8.2f}  {c[3]:>+8.2f}")
    print(f"{'='*100}")

    # ── Rasterise classification ───────────────────────────
    print("\nRasterising classification...")
    class_map = np.full((h, w), fill_value=255, dtype=np.uint8)
    flat_valid = np.where(valid_mask.ravel())[0]
    class_map.ravel()[flat_valid] = best_labels_sorted

    # ── Save GeoTIFF ───────────────────────────────────────
    with rasterio.open(
        OUT_CLASS_TIF, "w", driver="GTiff",
        height=h, width=w, count=1, dtype="uint8",
        crs=crs, transform=transform, nodata=255,
    ) as dst:
        dst.write(class_map, 1)
    print(f"  Saved: {OUT_CLASS_TIF}")

    # ── Figure ─────────────────────────────────────────────
    print("Generating classification map...")

    color_list = []
    for k in range(K):
        name = sorted_names[k]
        hex_c = CLASS_COLORS.get(name, FALLBACK_PALETTE[k % len(FALLBACK_PALETTE)])
        r = int(hex_c[1:3], 16) / 255
        g = int(hex_c[3:5], 16) / 255
        b = int(hex_c[5:7], 16) / 255
        color_list.append((r, g, b))

    rgba = np.ones((h, w, 4), dtype=np.float32)
    for k in range(K):
        mask_k = class_map == k
        rgba[mask_k, 0] = color_list[k][0]
        rgba[mask_k, 1] = color_list[k][1]
        rgba[mask_k, 2] = color_list[k][2]

    nodata = class_map == 255
    rgba[nodata] = [1.0, 1.0, 1.0, 0.0]

    fig, ax = plt.subplots(figsize=(12, 12))
    fig.patch.set_facecolor("white")
    ax.imshow(rgba, interpolation="nearest", aspect="equal")

    # UTM ticks
    left   = transform.c
    top_   = transform.f
    right  = left + w * transform.a
    bottom = top_ + h * transform.e

    x_ticks = np.linspace(left, right, 5)[1:-1]
    y_ticks = np.linspace(bottom, top_, 5)[1:-1]
    px_x = (x_ticks - left) / transform.a
    px_y = (top_ - y_ticks) / abs(transform.e)

    ax.set_xticks(px_x)
    ax.set_xticklabels([f"{v/1000:.0f}k" for v in x_ticks], fontsize=7)
    ax.set_yticks(px_y)
    ax.set_yticklabels([f"{v/1000:.0f}k" for v in y_ticks], fontsize=7)
    ax.set_xlabel("Easting (km, UTM 38N)", fontsize=9)
    ax.set_ylabel("Northing (km, UTM 38N)", fontsize=9)
    ax.tick_params(length=3, width=0.7, direction="in", top=True, right=True)
    for spine in ax.spines.values():
        spine.set_linewidth(1.0)
        spine.set_edgecolor("#444444")

    # Legend
    legend_elements = []
    for k in range(K):
        mask_k = best_labels_sorted == k
        count  = mask_k.sum()
        pct    = 100 * count / n_valid
        legend_elements.append(
            mpatches.Patch(facecolor=color_list[k],
                           label=f"{sorted_names[k]}  ({pct:.1f}%)")
        )
    legend_elements.append(
        mpatches.Patch(facecolor="white", edgecolor="#aaa",
                       label="No data / scene edge")
    )
    ax.legend(
        handles=legend_elements, loc="lower left",
        fontsize=9.5, framealpha=0.95, edgecolor="#bbbbbb",
        title=f"ML Classification ({best_name}, k={K})",
        title_fontsize=10,
    )

    ax.set_title(
        f"ML Land-Cover Change Classification — Riyadh 2022 vs 2024\n"
        f"{best_name} clustering (k={K})  ·  Sentinel-1A IW GRD  ·  VV pol",
        fontsize=13, fontweight="bold", pad=10,
    )

    # Stats box
    stats_text = (
        f"Silhouette: {max(km_sil, gmm_sil):.3f}\n"
        f"K-Means sil: {km_sil:.3f}\n"
        f"GMM sil: {gmm_sil:.3f}  BIC: {gmm_bic/1e6:.1f}M"
    )
    ax.text(
        0.985, 0.015, stats_text,
        transform=ax.transAxes, ha="right", va="bottom",
        fontsize=8, color="#333",
        bbox=dict(boxstyle="round,pad=0.4", facecolor="white",
                  edgecolor="#ccc", linewidth=0.8, alpha=0.92),
    )

    plt.tight_layout()
    plt.savefig(OUT_PNG, dpi=300, bbox_inches="tight", facecolor="white")
    print(f"  Saved: {OUT_PNG}")
    plt.close()

    print("\n✓ Classification complete.")


if __name__ == "__main__":
    main()

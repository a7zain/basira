"""
Multi-temporal Change Detection from Sentinel-2 Optical Imagery
================================================================
Computes RGB-based change maps across three epochs (2020, 2023, 2026),
classifies change via K-Means, and cross-references with SAR results.

Usage:
    python src/optical_change.py
"""

import numpy as np
import rasterio
from rasterio.warp import reproject, Resampling, calculate_default_transform
from rasterio.transform import from_bounds
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import os

from utils import RIYADH_BBOX

# ── Paths ───────────────────────────────────────────────────
OPTICAL_DIR = "data/optical"
OUT_DIR     = "outputs"
SAR_CHANGE  = f"{OUT_DIR}/change_map.tif"

EPOCHS = {
    "2020": f"{OPTICAL_DIR}/riyadh_2020.tif",
    "2023": f"{OPTICAL_DIR}/riyadh_2023.tif",
    "2026": f"{OPTICAL_DIR}/riyadh_2026.tif",
}

PAIRS = [
    ("2020", "2023", "11_optical_change_2020_2023.png"),
    ("2023", "2026", "12_optical_change_2023_2026.png"),
    ("2020", "2026", "13_optical_change_2020_2026.png"),
]

K = 4  # clusters for change classification

# ── Class definitions ───────────────────────────────────────
CLASS_COLORS = [
    (0.55, 0.55, 0.55),   # grey    — stable
    (0.84, 0.38, 0.30),   # red     — new construction
    (0.40, 0.70, 0.40),   # green   — vegetation change
    (0.13, 0.40, 0.68),   # blue    — land clearing
]
FALLBACK_NAMES = [
    "Stable", "New construction",
    "Vegetation change", "Land clearing",
]


def load_optical(path):
    """Load a 3-band optical GeoTIFF as float32 (H, W, 3)."""
    with rasterio.open(path) as src:
        img = src.read()           # (3, H, W)
        transform = src.transform
        crs = src.crs
    img = np.moveaxis(img, 0, -1).astype(np.float32)  # (H, W, 3)
    return img, transform, crs


def green_red_ratio(img):
    """
    Pseudo-vegetation index from RGB: (G - R) / (G + R + eps).
    Positive → more green (vegetation), Negative → more red (bare soil).
    """
    r, g = img[:, :, 0], img[:, :, 1]
    return (g - r) / (g + r + 1e-6)


def compute_change_features(img_before, img_after):
    """
    Build a feature stack for change classification.

    Features per pixel:
      0-2: RGB difference (after - before)
      3:   magnitude of RGB difference
      4:   brightness change (mean intensity)
      5:   green-red ratio change (pseudo-NDVI change)
    """
    diff = img_after - img_before                       # (H, W, 3)
    mag = np.sqrt(np.sum(diff ** 2, axis=2))            # (H, W)
    bright_before = img_before.mean(axis=2)
    bright_after  = img_after.mean(axis=2)
    bright_change = bright_after - bright_before         # (H, W)
    grr_before = green_red_ratio(img_before)
    grr_after  = green_red_ratio(img_after)
    grr_change = grr_after - grr_before                  # (H, W)

    h, w = mag.shape
    features = np.stack([
        diff[:, :, 0], diff[:, :, 1], diff[:, :, 2],
        mag, bright_change, grr_change,
    ], axis=-1)  # (H, W, 6)

    return features


def classify_change(features, valid_mask, k=K):
    """
    K-Means clustering on change features.
    Returns class map (H, W) and centroids.
    """
    h, w, n_feat = features.shape
    flat = features[valid_mask]

    scaler = StandardScaler()
    flat_scaled = scaler.fit_transform(flat)

    kmeans = KMeans(n_clusters=k, n_init=10, random_state=42, max_iter=300)
    labels = kmeans.fit_predict(flat_scaled)
    centroids = scaler.inverse_transform(kmeans.cluster_centers_)

    class_map = np.full((h, w), fill_value=255, dtype=np.uint8)
    class_map[valid_mask] = labels

    return class_map, centroids, labels


def interpret_and_sort(centroids):
    """
    Interpret clusters by their centroid features and assign
    labels + consistent ordering.

    Centroid features: [dR, dG, dB, magnitude, brightness_change, grr_change]
    """
    names = []
    for c in centroids:
        dr, dg, db, mag, bright, grr = c
        # Thresholds for uint8 [0-255] scale
        if mag < 20:
            names.append("Stable")
        elif bright > 10 and mag > 20:
            names.append("New construction")
        elif grr > 0.02 or grr < -0.03:
            names.append("Vegetation change")
        elif bright < -10:
            names.append("Land clearing")
        else:
            names.append("Other change")

    # Sort: stable first, then by magnitude descending
    order = sorted(range(len(centroids)),
                   key=lambda i: (0 if names[i] == "Stable" else 1,
                                  -centroids[i][3]))
    remap = np.zeros(len(centroids), dtype=int)
    for new_id, old_id in enumerate(order):
        remap[old_id] = new_id

    sorted_names = [names[order[i]] for i in range(len(order))]
    sorted_centroids = centroids[order]
    return remap, sorted_names, sorted_centroids


def render_class_map(class_map, n_classes, colors):
    """Render class map as RGBA."""
    h, w = class_map.shape
    rgba = np.ones((h, w, 4), dtype=np.float32)
    for k in range(n_classes):
        mask = class_map == k
        rgba[mask, 0] = colors[k % len(colors)][0]
        rgba[mask, 1] = colors[k % len(colors)][1]
        rgba[mask, 2] = colors[k % len(colors)][2]
    nodata = class_map == 255
    rgba[nodata] = [1, 1, 1, 0]
    return rgba


def plot_change_map(rgba, class_names, colors, n_valid, title, out_path,
                    class_counts, transform=None, shape=None):
    """Generate and save a classified change map figure."""
    fig, ax = plt.subplots(figsize=(12, 10))
    fig.patch.set_facecolor("white")
    ax.imshow(rgba, interpolation="nearest", aspect="equal")

    legend_els = []
    for k, name in enumerate(class_names):
        pct = 100 * class_counts[k] / n_valid if n_valid > 0 else 0
        legend_els.append(
            mpatches.Patch(facecolor=colors[k % len(colors)],
                           label=f"{name}  ({pct:.1f}%)")
        )
    legend_els.append(
        mpatches.Patch(facecolor="white", edgecolor="#aaa", label="No data")
    )
    ax.legend(handles=legend_els, loc="lower left", fontsize=9.5,
              framealpha=0.95, edgecolor="#bbb",
              title="Change Class", title_fontsize=10)

    ax.set_title(title, fontsize=13, fontweight="bold", pad=10)

    if transform is not None and shape is not None:
        h, w = shape
        left = transform.c
        top_ = transform.f
        right = left + w * transform.a
        bottom = top_ + h * transform.e
        x_ticks = np.linspace(left, right, 5)[1:-1]
        y_ticks = np.linspace(bottom, top_, 5)[1:-1]
        px_x = (x_ticks - left) / transform.a
        px_y = (top_ - y_ticks) / abs(transform.e)
        ax.set_xticks(px_x)
        ax.set_xticklabels([f"{v:.2f}" for v in x_ticks], fontsize=7)
        ax.set_yticks(px_y)
        ax.set_yticklabels([f"{v:.2f}" for v in y_ticks], fontsize=7)
        ax.set_xlabel("Longitude", fontsize=9)
        ax.set_ylabel("Latitude", fontsize=9)
    else:
        ax.axis("off")

    for spine in ax.spines.values():
        spine.set_linewidth(1.0)
        spine.set_edgecolor("#444")

    plt.tight_layout()
    plt.savefig(out_path, dpi=300, bbox_inches="tight", facecolor="white")
    plt.close()


def resample_sar_to_optical(sar_path, optical_transform, optical_crs,
                            optical_shape):
    """
    Reproject the SAR change map (UTM int8) onto the optical grid
    (WGS84) using nearest-neighbour resampling.
    """
    h, w = optical_shape
    dst = np.full((h, w), fill_value=0, dtype=np.int8)

    with rasterio.open(sar_path) as src:
        reproject(
            source=rasterio.band(src, 1),
            destination=dst,
            src_transform=src.transform,
            src_crs=src.crs,
            dst_transform=optical_transform,
            dst_crs=optical_crs,
            resampling=Resampling.nearest,
        )
    return dst


def main():
    os.makedirs(OUT_DIR, exist_ok=True)

    # ── Load optical images ────────────────────────────────
    print("Loading optical images...")
    images = {}
    opt_transform = opt_crs = None
    for label, path in EPOCHS.items():
        img, t, c = load_optical(path)
        images[label] = img
        opt_transform = t
        opt_crs = c
        print(f"  {label}: shape={img.shape}, "
              f"range=[{img.min():.3f}, {img.max():.3f}]")

    h, w, _ = images["2020"].shape
    # Valid mask: pixels where all epochs have data (not black)
    valid_mask = np.ones((h, w), dtype=bool)
    for img in images.values():
        valid_mask &= img.mean(axis=2) > 0.01

    n_valid = valid_mask.sum()
    pixel_area = 20.0 ** 2  # m² per pixel at 20m resolution
    print(f"  Valid pixels: {n_valid:,}")

    # ── Process each pair ──────────────────────────────────
    full_span_class_map = None
    full_span_names = None

    for year_a, year_b, out_filename in PAIRS:
        print(f"\n{'='*60}")
        print(f"Change Detection: {year_a} → {year_b}")
        print(f"{'='*60}")

        img_a = images[year_a]
        img_b = images[year_b]

        # Compute features
        features = compute_change_features(img_a, img_b)

        # Classify
        class_map, centroids, raw_labels = classify_change(
            features, valid_mask, k=K,
        )

        # Interpret and sort
        remap, class_names, sorted_centroids = interpret_and_sort(centroids)
        class_map_sorted = np.where(
            class_map < 255,
            remap[class_map.clip(0, K-1)],
            255,
        ).astype(np.uint8)

        # Stats
        class_counts = []
        print(f"\n{'Class':<5} {'Label':<25} {'Pixels':>10} {'%':>6} "
              f"{'Area (km²)':>10}  Centroid [dR, dG, dB, mag, bright, grr]")
        print("-" * 100)
        for k in range(K):
            count = ((class_map_sorted == k) & valid_mask).sum()
            class_counts.append(count)
            pct = 100 * count / n_valid
            area_km2 = count * pixel_area / 1e6
            c = sorted_centroids[k]
            cstr = ", ".join(f"{v:+.3f}" for v in c)
            print(f"  {k:<3}  {class_names[k]:<25} {count:>10,} {pct:>5.1f}% "
                  f"{area_km2:>10.2f}  [{cstr}]")

        total_changed = sum(
            c for k, c in enumerate(class_counts) if class_names[k] != "Stable"
        )
        pct_changed = 100 * total_changed / n_valid
        print(f"\n  Total changed: {total_changed:,} pixels "
              f"({pct_changed:.1f}%), "
              f"{total_changed * pixel_area / 1e6:.2f} km²")

        # Render and save figure
        rgba = render_class_map(class_map_sorted, K, CLASS_COLORS)
        title = (f"Optical Change Detection — Riyadh {year_a} → {year_b}\n"
                 f"Sentinel-2 L2A  ·  K-Means (k={K})  ·  20 m resolution")
        out_path = f"{OUT_DIR}/{out_filename}"
        plot_change_map(rgba, class_names, CLASS_COLORS, n_valid,
                        title, out_path, class_counts,
                        opt_transform, (h, w))
        print(f"  Saved: {out_path}")

        # Keep full-span for GeoTIFF export and SAR comparison
        if year_a == "2020" and year_b == "2026":
            full_span_class_map = class_map_sorted
            full_span_names = class_names
            full_span_counts = class_counts

    # ── Save full-span GeoTIFF ─────────────────────────────
    if full_span_class_map is not None:
        tif_path = f"{OUT_DIR}/optical_change_2020_2026.tif"
        with rasterio.open(
            tif_path, "w", driver="GTiff",
            height=h, width=w, count=1, dtype="uint8",
            crs=opt_crs, transform=opt_transform, nodata=255,
        ) as dst:
            dst.write(full_span_class_map, 1)
        print(f"\n  Saved GeoTIFF: {tif_path}")

    # ── Cross-reference with SAR ───────────────────────────
    print(f"\n{'='*60}")
    print("Cross-referencing with SAR change detection")
    print(f"{'='*60}")

    if not os.path.exists(SAR_CHANGE):
        print(f"  SAR change map not found: {SAR_CHANGE}")
        return

    print("  Reprojecting SAR change map to optical grid...")
    sar_on_optical = resample_sar_to_optical(
        SAR_CHANGE, opt_transform, opt_crs, (h, w),
    )

    # SAR: +1 = increase, -1 = decrease, 0 = no change / nodata
    # Load the dB GeoTIFF to distinguish stable from nodata
    sar_db_path = "data/processed/db_2022.tif"
    if os.path.exists(sar_db_path):
        with rasterio.open(sar_db_path) as src:
            sar_db = np.zeros((h, w), dtype=np.float32)
            reproject(
                source=rasterio.band(src, 1), destination=sar_db,
                src_transform=src.transform, src_crs=src.crs,
                dst_transform=opt_transform, dst_crs=opt_crs,
                resampling=Resampling.nearest,
            )
        sar_has_data = sar_db > -30  # valid SAR pixels
    else:
        sar_has_data = np.abs(sar_on_optical) > 0

    sar_changed = np.abs(sar_on_optical) == 1
    overlap_mask = valid_mask & sar_has_data  # both have data

    # Optical changed = any non-"Stable" class
    opt_changed = np.zeros((h, w), dtype=bool)
    if full_span_class_map is not None and full_span_names is not None:
        for k, name in enumerate(full_span_names):
            if name != "Stable":
                opt_changed |= (full_span_class_map == k)

    # Agreement metrics
    both_valid = overlap_mask
    n_both = both_valid.sum()

    if n_both > 0:
        both_changed = sar_changed & opt_changed & both_valid
        both_stable  = (~sar_changed) & (~opt_changed) & both_valid
        agree = (both_changed | both_stable).sum()
        agreement_pct = 100 * agree / n_both

        sar_only  = (sar_changed & ~opt_changed & both_valid).sum()
        opt_only  = (~sar_changed & opt_changed & both_valid).sum()

        print(f"\n  Overlap pixels (both SAR & optical valid): {n_both:,}")
        print(f"  Agreement (both detect change OR both stable): "
              f"{agree:,} ({agreement_pct:.1f}%)")
        print(f"  Both detect change:    {both_changed.sum():>10,}")
        print(f"  Both stable:           {both_stable.sum():>10,}")
        print(f"  SAR-only change:       {sar_only:>10,}")
        print(f"  Optical-only change:   {opt_only:>10,}")
        print(f"\n  High-confidence change (SAR + optical agree): "
              f"{both_changed.sum():,} pixels, "
              f"{both_changed.sum() * pixel_area / 1e6:.2f} km²")
    else:
        print("  No overlapping valid pixels between SAR and optical.")

    print("\n✓ Optical change detection complete.")


if __name__ == "__main__":
    main()

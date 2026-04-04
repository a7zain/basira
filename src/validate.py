"""
SAR Change Detection — Validation Site Identification
=====================================================
Finds the largest contiguous clusters of change, computes their
coordinates and area, and produces a summary table + annotated map
for cross-referencing with optical imagery (Google Earth / Maps).

Usage:
    python src/validate.py
"""

import numpy as np
import rasterio
from rasterio.warp import transform as rio_transform
from scipy.ndimage import label
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import matplotlib.patches as mpatches
import csv
import os

from utils import TARGET_CRS

# ── Paths ───────────────────────────────────────────────────
OUT_DIR    = "outputs"
CHANGE_TIF = f"{OUT_DIR}/change_map.tif"
OUT_CSV    = f"{OUT_DIR}/06_validation_sites.csv"
OUT_PNG    = f"{OUT_DIR}/06_validation_clusters.png"
TOP_N      = 5


def find_top_clusters(binary_mask, n=5):
    """
    Label connected components and return the top-n by pixel count.

    Returns list of dicts: {label, pixel_count, pixels} sorted descending.
    """
    labelled, n_features = label(binary_mask)
    if n_features == 0:
        return [], labelled

    # Count pixels per label (skip 0 = background)
    label_ids = np.arange(1, n_features + 1)
    counts = np.array([np.sum(labelled == lid) for lid in label_ids])

    # Sort descending
    order = np.argsort(-counts)
    top_ids = label_ids[order[:n]]
    top_counts = counts[order[:n]]

    clusters = []
    for lid, cnt in zip(top_ids, top_counts):
        rows, cols = np.where(labelled == lid)
        clusters.append({
            "label": int(lid),
            "pixel_count": int(cnt),
            "row_center": float(rows.mean()),
            "col_center": float(cols.mean()),
        })

    return clusters, labelled


def pixel_to_latlon(row, col, transform, src_crs):
    """Convert pixel (row, col) → (lat, lon) via the raster transform."""
    # Pixel center in CRS coordinates
    x = transform.c + col * transform.a + 0.5 * transform.a
    y = transform.f + row * transform.e + 0.5 * transform.e
    # Transform to WGS84
    lons, lats = rio_transform(src_crs, "EPSG:4326", [x], [y])
    return lats[0], lons[0]


def main():
    os.makedirs(OUT_DIR, exist_ok=True)

    # ── Load change map ────────────────────────────────────
    print("Loading change map...")
    with rasterio.open(CHANGE_TIF) as src:
        classified = src.read(1)
        transform  = src.transform
        crs        = src.crs

    pixel_res = abs(transform.a)  # metres
    pixel_area = pixel_res ** 2   # m²
    h, w = classified.shape
    print(f"  Shape: {h} x {w}, pixel size: {pixel_res:.1f} m")

    # ── Connected-component analysis ───────────────────────
    print("\nFinding largest increase clusters...")
    inc_clusters, inc_labels = find_top_clusters(classified == 1, TOP_N)
    print(f"  Found {len(inc_clusters)} clusters")

    print("Finding largest decrease clusters...")
    dec_clusters, dec_labels = find_top_clusters(classified == -1, TOP_N)
    print(f"  Found {len(dec_clusters)} clusters")

    # ── Build results table ────────────────────────────────
    rows = []
    rank = 0
    for cl in inc_clusters:
        rank += 1
        lat, lon = pixel_to_latlon(cl["row_center"], cl["col_center"],
                                   transform, crs)
        area_m2 = cl["pixel_count"] * pixel_area
        gmaps = f"https://www.google.com/maps/@{lat:.6f},{lon:.6f},17z"
        rows.append({
            "rank": rank,
            "type": "increase",
            "pixels": cl["pixel_count"],
            "area_m2": area_m2,
            "lat": lat,
            "lon": lon,
            "gmaps": gmaps,
            "row_px": cl["row_center"],
            "col_px": cl["col_center"],
        })

    for cl in dec_clusters:
        rank += 1
        lat, lon = pixel_to_latlon(cl["row_center"], cl["col_center"],
                                   transform, crs)
        area_m2 = cl["pixel_count"] * pixel_area
        gmaps = f"https://www.google.com/maps/@{lat:.6f},{lon:.6f},17z"
        rows.append({
            "rank": rank,
            "type": "decrease",
            "pixels": cl["pixel_count"],
            "area_m2": area_m2,
            "lat": lat,
            "lon": lon,
            "gmaps": gmaps,
            "row_px": cl["row_center"],
            "col_px": cl["col_center"],
        })

    # ── Print summary table ────────────────────────────────
    print(f"\n{'='*100}")
    print(f"{'Rank':>4}  {'Type':<10}  {'Pixels':>8}  {'Area (m²)':>12}  "
          f"{'Lat':>10}  {'Lon':>10}  Google Maps")
    print(f"{'-'*100}")
    for r in rows:
        print(f"{r['rank']:>4}  {r['type']:<10}  {r['pixels']:>8,}  "
              f"{r['area_m2']:>12,.0f}  {r['lat']:>10.5f}  {r['lon']:>10.5f}  "
              f"{r['gmaps']}")
    print(f"{'='*100}")

    # ── Save CSV ───────────────────────────────────────────
    with open(OUT_CSV, "w", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["rank", "type", "pixels", "area_m2",
                        "lat", "lon", "gmaps"],
        )
        writer.writeheader()
        for r in rows:
            writer.writerow({k: r[k] for k in writer.fieldnames})
    print(f"\nSaved: {OUT_CSV}")

    # ── Annotated cluster map ──────────────────────────────
    print("Generating annotated cluster map...")

    # Base change map as RGBA (same scheme as change_detect_v2)
    COLORS = {
        -1: np.array([0.133, 0.400, 0.675]),   # blue
         0: np.array([0.969, 0.969, 0.969]),    # light grey
         1: np.array([0.839, 0.376, 0.302]),    # red
    }
    nodata_mask = (classified == 0)

    base_rgb = np.ones((h, w, 3), dtype=np.float32)
    for val, col in COLORS.items():
        base_rgb[classified == val] = col
    # Make nodata white
    base_rgb[(classified == 0) & (classified == 0)] = [1.0, 1.0, 1.0]

    fig, ax = plt.subplots(figsize=(12, 12))
    fig.patch.set_facecolor("white")
    ax.imshow(base_rgb, interpolation="nearest", aspect="equal")

    # Draw numbered markers for each cluster
    for r in rows:
        px_r = r["row_px"]
        px_c = r["col_px"]
        color = "#d6604d" if r["type"] == "increase" else "#2166ac"
        text_color = "white"

        # Circle marker
        circle = plt.Circle(
            (px_c, px_r), radius=35,
            facecolor=color, edgecolor="white", linewidth=2, zorder=5,
        )
        ax.add_patch(circle)

        # Rank number
        ax.text(
            px_c, px_r, str(r["rank"]),
            ha="center", va="center", fontsize=9, fontweight="bold",
            color=text_color, zorder=6,
        )

        # Label with area
        area_ha = r["area_m2"] / 10000
        label_text = f"#{r['rank']}  {area_ha:.1f} ha"
        # Offset label to avoid overlap with marker
        offset_x = 60
        offset_y = -50 if r["rank"] % 2 == 0 else 50
        ax.annotate(
            label_text,
            xy=(px_c, px_r),
            xytext=(px_c + offset_x, px_r + offset_y),
            fontsize=8, fontweight="bold", color=color,
            ha="left", va="center",
            arrowprops=dict(
                arrowstyle="-|>", color=color,
                lw=1.2, connectionstyle="arc3,rad=0.15",
            ),
            bbox=dict(
                boxstyle="round,pad=0.25", facecolor="white",
                edgecolor=color, linewidth=0.8, alpha=0.92,
            ),
            zorder=7,
        )

    # Legend
    legend_elements = [
        mpatches.Patch(facecolor="#d6604d",
                       label=f"Increased backscatter (top {TOP_N})"),
        mpatches.Patch(facecolor="#2166ac",
                       label=f"Decreased backscatter (top {TOP_N})"),
    ]
    ax.legend(
        handles=legend_elements, loc="lower left",
        fontsize=10, framealpha=0.95, edgecolor="#bbbbbb",
        title="Largest Change Clusters", title_fontsize=10,
    )

    # UTM ticks (reuse logic from change_detect_v2)
    left   = transform.c
    top    = transform.f
    right  = left + w * transform.a
    bottom = top  + h * transform.e

    x_ticks = np.linspace(left, right, 5)[1:-1]
    y_ticks = np.linspace(bottom, top, 5)[1:-1]
    px_x = (x_ticks - left) / transform.a
    px_y = (top - y_ticks) / abs(transform.e)

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

    ax.set_title(
        f"Top {TOP_N * 2} Change Clusters — Riyadh 2022 vs 2024\n"
        f"Sentinel-1A IW GRD  ·  VV pol  ·  ±3 dB threshold",
        fontsize=13, fontweight="bold", pad=10,
    )

    plt.tight_layout()
    plt.savefig(OUT_PNG, dpi=300, bbox_inches="tight", facecolor="white")
    print(f"Saved: {OUT_PNG}")
    plt.close()

    print("\n✓ Validation complete. Cross-reference Google Maps links "
          "with satellite imagery.")


if __name__ == "__main__":
    main()

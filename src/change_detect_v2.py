"""
SAR Change Detection — Change Map (v2)
=======================================
Computes log-ratio change detection between two co-registered
SAR dB images and produces portfolio-quality output figures.

Usage:
    python src/change_detect_v2.py
    python src/change_detect_v2.py --threshold 2.5
"""

import argparse
import numpy as np
import matplotlib
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import matplotlib.ticker as mticker
import matplotlib.patches as mpatches
from matplotlib.patches import FancyArrowPatch, Rectangle
from matplotlib.lines import Line2D
import rasterio
from rasterio.transform import xy as rio_xy
import os

from utils import TARGET_CRS

# ── Paths ───────────────────────────────────────────────────
PROC_DIR = "data/processed"
OUT_DIR  = "outputs"


# ── Helpers ─────────────────────────────────────────────────
def log_ratio_change(db_before, db_after):
    """dB difference = log-ratio change map."""
    return db_after - db_before


def classify_change(change_map, threshold=3.0):
    classified = np.zeros_like(change_map, dtype=np.int8)
    classified[change_map >  threshold] =  1
    classified[change_map < -threshold] = -1
    return classified


def add_north_arrow(ax, x=0.96, y=0.96, size=0.06):
    """
    Draw a minimal north arrow in axis-fraction coordinates.
    x, y  — tip position (upper-right by default).
    size  — shaft length in axis-fraction units.
    """
    shaft_x = [x, x]
    shaft_y = [y - size, y]
    ax.annotate(
        "", xy=(x, y), xytext=(x, y - size),
        xycoords="axes fraction", textcoords="axes fraction",
        arrowprops=dict(arrowstyle="-|>", color="black", lw=1.5,
                        mutation_scale=12),
    )
    ax.text(x, y - size - 0.03, "N", transform=ax.transAxes,
            ha="center", va="top", fontsize=9, fontweight="bold", color="black")


def add_scale_bar(ax, transform, width_px, units="m", bar_km=5):
    """
    Draw a scale bar.

    Parameters
    ----------
    ax        : Axes
    transform : rasterio Affine  (used to get pixel size in metres)
    width_px  : int              image width in pixels
    bar_km    : float            desired bar length in km
    """
    pixel_size_m = abs(transform.a)           # metres per pixel
    bar_px = (bar_km * 1000) / pixel_size_m   # pixels for bar_km
    bar_frac = bar_px / width_px              # as fraction of axes width

    # Position: bottom-left corner
    x0, y0 = 0.05, 0.05
    ax.annotate(
        "", xy=(x0 + bar_frac, y0), xytext=(x0, y0),
        xycoords="axes fraction", textcoords="axes fraction",
        arrowprops=dict(arrowstyle="|-|,widthA=0.4,widthB=0.4",
                        color="white", lw=1.5),
    )
    ax.text(x0 + bar_frac / 2, y0 + 0.025, f"{bar_km} km",
            transform=ax.transAxes, ha="center", va="bottom",
            fontsize=8, color="white", fontweight="bold")


def utm_tick_formatter(val, pos, axis="x"):
    """Format UTM coordinates as compact labels (e.g. 660k, 24.6°)."""
    return f"{val/1000:.0f}k"


def set_utm_ticks(ax, transform, shape, n_ticks=4):
    """
    Set UTM coordinate ticks on both axes.

    Parameters
    ----------
    transform : rasterio Affine
    shape     : (height, width)
    n_ticks   : approximate number of ticks per axis
    """
    h, w = shape
    # Compute UTM extents from transform
    left   = transform.c
    top    = transform.f
    right  = left + w * transform.a
    bottom = top  + h * transform.e   # e is negative

    # Round tick positions to nice intervals
    x_ticks = np.linspace(left, right, n_ticks + 2)[1:-1]
    y_ticks = np.linspace(bottom, top, n_ticks + 2)[1:-1]

    # Convert UTM → pixel coords for imshow axes
    # imshow x = (utm_x - left) / pixel_size
    px = (x_ticks - left)  / transform.a
    py = (top - y_ticks)   / abs(transform.e)

    ax.set_xticks(px)
    ax.set_xticklabels([f"{v/1000:.0f}k" for v in x_ticks],
                       fontsize=7, color="#333333")
    ax.set_yticks(py)
    ax.set_yticklabels([f"{v/1000:.0f}k" for v in y_ticks],
                       fontsize=7, color="#333333")
    ax.tick_params(length=3, width=0.7, direction="in",
                   top=True, right=True)
    ax.set_xlabel("Easting (km, UTM 38N)", fontsize=8, color="#333333")
    ax.set_ylabel("Northing (km, UTM 38N)", fontsize=8, color="#333333")
    for spine in ax.spines.values():
        spine.set_linewidth(0.8)
        spine.set_edgecolor("#555555")


# ── Main Pipeline ───────────────────────────────────────────
def main(threshold=3.0):
    os.makedirs(OUT_DIR, exist_ok=True)

    # ── Load preprocessed data ─────────────────────────────
    print("Loading preprocessed data...")
    tif_2022 = f"{PROC_DIR}/db_2022.tif"
    tif_2024 = f"{PROC_DIR}/db_2024.tif"

    if os.path.exists(tif_2022) and os.path.exists(tif_2024):
        with rasterio.open(tif_2022) as src:
            db_2022    = src.read(1)
            transform  = src.transform
            crs        = src.crs
        with rasterio.open(tif_2024) as src:
            db_2024 = src.read(1)
        print(f"  Loaded GeoTIFFs (CRS: {crs})")
    else:
        npy_2022 = f"{PROC_DIR}/db_2022.npy"
        npy_2024 = f"{PROC_DIR}/db_2024.npy"
        if os.path.exists(npy_2022) and os.path.exists(npy_2024):
            db_2022   = np.load(npy_2022)
            db_2024   = np.load(npy_2024)
            transform = None
            print("  Loaded .npy arrays (no georeferencing)")
        else:
            print("ERROR: No preprocessed data found. Run preprocess_v2.py first.")
            return

    assert db_2022.shape == db_2024.shape, (
        f"Shape mismatch! {db_2022.shape} vs {db_2024.shape}. "
        "Re-run preprocess_v2.py."
    )
    print(f"  Shape: {db_2022.shape}")

    # ── Nodata mask ────────────────────────────────────────
    # Pixels where EITHER scene has no data
    nodata_mask = (db_2022 <= -30) | (db_2024 <= -30)
    valid_mask  = ~nodata_mask

    # ── Change map ─────────────────────────────────────────
    print(f"\nComputing change map (threshold = {threshold} dB)...")
    change     = log_ratio_change(db_2022, db_2024)
    classified = classify_change(change, threshold=threshold)

    # Zero out nodata regions in classified map
    classified[nodata_mask] = 0

    # ── Statistics ─────────────────────────────────────────
    total_valid = valid_mask.sum()
    increased   = ((classified ==  1) & valid_mask).sum()
    decreased   = ((classified == -1) & valid_mask).sum()
    unchanged   = ((classified ==  0) & valid_mask).sum()

    pct_inc = 100 * increased / total_valid
    pct_dec = 100 * decreased / total_valid
    pct_unc = 100 * unchanged / total_valid

    print(f"\nChange Detection Results (threshold = {threshold} dB):")
    print(f"  Valid pixels  : {total_valid:>12,}")
    print(f"  Increased     : {increased:>12,} ({pct_inc:.1f}%)")
    print(f"  Decreased     : {decreased:>12,} ({pct_dec:.1f}%)")
    print(f"  No change     : {unchanged:>12,} ({pct_unc:.1f}%)")
    print(f"\n  Mean change   : {change[valid_mask].mean():>+.2f} dB")
    print(f"  Std change    : {change[valid_mask].std():.2f} dB")

    # ── Save GeoTIFFs ──────────────────────────────────────
    if transform is not None:
        for path, arr, dtype in [
            (f"{OUT_DIR}/change_map.tif",        classified, "int8"),
            (f"{OUT_DIR}/change_continuous.tif", change,     "float32"),
        ]:
            with rasterio.open(
                path, "w", driver="GTiff",
                height=arr.shape[0], width=arr.shape[1],
                count=1, dtype=dtype, crs=crs, transform=transform,
            ) as dst:
                dst.write(arr, 1)
            print(f"  Saved GeoTIFF: {path}")

    # ── Prepare masked display arrays ─────────────────────
    h, w = db_2022.shape

    # SAR grayscale: mask nodata → NaN so imshow uses set_bad colour
    def sar_display(db, mask):
        arr = db.copy().astype(np.float32)
        arr[mask] = np.nan
        return arr

    disp_2022 = sar_display(db_2022, nodata_mask)
    disp_2024 = sar_display(db_2024, nodata_mask)

    # Change map with nodata as a 4th class (transparent via alpha)
    # Use RGBA so nodata pixels are white/transparent
    COLORS = {
        -1: np.array([0.133, 0.400, 0.675, 1.0]),   # blue  — decrease
         0: np.array([0.969, 0.969, 0.969, 1.0]),   # light grey — stable
         1: np.array([0.839, 0.376, 0.302, 1.0]),   # red   — increase
    }
    NODATA_RGBA = np.array([1.0, 1.0, 1.0, 0.0])    # transparent white

    change_rgba = np.zeros((h, w, 4), dtype=np.float32)
    for val, col in COLORS.items():
        change_rgba[classified == val] = col
    change_rgba[nodata_mask] = NODATA_RGBA

    # Color limits for SAR panels (shared, ignoring nodata)
    valid_db = db_2022[valid_mask]
    vmin = np.percentile(valid_db, 2)
    vmax = np.percentile(valid_db, 98)

    gray_cmap = plt.cm.gray.copy()
    gray_cmap.set_bad("white")   # nodata → white

    stats_str = (f"{pct_unc:.1f}% stable  |  "
                 f"{pct_inc:.1f}% increase  |  "
                 f"{pct_dec:.1f}% decrease")

    # ── Figure 1: Three-panel comparison ──────────────────
    print("\nGenerating three-panel comparison figure...")
    fig, axes = plt.subplots(
        1, 3, figsize=(22, 8.5),
        gridspec_kw={"wspace": 0.08}
    )
    fig.patch.set_facecolor("white")

    panel_titles = [
        "Riyadh — Jan 2022 (VV, SAR)",
        "Riyadh — Feb 2024 (VV, SAR)",
        "Change Detection 2022 → 2024",
    ]
    images = [disp_2022, disp_2024, change_rgba]
    cmaps  = [gray_cmap, gray_cmap, None]
    vmins  = [vmin, vmin, None]
    vmaxs  = [vmax, vmax, None]

    for i, (ax, title, img, cmap, vn, vx) in enumerate(
        zip(axes, panel_titles, images, cmaps, vmins, vmaxs)
    ):
        if cmap is not None:
            ax.imshow(img, cmap=cmap, vmin=vn, vmax=vx,
                      interpolation="nearest", aspect="equal")
        else:
            ax.imshow(img, interpolation="nearest", aspect="equal")

        ax.set_title(title, fontsize=13, fontweight="bold", pad=8,
                     color="#1a1a1a")

        if transform is not None:
            set_utm_ticks(ax, transform, (h, w), n_ticks=3)
        else:
            ax.axis("off")

        # Thin border frame
        for spine in ax.spines.values():
            spine.set_visible(True)
            spine.set_linewidth(1.0)
            spine.set_edgecolor("#444444")

        # North arrow + scale bar on SAR panels
        if i < 2 and transform is not None:
            add_north_arrow(ax)
            add_scale_bar(ax, transform, w, bar_km=5)

    # Legend for change panel
    legend_elements = [
        mpatches.Patch(facecolor=COLORS[ 1][:3], label=f"Increased  (>{threshold} dB)"),
        mpatches.Patch(facecolor=COLORS[ 0][:3], edgecolor="#aaaaaa",
                       label=f"No change  (±{threshold} dB)"),
        mpatches.Patch(facecolor=COLORS[-1][:3], label=f"Decreased  (<−{threshold} dB)"),
        mpatches.Patch(facecolor="white",         edgecolor="#aaaaaa",
                       label="No data"),
    ]
    axes[2].legend(
        handles=legend_elements, loc="upper left",
        fontsize=9, framealpha=0.92, edgecolor="#cccccc",
        handlelength=1.2, handleheight=0.9,
    )

    # Stats text box below change panel
    axes[2].text(
        0.5, -0.10, stats_str,
        transform=axes[2].transAxes,
        ha="center", va="top", fontsize=10, color="#222222",
        bbox=dict(boxstyle="round,pad=0.4", facecolor="#f5f5f5",
                  edgecolor="#cccccc", linewidth=0.8),
    )

    # North arrow on change panel
    add_north_arrow(axes[2])

    plt.suptitle(
        f"Sentinel-1 SAR Amplitude Change Detection — Riyadh, Saudi Arabia\n"
        f"Jan 2022 vs Feb 2024  ·  {threshold} dB threshold  ·  UTM Zone 38N",
        fontsize=13, y=1.01, color="#111111",
    )

    plt.savefig(
        f"{OUT_DIR}/03_change_detection.png",
        dpi=300, bbox_inches="tight",
        facecolor="white",
    )
    print(f"  Saved: {OUT_DIR}/03_change_detection.png")
    plt.close()

    # ── Figure 2: Hero change-map-only ────────────────────
    print("Generating hero change map figure...")

    fig2, ax2 = plt.subplots(figsize=(10, 10))
    fig2.patch.set_facecolor("white")

    ax2.imshow(change_rgba, interpolation="nearest", aspect="equal")

    if transform is not None:
        set_utm_ticks(ax2, transform, (h, w), n_ticks=4)
        add_north_arrow(ax2, x=0.96, y=0.96, size=0.055)
        add_scale_bar(ax2, transform, w, bar_km=5)
    else:
        ax2.axis("off")

    for spine in ax2.spines.values():
        spine.set_visible(True)
        spine.set_linewidth(1.2)
        spine.set_edgecolor("#333333")

    legend_elements2 = [
        mpatches.Patch(facecolor=COLORS[ 1][:3],
                       label=f"Backscatter increase  (>{threshold} dB)  —  {pct_inc:.1f}%"),
        mpatches.Patch(facecolor=COLORS[ 0][:3], edgecolor="#aaaaaa",
                       label=f"No significant change  (±{threshold} dB)  —  {pct_unc:.1f}%"),
        mpatches.Patch(facecolor=COLORS[-1][:3],
                       label=f"Backscatter decrease  (<−{threshold} dB)  —  {pct_dec:.1f}%"),
        mpatches.Patch(facecolor="white",         edgecolor="#aaaaaa",
                       label="No data / scene edge"),
    ]
    ax2.legend(
        handles=legend_elements2, loc="lower left",
        fontsize=10, framealpha=0.95, edgecolor="#bbbbbb",
        handlelength=1.4, handleheight=1.0,
        title="Change Class", title_fontsize=10,
    )

    ax2.set_title(
        "SAR Backscatter Change Detection — Riyadh, Saudi Arabia\n"
        "Sentinel-1A IW GRD  ·  Jan 2022 → Feb 2024  ·  VV polarisation",
        fontsize=13, fontweight="bold", pad=12, color="#111111",
    )

    # Stats annotation inside the figure
    ax2.text(
        0.985, 0.015,
        f"Threshold: ±{threshold} dB\n"
        f"Valid pixels: {total_valid:,}\n"
        f"Mean Δ: {change[valid_mask].mean():+.2f} dB\n"
        f"Std Δ: {change[valid_mask].std():.2f} dB",
        transform=ax2.transAxes,
        ha="right", va="bottom", fontsize=8.5, color="#222222",
        bbox=dict(boxstyle="round,pad=0.5", facecolor="white",
                  edgecolor="#cccccc", linewidth=0.8, alpha=0.92),
    )

    plt.tight_layout()
    plt.savefig(
        f"{OUT_DIR}/05_change_hero.png",
        dpi=300, bbox_inches="tight",
        facecolor="white",
    )
    print(f"  Saved: {OUT_DIR}/05_change_hero.png")
    plt.close()

    # ── Figure 3: Change histogram ─────────────────────────
    print("Generating change histogram...")
    fig3, ax3 = plt.subplots(figsize=(10, 5))
    fig3.patch.set_facecolor("white")

    change_valid = change[valid_mask]
    ax3.hist(change_valid, bins=200, range=(-15, 15),
             color="#555555", edgecolor="none", alpha=0.8)
    ax3.axvline( threshold, color=COLORS[1][:3],  ls="--", lw=2,
                label=f"+{threshold} dB threshold")
    ax3.axvline(-threshold, color=COLORS[-1][:3], ls="--", lw=2,
                label=f"−{threshold} dB threshold")
    ax3.set_xlabel("Change (dB)", fontsize=12)
    ax3.set_ylabel("Pixel count", fontsize=12)
    ax3.set_title("Distribution of SAR Backscatter Change — Riyadh 2022→2024",
                  fontsize=13)
    ax3.legend(fontsize=11)
    for spine in ax3.spines.values():
        spine.set_linewidth(0.8)

    plt.tight_layout()
    plt.savefig(
        f"{OUT_DIR}/04_change_histogram.png",
        dpi=300, bbox_inches="tight",
        facecolor="white",
    )
    print(f"  Saved: {OUT_DIR}/04_change_histogram.png")
    plt.close()

    print("\n✓ Change detection complete.")
    print(f"\nOutputs:")
    print(f"  {OUT_DIR}/03_change_detection.png  — three-panel comparison (300 DPI)")
    print(f"  {OUT_DIR}/05_change_hero.png        — hero change map (300 DPI)")
    print(f"  {OUT_DIR}/04_change_histogram.png   — change histogram (300 DPI)")
    print(f"  {OUT_DIR}/change_map.tif             — classified change GeoTIFF")
    print(f"  {OUT_DIR}/change_continuous.tif      — continuous change GeoTIFF")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="SAR Change Detection for Riyadh"
    )
    parser.add_argument(
        "--threshold", type=float, default=3.0,
        help="Change threshold in dB (default: 3.0)",
    )
    args = parser.parse_args()
    main(threshold=args.threshold)

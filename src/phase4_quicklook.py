"""
Phase 4 — Quicklook Grid
=========================
Builds a year×month grid of RGB thumbnails from all monthly Sentinel-2
GeoTIFFs, plus a first-vs-last comparison panel.

Band mapping in each .tif:
    Band 1 = B02 (blue)
    Band 2 = B03 (green)
    Band 3 = B04 (red)
    Band 4 = B08 (NIR)

Usage:
    python src/phase4_quicklook.py
"""

import os
import glob
import re

import numpy as np
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
import rasterio

# ── Paths ───────────────────────────────────────────────────
MONTHLY_DIR = "data/processed/monthly"
OUT_DIR     = "outputs"

THUMB_WIDTH = 200  # pixels


def list_monthly_tifs():
    """Return sorted list of (year, month, path) tuples."""
    pattern = os.path.join(MONTHLY_DIR, "*.tif")
    files = sorted(glob.glob(pattern))
    result = []
    for f in files:
        m = re.search(r"(\d{4})_(\d{2})\.tif$", f)
        if m:
            result.append((int(m.group(1)), int(m.group(2)), f))
    return result


def load_rgb_thumbnail(path, width=THUMB_WIDTH):
    """
    Load a 4-band GeoTIFF and return a percentile-stretched RGB thumbnail.
    Band order in file: B02(1), B03(2), B04(3), B08(4).
    RGB display order:  B04(red), B03(green), B02(blue).
    """
    with rasterio.open(path) as src:
        red   = src.read(3).astype(np.float32)  # B04
        green = src.read(2).astype(np.float32)  # B03
        blue  = src.read(1).astype(np.float32)  # B02

    rgb = np.stack([red, green, blue], axis=-1)

    # Percentile stretch per band (2nd–98th)
    for b in range(3):
        band = rgb[:, :, b]
        valid = band[band > 0]
        if valid.size == 0:
            continue
        lo = np.percentile(valid, 2)
        hi = np.percentile(valid, 98)
        if hi > lo:
            rgb[:, :, b] = np.clip((band - lo) / (hi - lo), 0, 1)
        else:
            rgb[:, :, b] = 0

    # Resize to thumbnail
    h, w, _ = rgb.shape
    scale = width / w
    new_h = max(1, int(h * scale))
    # Simple nearest-neighbor downsample via slicing
    row_idx = np.linspace(0, h - 1, new_h).astype(int)
    col_idx = np.linspace(0, w - 1, width).astype(int)
    thumb = rgb[np.ix_(row_idx, col_idx)]

    return thumb


def build_grid(scenes):
    """Build a year×month quicklook grid figure."""
    # Determine year range
    years = sorted(set(y for y, m, _ in scenes))
    n_years = len(years)
    year_to_row = {y: i for i, y in enumerate(years)}

    # Load all thumbnails
    thumbs = {}
    for y, m, path in scenes:
        thumbs[(y, m)] = load_rgb_thumbnail(path)

    # Get thumbnail dimensions from first image
    sample = list(thumbs.values())[0]
    th, tw, _ = sample.shape

    # Build figure
    fig_w = 12 * 1.2   # inches
    fig_h = n_years * (th / tw) * 1.6 + 1.5
    fig, axes = plt.subplots(
        n_years, 12,
        figsize=(fig_w, fig_h),
        gridspec_kw={"wspace": 0.05, "hspace": 0.25},
    )
    fig.patch.set_facecolor("#1a1a2e")

    # Handle single-year edge case
    if n_years == 1:
        axes = axes[np.newaxis, :]

    for r in range(n_years):
        for c in range(12):
            ax = axes[r, c]
            y = years[r]
            m = c + 1
            if (y, m) in thumbs:
                ax.imshow(thumbs[(y, m)], aspect="equal")
                ax.set_title(f"{y}-{m:02d}", fontsize=5, color="white",
                             pad=2, fontfamily="monospace")
            else:
                ax.set_facecolor("#0f0f23")
                ax.text(0.5, 0.5, "—", transform=ax.transAxes,
                        ha="center", va="center", color="#444",
                        fontsize=8)
            ax.set_xticks([])
            ax.set_yticks([])
            for spine in ax.spines.values():
                spine.set_visible(False)

    # Year labels on left
    for r, y in enumerate(years):
        axes[r, 0].set_ylabel(str(y), fontsize=9, color="white",
                              fontweight="bold", rotation=0, labelpad=25,
                              va="center")

    # Month labels on top
    month_names = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                   "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    for c in range(12):
        axes[0, c].set_title(
            f"{month_names[c]}\n{axes[0, c].get_title()}",
            fontsize=6, color="white", pad=4, fontfamily="monospace",
        ) if axes[0, c].get_title() != "" else axes[0, c].set_title(
            month_names[c], fontsize=6, color="white", pad=4,
        )

    fig.suptitle(
        "Sentinel-2 Monthly Quicklook Grid — Riyadh AOI\n"
        "20 m  |  RGB (B04/B03/B02)  |  2nd–98th percentile stretch",
        fontsize=11, color="white", y=0.98, fontfamily="monospace",
    )

    os.makedirs(OUT_DIR, exist_ok=True)
    out_path = os.path.join(OUT_DIR, "phase4_quicklook_grid.png")
    plt.savefig(out_path, dpi=200, bbox_inches="tight",
                facecolor=fig.get_facecolor())
    plt.close()
    print(f"  Saved quicklook grid: {out_path}")
    return out_path


def build_first_last(scenes):
    """Build a side-by-side comparison of the first and last scenes."""
    first_y, first_m, first_path = scenes[0]
    last_y, last_m, last_path = scenes[-1]

    # Load larger thumbnails for this comparison
    thumb_w = 600
    first_rgb = load_rgb_thumbnail(first_path, width=thumb_w)
    last_rgb = load_rgb_thumbnail(last_path, width=thumb_w)

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))
    fig.patch.set_facecolor("white")

    ax1.imshow(first_rgb, aspect="equal")
    ax1.set_title(f"{first_y}-{first_m:02d}", fontsize=14, fontweight="bold", pad=8)
    ax1.axis("off")

    ax2.imshow(last_rgb, aspect="equal")
    ax2.set_title(f"{last_y}-{last_m:02d}", fontsize=14, fontweight="bold", pad=8)
    ax2.axis("off")

    fig.suptitle(
        "Riyadh — First vs Last Monthly Scene\n"
        "Sentinel-2 L2A  |  20 m  |  RGB (B04/B03/B02)",
        fontsize=12, y=0.98,
    )
    plt.tight_layout()

    os.makedirs(OUT_DIR, exist_ok=True)
    out_path = os.path.join(OUT_DIR, "phase4_first_vs_last.png")
    plt.savefig(out_path, dpi=200, bbox_inches="tight", facecolor="white")
    plt.close()
    print(f"  Saved first vs last: {out_path}")
    return out_path


def main():
    print("Phase 4 — Quicklook Grid")
    print("=" * 40)

    scenes = list_monthly_tifs()
    if not scenes:
        print(f"ERROR: No .tif files found in {MONTHLY_DIR}/")
        return

    print(f"  Found {len(scenes)} monthly scenes")
    print(f"  Range: {scenes[0][0]}-{scenes[0][1]:02d} to "
          f"{scenes[-1][0]}-{scenes[-1][1]:02d}")
    print()

    print("Building quicklook grid...")
    build_grid(scenes)

    print("Building first vs last comparison...")
    build_first_last(scenes)

    print()
    print("Done.")


if __name__ == "__main__":
    main()

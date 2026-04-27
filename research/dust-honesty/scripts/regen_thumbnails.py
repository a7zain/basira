"""
Regenerate sq1_thumbnails.png with no polygon mask / no black frame.

The Phase 1 tifs are polygon-clipped at download time, so the raw rasters
contain a rectangular bounding box with nodata (zero) pixels outside the
AOI polygon. To deliver clean rectangular tiles for visual labeling, we
crop each tile to the largest all-valid axis-aligned interior rectangle
of its source raster ("inscribed rectangle"). All visible pixels are
real Sentinel-2 reflectance — we just trim the polygon-shaped hole away.

Stretch is computed once across the full sample (per-band 2/98 percentile
over all valid pixels in all 30 scenes), then applied uniformly so dust
contrast is comparable across tiles.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import rasterio

REPO = Path(__file__).resolve().parents[3]
SAMPLE_CSV = REPO / "research" / "dust-honesty" / "data" / "sq1_dbb_values.csv"
OUT = REPO / "research" / "dust-honesty" / "figures" / "sq1_thumbnails.png"


def largest_interior_rect(mask: np.ndarray) -> tuple[int, int, int, int]:
    """
    Largest axis-aligned all-True rectangle inside a 2D bool mask.
    Standard histogram-based O(H*W) algorithm.
    Returns (row0, col0, row1, col1) inclusive-exclusive bounds.
    """
    h, w = mask.shape
    heights = np.zeros(w, dtype=np.int32)
    best = (0, 0, 0, 0)
    best_area = 0
    for r in range(h):
        heights = np.where(mask[r], heights + 1, 0)
        # largest rectangle in histogram `heights`
        stack: list[int] = []
        for c in range(w + 1):
            cur = heights[c] if c < w else 0
            while stack and heights[stack[-1]] > cur:
                top = stack.pop()
                left = stack[-1] + 1 if stack else 0
                height = heights[top]
                width = c - left
                area = height * width
                if area > best_area:
                    best_area = area
                    best = (r - height + 1, left, r + 1, left + width)
            stack.append(c)
    return best


def read_scene(path: Path):
    with rasterio.open(path) as src:
        r = src.read(3).astype(np.float32)
        g = src.read(2).astype(np.float32)
        b = src.read(1).astype(np.float32)
    return r, g, b


def valid_mask(r, g, b):
    return (r > 0) & (g > 0) & (b > 0) & np.isfinite(r) & np.isfinite(g) & np.isfinite(b)


def main():
    df = pd.read_csv(SAMPLE_CSV).sort_values(["date", "AOI"]).reset_index(drop=True)
    if len(df) != 30:
        print(f"WARNING: expected 30 scenes, got {len(df)}")

    crops: list[tuple[np.ndarray, np.ndarray, np.ndarray, str]] = []
    sample_pixels = {"r": [], "g": [], "b": []}

    for _, row in df.iterrows():
        path = REPO / "data" / "phase1" / row["AOI"] / f"{row['date']}.tif"
        r, g, b = read_scene(path)
        m = valid_mask(r, g, b)
        if not m.any():
            print(f"  empty mask: {path}")
            continue
        r0, c0, r1, c1 = largest_interior_rect(m)
        rc = r[r0:r1, c0:c1]
        gc = g[r0:r1, c0:c1]
        bc = b[r0:r1, c0:c1]
        # any zero inside the inscribed rect would be a bug; inscribed rect is all-valid by construction
        title = f"{row['date']}  {row['AOI']}"
        crops.append((rc, gc, bc, title))
        # sample for stretch (cap to keep memory sane)
        n = min(rc.size, 20000)
        idx = np.random.default_rng(0).choice(rc.size, n, replace=False)
        sample_pixels["r"].append(rc.flat[idx])
        sample_pixels["g"].append(gc.flat[idx])
        sample_pixels["b"].append(bc.flat[idx])
        h, w = rc.shape
        print(f"  {row['AOI']:18s} {row['date']}  src={r.shape}  crop={rc.shape}  ({h*w/r.size:.0%} of raster)")

    # Global 2/98 stretch per band, computed once across the whole sample
    lo_hi = {}
    for band, samples in sample_pixels.items():
        vals = np.concatenate(samples)
        lo_hi[band] = (float(np.percentile(vals, 2)), float(np.percentile(vals, 98)))
    print(f"\nGlobal stretch (2/98 percentile, per-stack):")
    for band, (lo, hi) in lo_hi.items():
        print(f"  {band}: [{lo:.4f}, {hi:.4f}]")

    def stretch(band_arr, lo, hi):
        return np.clip((band_arr - lo) / (hi - lo + 1e-6), 0, 1)

    # Render
    cols, rows = 5, 6
    # Sized to roughly match a typical 4:3 tile aspect
    fig, axes = plt.subplots(rows, cols, figsize=(cols * 3, rows * 3))
    for ax, (rc, gc, bc, title) in zip(axes.flat, crops):
        rgb = np.stack(
            [
                stretch(rc, *lo_hi["r"]),
                stretch(gc, *lo_hi["g"]),
                stretch(bc, *lo_hi["b"]),
            ],
            axis=-1,
        )
        ax.imshow(rgb)
        ax.set_title(title, fontsize=9)
        ax.axis("off")
    for ax in axes.flat[len(crops):]:
        ax.axis("off")
    plt.tight_layout()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT, dpi=120, bbox_inches="tight")
    plt.close(fig)
    print(f"\nWrote {OUT}")


if __name__ == "__main__":
    main()

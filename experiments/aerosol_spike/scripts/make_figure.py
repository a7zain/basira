"""Build the 2x2 spike figure: TROPOMI UVAI (clear|dust) over VIIRS AOD."""
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import rasterio

DATA = Path(__file__).resolve().parent.parent / "data"
FIGS = Path(__file__).resolve().parent.parent / "figures"
FIGS.mkdir(parents=True, exist_ok=True)

AOI_EXTENT = [46.4, 47.0, 24.4, 24.9]  # lon_min, lon_max, lat_min, lat_max


def load(path):
    if not path.exists():
        return None
    with rasterio.open(path) as src:
        return src.read(1)


def panel(ax, arr, title, vmin, vmax, cmap, missing_msg=None):
    ax.set_xlabel("Lon")
    ax.set_ylabel("Lat")
    ax.set_title(title, fontsize=10)
    if arr is None:
        ax.text(0.5, 0.5, missing_msg or "DATA UNAVAILABLE\nsee SPIKE_RESULTS.md",
                ha="center", va="center", transform=ax.transAxes,
                fontsize=9, color="#a00")
        ax.set_xlim(AOI_EXTENT[0], AOI_EXTENT[1])
        ax.set_ylim(AOI_EXTENT[2], AOI_EXTENT[3])
        return None
    im = ax.imshow(arr, extent=AOI_EXTENT, origin="upper",
                   cmap=cmap, vmin=vmin, vmax=vmax, aspect="auto")
    return im


def main():
    uvai_clear = load(DATA / "tropomi_uvai_clear.tif")
    uvai_dust = load(DATA / "tropomi_uvai_dust.tif")
    aod_clear = load(DATA / "viirs_aod_clear.tif")
    aod_dust = load(DATA / "viirs_aod_dust.tif")

    # Shared color ranges across columns so dust vs clear is obvious
    uvai_lo, uvai_hi = -1.0, 4.0
    aod_lo, aod_hi = 0.0, 2.0

    fig, axes = plt.subplots(2, 2, figsize=(11, 9))
    fig.suptitle("Aerosol spike: TROPOMI UVAI + VIIRS DB AOD over Riyadh AOI",
                 fontsize=12)

    im00 = panel(axes[0, 0], uvai_clear,
                 "TROPOMI UVAI — clear day (2022-12-15)",
                 uvai_lo, uvai_hi, "magma")
    im01 = panel(axes[0, 1], uvai_dust,
                 "TROPOMI UVAI — dust day (2022-05-17)",
                 uvai_lo, uvai_hi, "magma")
    im10 = panel(axes[1, 0], aod_clear,
                 "VIIRS AOD 550nm — clear day (2022-12-15)",
                 aod_lo, aod_hi, "viridis")
    im11 = panel(axes[1, 1], aod_dust,
                 "VIIRS AOD 550nm — dust day (2022-05-17)",
                 aod_lo, aod_hi, "viridis")

    for im, ax in [(im00, axes[0, 0]), (im01, axes[0, 1]),
                   (im10, axes[1, 0]), (im11, axes[1, 1])]:
        if im is not None:
            fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)

    plt.tight_layout(rect=[0, 0, 1, 0.96])
    out = FIGS / "spike_2x2.png"
    fig.savefig(out, dpi=140)
    print(f"wrote {out}")

    # Print numbers for the results doc
    def stat(a):
        return None if a is None else (float(np.nanmean(a)),
                                       float(np.nanmin(a)),
                                       float(np.nanmax(a)))
    print("UVAI clear (mean,min,max):", stat(uvai_clear))
    print("UVAI dust  (mean,min,max):", stat(uvai_dust))
    print("AOD  clear (mean,min,max):", stat(aod_clear))
    print("AOD  dust  (mean,min,max):", stat(aod_dust))


if __name__ == "__main__":
    main()

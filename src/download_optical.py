"""
Sentinel-2 Optical Imagery Downloader
======================================
Downloads true-color (RGB) Sentinel-2 L2A imagery for the Riyadh AOI
using the Sentinel Hub Process API on Copernicus Dataspace.

Three time periods: 2020, 2023, 2026 (Jan–Mar, least-cloudy mosaic).

Usage:
    python src/download_optical.py

Credentials:
    Set environment variables SH_CLIENT_ID and SH_CLIENT_SECRET,
    or the script will prompt for them interactively.
"""

import os
import sys
import time
import numpy as np
import matplotlib.pyplot as plt
from datetime import datetime

from dotenv import load_dotenv

load_dotenv()

from sentinelhub import (
    SHConfig,
    BBox,
    CRS,
    DataCollection,
    MimeType,
    MosaickingOrder,
    SentinelHubRequest,
    bbox_to_dimensions,
)

from utils import RIYADH_BBOX

# ── Paths ───────────────────────────────────────────────────
OPTICAL_DIR = "data/optical"
OUT_DIR     = "outputs"

# ── Time periods ────────────────────────────────────────────
PERIODS = {
    "2020": ("2020-01-01", "2020-03-31"),
    "2023": ("2023-01-01", "2023-03-31"),
    "2026": ("2026-01-01", "2026-03-31"),
}

# ── Evalscript: true-color RGB ──────────────────────────────
EVALSCRIPT_TRUE_COLOR = """
//VERSION=3
function setup() {
    return {
        input: [{
            bands: ["B04", "B03", "B02"]
        }],
        output: {
            bands: 3,
            sampleType: "FLOAT32"
        }
    };
}

function evaluatePixel(sample) {
    // Brightness boost (x2.5) for visual appeal
    var gain = 2.5;
    return [
        gain * sample.B04,
        gain * sample.B03,
        gain * sample.B02
    ];
}
"""

RESOLUTION = 20  # metres (fits single request under 2500px API limit)


def get_credentials():
    """Get OAuth client credentials from env vars or interactive input."""
    client_id = os.environ.get("SH_CLIENT_ID", "")
    client_secret = os.environ.get("SH_CLIENT_SECRET", "")

    if not client_id or not client_secret:
        print("Sentinel Hub credentials not found in environment.")
        print("Create OAuth client at: https://shapps.dataspace.copernicus.eu/dashboard/#/account/settings")
        print()
        client_id = input("Enter SH_CLIENT_ID: ").strip()
        client_secret = input("Enter SH_CLIENT_SECRET: ").strip()

    if not client_id or not client_secret:
        print("ERROR: Credentials are required.")
        sys.exit(1)

    return client_id, client_secret


CDSE_BASE_URL = "https://sh.dataspace.copernicus.eu"

def configure_sh(client_id, client_secret):
    """Configure sentinelhub for Copernicus Dataspace."""
    config = SHConfig()
    config.sh_client_id = client_id
    config.sh_client_secret = client_secret
    config.sh_base_url = CDSE_BASE_URL
    config.sh_token_url = (
        "https://identity.dataspace.copernicus.eu/"
        "auth/realms/CDSE/protocol/openid-connect/token"
    )
    return config


# CDSE-specific data collection (overrides default service URL)
S2_L2A_CDSE = DataCollection.SENTINEL2_L2A.define_from(
    "s2l2a_cdse",
    service_url=CDSE_BASE_URL,
)


MAX_PX = 2500  # Sentinel Hub per-axis pixel limit


def download_tile(config, bbox, size, time_interval, max_retries=4):
    """Download a single tile with retry and backoff."""
    request = SentinelHubRequest(
        evalscript=EVALSCRIPT_TRUE_COLOR,
        input_data=[
            SentinelHubRequest.input_data(
                data_collection=S2_L2A_CDSE,
                time_interval=time_interval,
                mosaicking_order=MosaickingOrder.LEAST_CC,
            )
        ],
        responses=[
            SentinelHubRequest.output_response("default", MimeType.TIFF),
        ],
        bbox=bbox,
        size=size,
        config=config,
    )
    for attempt in range(max_retries):
        try:
            data = request.get_data()
            return data[0]
        except Exception as e:
            wait = 30 * (2 ** attempt)
            if attempt < max_retries - 1:
                print(f"\n    Retry {attempt+1}/{max_retries} after "
                      f"{wait}s ({e.__class__.__name__})...", end=" ", flush=True)
                time.sleep(wait)
            else:
                raise


def download_image(config, bbox_obj, full_size, time_interval, label):
    """
    Download a true-color mosaic, tiling if the image exceeds
    the 2500 px API limit.
    """
    print(f"\n  Requesting {label} ({time_interval[0]} to {time_interval[1]})...")
    full_w, full_h = full_size

    # Check if tiling is needed
    n_cols = (full_w + MAX_PX - 1) // MAX_PX
    n_rows = (full_h + MAX_PX - 1) // MAX_PX

    if n_cols == 1 and n_rows == 1:
        image = download_tile(config, bbox_obj, full_size, time_interval)
    else:
        print(f"  Image {full_w}x{full_h} exceeds {MAX_PX}px limit — "
              f"splitting into {n_cols}x{n_rows} tiles...")
        west, south, east, north = bbox_obj
        lon_step = (east - west) / n_cols
        lat_step = (north - south) / n_rows

        # Tile widths/heights in pixels
        tile_ws = [full_w // n_cols] * n_cols
        tile_ws[-1] = full_w - sum(tile_ws[:-1])
        tile_hs = [full_h // n_rows] * n_rows
        tile_hs[-1] = full_h - sum(tile_hs[:-1])

        image = np.zeros((full_h, full_w, 3), dtype=np.float32)
        row_offset = 0
        for r in range(n_rows):
            col_offset = 0
            for c in range(n_cols):
                tile_bbox = BBox(
                    bbox=[
                        west + c * lon_step,
                        south + r * lat_step,
                        west + (c + 1) * lon_step,
                        south + (r + 1) * lat_step,
                    ],
                    crs=CRS.WGS84,
                )
                tw, th = tile_ws[c], tile_hs[r]
                print(f"    Tile ({r},{c}): {tw}x{th} px...", end=" ", flush=True)
                tile = download_tile(config, tile_bbox, (tw, th), time_interval)
                print("OK")
                time.sleep(10)  # respect rate limits
                # Rows: bottom-up in lat, but top-down in image
                # Row 0 = south = bottom of image
                img_row = full_h - row_offset - th
                image[img_row:img_row + th,
                      col_offset:col_offset + tw, :] = tile[:th, :tw, :]
                col_offset += tw
            row_offset += th

    print(f"  Downloaded: shape={image.shape}, dtype={image.dtype}, "
          f"range=[{image.min():.3f}, {image.max():.3f}]")
    return image


def save_geotiff_rgb(image, bbox_obj, path):
    """Save RGB image as a simple GeoTIFF using rasterio."""
    import rasterio
    from rasterio.transform import from_bounds

    os.makedirs(os.path.dirname(path), exist_ok=True)
    h, w, bands = image.shape

    west, south, east, north = bbox_obj
    transform = from_bounds(west, south, east, north, w, h)

    # Clip to [0, 1] and convert to uint8
    img_uint8 = (np.clip(image, 0, 1) * 255).astype(np.uint8)

    with rasterio.open(
        path, "w", driver="GTiff",
        height=h, width=w, count=bands,
        dtype="uint8", crs="EPSG:4326",
        transform=transform,
    ) as dst:
        for b in range(bands):
            dst.write(img_uint8[:, :, b], b + 1)
    print(f"  Saved GeoTIFF: {path}")


def save_png(image, path):
    """Save as PNG preview."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    img_clipped = np.clip(image, 0, 1)
    plt.imsave(path, img_clipped)
    print(f"  Saved PNG: {path}")


def main():
    os.makedirs(OPTICAL_DIR, exist_ok=True)
    os.makedirs(OUT_DIR, exist_ok=True)

    # ── Credentials ────────────────────────────────────────
    client_id, client_secret = get_credentials()
    config = configure_sh(client_id, client_secret)

    # ── AOI bounding box ───────────────────────────────────
    bbox = BBox(
        bbox=[
            RIYADH_BBOX["lon_min"], RIYADH_BBOX["lat_min"],
            RIYADH_BBOX["lon_max"], RIYADH_BBOX["lat_max"],
        ],
        crs=CRS.WGS84,
    )
    size = bbox_to_dimensions(bbox, resolution=RESOLUTION)
    print(f"AOI: {RIYADH_BBOX}")
    print(f"Output size: {size} pixels at {RESOLUTION} m resolution")

    # ── Download each period ───────────────────────────────
    images = {}
    for label, (start, end) in PERIODS.items():
        image = download_image(config, bbox, size, (start, end), label)

        # Save GeoTIFF
        save_geotiff_rgb(
            image, bbox,
            f"{OPTICAL_DIR}/riyadh_{label}.tif",
        )

        # Save PNG preview
        save_png(image, f"{OUT_DIR}/optical_{label}.png")

        images[label] = image

    # ── Three-panel comparison figure ──────────────────────
    print("\nGenerating timeline comparison figure...")
    fig, axes = plt.subplots(1, 3, figsize=(22, 8))
    fig.patch.set_facecolor("white")

    for ax, (label, image) in zip(axes, images.items()):
        img_clipped = np.clip(image, 0, 1)
        ax.imshow(img_clipped, aspect="equal")
        ax.set_title(f"Riyadh — {label}", fontsize=14, fontweight="bold", pad=8)
        ax.axis("off")
        for spine in ax.spines.values():
            spine.set_visible(True)
            spine.set_linewidth(1.0)
            spine.set_edgecolor("#444444")

    plt.suptitle(
        "Sentinel-2 True-Color Timeline — Riyadh, Saudi Arabia\n"
        "10 m resolution  ·  Least-cloudy mosaic  ·  Jan–Mar each year",
        fontsize=13, y=0.98,
    )
    plt.tight_layout()
    plt.savefig(
        f"{OUT_DIR}/10_optical_timeline.png",
        dpi=300, bbox_inches="tight", facecolor="white",
    )
    print(f"  Saved: {OUT_DIR}/10_optical_timeline.png")
    plt.close()

    print("\n✓ Optical imagery download complete.")
    print(f"  GeoTIFFs: {OPTICAL_DIR}/riyadh_{{2020,2023,2026}}.tif")
    print(f"  Previews: {OUT_DIR}/optical_{{2020,2023,2026}}.png")
    print(f"  Timeline: {OUT_DIR}/10_optical_timeline.png")


if __name__ == "__main__":
    main()

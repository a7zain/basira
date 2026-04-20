"""
Phase 5 — Annual Sentinel-2 Download (city-agnostic)
=====================================================
Downloads exactly two 4-band Sentinel-2 L2A scenes per city:
  - baseline_year / baseline_month
  - current_year / current_month

Scenes are stored as {year}_{month:02d}.tif under the city's
monthly_dir (reuses any existing file to save PU).

Usage:
    python src/phase5_download_annual.py --city riyadh
    python src/phase5_download_annual.py --city jeddah

Credentials:
    SH_CLIENT_ID and SH_CLIENT_SECRET env vars (see .env.example).
"""

import argparse
import os
import sys
import time

from dotenv import load_dotenv
from pyproj import Transformer

load_dotenv()

from sentinelhub import (
    BBox,
    CRS,
    DataCollection,
    MimeType,
    MosaickingOrder,
    SentinelHubRequest,
    bbox_to_dimensions,
    SHConfig,
)

from city_config import add_city_arg, load_city

RESOLUTION_DEFAULT = 20
BANDS = ["B02", "B03", "B04", "B08"]
PU_CEILING = 500  # Phase 5.0 per-session cap

CDSE_BASE_URL = "https://sh.dataspace.copernicus.eu"
CDSE_TOKEN_URL = (
    "https://identity.dataspace.copernicus.eu/"
    "auth/realms/CDSE/protocol/openid-connect/token"
)

EVALSCRIPT_4BAND = """
//VERSION=3
function setup() {
    return {
        input: [{
            bands: ["B02", "B03", "B04", "B08"]
        }],
        output: { bands: 4, sampleType: "FLOAT32" }
    };
}
function evaluatePixel(sample) {
    return [sample.B02, sample.B03, sample.B04, sample.B08];
}
"""

S2_L2A_CDSE = DataCollection.SENTINEL2_L2A.define_from(
    "s2l2a_cdse_phase5", service_url=CDSE_BASE_URL,
)


def get_credentials():
    cid = os.environ.get("SH_CLIENT_ID", "")
    cs = os.environ.get("SH_CLIENT_SECRET", "")
    if not cid or not cs:
        print("Sentinel Hub credentials not set. Add SH_CLIENT_ID / SH_CLIENT_SECRET to .env")
        sys.exit(1)
    return cid, cs


def configure_sh(client_id, client_secret):
    cfg = SHConfig()
    cfg.sh_client_id = client_id
    cfg.sh_client_secret = client_secret
    cfg.sh_base_url = CDSE_BASE_URL
    cfg.sh_token_url = CDSE_TOKEN_URL
    return cfg


def build_utm_bbox(city):
    t = Transformer.from_crs("EPSG:4326", city.target_crs, always_xy=True)
    x_min, y_min = t.transform(city.aoi["lon_min"], city.aoi["lat_min"])
    x_max, y_max = t.transform(city.aoi["lon_max"], city.aoi["lat_max"])
    bbox = BBox([x_min, y_min, x_max, y_max], CRS(city.utm_epsg))
    size = bbox_to_dimensions(bbox, resolution=city.resolution_m)
    return bbox, size


def estimate_pu(w, h, n_bands=4):
    return max((w * h) / (512 * 512) * (n_bands / 3), 0.001)


def download_monthly_mosaic(config, bbox, size, year, month, max_retries=4):
    start = f"{year}-{month:02d}-01"
    if month == 12:
        end = f"{year+1}-01-01"
    else:
        end = f"{year}-{month+1:02d}-01"
    request = SentinelHubRequest(
        evalscript=EVALSCRIPT_4BAND,
        input_data=[
            SentinelHubRequest.input_data(
                data_collection=S2_L2A_CDSE,
                time_interval=(start, end),
                mosaicking_order=MosaickingOrder.LEAST_CC,
            )
        ],
        responses=[SentinelHubRequest.output_response("default", MimeType.TIFF)],
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
                print(f"    retry {attempt+1}/{max_retries} in {wait}s ({e.__class__.__name__})")
                time.sleep(wait)
            else:
                raise


def save_geotiff_4band(image, bbox, path, target_crs):
    import rasterio
    from rasterio.transform import from_bounds
    os.makedirs(os.path.dirname(path), exist_ok=True)
    h, w = image.shape[:2]
    n_bands = image.shape[2] if image.ndim == 3 else 1
    west, south, east, north = bbox
    transform = from_bounds(west, south, east, north, w, h)
    with rasterio.open(
        path, "w", driver="GTiff",
        height=h, width=w, count=n_bands,
        dtype="float32", crs=target_crs,
        transform=transform,
        compress="deflate", predictor=3, tiled=True,
        blockxsize=256, blockysize=256,
    ) as dst:
        for b in range(n_bands):
            dst.write(image[:, :, b], b + 1)
    return os.path.getsize(path)


def main():
    parser = argparse.ArgumentParser()
    add_city_arg(parser)
    args = parser.parse_args()
    city = load_city(args.city)

    print(f"Phase 5 — Annual Download for {city.display_name}")
    print("=" * 50)

    os.makedirs(city.monthly_dir, exist_ok=True)

    targets = [
        (city.baseline_year, city.baseline_month),
        (city.current_year, city.current_month),
    ]

    bbox, size = build_utm_bbox(city)
    w, h = size
    pu = estimate_pu(w, h, n_bands=len(BANDS))
    print(f"  AOI: {city.aoi}")
    print(f"  CRS: {city.target_crs}")
    print(f"  Size: {w} x {h} px @ {city.resolution_m} m")
    print(f"  PU per scene: {pu:.2f}  |  ceiling: {PU_CEILING}")
    print()

    to_download = []
    for year, month in targets:
        path = os.path.join(city.monthly_dir, f"{year}_{month:02d}.tif")
        if os.path.exists(path):
            print(f"  {year}-{month:02d}: exists — skip ({os.path.getsize(path)/1e6:.1f} MB)")
        else:
            to_download.append((year, month, path))

    if not to_download:
        print("  All scenes already present. Done.")
        return

    total_pu = pu * len(to_download)
    if total_pu > PU_CEILING:
        print(f"  ERROR: would exceed PU ceiling ({total_pu:.1f} > {PU_CEILING})")
        sys.exit(1)

    cid, cs = get_credentials()
    config = configure_sh(cid, cs)

    cumulative_pu = 0.0
    for year, month, path in to_download:
        print(f"  {year}-{month:02d}: downloading …", end=" ", flush=True)
        try:
            image = download_monthly_mosaic(config, bbox, size, year, month)
        except Exception as e:
            print(f"FAILED ({e})")
            sys.exit(2)
        size_bytes = save_geotiff_4band(image, bbox, path, city.target_crs)
        cumulative_pu += pu
        print(f"OK ({size_bytes/1e6:.1f} MB) — PU used: {cumulative_pu:.1f}")
        time.sleep(3)

    print()
    print(f"  Done. PU used this run: {cumulative_pu:.1f}")
    print("=" * 50)


if __name__ == "__main__":
    main()

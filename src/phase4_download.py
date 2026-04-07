"""
Phase 4 — Monthly Sentinel-2 Downloader
========================================
Downloads the best (lowest cloud cover) Sentinel-2 L2A scene per month
for the Riyadh AOI from Jan 2020 to present.

Reads the catalog CSV from Phase 4 step 1, selects one scene per month,
and fetches 4-band GeoTIFFs (B02, B03, B04, B08) at 20m resolution
via the Sentinel Hub Process API.

Usage:
    python src/phase4_download.py

Credentials:
    Set SH_CLIENT_ID and SH_CLIENT_SECRET env vars, or enter interactively.
"""

import csv
import os
import sys
import time
from collections import defaultdict
from datetime import datetime

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

from utils import RIYADH_BBOX, TARGET_CRS

# ── Paths ───────────────────────────────────────────────────
CATALOG_CSV  = "outputs/phase4_catalog.csv"
MONTHLY_DIR  = "data/processed/monthly"
MANIFEST_CSV = "outputs/phase4_download_manifest.csv"
OUT_DIR      = "outputs"

# ── Download parameters ─────────────────────────────────────
RESOLUTION = 20  # metres
BANDS      = ["B02", "B03", "B04", "B08"]

# ── Safety ceiling ──────────────────────────────────────────
PU_CEILING = 5000

# ── CDSE configuration ──────────────────────────────────────
CDSE_BASE_URL  = "https://sh.dataspace.copernicus.eu"
CDSE_TOKEN_URL = (
    "https://identity.dataspace.copernicus.eu/"
    "auth/realms/CDSE/protocol/openid-connect/token"
)

# ── Evalscript: 4-band reflectance ──────────────────────────
EVALSCRIPT_4BAND = """
//VERSION=3
function setup() {
    return {
        input: [{
            bands: ["B02", "B03", "B04", "B08"]
        }],
        output: {
            bands: 4,
            sampleType: "FLOAT32"
        }
    };
}

function evaluatePixel(sample) {
    return [sample.B02, sample.B03, sample.B04, sample.B08];
}
"""

# CDSE-specific data collection
S2_L2A_CDSE = DataCollection.SENTINEL2_L2A.define_from(
    "s2l2a_cdse_dl",
    service_url=CDSE_BASE_URL,
)


def get_credentials():
    """Get OAuth client credentials from env vars or interactive input."""
    client_id = os.environ.get("SH_CLIENT_ID", "")
    client_secret = os.environ.get("SH_CLIENT_SECRET", "")

    if not client_id or not client_secret:
        print("Sentinel Hub credentials not found in environment.")
        print("Create OAuth client at: "
              "https://shapps.dataspace.copernicus.eu/dashboard/#/account/settings")
        print()
        client_id = input("Enter SH_CLIENT_ID: ").strip()
        client_secret = input("Enter SH_CLIENT_SECRET: ").strip()

    if not client_id or not client_secret:
        print("ERROR: Credentials are required.")
        sys.exit(1)

    return client_id, client_secret


def configure_sh(client_id, client_secret):
    """Configure sentinelhub for Copernicus Dataspace."""
    config = SHConfig()
    config.sh_client_id = client_id
    config.sh_client_secret = client_secret
    config.sh_base_url = CDSE_BASE_URL
    config.sh_token_url = CDSE_TOKEN_URL
    return config


def build_utm_bbox():
    """
    Build a sentinelhub BBox in UTM Zone 38N from the shared Riyadh AOI.
    Returns (bbox, (width, height)) for the target resolution.
    """
    transformer = Transformer.from_crs("EPSG:4326", TARGET_CRS, always_xy=True)
    x_min, y_min = transformer.transform(
        RIYADH_BBOX["lon_min"], RIYADH_BBOX["lat_min"],
    )
    x_max, y_max = transformer.transform(
        RIYADH_BBOX["lon_max"], RIYADH_BBOX["lat_max"],
    )
    bbox = BBox([x_min, y_min, x_max, y_max], CRS("32638"))
    size = bbox_to_dimensions(bbox, resolution=RESOLUTION)
    return bbox, size


def load_best_per_month(catalog_path):
    """
    Read the catalog CSV and select the single best scene per month
    (lowest cloud cover). Returns a sorted list of dicts.
    """
    rows = []
    with open(catalog_path, newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            cc = row["cloud_cover"]
            if cc == "" or cc is None:
                continue
            rows.append({
                "id": row["id"],
                "date": row["date"],
                "cloud_cover": float(cc),
            })

    # Group by year-month
    monthly = defaultdict(list)
    for r in rows:
        dt = datetime.strptime(r["date"][:10], "%Y-%m-%d")
        monthly[(dt.year, dt.month)].append(r)

    # Pick lowest cloud cover per month
    best = []
    for key in sorted(monthly.keys()):
        scene = min(monthly[key], key=lambda s: s["cloud_cover"])
        y, m = key
        best.append({
            "year": y,
            "month": m,
            "date": scene["date"][:10],
            "cloud_cover": scene["cloud_cover"],
            "scene_id": scene["id"],
            "output_path": os.path.join(MONTHLY_DIR, f"{y}_{m:02d}.tif"),
        })

    return best


def estimate_pu(width, height, n_bands=4):
    """Estimate Sentinel Hub PU for a single request."""
    pu = (width * height) / (512 * 512) * (n_bands / 3)
    return max(pu, 0.001)


def download_scene(config, bbox, size, date_str, max_retries=4):
    """
    Download a single scene via Process API.
    Returns raw TIFF bytes.
    """
    request = SentinelHubRequest(
        evalscript=EVALSCRIPT_4BAND,
        input_data=[
            SentinelHubRequest.input_data(
                data_collection=S2_L2A_CDSE,
                time_interval=(date_str, date_str),
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
                      f"{wait}s ({e.__class__.__name__}: {e})...",
                      end=" ", flush=True)
                time.sleep(wait)
            else:
                raise


def save_geotiff_4band(image, bbox, path):
    """Save 4-band float32 image as a GeoTIFF in UTM."""
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
        dtype="float32", crs=TARGET_CRS,
        transform=transform,
        compress="deflate",
        predictor=3,       # floating-point predictor
        tiled=True,
        blockxsize=256,
        blockysize=256,
    ) as dst:
        for b in range(n_bands):
            dst.write(image[:, :, b], b + 1)

    return os.path.getsize(path)


def save_manifest(records, path):
    """Write the download manifest CSV."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fieldnames = [
        "year_month", "date", "cloud_cover", "scene_id",
        "file_size_mb", "pu_estimated", "output_path",
    ]
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in records:
            writer.writerow(r)
    print(f"\n  Saved manifest: {path}")


def main():
    os.makedirs(MONTHLY_DIR, exist_ok=True)
    os.makedirs(OUT_DIR, exist_ok=True)

    # ── Load catalog ──────────────────────────────────────────
    if not os.path.exists(CATALOG_CSV):
        print(f"ERROR: Catalog not found at {CATALOG_CSV}")
        print("Run phase4_catalog.py first.")
        sys.exit(1)

    best = load_best_per_month(CATALOG_CSV)
    print(f"Phase 4 — Monthly Sentinel-2 Download")
    print("=" * 50)

    # ── Build UTM bbox ────────────────────────────────────────
    bbox, size = build_utm_bbox()
    w, h = size
    pu_per_request = estimate_pu(w, h, n_bands=len(BANDS))

    print(f"  AOI: {RIYADH_BBOX}")
    print(f"  CRS: {TARGET_CRS}")
    print(f"  Image size: {w} x {h} pixels at {RESOLUTION}m")
    print(f"  Bands: {', '.join(BANDS)}")
    print(f"  Scenes to download: {len(best)}")
    print(f"  PU per request: {pu_per_request:.2f}")
    print(f"  Total estimated PU: {pu_per_request * len(best):.1f}")
    print(f"  PU safety ceiling: {PU_CEILING}")
    print(f"  Est. disk per scene: ~13 MB (compressed DEFLATE)")
    print(f"  Est. total disk: ~{13 * len(best) / 1024:.1f} GB")
    print()

    # ── Check how many already exist ──────────────────────────
    existing = sum(1 for s in best if os.path.exists(s["output_path"]))
    remaining = len(best) - existing
    if existing > 0:
        print(f"  Already downloaded: {existing}/{len(best)} (will skip)")
        print(f"  Remaining: {remaining}")
        print()

    # ── Authenticate ──────────────────────────────────────────
    client_id, client_secret = get_credentials()
    config = configure_sh(client_id, client_secret)

    # ── Download loop ─────────────────────────────────────────
    cumulative_pu = 0.0
    manifest = []
    downloaded = 0
    skipped = 0

    for i, scene in enumerate(best, 1):
        label = f"{scene['year']}-{scene['month']:02d}"
        path = scene["output_path"]

        # Skip if already exists
        if os.path.exists(path):
            file_size = os.path.getsize(path)
            print(f"  [{i:>2}/{len(best)}] {label} — SKIP (exists, "
                  f"{file_size / 1e6:.1f} MB)")
            manifest.append({
                "year_month": label,
                "date": scene["date"],
                "cloud_cover": scene["cloud_cover"],
                "scene_id": scene["scene_id"],
                "file_size_mb": f"{file_size / 1e6:.1f}",
                "pu_estimated": "0 (cached)",
                "output_path": path,
            })
            skipped += 1
            continue

        # PU safety check
        if cumulative_pu + pu_per_request > PU_CEILING:
            print(f"\n  ERROR: PU ceiling would be exceeded "
                  f"({cumulative_pu:.1f} + {pu_per_request:.1f} > {PU_CEILING})")
            print(f"  Stopping after {downloaded} downloads.")
            break

        # Download
        print(f"  [{i:>2}/{len(best)}] {label} — "
              f"{scene['cloud_cover']:.1f}% cloud — downloading...",
              end=" ", flush=True)

        try:
            image = download_scene(config, bbox, size, scene["date"])
        except Exception as e:
            print(f"FAILED ({e})")
            manifest.append({
                "year_month": label,
                "date": scene["date"],
                "cloud_cover": scene["cloud_cover"],
                "scene_id": scene["scene_id"],
                "file_size_mb": "FAILED",
                "pu_estimated": f"{pu_per_request:.2f}",
                "output_path": path,
            })
            continue

        # Save GeoTIFF
        file_size = save_geotiff_4band(image, bbox, path)
        cumulative_pu += pu_per_request
        downloaded += 1

        print(f"OK ({file_size / 1e6:.1f} MB) — "
              f"PU: {cumulative_pu:.1f}/{PU_CEILING}")

        manifest.append({
            "year_month": label,
            "date": scene["date"],
            "cloud_cover": scene["cloud_cover"],
            "scene_id": scene["scene_id"],
            "file_size_mb": f"{file_size / 1e6:.1f}",
            "pu_estimated": f"{pu_per_request:.2f}",
            "output_path": path,
        })

        # Rate-limit: pause between requests
        if i < len(best):
            time.sleep(5)

    # ── Summary ───────────────────────────────────────────────
    save_manifest(manifest, MANIFEST_CSV)

    print()
    print("=" * 50)
    print(f"  Download complete.")
    print(f"  Downloaded: {downloaded}")
    print(f"  Skipped (cached): {skipped}")
    print(f"  Estimated PU used: {cumulative_pu:.1f}")
    print(f"  Output directory: {MONTHLY_DIR}/")
    print(f"  Manifest: {MANIFEST_CSV}")
    print("=" * 50)


if __name__ == "__main__":
    main()

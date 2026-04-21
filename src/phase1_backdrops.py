"""
Phase 1 — Wide-context backdrop downloader
==========================================
Downloads a single cloud-free RGB composite per AOI, using a bbox that
extends the tight KML polygon bbox by ~3× in each dimension (centred on
the polygon centroid).  Output is a JPEG visual asset for use as blurred
background imagery on the Basira site — not for analysis.

Usage (from repo root, sarsat env):
    python src/phase1_backdrops.py [--dry-run]

Outputs:
    assets/backdrops/<aoi_id>_context.jpg   (one per AOI, 200–500 KB)

PU budget: ~2 PU per AOI, ~6 PU total.  Script aborts if a single AOI
would exceed PU_PER_AOI_CEILING before downloading.

Do NOT modify phase1_download.py — this is a one-off pull.
"""

import os
import sys
import time
import argparse

import numpy as np
from PIL import Image
from shapely.geometry import Polygon
from pyproj import Transformer

from sentinelhub import (
    BBox,
    CRS,
    MimeType,
    MosaickingOrder,
    SentinelHubRequest,
    bbox_to_dimensions,
)

# ── Resolve paths relative to repo root regardless of CWD ──────────────
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(REPO_ROOT, "src"))

from phase1_aois import get_aoi, list_primary_aois          # noqa: E402
from phase4_download import S2_L2A_CDSE, get_credentials, configure_sh  # noqa: E402

# ── Constants ───────────────────────────────────────────────────────────
RESOLUTION    = 20          # metres — coarser = smaller file, fine for blurred bg
BANDS         = ["B02", "B03", "B04"]  # R/G/B only
DATE_START    = "2024-01-01"
DATE_END      = "2024-12-31"
JPEG_QUALITY  = 85
OUT_DIR       = os.path.join(REPO_ROOT, "assets", "backdrops")
TARGET_CRS    = "EPSG:32638"  # UTM Zone 38N — matches existing pipeline

# Abort if a single AOI download is estimated to exceed this PU count.
PU_PER_AOI_CEILING = 5.0

# How much to expand the tight polygon bbox on each side.
# 1.0 → 3× total width/height (1 tight + 1 extra each side).
EXPAND_FACTOR = 1.0

EVALSCRIPT_RGB = """
//VERSION=3
function setup() {
    return {
        input:  [{ bands: ["B02", "B03", "B04"] }],
        output: { bands: 3, sampleType: "FLOAT32" }
    };
}
function evaluatePixel(s) {
    // Return raw reflectance (0.0–1.0); Python handles stretch.
    return [s.B02, s.B03, s.B04];
}
"""


# ── Geometry helpers ─────────────────────────────────────────────────────

def polygon_centroid(polygon_lonlat):
    """Return (lon, lat) centroid from a list of [lon, lat] pairs."""
    shp = Polygon(polygon_lonlat)
    return shp.centroid.x, shp.centroid.y


def wide_bbox_wgs84(polygon_lonlat, expand_factor=EXPAND_FACTOR):
    """
    Compute a bbox ~3× the tight polygon bbox, centred on the centroid.

    expand_factor=1.0 adds 1× the tight width/height on each side,
    yielding 3× total extent.  Returns (minlon, minlat, maxlon, maxlat).
    """
    shp  = Polygon(polygon_lonlat)
    minx, miny, maxx, maxy = shp.bounds
    cx, cy = shp.centroid.x, shp.centroid.y
    w = maxx - minx
    h = maxy - miny
    margin_lon = w * expand_factor
    margin_lat = h * expand_factor
    return (cx - w/2 - margin_lon,
            cy - h/2 - margin_lat,
            cx + w/2 + margin_lon,
            cy + h/2 + margin_lat)


def wgs84_bbox_to_utm(minlon, minlat, maxlon, maxlat):
    """Return a sentinelhub BBox in UTM 38N from WGS84 coordinates."""
    t = Transformer.from_crs("EPSG:4326", TARGET_CRS, always_xy=True)
    x0, y0 = t.transform(minlon, minlat)
    x1, y1 = t.transform(maxlon, maxlat)
    return BBox([x0, y0, x1, y1], CRS("32638"))


def estimate_pu(width, height, n_bands=3):
    """Sentinel Hub PU estimate: 1 PU per 512×512 px per 3 bands."""
    return max((width * height) / (512 * 512) * (n_bands / 3), 0.001)


# ── Image processing ─────────────────────────────────────────────────────

def to_uint8(band_float, lo_pct=2, hi_pct=98):
    """
    Percentile stretch a single float32 band to uint8.
    Pixels at or below lo_pct → 0; at or above hi_pct → 255.
    """
    valid = band_float[band_float > 0]
    if valid.size == 0:
        return np.zeros(band_float.shape, dtype=np.uint8)
    lo = np.percentile(valid, lo_pct)
    hi = np.percentile(valid, hi_pct)
    if hi == lo:
        return np.zeros(band_float.shape, dtype=np.uint8)
    stretched = (band_float - lo) / (hi - lo)
    return np.clip(stretched * 255, 0, 255).astype(np.uint8)


def array_to_jpeg(data, out_path, quality=JPEG_QUALITY):
    """
    Convert a (H, W, 3) float32 reflectance array to a JPEG file.
    Applies percentile stretch per-band then saves as RGB JPEG.
    Returns file size in bytes.
    """
    r = to_uint8(data[:, :, 0])  # B04 → Red
    g = to_uint8(data[:, :, 1])  # B03 → Green
    b = to_uint8(data[:, :, 2])  # B02 → Blue
    rgb = np.stack([r, g, b], axis=2)
    img = Image.fromarray(rgb, mode="RGB")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    img.save(out_path, format="JPEG", quality=quality, optimize=True)
    return os.path.getsize(out_path)


# ── Download ─────────────────────────────────────────────────────────────

def download_backdrop(config, utm_bbox, size):
    """
    Single leastCC composite over DATE_START–DATE_END, returns numpy array.
    Retries up to 3 times with backoff.
    """
    request = SentinelHubRequest(
        evalscript=EVALSCRIPT_RGB,
        input_data=[
            SentinelHubRequest.input_data(
                data_collection=S2_L2A_CDSE,
                time_interval=(DATE_START, DATE_END),
                mosaicking_order=MosaickingOrder.LEAST_CC,
            )
        ],
        responses=[
            SentinelHubRequest.output_response("default", MimeType.TIFF),
        ],
        bbox=utm_bbox,
        size=size,
        config=config,
    )

    for attempt in range(3):
        try:
            data = request.get_data()
            return data[0]
        except Exception as e:
            wait = 30 * (2 ** attempt)
            if attempt < 2:
                print(f"    retry {attempt+1}/3 in {wait}s ({e.__class__.__name__})",
                      flush=True)
                time.sleep(wait)
            else:
                raise


# ── Main ──────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Phase 1 backdrop downloader")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print plan and PU estimates without downloading.")
    args = parser.parse_args()

    aois = list_primary_aois()

    print("Phase 1 — Wide-context Backdrop Downloader")
    print("=" * 55)
    print(f"  AOIs:       {', '.join(aois)}")
    print(f"  Date range: {DATE_START} → {DATE_END}")
    print(f"  Resolution: {RESOLUTION} m  (JPEG, not analysis)")
    print(f"  Bands:      B02 B03 B04  (RGB)")
    print(f"  Mosaicking: leastCC")
    print(f"  Expand:     {EXPAND_FACTOR}× → ~3× tight bbox in each dimension")
    print(f"  Output:     {OUT_DIR}/<aoi>_context.jpg")
    print()

    # ── Pre-flight: compute geometry and PU for all AOIs ──
    plans = []
    for aoi_key in aois:
        aoi    = get_aoi(aoi_key)
        wgs84  = wide_bbox_wgs84(aoi["polygon"])
        utm_bb = wgs84_bbox_to_utm(*wgs84)
        size   = bbox_to_dimensions(utm_bb, resolution=RESOLUTION)
        w, h   = size
        pu     = estimate_pu(w, h, n_bands=3)
        out_path = os.path.join(OUT_DIR, f"{aoi_key}_context.jpg")

        cx = (wgs84[0] + wgs84[2]) / 2
        cy = (wgs84[1] + wgs84[3]) / 2
        km_w = (wgs84[2] - wgs84[0]) * 111.0
        km_h = (wgs84[3] - wgs84[1]) * 111.0

        print(f"  {aoi_key}:")
        print(f"    wide bbox WGS84:  ({wgs84[0]:.5f}, {wgs84[1]:.5f}) → "
              f"({wgs84[2]:.5f}, {wgs84[3]:.5f})")
        print(f"    centroid:         ({cx:.5f}, {cy:.5f})")
        print(f"    extent:           ~{km_w:.1f} km × {km_h:.1f} km")
        print(f"    image size:       {w} × {h} px")
        print(f"    estimated PU:     {pu:.2f}")
        print(f"    output:           {os.path.relpath(out_path, REPO_ROOT)}")

        if pu > PU_PER_AOI_CEILING:
            print(f"\n  ABORT: {aoi_key} estimated at {pu:.2f} PU "
                  f"(ceiling {PU_PER_AOI_CEILING}).  Check bbox — do not download.")
            sys.exit(1)

        plans.append({
            "key":      aoi_key,
            "utm_bbox": utm_bb,
            "size":     size,
            "pu":       pu,
            "out_path": out_path,
        })
        print()

    total_pu = sum(p["pu"] for p in plans)
    print(f"  Total estimated PU: {total_pu:.2f}")
    print()

    if args.dry_run:
        print("  --dry-run: stopping before download.")
        return

    client_id, client_secret = get_credentials()
    config = configure_sh(client_id, client_secret)

    cumulative_pu = 0.0
    for p in plans:
        aoi_key  = p["key"]
        out_path = p["out_path"]

        if os.path.exists(out_path):
            sz = os.path.getsize(out_path)
            print(f"  [skip] {aoi_key} — already exists ({sz/1024:.0f} KB)")
            continue

        print(f"  [{aoi_key}] downloading...", end=" ", flush=True)
        data = download_backdrop(config, p["utm_bbox"], p["size"])

        if data is None or not np.any(data):
            print("NO DATA — no scenes found for this bbox/date range")
            continue

        sz = array_to_jpeg(data, out_path)
        cumulative_pu += p["pu"]
        print(f"OK  {sz/1024:.0f} KB  (est. PU so far: {cumulative_pu:.2f})")

        # Brief pause between requests to be polite to the API
        time.sleep(5)

    print()
    print("=" * 55)
    print(f"  Done. Estimated PU used: {cumulative_pu:.2f}")
    print(f"  Output: {OUT_DIR}/")


if __name__ == "__main__":
    # Run from repo root: python src/phase1_backdrops.py
    os.chdir(REPO_ROOT)
    main()

"""
Phase 1 — Wide-context backdrop downloader
==========================================
Downloads a single cloud-free RGB composite per AOI, using a bbox that
extends the tight KML polygon bbox by ~5× in each dimension (centred on
the polygon centroid).  Output is a JPEG visual asset for use as blurred
background imagery on the Basira site — not for analysis.

Usage (from repo root, sarsat env):
    python src/phase1_backdrops.py [--dry-run] [--overwrite]

Outputs:
    assets/backdrops/<aoi_id>_context.jpg   (one per AOI, 200–500 KB)

PU budget: ~3–5 PU per AOI.  Script aborts if a single AOI would exceed
PU_PER_AOI_CEILING before downloading.

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
DATE_START    = "2024-04-01"  # Saudi dry season: less haze, cleaner composites
DATE_END      = "2024-10-31"
JPEG_QUALITY  = 90
OUT_DIR       = os.path.join(REPO_ROOT, "assets", "backdrops")
TARGET_CRS    = "EPSG:32638"  # UTM Zone 38N — matches existing pipeline

# Abort if a single AOI download is estimated to exceed this PU count.
# Raised to 12.0 to accommodate 5× bbox (EXPAND_FACTOR=2.0); monthly budget is 30K PU.
PU_PER_AOI_CEILING = 12.0

# How much to expand the tight polygon bbox on each side.
# 2.0 → 5× total width/height (1 tight + 2 extra each side).
# Diriyah's tight polygon is small, so 5× gives it enough physical extent
# to be used as a full-viewport backdrop without JPEG artifacts through blur.
EXPAND_FACTOR = 2.0

# True-color stretch: gain=2.5 applied in evalscript, values clamped to [0,1].
# Band order MUST be [B04, B03, B02] = [Red, Green, Blue] for correct colors.
# Previous version incorrectly returned [B02, B03, B04] (Blue→R channel).
EVALSCRIPT_RGB = """
//VERSION=3
function setup() {
  return {
    input: [{bands: ["B02","B03","B04"]}],
    output: {bands: 3, sampleType: "AUTO"}
  };
}
function evaluatePixel(s) {
  // Standard true-color stretch — gain 2.5, clip at 1.0 reflectance.
  // B04=Red, B03=Green, B02=Blue: must be in this order for correct RGB.
  const gain = 2.5;
  return [
    Math.min(1, s.B04 * gain),
    Math.min(1, s.B03 * gain),
    Math.min(1, s.B02 * gain)
  ];
}
"""


# ── Geometry helpers ─────────────────────────────────────────────────────

def polygon_centroid(polygon_lonlat):
    """Return (lon, lat) centroid from a list of [lon, lat] pairs."""
    shp = Polygon(polygon_lonlat)
    return shp.centroid.x, shp.centroid.y


def wide_bbox_wgs84(polygon_lonlat, expand_factor=EXPAND_FACTOR):
    """
    Compute a wide bbox centred on the polygon centroid.

    expand_factor=2.0 adds 2× the tight width/height on each side,
    yielding 5× total extent.  Returns (minlon, minlat, maxlon, maxlat).
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

def array_to_jpeg(data, out_path, quality=JPEG_QUALITY):
    """
    Convert a (H, W, 3) array to a JPEG file and return file size in bytes.

    The evalscript uses sampleType "AUTO" with values in [0, 1], so sentinelhub
    returns the array as float32 in [0, 1].  We convert directly to uint8 —
    no per-band stretch, because the evalscript has already applied gain+clamp.
    Per-band percentile stretch (previous version) equalized all channels and
    destroyed color balance.
    """
    if data.dtype == np.uint8:
        rgb = data  # API returned uint8 directly (shouldn't happen with TIFF, but safe)
    else:
        rgb = np.clip(data * 255.0, 0, 255).astype(np.uint8)
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
    parser.add_argument("--overwrite", action="store_true",
                        help="Re-download and overwrite existing output files.")
    args = parser.parse_args()

    aois = list_primary_aois()

    print("Phase 1 — Wide-context Backdrop Downloader")
    print("=" * 55)
    print(f"  AOIs:       {', '.join(aois)}")
    print(f"  Date range: {DATE_START} → {DATE_END}")
    print(f"  Resolution: {RESOLUTION} m  (JPEG, not analysis)")
    print(f"  Bands:      B02 B03 B04  (RGB)")
    print(f"  Mosaicking: leastCC")
    print(f"  Expand:     {EXPAND_FACTOR}× → ~{1+2*EXPAND_FACTOR:.0f}× tight bbox in each dimension")
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

        if os.path.exists(out_path) and not args.overwrite:
            sz = os.path.getsize(out_path)
            print(f"  [skip] {aoi_key} — already exists ({sz/1024:.0f} KB)  (use --overwrite to replace)")
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

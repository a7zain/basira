"""
Phase 1 — Parameterized Sentinel-2 Downloader
==============================================
Monthly 6-band (B02, B03, B04, B08, B11, B12) least-cloud mosaics at 10 m
for a named Phase 1 AOI, over a year-month range.

Usage:
    python src/phase1_download.py --aoi <name> --start YYYY-MM --end YYYY-MM [--preview]

OAuth credentials and Process API request scaffolding are imported from
phase4_download.py to avoid duplication.
"""

import argparse
import os
import sys
import time
from datetime import datetime
from calendar import monthrange

from pyproj import Transformer

from sentinelhub import (
    BBox,
    CRS,
    MimeType,
    MosaickingOrder,
    SentinelHubRequest,
    bbox_to_dimensions,
)

from phase1_aois import get_aoi, list_aois
from phase4_download import (
    S2_L2A_CDSE,
    get_credentials,
    configure_sh,
    save_geotiff_4band,  # generic N-band writer despite the name
)

# ── Download parameters ─────────────────────────────────────
RESOLUTION = 10  # metres
BANDS = ["B02", "B03", "B04", "B08", "B11", "B12"]
TARGET_CRS = "EPSG:32638"  # UTM Zone 38N (covers Riyadh)
PU_CEILING = 5000

DATA_ROOT = "data/phase1"

# Evalscript: 6-band reflectance, float32
EVALSCRIPT_6BAND = """
//VERSION=3
function setup() {
    return {
        input: [{
            bands: ["B02", "B03", "B04", "B08", "B11", "B12"]
        }],
        output: {
            bands: 6,
            sampleType: "FLOAT32"
        }
    };
}

function evaluatePixel(s) {
    return [s.B02, s.B03, s.B04, s.B08, s.B11, s.B12];
}
"""


def build_utm_bbox(bbox_wgs84):
    """Reproject an (minlon, minlat, maxlon, maxlat) bbox to UTM 38N and size at RESOLUTION."""
    lon_min, lat_min, lon_max, lat_max = bbox_wgs84
    transformer = Transformer.from_crs("EPSG:4326", TARGET_CRS, always_xy=True)
    x_min, y_min = transformer.transform(lon_min, lat_min)
    x_max, y_max = transformer.transform(lon_max, lat_max)
    bbox = BBox([x_min, y_min, x_max, y_max], CRS("32638"))
    size = bbox_to_dimensions(bbox, resolution=RESOLUTION)
    return bbox, size


def month_range(start_ym, end_ym):
    """Yield (year, month) tuples inclusive from 'YYYY-MM' to 'YYYY-MM'."""
    s = datetime.strptime(start_ym, "%Y-%m")
    e = datetime.strptime(end_ym, "%Y-%m")
    if e < s:
        raise ValueError("end must be >= start")
    y, m = s.year, s.month
    while (y, m) <= (e.year, e.month):
        yield y, m
        m += 1
        if m == 13:
            m = 1
            y += 1


def estimate_pu(width, height, n_bands):
    """SH PU estimate for a single Process API request."""
    pu = (width * height) / (512 * 512) * (n_bands / 3)
    return max(pu, 0.001)


def download_month(config, bbox, size, year, month, max_retries=4):
    """Download a least-cloud mosaic across the full month. Returns the image array."""
    last_day = monthrange(year, month)[1]
    t0 = f"{year}-{month:02d}-01"
    t1 = f"{year}-{month:02d}-{last_day:02d}"

    request = SentinelHubRequest(
        evalscript=EVALSCRIPT_6BAND,
        input_data=[
            SentinelHubRequest.input_data(
                data_collection=S2_L2A_CDSE,
                time_interval=(t0, t1),
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
                print(f"    retry {attempt+1}/{max_retries} in {wait}s "
                      f"({e.__class__.__name__})", flush=True)
                time.sleep(wait)
            else:
                raise


def parse_args():
    p = argparse.ArgumentParser(description="Phase 1 Sentinel-2 downloader")
    p.add_argument("--aoi", required=True, choices=list_aois(),
                   help="AOI key from phase1_aois.py")
    p.add_argument("--start", required=True, help="Start year-month (YYYY-MM)")
    p.add_argument("--end", required=True, help="End year-month (YYYY-MM)")
    p.add_argument("--preview", action="store_true",
                   help="Download only the most recent month in the range and exit.")
    return p.parse_args()


def main():
    args = parse_args()
    aoi = get_aoi(args.aoi)
    out_dir = os.path.join(DATA_ROOT, args.aoi)
    os.makedirs(out_dir, exist_ok=True)

    bbox, (w, h) = build_utm_bbox(aoi["bbox_wgs84"])
    pu_per = estimate_pu(w, h, n_bands=len(BANDS))

    months = list(month_range(args.start, args.end))
    if args.preview:
        months = months[-1:]

    print("Phase 1 — Sentinel-2 Download")
    print("=" * 50)
    print(f"  AOI:         {args.aoi}  ({aoi['name']})")
    print(f"  bbox WGS84:  {aoi['bbox_wgs84']}")
    print(f"  CRS:         {TARGET_CRS}")
    print(f"  Size:        {w} x {h} px at {RESOLUTION} m")
    print(f"  Bands:       {', '.join(BANDS)}")
    print(f"  Months:      {len(months)} ({months[0][0]}-{months[0][1]:02d} → "
          f"{months[-1][0]}-{months[-1][1]:02d})")
    print(f"  PU / month:  {pu_per:.2f}")
    print(f"  PU total:    {pu_per * len(months):.1f}")
    print(f"  Output:      {out_dir}/YYYY-MM.tif")
    if args.preview:
        print("  MODE:        PREVIEW (single month)")
    print()

    # Skip-count existing
    to_do = []
    for y, m in months:
        path = os.path.join(out_dir, f"{y}-{m:02d}.tif")
        if os.path.exists(path):
            print(f"  [skip] {y}-{m:02d} — {os.path.getsize(path)/1e6:.1f} MB")
        else:
            to_do.append((y, m, path))

    if not to_do:
        print("  Nothing to do — all months present.")
        return

    client_id, client_secret = get_credentials()
    config = configure_sh(client_id, client_secret)

    cumulative_pu = 0.0
    for i, (y, m, path) in enumerate(to_do, 1):
        label = f"{y}-{m:02d}"
        if cumulative_pu + pu_per > PU_CEILING:
            print(f"  PU ceiling reached ({cumulative_pu:.1f}). Stopping.")
            break

        print(f"  [{i:>2}/{len(to_do)}] {label} — downloading...",
              end=" ", flush=True)
        try:
            image = download_month(config, bbox, (w, h), y, m)
        except Exception as e:
            print(f"FAILED ({e.__class__.__name__}: {e})")
            continue

        # Detect empty mosaic (no scenes in month) — all zeros
        import numpy as np
        if image is None or not np.any(image):
            print("NO DATA (no scenes this month)")
            continue

        file_size = save_geotiff_4band(image, bbox, path)
        cumulative_pu += pu_per
        print(f"OK ({file_size/1e6:.1f} MB) — PU {cumulative_pu:.1f}/{PU_CEILING}")

        if i < len(to_do):
            time.sleep(5)

    print()
    print("=" * 50)
    print(f"  Estimated PU used: {cumulative_pu:.1f}")
    print(f"  Output directory:  {out_dir}/")


if __name__ == "__main__":
    main()

"""
Phase 1 — Parameterized Sentinel-2 Downloader (polygon geometry)
=================================================================
Monthly 6-band (B02, B03, B04, B08, B11, B12) least-cloud mosaics at 10 m
for a named Phase 1 AOI, over a year-month range. Uses the AOI's
polygon (not just its bbox) as the Process API geometry, so pixels
outside the polygon are returned as nodata.

Usage:
    python src/phase1_download.py --aoi <name> --start YYYY-MM --end YYYY-MM [--preview]
"""

import argparse
import os
import sys
import time
from datetime import datetime
from calendar import monthrange

import numpy as np
from pyproj import Transformer
from shapely.geometry import Polygon
from shapely.ops import transform as shp_transform

from sentinelhub import (
    BBox,
    CRS,
    Geometry,
    MimeType,
    MosaickingOrder,
    SentinelHubRequest,
    bbox_to_dimensions,
)

from phase1_aois import get_aoi, list_primary_aois
from phase4_download import (
    S2_L2A_CDSE,
    get_credentials,
    configure_sh,
    save_geotiff_4band,  # generic N-band writer despite the name
)

RESOLUTION = 10  # metres
BANDS = ["B02", "B03", "B04", "B08", "B11", "B12"]
TARGET_CRS = "EPSG:32638"  # UTM Zone 38N
PU_CEILING = 5000
DATA_ROOT = "data/phase1"

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


def polygon_to_utm(polygon_lonlat):
    """Return a shapely Polygon in UTM 38N from a list of [lon, lat]."""
    t = Transformer.from_crs("EPSG:4326", TARGET_CRS, always_xy=True).transform
    wgs_poly = Polygon(polygon_lonlat)
    return shp_transform(t, wgs_poly)


def build_request_geometry(polygon_lonlat):
    """Return (Geometry in UTM, BBox in UTM, (w,h)) for a Process API request."""
    utm_poly = polygon_to_utm(polygon_lonlat)
    minx, miny, maxx, maxy = utm_poly.bounds
    bbox = BBox([minx, miny, maxx, maxy], CRS("32638"))
    size = bbox_to_dimensions(bbox, resolution=RESOLUTION)
    geometry = Geometry(utm_poly, crs=CRS("32638"))
    return geometry, bbox, size


def month_range(start_ym, end_ym):
    s = datetime.strptime(start_ym, "%Y-%m")
    e = datetime.strptime(end_ym, "%Y-%m")
    if e < s:
        raise ValueError("end must be >= start")
    y, m = s.year, s.month
    while (y, m) <= (e.year, e.month):
        yield y, m
        m += 1
        if m == 13:
            m, y = 1, y + 1


def estimate_pu(width, height, n_bands):
    pu = (width * height) / (512 * 512) * (n_bands / 3)
    return max(pu, 0.001)


def download_month(config, geometry, size, year, month, max_retries=4):
    """Least-cloud mosaic across the full month, masked by polygon."""
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
        geometry=geometry,
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
    p.add_argument("--aoi", required=True, choices=list_primary_aois(),
                   help="Primary AOI key from phase1_aois.py")
    p.add_argument("--start", required=True, help="Start year-month (YYYY-MM)")
    p.add_argument("--end", required=True, help="End year-month (YYYY-MM)")
    p.add_argument("--preview", action="store_true",
                   help="Download only the most recent month and exit.")
    return p.parse_args()


def main():
    args = parse_args()
    aoi = get_aoi(args.aoi)
    out_dir = os.path.join(DATA_ROOT, args.aoi)
    os.makedirs(out_dir, exist_ok=True)

    geometry, bbox, (w, h) = build_request_geometry(aoi["polygon"])
    pu_per = estimate_pu(w, h, n_bands=len(BANDS))

    months = list(month_range(args.start, args.end))
    if args.preview:
        months = months[-1:]

    print("Phase 1 — Sentinel-2 Download (polygon geometry)")
    print("=" * 55)
    print(f"  AOI:         {args.aoi}  ({aoi['name']})")
    print(f"  polygon:     {len(aoi['polygon'])} vertices")
    print(f"  bbox WGS84:  {tuple(round(x,4) for x in aoi['bbox'])}")
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
            image = download_month(config, geometry, (w, h), y, m)
        except Exception as e:
            print(f"FAILED ({e.__class__.__name__}: {e})")
            continue

        if image is None or not np.any(image):
            print("NO DATA (no scenes this month)")
            continue

        file_size = save_geotiff_4band(image, bbox, path)
        cumulative_pu += pu_per
        print(f"OK ({file_size/1e6:.1f} MB) — PU {cumulative_pu:.1f}/{PU_CEILING}")

        if i < len(to_do):
            time.sleep(5)

    print()
    print("=" * 55)
    print(f"  Estimated PU used: {cumulative_pu:.1f}")
    print(f"  Output directory:  {out_dir}/")


if __name__ == "__main__":
    main()

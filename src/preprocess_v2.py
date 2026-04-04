"""
SAR Change Detection — Preprocessing (v2)
==========================================
Properly georeference, reproject, crop, filter, and align
two Sentinel-1 GRD COG scenes for change detection.

Key improvements over v1:
  1. Parses GCPs from annotation XML and assigns CRS (EPSG:4326)
  2. Reprojects via GCP-based warping to UTM EPSG:32638
  3. Crops to Riyadh geographic bounding box on a fixed grid
  4. Prints scene extents and overlap check BEFORE processing
  5. Applies Lee speckle filter before saving
  6. Exports as GeoTIFF preserving georeferencing

Usage:
    python src/preprocess_v2.py
"""

import xml.etree.ElementTree as ET
import numpy as np
import rasterio
from rasterio.control import GroundControlPoint
from rasterio.crs import CRS
from rasterio.warp import reproject, Resampling, transform_bounds
from rasterio.transform import from_bounds
import matplotlib.pyplot as plt
import os

from utils import (
    RIYADH_BBOX,
    TARGET_CRS,
    TARGET_RES,
    lee_filter,
    amplitude_to_db,
)

# ── File Paths ──────────────────────────────────────────────
RAW = "data/raw"

SCENES = {
    "2022": {
        "tiff": f"{RAW}/S1A_IW_GRDH_1SDV_20220125T145758_20220125T145823_041619_04F365_5BEC_COG.SAFE/"
                "measurement/s1a-iw-grd-vv-20220125t145758-20220125t145823-041619-04f365-001-cog.tiff",
        "xml":  f"{RAW}/S1A_IW_GRDH_1SDV_20220125T145758_20220125T145823_041619_04F365_5BEC_COG.SAFE/"
                "annotation/s1a-iw-grd-vv-20220125t145758-20220125t145823-041619-04f365-001-cog.xml",
        "label": "Riyadh — Jan 2022 (SAR VV)",
    },
    "2024": {
        "tiff": f"{RAW}/S1A_IW_GRDH_1SDV_20240220T145808_20240220T145833_052644_065E6B_D52C_COG.SAFE/"
                "measurement/s1a-iw-grd-vv-20240220t145808-20240220t145833-052644-065e6b-001-cog.tiff",
        "xml":  f"{RAW}/S1A_IW_GRDH_1SDV_20240220T145808_20240220T145833_052644_065E6B_D52C_COG.SAFE/"
                "annotation/s1a-iw-grd-vv-20240220t145808-20240220t145833-052644-065e6b-001-cog.xml",
        "label": "Riyadh — Feb 2024 (SAR VV)",
    },
}

OUT_DIR = "data/processed"
OUTPUT_DIR = "outputs"
GCP_CRS = CRS.from_epsg(4326)


# ── GCP Parsing ─────────────────────────────────────────────
def parse_gcps(xml_path):
    """
    Parse geolocation grid points from a Sentinel-1 annotation XML.

    Returns
    -------
    gcps : list of rasterio.control.GroundControlPoint
    lats : np.ndarray
    lons : np.ndarray
    """
    tree = ET.parse(xml_path)
    root = tree.getroot()
    gcps, lats, lons = [], [], []
    for g in root.findall(".//geolocationGridPoint"):
        line  = int(g.find("line").text)
        pixel = int(g.find("pixel").text)
        lat   = float(g.find("latitude").text)
        lon   = float(g.find("longitude").text)
        lats.append(lat)
        lons.append(lon)
        # rasterio GCP: row=line, col=pixel, x=easting/lon, y=northing/lat
        gcps.append(GroundControlPoint(row=line, col=pixel, x=lon, y=lat))
    return gcps, np.array(lats), np.array(lons)


# ── Overlap Check ───────────────────────────────────────────
def check_overlap(year, lats, lons, bbox):
    """
    Print the scene's geographic extent and assess overlap with the AOI.

    Returns True if the scene sufficiently covers the bounding box.
    """
    lat_min, lat_max = lats.min(), lats.max()
    lon_min, lon_max = lons.min(), lons.max()

    print(f"\n  {year} scene extent:")
    print(f"    lat: {lat_min:.3f} to {lat_max:.3f}  "
          f"(AOI needs {bbox['lat_min']} – {bbox['lat_max']})")
    print(f"    lon: {lon_min:.3f} to {lon_max:.3f}  "
          f"(AOI needs {bbox['lon_min']} – {bbox['lon_max']})")

    gcps_in = sum(
        1 for la, lo in zip(lats, lons)
        if bbox["lat_min"] <= la <= bbox["lat_max"]
        and bbox["lon_min"] <= lo <= bbox["lon_max"]
    )
    print(f"    GCPs inside AOI: {gcps_in}")

    # Bounding-box overlap test
    lat_ok = lat_min < bbox["lat_max"] and lat_max > bbox["lat_min"]
    lon_ok = lon_min < bbox["lon_max"] and lon_max > bbox["lon_min"]
    overlaps = lat_ok and lon_ok

    # Coverage fraction (how much of the AOI is covered)
    covered_lat = (min(lat_max, bbox["lat_max"]) -
                   max(lat_min, bbox["lat_min"])) / (bbox["lat_max"] - bbox["lat_min"])
    covered_lon = (min(lon_max, bbox["lon_max"]) -
                   max(lon_min, bbox["lon_min"])) / (bbox["lon_max"] - bbox["lon_min"])
    coverage = max(0, covered_lat) * max(0, covered_lon) * 100

    print(f"    AOI coverage: {coverage:.1f}%  "
          f"({'OK' if coverage >= 80 else 'WARNING: partial coverage'})")

    if not overlaps:
        print(f"    *** Scene does NOT overlap the Riyadh AOI — "
              "download a better-matched scene! ***")
    elif coverage < 80:
        print(f"    *** Less than 80% AOI coverage — "
              "consider downloading a better-matched scene. ***")

    return overlaps, coverage


# ── Reprojection ────────────────────────────────────────────
def reproject_with_gcps(src_path, gcps, bbox, target_crs, target_res):
    """
    Warp a Sentinel-1 COG (no embedded CRS) to a fixed UTM grid
    using GCPs from the annotation XML.

    Parameters
    ----------
    src_path   : str   Path to the input TIFF.
    gcps       : list  rasterio GroundControlPoint objects (in EPSG:4326).
    bbox       : dict  lat_min/max, lon_min/max of the AOI.
    target_crs : str   Target CRS (e.g. "EPSG:32638").
    target_res : float Pixel size in CRS units (metres for UTM).

    Returns
    -------
    dst_array   : np.ndarray (float32), shape (H, W)
    dst_transform : rasterio.transform.Affine
    """
    with rasterio.open(src_path) as src:
        print(f"  Source shape : {src.height} x {src.width}")
        print(f"  Source CRS   : {src.crs}  (will be overridden by GCPs)")

        # Fixed output grid derived from the AOI bounding box
        dst_bounds = transform_bounds(
            "EPSG:4326", target_crs,
            bbox["lon_min"], bbox["lat_min"],
            bbox["lon_max"], bbox["lat_max"],
        )
        dst_left, dst_bottom, dst_right, dst_top = dst_bounds
        dst_width  = int((dst_right - dst_left)  / target_res)
        dst_height = int((dst_top   - dst_bottom) / target_res)
        print(f"  Target bounds (UTM): {tuple(f'{v:.1f}' for v in dst_bounds)}")
        print(f"  Target shape : {dst_height} x {dst_width}")

        dst_transform = from_bounds(
            dst_left, dst_bottom, dst_right, dst_top,
            dst_width, dst_height,
        )

        dst_array = np.zeros((dst_height, dst_width), dtype=np.float32)

        reproject(
            source=rasterio.band(src, 1),
            destination=dst_array,
            gcps=gcps,
            src_crs=GCP_CRS,          # CRS that the GCP coords are in
            dst_transform=dst_transform,
            dst_crs=target_crs,
            resampling=Resampling.bilinear,
        )

    nonzero = np.count_nonzero(dst_array)
    valid_pct = 100.0 * nonzero / dst_array.size
    print(f"  Reprojected  : min={dst_array.min():.1f}, "
          f"max={dst_array.max():.1f}, valid={valid_pct:.1f}%")

    if valid_pct < 50:
        print("  WARNING: <50% valid pixels — scene may only partially "
              "cover the AOI.")

    return dst_array, dst_transform


# ── GeoTIFF Export ──────────────────────────────────────────
def save_geotiff(arr, transform, crs, path, nodata=0):
    """Save a 2D array as a single-band GeoTIFF."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with rasterio.open(
        path, "w",
        driver="GTiff",
        height=arr.shape[0],
        width=arr.shape[1],
        count=1,
        dtype=arr.dtype,
        crs=crs,
        transform=transform,
        nodata=nodata,
    ) as dst:
        dst.write(arr, 1)
    print(f"  Saved: {path}")


# ── Main Pipeline ───────────────────────────────────────────
def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # ── Step 0: Overlap check before any heavy work ─────────
    print("=" * 60)
    print("STEP 0: Checking scene extents and AOI overlap")
    print("=" * 60)
    print(f"\nRiyadh AOI: lat {RIYADH_BBOX['lat_min']}–{RIYADH_BBOX['lat_max']}, "
          f"lon {RIYADH_BBOX['lon_min']}–{RIYADH_BBOX['lon_max']}")

    scene_gcps = {}
    all_ok = True
    rel_orbits = {}
    for year, scene in SCENES.items():
        gcps, lats, lons = parse_gcps(scene["xml"])
        overlaps, coverage = check_overlap(year, lats, lons, RIYADH_BBOX)
        scene_gcps[year] = gcps
        if not overlaps or coverage < 50:
            all_ok = False

        # Extract orbit numbers from annotation XML
        tree = ET.parse(scene["xml"])
        root = tree.getroot()
        abs_orbit = root.findtext(".//absoluteOrbitNumber")
        rel_orbit = root.findtext(".//relativeOrbitNumber")
        pass_dir  = root.findtext(".//pass")
        if abs_orbit:
            abs_orb = int(abs_orbit)
            # Compute relative orbit for S1A: (abs - 73) % 175 + 1
            if rel_orbit is None:
                rel_orb = (abs_orb - 73) % 175 + 1
            else:
                rel_orb = int(rel_orbit)
            print(f"    Absolute orbit: {abs_orb}  |  "
                  f"Relative orbit: {rel_orb}  |  Pass: {pass_dir}")
            rel_orbits[year] = rel_orb

    # Verify same relative orbit
    if len(rel_orbits) == 2:
        orb_vals = list(rel_orbits.values())
        if orb_vals[0] == orb_vals[1]:
            print(f"\n  ✓ Both scenes share relative orbit {orb_vals[0]} — "
                  "geometry is consistent.")
        else:
            print(f"\n  ✗ WARNING: Different relative orbits "
                  f"({rel_orbits}) — viewing geometry mismatch!")
            all_ok = False

    if not all_ok:
        print("\n*** At least one scene has insufficient AOI coverage. ***")
        print("*** Consider downloading better-matched Sentinel-1 scenes. ***")
        print("*** Continuing anyway — output may be mostly nodata.       ***\n")

    # ── Steps 1-4: Reproject, filter, export ────────────────
    results = {}
    for year, scene in SCENES.items():
        print(f"\n{'=' * 60}")
        print(f"Processing {year}...")
        print(f"{'=' * 60}")

        print("\n[1] Reprojecting to UTM via GCPs...")
        amp, transform = reproject_with_gcps(
            scene["tiff"],
            scene_gcps[year],
            RIYADH_BBOX,
            TARGET_CRS,
            TARGET_RES,
        )

        print("\n[2] Applying Lee speckle filter (7x7 window)...")
        amp_filtered = lee_filter(amp, window_size=7)

        print("\n[3] Converting to dB scale...")
        db = amplitude_to_db(amp_filtered)

        print("\n[4] Saving outputs...")
        save_geotiff(amp_filtered, transform, TARGET_CRS,
                     f"{OUT_DIR}/amplitude_{year}.tif")
        save_geotiff(db, transform, TARGET_CRS,
                     f"{OUT_DIR}/db_{year}.tif")
        np.save(f"{OUT_DIR}/db_{year}.npy", db)
        print(f"  Saved: {OUT_DIR}/db_{year}.npy")

        results[year] = {
            "db": db, "amp": amp_filtered,
            "transform": transform, "label": scene["label"],
        }

    # ── Alignment verification ───────────────────────────────
    print(f"\n{'=' * 60}")
    print("Verifying spatial alignment...")
    print(f"{'=' * 60}")
    for year, r in results.items():
        print(f"  {year}: shape={r['db'].shape}, transform={r['transform']}")

    shapes_match    = results["2022"]["db"].shape == results["2024"]["db"].shape
    transforms_match = results["2022"]["transform"] == results["2024"]["transform"]
    print(f"\n  Shapes match    : {shapes_match}")
    print(f"  Transforms match: {transforms_match}")

    if shapes_match and transforms_match:
        print("  ✓ Perfect pixel-to-pixel alignment confirmed!")
    else:
        print("  ✗ Alignment mismatch — check inputs.")
        return

    # ── Visualization ────────────────────────────────────────
    print("\n[5] Generating comparison plot...")
    db_2022 = results["2022"]["db"]
    db_2024 = results["2024"]["db"]

    valid = db_2022[db_2022 > -30]
    vmin = np.percentile(valid, 2)
    vmax = np.percentile(valid, 98)

    fig, axes = plt.subplots(1, 2, figsize=(16, 8))
    axes[0].imshow(db_2022, cmap="gray", vmin=vmin, vmax=vmax)
    axes[0].set_title(results["2022"]["label"], fontsize=14)
    axes[0].axis("off")
    axes[1].imshow(db_2024, cmap="gray", vmin=vmin, vmax=vmax)
    axes[1].set_title(results["2024"]["label"], fontsize=14)
    axes[1].axis("off")

    plt.suptitle("Sentinel-1 SAR (VV) — GCP-corrected & Aligned",
                 fontsize=15, y=0.98)
    plt.tight_layout()
    plt.savefig(f"{OUTPUT_DIR}/02_riyadh_aligned.png",
                dpi=150, bbox_inches="tight")
    print(f"  Saved: {OUTPUT_DIR}/02_riyadh_aligned.png")
    plt.show()

    print("\n✓ Preprocessing complete. Ready for change detection.")


if __name__ == "__main__":
    main()

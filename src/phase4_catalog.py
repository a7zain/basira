"""
Phase 4 — Sentinel-2 Catalog Dry-Run
=====================================
Queries the Sentinel Hub Catalog API (free, no PU cost) for all
Sentinel-2 L2A scenes over the Riyadh AOI from 2020-01-01 to today.

Produces:
    outputs/phase4_catalog.csv       — full scene catalog
    outputs/phase4_catalog_summary.txt — monthly summary + PU estimate

Usage:
    python src/phase4_catalog.py

Credentials:
    Set SH_CLIENT_ID and SH_CLIENT_SECRET env vars, or enter interactively.
"""

import os
import sys
import csv
from collections import defaultdict
from datetime import datetime, timezone

from dotenv import load_dotenv

load_dotenv()

from sentinelhub import (
    SHConfig,
    BBox,
    CRS,
    DataCollection,
    SentinelHubCatalog,
    bbox_to_dimensions,
)

from utils import RIYADH_BBOX

# ── Paths ───────────────────────────────────────────────────
OUT_DIR = "outputs"

# ── Query parameters ────────────────────────────────────────
DATE_START = "2020-01-01"
DATE_END = datetime.now(timezone.utc).strftime("%Y-%m-%d")

CLOUD_USABLE_THRESHOLD = 30  # % — scenes below this are "usable"

# ── PU estimation parameters ────────────────────────────────
PU_RESOLUTION = 20       # metres
PU_NUM_BANDS  = 4        # B02, B03, B04, B08
PU_FREE_TIER  = 30_000   # monthly free PU allowance

# ── CDSE configuration ──────────────────────────────────────
CDSE_BASE_URL  = "https://sh.dataspace.copernicus.eu"
CDSE_TOKEN_URL = (
    "https://identity.dataspace.copernicus.eu/"
    "auth/realms/CDSE/protocol/openid-connect/token"
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


def build_bbox():
    """Build a sentinelhub BBox from the shared Riyadh AOI."""
    return BBox(
        bbox=[
            RIYADH_BBOX["lon_min"], RIYADH_BBOX["lat_min"],
            RIYADH_BBOX["lon_max"], RIYADH_BBOX["lat_max"],
        ],
        crs=CRS.WGS84,
    )


def query_catalog(config, bbox):
    """Query Catalog API for all S2-L2A scenes in the AOI + date range."""
    catalog = SentinelHubCatalog(config=config)

    search_iter = catalog.search(
        DataCollection.SENTINEL2_L2A,
        bbox=bbox,
        time=(DATE_START, DATE_END),
        fields={
            "include": [
                "id",
                "properties.datetime",
                "properties.eo:cloud_cover",
                "properties.s2:tile",
            ],
            "exclude": [],
        },
    )

    scenes = []
    for feature in search_iter:
        props = feature["properties"]
        geom = feature.get("geometry", {})
        scenes.append({
            "id": feature["id"],
            "date": props.get("datetime", ""),
            "cloud_cover": props.get("eo:cloud_cover"),
            "tile_id": props.get("s2:tile", ""),
            "geometry_type": geom.get("type", ""),
            "geometry_coords_count": _count_coords(geom),
        })

    return scenes


def _count_coords(geom):
    """Count coordinate points in a GeoJSON geometry."""
    coords = geom.get("coordinates", [])
    if not coords:
        return 0
    # Polygon: [[ring]], MultiPolygon: [[[ring]]]
    try:
        if geom.get("type") == "MultiPolygon":
            return sum(len(ring) for poly in coords for ring in poly)
        elif geom.get("type") == "Polygon":
            return sum(len(ring) for ring in coords)
        return len(coords)
    except TypeError:
        return 0


def parse_date(date_str):
    """Extract year-month from ISO datetime string."""
    # Python 3.9 fromisoformat can't handle fractional seconds — parse manually
    dt = datetime.strptime(date_str[:19], "%Y-%m-%dT%H:%M:%S")
    return dt.year, dt.month, dt.day


def build_summary(scenes, bbox):
    """Build all summary statistics from the scene list."""
    # ── Monthly aggregation ─────────────────────────────────
    monthly = defaultdict(list)  # (year, month) -> [cloud_cover, ...]
    for s in scenes:
        if s["cloud_cover"] is None:
            continue
        y, m, _ = parse_date(s["date"])
        monthly[(y, m)].append(s)

    # ── Cloud cover distribution ────────────────────────────
    cloud_bins = {"<10%": 0, "10-30%": 0, "30-60%": 0, ">60%": 0}
    for s in scenes:
        cc = s["cloud_cover"]
        if cc is None:
            continue
        if cc < 10:
            cloud_bins["<10%"] += 1
        elif cc < 30:
            cloud_bins["10-30%"] += 1
        elif cc < 60:
            cloud_bins["30-60%"] += 1
        else:
            cloud_bins[">60%"] += 1

    # ── Best scene per month (lowest cloud cover) ───────────
    best_per_month = {}
    for key, month_scenes in sorted(monthly.items()):
        best = min(month_scenes, key=lambda s: s["cloud_cover"])
        best_per_month[key] = best

    # ── Months with zero usable scenes ──────────────────────
    gap_months = []
    for key, month_scenes in sorted(monthly.items()):
        usable = [s for s in month_scenes if s["cloud_cover"] < CLOUD_USABLE_THRESHOLD]
        if not usable:
            gap_months.append(key)

    # ── Check for completely missing months ─────────────────
    all_months = set()
    start_y, start_m = 2020, 1
    end_dt = datetime.now(timezone.utc)
    y, m = start_y, start_m
    while (y, m) <= (end_dt.year, end_dt.month):
        all_months.add((y, m))
        m += 1
        if m > 12:
            m = 1
            y += 1
    missing_months = sorted(all_months - set(monthly.keys()))

    # ── PU estimation ───────────────────────────────────────
    size = bbox_to_dimensions(bbox, resolution=PU_RESOLUTION)
    w, h = size
    # Sentinel Hub PU formula:
    #   PU = (width * height) / (512 * 512) * (n_output_bands / 3)
    #   minimum 0.001 PU per request
    pu_per_request = (w * h) / (512 * 512) * (PU_NUM_BANDS / 3)
    pu_per_request = max(pu_per_request, 0.001)
    n_best = len(best_per_month)
    total_pu = pu_per_request * n_best

    return {
        "total_scenes": len(scenes),
        "monthly": monthly,
        "cloud_bins": cloud_bins,
        "best_per_month": best_per_month,
        "gap_months": gap_months,
        "missing_months": missing_months,
        "image_size": (w, h),
        "pu_per_request": pu_per_request,
        "n_best": n_best,
        "total_pu": total_pu,
    }


def format_summary(summary):
    """Format the summary as a human-readable string."""
    lines = []
    lines.append("=" * 65)
    lines.append("  Phase 4 — Sentinel-2 Catalog Summary (Riyadh AOI)")
    lines.append("=" * 65)
    lines.append(f"  AOI: {RIYADH_BBOX}")
    lines.append(f"  Period: {DATE_START} to {DATE_END}")
    lines.append(f"  Total scenes found: {summary['total_scenes']}")
    lines.append("")

    # ── Scenes per month table ──────────────────────────────
    lines.append("  Scenes per month:")
    lines.append("  " + "-" * 50)
    lines.append(f"  {'Year':>6}  {'Month':>5}  {'Count':>5}  "
                 f"{'Usable(<30%)':>12}  {'Best CC%':>8}")
    lines.append("  " + "-" * 50)

    monthly = summary["monthly"]
    best = summary["best_per_month"]
    for key in sorted(monthly.keys()):
        y, m = key
        count = len(monthly[key])
        usable = sum(1 for s in monthly[key]
                     if s["cloud_cover"] < CLOUD_USABLE_THRESHOLD)
        best_cc = best[key]["cloud_cover"] if key in best else "—"
        if isinstance(best_cc, (int, float)):
            best_cc = f"{best_cc:.1f}"
        lines.append(f"  {y:>6}  {m:>5}  {count:>5}  {usable:>12}  {best_cc:>8}")
    lines.append("  " + "-" * 50)
    lines.append("")

    # ── Cloud cover distribution ────────────────────────────
    lines.append("  Cloud cover distribution:")
    for label, count in summary["cloud_bins"].items():
        bar = "#" * (count // 10)
        lines.append(f"    {label:>6}: {count:>5}  {bar}")
    lines.append("")

    # ── Gap months ──────────────────────────────────────────
    gap = summary["gap_months"]
    missing = summary["missing_months"]
    if gap:
        lines.append(f"  Months with zero usable scenes (<{CLOUD_USABLE_THRESHOLD}% cloud): "
                     f"{len(gap)}")
        for y, m in gap:
            lines.append(f"    {y}-{m:02d}")
    else:
        lines.append(f"  All months have at least one usable scene (<{CLOUD_USABLE_THRESHOLD}% cloud).")

    if missing:
        lines.append(f"\n  Months with NO catalog results at all: {len(missing)}")
        for y, m in missing:
            lines.append(f"    {y}-{m:02d}")
    lines.append("")

    # ── Best scene per month ────────────────────────────────
    lines.append("  Best scene per month (lowest cloud cover):")
    lines.append("  " + "-" * 60)
    lines.append(f"  {'Year':>6}  {'Month':>5}  {'Cloud%':>7}  {'Scene ID'}")
    lines.append("  " + "-" * 60)
    for key in sorted(best.keys()):
        y, m = key
        s = best[key]
        lines.append(f"  {y:>6}  {m:>5}  {s['cloud_cover']:>7.1f}  {s['id']}")
    lines.append("  " + "-" * 60)
    lines.append("")

    # ── PU estimation ───────────────────────────────────────
    lines.append("  Processing Unit (PU) Estimation:")
    lines.append("  " + "-" * 50)
    w, h = summary["image_size"]
    lines.append(f"    Image size at {PU_RESOLUTION}m: {w} x {h} pixels")
    lines.append(f"    Bands: {PU_NUM_BANDS} (B02, B03, B04, B08)")
    lines.append(f"    PU per request: {summary['pu_per_request']:.2f}")
    lines.append(f"    Best scenes to download: {summary['n_best']}")
    lines.append(f"    Total estimated PU: {summary['total_pu']:.1f}")
    lines.append(f"    Free tier (monthly): {PU_FREE_TIER:,}")
    fits = summary["total_pu"] <= PU_FREE_TIER
    lines.append(f"    Fits in free tier: {'YES' if fits else 'NO'}"
                 f" ({summary['total_pu']:.0f} / {PU_FREE_TIER:,})")
    lines.append("  " + "-" * 50)
    lines.append("")

    return "\n".join(lines)


def save_catalog_csv(scenes, path):
    """Save full scene catalog to CSV."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fieldnames = [
        "id", "date", "cloud_cover", "tile_id",
        "geometry_type", "geometry_coords_count",
    ]
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for s in sorted(scenes, key=lambda s: s["date"]):
            writer.writerow(s)
    print(f"  Saved catalog CSV: {path} ({len(scenes)} scenes)")


def save_summary(text, path):
    """Save summary text to file."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write(text)
    print(f"  Saved summary: {path}")


def main():
    os.makedirs(OUT_DIR, exist_ok=True)

    # ── Authenticate ──────────────────────────────────────────
    print("Phase 4 — Sentinel-2 Catalog Dry-Run")
    print("=" * 40)
    client_id, client_secret = get_credentials()
    config = configure_sh(client_id, client_secret)

    # ── Build AOI ─────────────────────────────────────────────
    bbox = build_bbox()
    size = bbox_to_dimensions(bbox, resolution=PU_RESOLUTION)
    print(f"AOI: {RIYADH_BBOX}")
    print(f"Image size at {PU_RESOLUTION}m: {size[0]} x {size[1]} pixels")
    print(f"Query period: {DATE_START} to {DATE_END}")
    print()

    # ── Query catalog ─────────────────────────────────────────
    print("Querying Sentinel Hub Catalog API (free, no PU cost)...")
    scenes = query_catalog(config, bbox)
    print(f"  Found {len(scenes)} scenes.")
    print()

    # ── Build and display summary ─────────────────────────────
    summary = build_summary(scenes, bbox)
    summary_text = format_summary(summary)

    save_catalog_csv(scenes, f"{OUT_DIR}/phase4_catalog.csv")
    save_summary(summary_text, f"{OUT_DIR}/phase4_catalog_summary.txt")

    print()
    print(summary_text)


if __name__ == "__main__":
    main()

"""
SAR Change Detection — Interactive Folium Map
==============================================
Loads the classified change GeoTIFF and renders it as an
interactive web map with basemap switching, legend, and AOI outline.

Usage:
    python src/map_interactive.py
"""

import numpy as np
import rasterio
from rasterio.warp import transform_bounds
import folium
from folium.raster_layers import ImageOverlay
import os

from utils import RIYADH_BBOX

# ── Paths ───────────────────────────────────────────────────
OUT_DIR = "outputs"
CHANGE_TIF = f"{OUT_DIR}/change_map.tif"
OUTPUT_HTML = f"{OUT_DIR}/riyadh_change_map.html"


def main():
    # ── Load classified change map GeoTIFF ─────────────────
    print("Loading change map GeoTIFF...")
    with rasterio.open(CHANGE_TIF) as src:
        classified = src.read(1)             # int8: -1, 0, +1
        src_crs = src.crs
        src_transform = src.transform
        h, w = classified.shape

        # Compute geographic bounds (lat/lon) from UTM transform
        utm_left   = src_transform.c
        utm_top    = src_transform.f
        utm_right  = utm_left + w * src_transform.a
        utm_bottom = utm_top  + h * src_transform.e  # e is negative

        bounds_wgs84 = transform_bounds(
            src_crs, "EPSG:4326",
            utm_left, utm_bottom, utm_right, utm_top,
        )
        lon_min, lat_min, lon_max, lat_max = bounds_wgs84

    print(f"  Shape: {h} x {w}")
    print(f"  Bounds (WGS84): lat {lat_min:.4f}–{lat_max:.4f}, "
          f"lon {lon_min:.4f}–{lon_max:.4f}")

    # ── Build RGBA overlay (only changed pixels visible) ───
    print("Building overlay image...")
    # Red = increase, Blue = decrease, No-change & nodata = fully transparent
    rgba = np.zeros((h, w, 4), dtype=np.uint8)

    inc_mask = classified == 1
    dec_mask = classified == -1

    # Increased → red
    rgba[inc_mask] = [214, 96, 77, 180]    # #d6604d, semi-transparent
    # Decreased → blue
    rgba[dec_mask] = [33, 102, 172, 180]   # #2166ac, semi-transparent
    # No-change and nodata → fully transparent (already zeros)

    changed = inc_mask.sum() + dec_mask.sum()
    print(f"  Changed pixels rendered: {changed:,} "
          f"({100 * changed / classified.size:.1f}% of image)")

    # ── Create Folium map ──────────────────────────────────
    print("Building Folium map...")
    m = folium.Map(
        location=[24.7, 46.75],
        zoom_start=11,
        tiles="OpenStreetMap",
        control_scale=True,
    )

    # Esri satellite basemap
    folium.TileLayer(
        tiles="https://server.arcgisonline.com/ArcGIS/rest/services/"
              "World_Imagery/MapServer/tile/{z}/{y}/{x}",
        attr="Esri",
        name="Esri World Imagery",
    ).add_to(m)

    # ── Change detection overlay ───────────────────────────
    # ImageOverlay expects bounds as [[south, west], [north, east]]
    image_bounds = [[lat_min, lon_min], [lat_max, lon_max]]

    ImageOverlay(
        image=rgba,
        bounds=image_bounds,
        origin="upper",
        opacity=0.85,
        name="Change Detection (2022→2024)",
        interactive=True,
    ).add_to(m)

    # ── AOI bounding box rectangle ─────────────────────────
    aoi_group = folium.FeatureGroup(name="Riyadh AOI", show=True)
    folium.Rectangle(
        bounds=[
            [RIYADH_BBOX["lat_min"], RIYADH_BBOX["lon_min"]],
            [RIYADH_BBOX["lat_max"], RIYADH_BBOX["lon_max"]],
        ],
        color="#ff7800",
        weight=2.5,
        fill=False,
        dash_array="8 4",
        tooltip="Riyadh AOI (24.55–24.85°N, 46.55–46.95°E)",
    ).add_to(aoi_group)
    aoi_group.add_to(m)

    # ── Layer control toggle ───────────────────────────────
    folium.LayerControl(collapsed=False).add_to(m)

    # ── Title banner (top center) ──────────────────────────
    title_html = """
    <div style="
        position: fixed;
        top: 10px;
        left: 50%;
        transform: translateX(-50%);
        z-index: 9999;
        background: rgba(255,255,255,0.92);
        border: 1px solid #ccc;
        border-radius: 6px;
        padding: 8px 20px;
        font-family: 'Helvetica Neue', Arial, sans-serif;
        font-size: 15px;
        font-weight: 600;
        color: #1a1a1a;
        box-shadow: 0 2px 6px rgba(0,0,0,0.15);
        pointer-events: none;
    ">
        SAR Change Detection &mdash; Riyadh 2022 vs 2024
    </div>
    """
    m.get_root().html.add_child(folium.Element(title_html))

    # ── Legend (bottom-right corner) ───────────────────────
    legend_html = """
    <div style="
        position: fixed;
        bottom: 30px;
        right: 12px;
        z-index: 9999;
        background: rgba(255,255,255,0.94);
        border: 1px solid #bbb;
        border-radius: 6px;
        padding: 12px 16px;
        font-family: 'Helvetica Neue', Arial, sans-serif;
        font-size: 12px;
        color: #222;
        line-height: 1.6;
        box-shadow: 0 2px 6px rgba(0,0,0,0.15);
    ">
        <div style="font-weight:700; font-size:13px; margin-bottom:6px;
                     border-bottom:1px solid #ddd; padding-bottom:4px;">
            Change Detection Legend
        </div>
        <div>
            <span style="display:inline-block; width:14px; height:14px;
                         background:#d6604d; border-radius:2px;
                         vertical-align:middle; margin-right:6px;"></span>
            Increased backscatter (new construction)
        </div>
        <div>
            <span style="display:inline-block; width:14px; height:14px;
                         background:#2166ac; border-radius:2px;
                         vertical-align:middle; margin-right:6px;"></span>
            Decreased backscatter (clearing / demolition)
        </div>
        <div style="margin-top:4px; font-size:11px; color:#666;">
            Sentinel-1A IW GRD &middot; VV pol &middot; &pm;3 dB threshold
        </div>
        <div style="font-size:11px; color:#666;">
            Transparent = no significant change / no data
        </div>
    </div>
    """
    m.get_root().html.add_child(folium.Element(legend_html))

    # ── Save ───────────────────────────────────────────────
    os.makedirs(OUT_DIR, exist_ok=True)
    m.save(OUTPUT_HTML)
    print(f"\nSaved: {OUTPUT_HTML}")
    print("Open in a browser to explore the interactive map.")


if __name__ == "__main__":
    main()

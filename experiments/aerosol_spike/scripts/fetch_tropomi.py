"""Fetch TROPOMI UVAI (AER_AI_354_388) for Riyadh AOI on dust + clear days
via Copernicus Dataspace Sentinel Hub.

Note on qa_value: Sentinel Hub's S5P L2 product exposes AER_AI_354_388 as a
processed band; the underlying qa_value is not available as a separate band
through the Process API. SH applies its own preprocessing/filtering.
"""
import os
import sys
from pathlib import Path

import numpy as np
import rasterio
from rasterio.transform import from_bounds
from sentinelhub import (
    BBox,
    CRS,
    DataCollection,
    MimeType,
    SentinelHubRequest,
    SHConfig,
    bbox_to_dimensions,
)

CDSE_BASE_URL = "https://sh.dataspace.copernicus.eu"
CDSE_TOKEN_URL = (
    "https://identity.dataspace.copernicus.eu/auth/realms/CDSE/"
    "protocol/openid-connect/token"
)

S5P_CDSE = DataCollection.SENTINEL5P.define_from(
    "s5p_cdse", service_url=CDSE_BASE_URL
)

AOI_BBOX = (46.4, 24.4, 47.0, 24.9)  # lon_min, lat_min, lon_max, lat_max
RES_DEG = 0.05  # ~5 km — TROPOMI native ~5.5 km

DUST_DAY = "2022-05-17"
CLEAR_DAY = "2022-12-15"

EVALSCRIPT = """
//VERSION=3
function setup() {
  return {
    input: [{ bands: ["AER_AI_354_388"] }],
    output: { bands: 1, sampleType: "FLOAT32" }
  };
}
function evaluatePixel(s) {
  return [s.AER_AI_354_388];
}
"""


def configure():
    cfg = SHConfig()
    cfg.sh_client_id = os.environ["SH_CLIENT_ID"]
    cfg.sh_client_secret = os.environ["SH_CLIENT_SECRET"]
    cfg.sh_base_url = CDSE_BASE_URL
    cfg.sh_token_url = CDSE_TOKEN_URL
    return cfg


def fetch(cfg, date_str, out_path):
    bbox = BBox(AOI_BBOX, CRS.WGS84)
    size = bbox_to_dimensions(bbox, resolution=RES_DEG * 111000)  # meters approx
    # Force a small grid (~12x10) for TROPOMI's coarse footprint
    size = (max(size[0], 12), max(size[1], 10))
    print(f"  bbox={AOI_BBOX} size={size} date={date_str}")

    req = SentinelHubRequest(
        evalscript=EVALSCRIPT,
        input_data=[
            SentinelHubRequest.input_data(
                data_collection=S5P_CDSE,
                time_interval=(f"{date_str}T00:00:00Z", f"{date_str}T23:59:59Z"),
            )
        ],
        responses=[SentinelHubRequest.output_response("default", MimeType.TIFF)],
        bbox=bbox,
        size=size,
        config=cfg,
    )
    arr = req.get_data()[0]
    print(f"  shape={arr.shape} dtype={arr.dtype} "
          f"min={np.nanmin(arr):.3f} max={np.nanmax(arr):.3f} "
          f"mean={np.nanmean(arr):.3f} nz_frac={(arr != 0).mean():.2f}")

    transform = from_bounds(*AOI_BBOX, size[0], size[1])
    with rasterio.open(
        out_path, "w",
        driver="GTiff", height=size[1], width=size[0],
        count=1, dtype="float32", crs="EPSG:4326",
        transform=transform, nodata=np.nan,
    ) as dst:
        dst.write(arr.astype("float32"), 1)
    print(f"  wrote {out_path}")
    return arr


def main():
    out_dir = Path(__file__).resolve().parent.parent / "data"
    out_dir.mkdir(parents=True, exist_ok=True)
    cfg = configure()
    print("Fetching TROPOMI UVAI (clear day)…")
    arr_c = fetch(cfg, CLEAR_DAY, out_dir / "tropomi_uvai_clear.tif")
    print("Fetching TROPOMI UVAI (dust day)…")
    arr_d = fetch(cfg, DUST_DAY, out_dir / "tropomi_uvai_dust.tif")
    print("\nUVAI clear mean:", float(np.nanmean(arr_c)))
    print("UVAI dust  mean:", float(np.nanmean(arr_d)))


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"FAILED: {type(e).__name__}: {e}", file=sys.stderr)
        raise

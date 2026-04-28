"""
Fetch TROPOMI monthly UVAI (AER_AI_354_388) for the Riyadh AOI from
2020-01 through 2026-04 via Sentinel Hub Statistical API on CDSE.

Uses the Statistical API rather than the Process API because we want
true temporal aggregation (mean + max per month) rather than a single
mosaicked snapshot. One Statistical API call covers the whole 2020-2026
window with monthly bins.

Output:
  research/dust-honesty/data/uvai_monthly.csv
    schema: year, month, uvai_mean, uvai_max, n_observations

Auth: SH_CLIENT_ID / SH_CLIENT_SECRET in .env (CDSE OAuth client).
"""

from __future__ import annotations

import csv
import os
import sys
from datetime import datetime
from pathlib import Path

from sentinelhub import (
    BBox,
    CRS,
    DataCollection,
    SentinelHubStatistical,
    SHConfig,
    bbox_to_dimensions,
)

# -- env loader (no python-dotenv dependency) --
def load_env(path: Path):
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip())


REPO = Path(__file__).resolve().parents[3]
load_env(REPO / ".env")

CDSE_BASE_URL = "https://sh.dataspace.copernicus.eu"
CDSE_TOKEN_URL = (
    "https://identity.dataspace.copernicus.eu/auth/realms/CDSE/"
    "protocol/openid-connect/token"
)

S5P_CDSE = DataCollection.SENTINEL5P.define_from("s5p_cdse", service_url=CDSE_BASE_URL)

AOI_BBOX = (46.4, 24.4, 47.0, 24.9)
START = "2020-01-01"
END = "2026-05-01"  # exclusive

EVALSCRIPT = """
//VERSION=3
function setup() {
  return {
    input: [{ bands: ["AER_AI_354_388", "dataMask"] }],
    output: [
      { id: "uvai", bands: 1, sampleType: "FLOAT32" },
      { id: "dataMask", bands: 1 }
    ],
    mosaicking: "ORBIT"
  };
}
function evaluatePixel(samples) {
  // Per-orbit return; Statistical API aggregates across orbit×pixel
  // samples within each monthly bin to give mean/max.
  if (samples.length === 0) {
    return { uvai: [NaN], dataMask: [0] };
  }
  let s = samples[0];
  return { uvai: [s.AER_AI_354_388], dataMask: [s.dataMask] };
}
"""


def configure() -> SHConfig:
    cfg = SHConfig()
    cfg.sh_client_id = os.environ["SH_CLIENT_ID"]
    cfg.sh_client_secret = os.environ["SH_CLIENT_SECRET"]
    cfg.sh_base_url = CDSE_BASE_URL
    cfg.sh_token_url = CDSE_TOKEN_URL
    return cfg


YEAR_CHUNKS = [
    ("2020-01-01", "2021-01-01"),
    ("2021-01-01", "2022-01-01"),
    ("2022-01-01", "2023-01-01"),
    ("2023-01-01", "2024-01-01"),
    ("2024-01-01", "2025-01-01"),
    ("2025-01-01", "2026-01-01"),
    ("2026-01-01", "2026-05-01"),
]


def fetch_chunk(cfg, bbox, size, t0, t1):
    request = SentinelHubStatistical(
        aggregation=SentinelHubStatistical.aggregation(
            evalscript=EVALSCRIPT,
            time_interval=(t0, t1),
            aggregation_interval="P1M",
            size=size,
        ),
        input_data=[SentinelHubStatistical.input_data(data_collection=S5P_CDSE)],
        bbox=bbox,
        config=cfg,
    )
    return request.get_data()[0]


def main():
    cfg = configure()
    cfg.download_timeout_seconds = 300
    bbox = BBox(AOI_BBOX, CRS.WGS84)
    size = bbox_to_dimensions(bbox, resolution=5500)
    size = (max(size[0], 12), max(size[1], 10))
    print(f"bbox={AOI_BBOX} size={size}")

    rows = []
    all_entries = []
    for t0, t1 in YEAR_CHUNKS:
        print(f"chunk {t0} -> {t1} …", flush=True)
        for attempt in (1, 2, 3):
            try:
                resp = fetch_chunk(cfg, bbox, size, t0, t1)
                break
            except Exception as e:
                print(f"  attempt {attempt} failed: {type(e).__name__}: {e}", flush=True)
                if attempt == 3:
                    raise
        if "data" not in resp:
            print("  unexpected response:", resp)
            continue
        all_entries.extend(resp["data"])
        print(f"  got {len(resp['data'])} monthly bins", flush=True)

    for entry in all_entries:
        interval = entry["interval"]
        from_str = interval["from"]  # "YYYY-MM-DDT…"
        d = datetime.fromisoformat(from_str.replace("Z", "+00:00"))
        outputs = entry.get("outputs", {})
        uvai_block = outputs.get("uvai", {})
        bands = uvai_block.get("bands", {})
        b0 = bands.get("B0", {})
        stats = b0.get("stats", {})
        mean = stats.get("mean")
        mx = stats.get("max")
        n = stats.get("sampleCount")
        nodata = stats.get("noDataCount", 0)
        valid = (n - nodata) if n is not None else None
        rows.append({
            "year": d.year,
            "month": d.month,
            "uvai_mean": mean,
            "uvai_max": mx,
            "n_observations": valid,
        })
        print(f"  {d.year}-{d.month:02d}  mean={mean}  max={mx}  n_valid={valid}")

    out = REPO / "research" / "dust-honesty" / "data" / "uvai_monthly.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["year", "month", "uvai_mean", "uvai_max", "n_observations"])
        w.writeheader()
        w.writerows(rows)
    print(f"\nWrote {len(rows)} rows -> {out}")


if __name__ == "__main__":
    main()

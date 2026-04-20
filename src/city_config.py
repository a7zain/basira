"""
City configuration loader (Phase 5.0).

Loads city-specific parameters from cities/<city>.yaml so pipeline
scripts can operate on any configured AOI. Replaces the hardcoded
Riyadh constants that used to live in utils.py.
"""

import argparse
import json
import os
from dataclasses import dataclass
from typing import Any, Dict, List

import yaml

CITIES_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "cities")


@dataclass
class CityConfig:
    name: str
    display_name: str
    country: str
    arabic_label: str
    aoi: Dict[str, float]
    target_crs: str
    resolution_m: int
    baseline_year: int
    current_year: int
    baseline_month: int
    current_month: int
    pipelines: Dict[str, bool]
    monthly_dir: str
    ndvi_dir: str
    web_dir: str
    green_map_params: Dict[str, float]
    rois: List[Dict[str, Any]]
    raw: Dict[str, Any]

    @property
    def utm_epsg(self) -> str:
        return self.target_crs.split(":")[-1]


def load_city(name: str) -> CityConfig:
    path = os.path.join(CITIES_DIR, f"{name}.yaml")
    if not os.path.exists(path):
        raise FileNotFoundError(f"City config not found: {path}")
    with open(path) as f:
        data = yaml.safe_load(f)

    return CityConfig(
        name=data["name"],
        display_name=data["display_name"],
        country=data["country"],
        arabic_label=data.get("arabic_label", ""),
        aoi=data["aoi"],
        target_crs=data["crs"]["target"],
        resolution_m=int(data["resolution_m"]),
        baseline_year=int(data["years"]["baseline"]),
        current_year=int(data["years"]["current"]),
        baseline_month=int(data["annual_scenes"]["baseline_month"]),
        current_month=int(data["annual_scenes"]["current_month"]),
        pipelines=data.get("pipelines", {}),
        monthly_dir=data["paths"]["monthly_dir"],
        ndvi_dir=data["paths"]["ndvi_dir"],
        web_dir=data["paths"]["web_dir"],
        green_map_params=data.get("green_map", {}),
        rois=data.get("rois", []),
        raw=data,
    )


def add_city_arg(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--city",
        required=True,
        help="City name (matches cities/<city>.yaml)",
    )


def write_index() -> None:
    """Write cities/index.json listing all available cities for the webapp."""
    entries = []
    for fname in sorted(os.listdir(CITIES_DIR)):
        if not fname.endswith(".yaml"):
            continue
        cfg = load_city(fname[:-5])
        entries.append({
            "name": cfg.name,
            "display_name": cfg.display_name,
            "country": cfg.country,
            "arabic_label": cfg.arabic_label,
            "aoi": cfg.aoi,
            "center": {
                "lat": (cfg.aoi["lat_min"] + cfg.aoi["lat_max"]) / 2,
                "lon": (cfg.aoi["lon_min"] + cfg.aoi["lon_max"]) / 2,
            },
            "pipelines": cfg.pipelines,
            "web_dir": cfg.web_dir,
        })
    out = {"cities": entries}
    out_path = os.path.join(CITIES_DIR, "index.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)
    return out_path


if __name__ == "__main__":
    path = write_index()
    print(f"Wrote {path}")

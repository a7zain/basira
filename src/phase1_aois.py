"""
Phase 1 — AOI definitions (from KML)
=====================================
Parses data/phase1/aois/phase1.kml into a dict of named AOIs. Three
primary AOIs are downloaded; two sub-regions are retained for dashboard
overlay use but are not downloaded separately.

Each entry has:
    name         (str)
    polygon      (list of [lon, lat])  — outer ring
    bbox         (minlon, minlat, maxlon, maxlat)  — auto-computed
    description  (str)
    kind         ("primary" | "subregion")
    parent       (str | None)  — for sub-regions, the parent AOI key
"""

import os
import xml.etree.ElementTree as ET

KML_PATH = "data/phase1/aois/phase1.kml"
KML_NS = {"kml": "http://www.opengis.net/kml/2.2"}

# KML Placemark name → AOI key + metadata
_KML_MAP = {
    "Qiddiya": {
        "key": "qiddiya_core",
        "name": "Qiddiya",
        "kind": "primary",
        "parent": None,
        "description": (
            "Qiddiya entertainment district — Six Flags, Aquarabia, Falcons Flight"
        ),
    },
    "KSP": {
        "key": "king_salman_park",
        "name": "King Salman Park",
        "kind": "primary",
        "parent": None,
        "description": "Urban park — vegetation establishment and landscape transformation.",
    },
    "Diriyah": {
        "key": "diriyah_gate",
        "name": "Diriyah Gate",
        "kind": "primary",
        "parent": None,
        "description": "Heritage-adjacent mixed-use development — subtler change patterns.",
    },
    "Six Flags": {
        "key": "six_flags",
        "name": "Six Flags",
        "kind": "subregion",
        "parent": "qiddiya_core",
        "description": "Six Flags Qiddiya — sub-region overlay only.",
    },
    "Aquarabia": {
        "key": "aquarabia",
        "name": "Aquarabia",
        "kind": "subregion",
        "parent": "qiddiya_core",
        "description": "Aquarabia waterpark — sub-region overlay only.",
    },
}


def _parse_coords(coord_text):
    """KML <coordinates> text → list of [lon, lat]."""
    pts = []
    for tok in coord_text.strip().split():
        parts = tok.split(",")
        if len(parts) >= 2:
            pts.append([float(parts[0]), float(parts[1])])
    return pts


def _bbox_of(polygon):
    lons = [p[0] for p in polygon]
    lats = [p[1] for p in polygon]
    return (min(lons), min(lats), max(lons), max(lats))


def _load_kml(path=KML_PATH):
    if not os.path.exists(path):
        raise FileNotFoundError(f"KML not found at {path}")
    tree = ET.parse(path)
    root = tree.getroot()

    aois = {}
    for pm in root.iter("{http://www.opengis.net/kml/2.2}Placemark"):
        name_el = pm.find("kml:name", KML_NS)
        if name_el is None or name_el.text not in _KML_MAP:
            continue
        meta = _KML_MAP[name_el.text]

        coords_el = pm.find(
            "kml:Polygon/kml:outerBoundaryIs/kml:LinearRing/kml:coordinates",
            KML_NS,
        )
        if coords_el is None or not coords_el.text:
            continue
        polygon = _parse_coords(coords_el.text)

        aois[meta["key"]] = {
            "name": meta["name"],
            "polygon": polygon,
            "bbox": _bbox_of(polygon),
            "description": meta["description"],
            "kind": meta["kind"],
            "parent": meta["parent"],
        }
    return aois


AOIS = _load_kml()


def list_aois():
    return list(AOIS.keys())


def list_primary_aois():
    return [k for k, v in AOIS.items() if v["kind"] == "primary"]


def list_subregions(parent=None):
    return [
        k for k, v in AOIS.items()
        if v["kind"] == "subregion" and (parent is None or v["parent"] == parent)
    ]


def get_aoi(name):
    if name not in AOIS:
        raise KeyError(
            f"Unknown AOI '{name}'. Known: {', '.join(AOIS.keys())}"
        )
    return AOIS[name]


def get_bbox(name):
    return get_aoi(name)["bbox"]


def get_polygon(name):
    return get_aoi(name)["polygon"]

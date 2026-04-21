"""
Phase 1 — AOI definitions
==========================
Single source of truth for the three Vision 2030 megaproject AOIs.
Edit bbox values here; downstream scripts import from this module.
"""

AOIS = {
    "qiddiya_core": {
        "name": "Qiddiya (core)",
        "bbox_wgs84": (46.41, 24.58, 46.47, 24.62),
        "description": "Qiddiya entertainment megaproject — dense construction activity.",
    },
    "king_salman_park": {
        "name": "King Salman Park",
        "bbox_wgs84": (46.63, 24.72, 46.69, 24.77),
        "description": "Urban park — vegetation establishment and landscape transformation.",
    },
    "diriyah_gate": {
        "name": "Diriyah Gate",
        "bbox_wgs84": (46.55, 24.72, 46.59, 24.76),
        "description": "Heritage-adjacent mixed-use development — subtler change patterns.",
    },
}


def list_aois():
    """Return the list of AOI keys."""
    return list(AOIS.keys())


def get_aoi(name):
    """Return the AOI dict for a given key, or raise KeyError."""
    if name not in AOIS:
        raise KeyError(
            f"Unknown AOI '{name}'. Known: {', '.join(AOIS.keys())}"
        )
    return AOIS[name]

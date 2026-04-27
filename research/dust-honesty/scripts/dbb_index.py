"""
DBB (Dust & Biomass Burning) composite index — Lolli et al. 2024 inspired.

Lolli, S. et al. (2024). "Characterizing Dust and Biomass Burning Events
from Sentinel-2 Imagery." Atmosphere 15(6):672.

Structure: dust scatters strongly in visible (B2/B3/B4) but is partly
transparent in SWIR (B11/B12). A normalized difference between visible
and SWIR mean isolates the aerosol signal while damping terrain.

NOTE: Lolli's exact normalization should be verified against the paper.
This implementation follows the structure described in the SQ1 brief
and is the working definition pending paper verification.
"""

from __future__ import annotations

import numpy as np


def dbb_index(b2, b3, b4, b11, b12):
    """
    Compute the DBB composite normalized differential index.

    Inputs are surface-reflectance arrays in [0, 1] (Sentinel-2 L2A as
    delivered by the Phase 1 download pipeline — already FLOAT32 reflectance,
    no /10000 scaling needed).

    Returns float32 array. Higher values = more aerosol/dust signal.
    """
    visible_mean = (b2.astype(np.float32) + b3.astype(np.float32) + b4.astype(np.float32)) / 3.0
    swir_mean = (b11.astype(np.float32) + b12.astype(np.float32)) / 2.0
    denom = visible_mean + swir_mean + 1e-6
    return ((visible_mean - swir_mean) / denom).astype(np.float32)


def dbb_from_phase1_tif(path):
    """
    Convenience: open a Phase 1 6-band tif (B02/B03/B04/B08/B11/B12 order)
    and return the DBB index array.
    """
    import rasterio

    with rasterio.open(path) as src:
        b2 = src.read(1)
        b3 = src.read(2)
        b4 = src.read(3)
        # b8 = src.read(4)  # NIR, unused for DBB
        b11 = src.read(5)
        b12 = src.read(6)
    return dbb_index(b2, b3, b4, b11, b12)


def dbb_scene_mean(path, valid_min=0.0, valid_max=1.5):
    """
    Mean DBB over a scene, ignoring nodata / out-of-range pixels.
    """
    import rasterio

    with rasterio.open(path) as src:
        b2 = src.read(1)
        b3 = src.read(2)
        b4 = src.read(3)
        b11 = src.read(5)
        b12 = src.read(6)

    valid = (
        (b2 > valid_min) & (b2 < valid_max)
        & (b3 > valid_min) & (b3 < valid_max)
        & (b4 > valid_min) & (b4 < valid_max)
        & (b11 > valid_min) & (b11 < valid_max)
        & (b12 > valid_min) & (b12 < valid_max)
    )
    dbb = dbb_index(b2, b3, b4, b11, b12)
    if valid.sum() == 0:
        return float("nan")
    return float(np.nanmean(dbb[valid]))

"""
SAR Change Detection — Utility Functions
=========================================
Shared constants, speckle filtering, and helper functions.
"""

import numpy as np
from scipy.ndimage import uniform_filter

# ── Riyadh AOI ──────────────────────────────────────────────
# Bounding box in geographic coordinates (WGS84 / EPSG:4326)
RIYADH_BBOX = {
    "lat_min": 24.55,
    "lat_max": 24.85,
    "lon_min": 46.55,
    "lon_max": 46.95,
}

# Target CRS: UTM Zone 38N (covers Riyadh)
TARGET_CRS = "EPSG:32638"

# Target pixel resolution in metres
TARGET_RES = 10.0


# ── Speckle Filtering ──────────────────────────────────────
def lee_filter(img, window_size=7):
    """
    Lee speckle filter for SAR amplitude data.

    Reduces speckle noise while preserving edges by adapting the
    filter weight based on local statistics.

    Parameters
    ----------
    img : np.ndarray
        2D SAR amplitude (linear scale, NOT dB).
    window_size : int
        Size of the moving window (must be odd).

    Returns
    -------
    np.ndarray
        Filtered image (same shape as input).
    """
    img = img.astype(np.float64)
    img = np.where(img > 0, img, 1e-10)

    # Local statistics
    mean_local = uniform_filter(img, size=window_size)
    sq_mean = uniform_filter(img ** 2, size=window_size)
    var_local = sq_mean - mean_local ** 2
    var_local = np.maximum(var_local, 0)  # numerical safety

    # Overall noise variance (estimated from image)
    overall_var = np.var(img)

    # Lee filter weight
    weight = var_local / (var_local + overall_var + 1e-10)

    # Filtered result
    filtered = mean_local + weight * (img - mean_local)
    return filtered.astype(np.float32)


# ── Conversion ──────────────────────────────────────────────
def amplitude_to_db(arr):
    """Convert linear amplitude to decibels."""
    safe = np.where(arr > 0, arr, 1e-10)
    return (10.0 * np.log10(safe)).astype(np.float32)


def amplitude_to_sigma0(dn, calibration_lut=None):
    """
    Convert digital numbers to sigma-naught.

    For Sentinel-1 GRD COG products, the DN values in the measurement
    TIFF are already calibrated amplitude values. Sigma-naught is:
        σ⁰ = DN² / A_sigma²
    where A_sigma comes from the calibration annotation.

    If no calibration LUT is provided, we assume DN is raw amplitude
    and return DN² (intensity), which is sufficient for relative
    change detection between same-sensor images.
    """
    intensity = arr_to_intensity(dn)
    if calibration_lut is not None:
        return intensity / (calibration_lut ** 2 + 1e-10)
    return intensity


def arr_to_intensity(arr):
    """Convert amplitude to intensity (power)."""
    return (arr.astype(np.float64) ** 2).astype(np.float32)

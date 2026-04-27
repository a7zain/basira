# Aerosol spike — results

**Date run:** 2026-04-27
**AOI:** Riyadh, bbox 46.4–47.0 E, 24.4–24.9 N
**Test days:** dust 2022-05-17, clear 2022-12-15

## What worked

- **TROPOMI UVAI via Copernicus Dataspace Sentinel Hub.**
  Existing `SH_CLIENT_ID`/`SH_CLIENT_SECRET` from `.env` (the same OAuth
  client used for Sentinel-2 in `phase4_download.py`) authenticated cleanly
  against `sh.dataspace.copernicus.eu` for the `sentinel-5p-l2` collection.
  Pulled the `AER_AI_354_388` band for both days at the AOI bbox via the
  Process API (FLOAT32 GeoTIFF, ~12×10 px to match TROPOMI's ~5.5 km
  footprint). Saved as `data/tropomi_uvai_{clear,dust}.tif`. Signal is
  textbook: dust day mean UVAI ≈ 2.89 (saturated absorbing aerosol), clear
  day mean ≈ 0.06 (background). 2022-05-17 was the right day — picked the
  May 2022 storm on first try, no fallback needed.

## What did not work

- **VIIRS Deep Blue AOD via Earth Engine.** `earthengine-api` was not
  installed in the `sarsat` env and no GEE credential file exists at
  `~/.config/earthengine/`. Installed the package, then `ee.Initialize()`
  raised `EEException: Please authorize access to your Earth Engine
  account…`. Per spike protocol, did not run interactive `ee.Authenticate()`;
  logged and skipped. Stub at `scripts/fetch_viirs.py` exits with the
  failure mode recorded.
- **qa_value mask not applied.** Sentinel Hub's `sentinel-5p-l2` Process
  API exposes `AER_AI_354_388` as a processed band; `qa_value` is not
  available as a separate band. SH applies its own filtering. For
  production use this is worth double-checking against raw netCDF from
  CDSE OData if strict QA control matters.

## Numbers

| | UVAI mean | UVAI range |
|---|---|---|
| Clear (2022-12-15) | 0.06 | -0.65 to 0.84 |
| Dust  (2022-05-17) | 2.89 |  2.54 to 3.17 |
| Ratio dust/clear | **~49×** | — |

VIIRS AOD: not collected.

## Verdict

TROPOMI UVAI accessible end-to-end with existing CDSE creds and the dust-vs-clear contrast is unambiguous; VIIRS AOD via GEE blocked on one-time interactive `ee.Authenticate()`, so the dust-honesty piece can proceed on TROPOMI alone today and add VIIRS once GEE is authorized.

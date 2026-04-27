"""Attempt to fetch VIIRS Deep Blue AOD via Google Earth Engine.

Per spike protocol: try ee.Initialize() once. If auth requires interactive
flow, log and skip — do not block the spike.
"""
import sys


def main():
    try:
        import ee
    except ImportError as e:
        print(f"VIIRS_SKIP: earthengine-api not installed ({e})")
        return 1

    try:
        ee.Initialize()
        print("GEE initialized")
    except Exception as e:
        print(f"VIIRS_SKIP: GEE auth not initialized — interactive "
              f"`ee.Authenticate()` flow required. Detail: "
              f"{type(e).__name__}: {e}")
        return 1

    # If initialized, this would proceed. Left as a stub for future runs.
    print("VIIRS_SKIP: stub — VIIRS pull not implemented post-auth.")
    return 1


if __name__ == "__main__":
    sys.exit(main())

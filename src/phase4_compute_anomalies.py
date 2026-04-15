"""
Phase 4.8 — NDVI Anomaly Detection on ROI Time Series
=======================================================
Computes z-scored anomalies from monthly climatology for each ROI,
flags months where |z| > 2, and augments the existing NDVI timeseries
JSON with anomaly metadata.

Usage:
    python src/phase4_compute_anomalies.py
"""

import json
import os
import shutil
from collections import defaultdict

import numpy as np

# ── Paths ───────────────────────────────────────────────────
JSON_PATH = "webapp/data/phase4/ndvi_timeseries.json"
BACKUP_PATH = "webapp/data/phase4/ndvi_timeseries_pre_anomaly.json"

Z_THRESHOLD = 2.0


def main():
    print("Phase 4.8 — NDVI Anomaly Detection")
    print("=" * 50)

    if not os.path.exists(JSON_PATH):
        print(f"  ERROR: {JSON_PATH} not found")
        return

    # ── Backup ────────────────────────────────────────────
    shutil.copy2(JSON_PATH, BACKUP_PATH)
    print(f"  Backup: {BACKUP_PATH}")

    with open(JSON_PATH) as f:
        data = json.load(f)

    for roi in data:
        name = roi["roi_name"]
        series = roi["data"]

        # a. Parse dates and values
        months = []
        values = []
        for pt in series:
            month = int(pt["date"].split("-")[1])
            months.append(month)
            values.append(pt["mean_ndvi"])

        values = np.array(values, dtype=np.float64)
        months = np.array(months)

        # b. Monthly climatology (mean per calendar month)
        climatology = np.zeros(12)
        for m in range(1, 13):
            mask = months == m
            if mask.any():
                climatology[m - 1] = values[mask].mean()

        # c. Anomaly = observed - climatology
        anomalies = values - climatology[months - 1]

        # d. Std of anomalies
        std = anomalies.std()
        if std < 1e-10:
            std = 1.0  # prevent division by zero for flat series

        # e. Z-score
        zscores = anomalies / std

        # f. Flag anomalies
        n_anomalies = 0
        flagged = []

        for i, pt in enumerate(series):
            z = float(zscores[i])
            is_anom = abs(z) > Z_THRESHOLD
            direction = None
            if is_anom:
                direction = "positive" if z > 0 else "negative"
                n_anomalies += 1
                flagged.append(f"    {pt['date']}  z={z:+.2f}  ({direction})")

            pt["anomaly_zscore"] = round(z, 4)
            pt["is_anomaly"] = is_anom
            pt["anomaly_direction"] = direction

        # Add top-level summary
        roi["n_anomalies"] = n_anomalies
        roi["climatology"] = [round(float(v), 6) for v in climatology]

        # Print report
        print(f"\n  {name}: {n_anomalies} anomalies out of {len(series)} months")
        if flagged:
            for line in flagged:
                print(line)
        else:
            print("    (none)")

    # ── Save ──────────────────────────────────────────────
    with open(JSON_PATH, "w") as f:
        json.dump(data, f, indent=2)
    print(f"\n  Saved: {JSON_PATH} ({os.path.getsize(JSON_PATH) / 1024:.0f} KB)")
    print("=" * 50)


if __name__ == "__main__":
    main()

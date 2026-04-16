"""
Phase 4.9 — Hotspot Detection
===============================
Combines pixel classification, per-cell change breakdowns, and ROI
anomaly data into a composite hotspot score per grid cell. Selects
top 10 as "active hotspots."

Outputs:
    webapp/data/phase4/hotspots.json

Usage:
    python src/phase4_compute_hotspots.py
"""

import json
import os
from datetime import datetime, timezone

import numpy as np
import rasterio

# ── Paths ───────────────────────────────────────────────────
PIXEL_CLASSES_TIF = "outputs/phase4_pixel_classes.tif"
GRID_INDEX_JSON = "webapp/data/grid_index.json"
NDVI_JSON = "webapp/data/phase4/ndvi_timeseries.json"
OUT_PATH = "webapp/data/phase4/hotspots.json"

THUMB_SIZE = 256  # must match prepare_webapp_data.py
VEG_LOSS_CLUSTER = 5
ANOMALY_DATE_CUTOFF = "2025-04-15"
TOP_N = 10


def main():
    print("Phase 4.9 — Hotspot Detection")
    print("=" * 50)

    # ── Load pixel classes raster ─────────────────────────
    with rasterio.open(PIXEL_CLASSES_TIF) as src:
        classes = src.read(1)  # uint8, 0=nodata, 1-5=clusters
    h, w = classes.shape
    print(f"  Pixel classes: {h} x {w}")

    # ── Load grid index ───────────────────────────────────
    with open(GRID_INDEX_JSON) as f:
        grid = json.load(f)
    cells = grid["cells"]
    n_rows = grid["n_rows"]
    n_cols = grid["n_cols"]
    print(f"  Grid: {n_rows} x {n_cols} = {len(cells)} cells")

    # ── Load NDVI anomaly data ────────────────────────────
    with open(NDVI_JSON) as f:
        ndvi_data = json.load(f)

    # Build set of ROI names that have recent anomalies
    rois_with_recent_anomalies = set()
    for roi in ndvi_data:
        name = roi["roi_name"]
        for pt in roi["data"]:
            if pt.get("is_anomaly") and pt["date"] >= ANOMALY_DATE_CUTOFF:
                rois_with_recent_anomalies.add(name)
                break
    print(f"  ROIs with recent anomalies: {rois_with_recent_anomalies or 'none'}")

    # ── Load ROI geometries for overlap check ─────────────
    with open("webapp/data/phase4/rois.geojson") as f:
        roi_geo = json.load(f)

    def point_in_polygon(lat, lng, coords):
        inside = False
        for i in range(len(coords)):
            j = (i - 1) % len(coords)
            yi, xi = coords[i][1], coords[i][0]
            yj, xj = coords[j][1], coords[j][0]
            if ((yi > lat) != (yj > lat) and
                    lng < (xj - xi) * (lat - yi) / (yj - yi) + xi):
                inside = not inside
        return inside

    def find_roi_for_cell(lat, lng):
        for feat in roi_geo["features"]:
            geom = feat["geometry"]
            rings = (geom["coordinates"] if geom["type"] == "Polygon"
                     else [r for poly in geom["coordinates"] for r in poly])
            for ring in rings:
                if point_in_polygon(lat, lng, ring):
                    return feat["properties"]["name"]
        return None

    # ── Compute per-cell scores ───────────────────────────
    print("\n  Computing per-cell scores...")
    cell_scores = []

    for cell in cells:
        r, c = cell["row"], cell["col"]
        y0 = r * THUMB_SIZE
        x0 = c * THUMB_SIZE
        y1 = min(y0 + THUMB_SIZE, h)
        x1 = min(x0 + THUMB_SIZE, w)

        cell_classes = classes[y0:y1, x0:x1]
        valid = cell_classes > 0
        n_valid = int(valid.sum())

        if n_valid == 0:
            cell_scores.append({
                "cell": cell,
                "veg_loss_pct": 0.0,
                "veg_loss_count": 0,
                "change_pct_masked": cell.get("change_pct_masked", 0),
                "anomaly_overlap": 0,
            })
            continue

        n_veg_loss = int((cell_classes == VEG_LOSS_CLUSTER).sum())
        veg_loss_pct = 100.0 * n_veg_loss / n_valid

        # Anomaly overlap
        roi_name = find_roi_for_cell(cell["lat"], cell["lng"])
        anomaly_overlap = 1 if roi_name in rois_with_recent_anomalies else 0

        cell_scores.append({
            "cell": cell,
            "veg_loss_pct": veg_loss_pct,
            "veg_loss_count": n_veg_loss,
            "change_pct_masked": cell.get("change_pct_masked", 0),
            "anomaly_overlap": anomaly_overlap,
        })

    # ── Normalize to 0-1 ─────────────────────────────────
    all_change = [cs["change_pct_masked"] for cs in cell_scores]
    all_veg = [cs["veg_loss_pct"] for cs in cell_scores]

    change_min, change_max = min(all_change), max(all_change)
    veg_min, veg_max = min(all_veg), max(all_veg)

    change_range = change_max - change_min if change_max > change_min else 1.0
    veg_range = veg_max - veg_min if veg_max > veg_min else 1.0

    for cs in cell_scores:
        cs["change_score"] = (cs["change_pct_masked"] - change_min) / change_range
        cs["veg_loss_score"] = (cs["veg_loss_pct"] - veg_min) / veg_range
        cs["score"] = 100.0 * (
            0.50 * cs["veg_loss_score"]
            + 0.40 * cs["change_score"]
            + 0.10 * cs["anomaly_overlap"]
        )

    # ── Rank and select top 10 ────────────────────────────
    cell_scores.sort(key=lambda x: x["score"], reverse=True)
    top10 = cell_scores[:TOP_N]

    # ── Build reason strings ──────────────────────────────
    def build_reason(cs):
        parts = []
        if cs["veg_loss_score"] >= 0.5:
            parts.append(f"High vegetation loss ({cs['veg_loss_pct']:.1f}%)")
        elif cs["veg_loss_score"] >= 0.2:
            parts.append(f"Moderate vegetation loss ({cs['veg_loss_pct']:.1f}%)")
        if cs["change_score"] >= 0.5:
            parts.append("significant surface change")
        elif cs["change_score"] >= 0.2:
            parts.append("moderate surface change")
        if cs["anomaly_overlap"]:
            parts.append("recent NDVI anomaly in ROI")
        if not parts:
            parts.append(f"Surface change ({cs['change_pct_masked']:.1f}%)")
        return parts[0][0].upper() + parts[0][1:] + (
            " + " + " + ".join(parts[1:]) if len(parts) > 1 else ""
        )

    # ── Build output records ──────────────────────────────
    hotspot_records = []
    for rank, cs in enumerate(top10, 1):
        cell = cs["cell"]
        bd = cell.get("change_breakdown", {})
        # Dominant change category (excluding stable)
        non_stable = {k: v for k, v in bd.items() if k != "stable"}
        dominant = max(non_stable, key=non_stable.get) if non_stable else "stable"

        CATEGORY_LABELS = {
            "new_construction": "New construction",
            "land_clearing": "Surface change / clearing",
            "vegetation_change": "Vegetation change",
            "stable": "Stable",
        }

        record = {
            "rank": rank,
            "cell_id": cell["id"],
            "lat": cell["lat"],
            "lng": cell["lng"],
            "score": round(cs["score"], 1),
            "veg_loss_pct": round(cs["veg_loss_pct"], 1),
            "change_pct_masked": cs["change_pct_masked"],
            "dominant_change_category": CATEGORY_LABELS.get(dominant, dominant),
            "reason": build_reason(cs),
        }
        hotspot_records.append(record)

    # ── Save ──────────────────────────────────────────────
    output = {
        "computed_at": datetime.now(timezone.utc).isoformat(),
        "n_cells_analyzed": len(cells),
        "score_threshold": "top 10",
        "hotspots": hotspot_records,
    }

    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w") as f:
        json.dump(output, f, indent=2)
    print(f"\n  Saved: {OUT_PATH}")

    # ── Print top 10 ─────────────────────────────────────
    print(f"\n  {'Rank':>4}  {'Score':>5}  {'Cell':>5}  {'VegLoss%':>8}  {'Change%':>8}  Reason")
    print(f"  {'-'*4}  {'-'*5}  {'-'*5}  {'-'*8}  {'-'*8}  {'-'*40}")
    for r in hotspot_records:
        print(f"  {r['rank']:>4}  {r['score']:>5.1f}  {r['cell_id']:>5}  "
              f"{r['veg_loss_pct']:>7.1f}%  {r['change_pct_masked']:>7.1f}%  "
              f"{r['reason']}")

    print(f"\n  Score range: {top10[0]['score']:.1f} - {top10[-1]['score']:.1f}")

    # ── Save per-cell veg loss stats (all 56 cells) ──────
    cell_veg_loss = {}
    for cs in cell_scores:
        cell = cs["cell"]
        cell_veg_loss[cell["id"]] = {
            "veg_loss_pct": round(cs["veg_loss_pct"], 2),
            "veg_loss_count": cs["veg_loss_count"],
        }

    veg_loss_path = os.path.join(os.path.dirname(OUT_PATH), "cell_veg_loss.json")
    with open(veg_loss_path, "w") as f:
        json.dump(cell_veg_loss, f, indent=2)
    print(f"  Saved: {veg_loss_path} ({len(cell_veg_loss)} cells)")

    print("=" * 50)


if __name__ == "__main__":
    main()

"""
Phase 4.14 — Basira one-page analytical report PDF.

Usage:
    python src/generate_report_pdf.py

Outputs:
    outputs/report_hero_map.png   — 300-DPI hero map
    outputs/basira_report.pdf     — one-page A4 PDF
"""

import json
import os
import time

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import Rectangle
from PIL import Image as PILImage

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.colors import HexColor, white
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_JUSTIFY, TA_RIGHT
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Image, Table, TableStyle,
    HRFlowable,
)

# ── Paths ──────────────────────────────────────────────────────────────────
ROOT = os.path.join(os.path.dirname(__file__), "..")
HERO_IMG_OUT  = os.path.join(ROOT, "outputs", "report_hero_map.png")
OUT_PDF       = os.path.join(ROOT, "outputs", "basira_report.pdf")
BASEMAP_PNG   = os.path.join(ROOT, "webapp", "data", "phase4", "latest_rgb.png")
BASEMAP_BOUNDS= os.path.join(ROOT, "webapp", "data", "phase4", "latest_rgb_bounds.json")
HOTSPOTS_JSON = os.path.join(ROOT, "webapp", "data", "phase4", "hotspots.json")
ROIS_GEOJSON  = os.path.join(ROOT, "webapp", "data", "phase4", "rois.geojson")
GRID_JSON     = os.path.join(ROOT, "webapp", "data", "grid_index.json")
TIMESERIES_JSON = os.path.join(ROOT, "webapp", "data", "phase4", "ndvi_timeseries.json")

PAGE_W, PAGE_H = A4
MARGIN = 16 * mm


# ── Part A: Hero map ───────────────────────────────────────────────────────

def render_hero_map():
    with open(BASEMAP_BOUNDS) as f:
        bnd = json.load(f)
    with open(HOTSPOTS_JSON) as f:
        hotspot_data = json.load(f)
    with open(ROIS_GEOJSON) as f:
        rois = json.load(f)
    with open(GRID_JSON) as f:
        grid = json.load(f)

    # Cell size in degrees
    cell_w = (grid["bounds"]["east"] - grid["bounds"]["west"]) / grid["n_cols"]
    cell_h = (grid["bounds"]["north"] - grid["bounds"]["south"]) / grid["n_rows"]

    # Build cell lookup: id -> bounds
    cell_lookup = {c["id"]: c for c in grid["cells"]}

    img_bounds = [bnd["west"], bnd["east"], bnd["south"], bnd["north"]]
    extent = [bnd["west"], bnd["east"], bnd["south"], bnd["north"]]

    basemap = PILImage.open(BASEMAP_PNG).convert("RGB")

    fig, ax = plt.subplots(figsize=(10, 8), dpi=300)
    ax.imshow(basemap, extent=extent, aspect="auto", interpolation="bilinear")

    # ROI outlines (yellow-orange)
    roi_colors = ["#FFD700", "#FFA500", "#FF8C00", "#FFEC8B"]
    roi_labels_drawn = set()
    for i, feature in enumerate(rois["features"]):
        coords = feature["geometry"]["coordinates"][0]
        xs = [c[0] for c in coords]
        ys = [c[1] for c in coords]
        name = feature["properties"]["name"].replace("_", " ").title()
        color = roi_colors[i % len(roi_colors)]
        ax.plot(xs, ys, color=color, linewidth=1.5, linestyle="--", zorder=3)
        cx = (min(xs) + max(xs)) / 2
        cy = max(ys) + 0.003
        ax.text(cx, cy, name, color=color, fontsize=5.5, ha="center",
                fontweight="bold", zorder=4,
                bbox=dict(boxstyle="round,pad=0.15", facecolor="#000000",
                          alpha=0.55, edgecolor="none"))

    # Top-10 hotspot cells (red rectangles)
    hotspots = hotspot_data["hotspots"]
    for hs in hotspots:
        cell = cell_lookup.get(hs["cell_id"])
        if cell is None:
            continue
        west  = cell["lng"] - cell_w / 2
        south = cell["lat"] - cell_h / 2
        rank  = hs["rank"]
        # Gradient: rank 1 bright red, rank 10 darker red
        alpha = 1.0 - (rank - 1) * 0.04
        rect = Rectangle(
            (west, south), cell_w, cell_h,
            linewidth=1.5, edgecolor="#FF2222",
            facecolor="#FF2222", alpha=0.25 * alpha, zorder=5,
        )
        ax.add_patch(rect)
        ax.add_patch(Rectangle(
            (west, south), cell_w, cell_h,
            linewidth=1.5 if rank <= 3 else 1.0,
            edgecolor="#FF2222", facecolor="none", zorder=6,
        ))
        # Rank label for top-5
        if rank <= 5:
            ax.text(
                west + cell_w / 2, south + cell_h / 2,
                str(rank),
                color="white", fontsize=7, ha="center", va="center",
                fontweight="bold", zorder=7,
                bbox=dict(boxstyle="round,pad=0.2", facecolor="#CC0000",
                          alpha=0.85, edgecolor="none"),
            )

    # Legend
    legend_handles = [
        mpatches.Patch(facecolor="#FF2222", alpha=0.5, edgecolor="#FF2222",
                       label="Top-10 hotspot cells"),
        mpatches.Patch(facecolor="none", edgecolor="#FFD700",
                       linestyle="--", label="Study ROIs"),
    ]
    ax.legend(handles=legend_handles, loc="lower left", fontsize=7,
              framealpha=0.75, facecolor="#111111", labelcolor="white",
              edgecolor="#444444")

    ax.set_xlim(bnd["west"], bnd["east"])
    ax.set_ylim(bnd["south"], bnd["north"])
    ax.set_xlabel("Longitude", fontsize=7, color="#888888")
    ax.set_ylabel("Latitude",  fontsize=7, color="#888888")
    ax.tick_params(labelsize=6, colors="#888888")
    ax.set_facecolor("#0b1120")
    fig.patch.set_facecolor("#0b1120")
    for spine in ax.spines.values():
        spine.set_edgecolor("#333333")

    ax.set_title(
        "Basira — Riyadh Change Hotspot Map (Jan 2020 – Apr 2026)",
        fontsize=9, color="#cccccc", pad=6,
    )

    os.makedirs(os.path.join(ROOT, "outputs"), exist_ok=True)
    fig.savefig(HERO_IMG_OUT, dpi=300, bbox_inches="tight",
                facecolor=fig.get_facecolor())
    plt.close(fig)
    print(f"  Hero map: {HERO_IMG_OUT}")


# ── Part B: PDF ────────────────────────────────────────────────────────────

def build_pdf():
    with open(HOTSPOTS_JSON) as f:
        hotspot_data = json.load(f)
    with open(TIMESERIES_JSON) as f:
        ts_data = json.load(f)

    hotspots   = hotspot_data["hotspots"]
    n_anomalies = sum(d["n_anomalies"] for d in ts_data)

    doc = SimpleDocTemplate(
        OUT_PDF, pagesize=A4,
        leftMargin=MARGIN, rightMargin=MARGIN,
        topMargin=12 * mm, bottomMargin=12 * mm,
    )

    styles = getSampleStyleSheet()

    # ── Styles ──
    s_title = ParagraphStyle(
        "BTitle", parent=styles["Title"],
        fontSize=17, leading=20, spaceAfter=1 * mm,
        textColor=HexColor("#111111"),
    )
    s_subtitle = ParagraphStyle(
        "BSubtitle", parent=styles["Normal"],
        fontSize=9, leading=12, spaceAfter=3 * mm,
        textColor=HexColor("#666666"), alignment=TA_CENTER,
    )
    s_heading = ParagraphStyle(
        "BHeading", parent=styles["Heading2"],
        fontSize=10, leading=12, spaceBefore=3 * mm, spaceAfter=1.5 * mm,
        textColor=HexColor("#1a1a1a"), fontName="Helvetica-Bold",
    )
    s_body = ParagraphStyle(
        "BBody", parent=styles["Normal"],
        fontSize=8.5, leading=11.5, spaceAfter=2 * mm,
        alignment=TA_JUSTIFY, textColor=HexColor("#222222"),
    )
    s_caption = ParagraphStyle(
        "BCaption", parent=styles["Normal"],
        fontSize=7, leading=9.5, spaceAfter=2 * mm,
        textColor=HexColor("#666666"), alignment=TA_CENTER,
    )
    s_callout = ParagraphStyle(
        "BCallout", parent=styles["Normal"],
        fontSize=8.5, leading=12, textColor=HexColor("#1a1a1a"),
        alignment=TA_JUSTIFY,
    )
    s_footer = ParagraphStyle(
        "BFooter", parent=styles["Normal"],
        fontSize=6.5, leading=9, textColor=HexColor("#999999"),
        alignment=TA_CENTER,
    )
    s_stat_val = ParagraphStyle(
        "BStatVal", parent=styles["Normal"],
        fontSize=18, leading=20, fontName="Helvetica-Bold",
        textColor=HexColor("#111111"), alignment=TA_CENTER,
    )
    s_stat_label = ParagraphStyle(
        "BStatLabel", parent=styles["Normal"],
        fontSize=7, leading=9, textColor=HexColor("#555555"),
        alignment=TA_CENTER,
    )

    elements = []

    # ── Header ──────────────────────────────────────────────────────────────
    elements.append(Paragraph(
        "Basira  <font color='#888888'>·</font>  بصيرة",
        s_title,
    ))
    elements.append(Paragraph(
        "Satellite Change Monitoring — Riyadh, Saudi Arabia  |  Phase 4 Analytical Summary  |  April 2026",
        s_subtitle,
    ))
    elements.append(HRFlowable(
        width="100%", thickness=1.0, color=HexColor("#e0e0e0"),
        spaceAfter=3 * mm,
    ))

    # ── Hero map ─────────────────────────────────────────────────────────────
    content_w = PAGE_W - 2 * MARGIN
    hero_h = content_w * 0.72
    elements.append(Image(HERO_IMG_OUT, width=content_w, height=hero_h))
    elements.append(Paragraph(
        "Figure 1. Top-10 change hotspot cells (red) overlaid on 2026 Sentinel-2 basemap. "
        "Numbered labels mark the five highest-scoring cells. Dashed outlines show the four study ROIs.",
        s_caption,
    ))

    # ── Headline stat bar ────────────────────────────────────────────────────
    stat_col_w = content_w / 4

    def stat_cell(val, label):
        return [Paragraph(val, s_stat_val), Paragraph(label, s_stat_label)]

    stat_table = Table(
        [[
            stat_cell("10", "Change hotspots"),
            stat_cell(str(n_anomalies), "NDVI anomalies"),
            stat_cell("3.35M", "Pixels analysed"),
            stat_cell("76", "Monthly scenes"),
        ]],
        colWidths=[stat_col_w] * 4,
    )
    stat_table.setStyle(TableStyle([
        ("ALIGN",       (0, 0), (-1, -1), "CENTER"),
        ("VALIGN",      (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING",  (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("BACKGROUND",  (0, 0), (-1, -1), HexColor("#f7f7f7")),
        ("LINEAFTER",   (0, 0), (2, 0), 0.5, HexColor("#dddddd")),
        ("BOX",         (0, 0), (-1, -1), 0.5, HexColor("#dddddd")),
        ("SPAN",        (0, 0), (0, 0), ),
    ]))
    elements.append(stat_table)
    elements.append(Spacer(1, 2 * mm))

    # ── Top-5 hotspots table ─────────────────────────────────────────────────
    elements.append(Paragraph("Top 5 Change Hotspots", s_heading))

    tbl_header = ["Rank", "Cell", "Score", "Veg Loss", "Change %",
                  "Category", "Est. Onset"]
    tbl_data = [tbl_header]
    for hs in hotspots[:5]:
        onset = hs.get("est_onset") or "—"
        tbl_data.append([
            str(hs["rank"]),
            hs["cell_id"],
            f"{hs['score']:.1f}",
            f"{hs['veg_loss_pct']:.1f}%",
            f"{hs['change_pct_masked']:.1f}%",
            hs["dominant_change_category"],
            onset,
        ])

    col_widths = [
        10 * mm, 14 * mm, 14 * mm, 16 * mm, 16 * mm,
        content_w - 10 - 14 - 14 - 16 - 16 - 22,
        22 * mm,
    ]
    hs_table = Table(tbl_data, colWidths=col_widths, hAlign="LEFT")
    hs_table.setStyle(TableStyle([
        ("FONTNAME",    (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE",    (0, 0), (-1, -1), 7.5),
        ("LEADING",     (0, 0), (-1, -1), 10),
        ("TEXTCOLOR",   (0, 0), (-1, -1), HexColor("#222222")),
        ("BACKGROUND",  (0, 0), (-1, 0), HexColor("#f0f0f0")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1),
         [HexColor("#ffffff"), HexColor("#fafafa")]),
        ("GRID",        (0, 0), (-1, -1), 0.35, HexColor("#cccccc")),
        ("VALIGN",      (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 3),
        ("RIGHTPADDING", (0, 0), (-1, -1), 3),
        ("TOPPADDING",  (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ("TEXTCOLOR",   (2, 1), (2, -1), HexColor("#CC0000")),
        ("FONTNAME",    (2, 1), (2, -1), "Helvetica-Bold"),
    ]))
    elements.append(hs_table)
    elements.append(Spacer(1, 2 * mm))

    # ── Callout box ──────────────────────────────────────────────────────────
    april_2022_cells = sum(
        1 for hs in hotspots if hs.get("est_onset") == "2022-04"
    )
    callout_text = (
        f"<b>Event spotlight — April 2022:</b>  {april_2022_cells} of the top-10 hotspot "
        "cells show a detected onset of sustained NDVI decline beginning in April 2022. "
        "This cluster of co-occurring onsets is consistent with large-scale ground-clearing "
        "activity across the central and southern zones of the AOI, likely linked to "
        "infrastructure development projects confirmed in optical imagery."
    )
    callout_table = Table(
        [[Paragraph(callout_text, s_callout)]],
        colWidths=[content_w],
    )
    callout_table.setStyle(TableStyle([
        ("BACKGROUND",   (0, 0), (-1, -1), HexColor("#FFF8E1")),
        ("BOX",          (0, 0), (-1, -1), 1.0, HexColor("#FFD700")),
        ("LEFTPADDING",  (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING",   (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING",(0, 0), (-1, -1), 5),
    ]))
    elements.append(callout_table)
    elements.append(Spacer(1, 2 * mm))

    # ── Methodology ──────────────────────────────────────────────────────────
    elements.append(Paragraph("Methodology", s_heading))
    elements.append(Paragraph(
        "76 monthly Sentinel-2 L2A scenes (Jan 2020 – Apr 2026, 20 m, bands B02/B03/B04/B08) "
        "were processed via Sentinel Hub to produce per-pixel NDVI time series. A common valid "
        "mask (≥80% scene coverage) retained 3.35 M pixels across the AOI. K-Means clustering "
        "(k=5) on five temporal features (mean NDVI, linear slope, seasonal amplitude, first/second "
        "half mean) classified each pixel. A 7×8 analysis grid (56 cells) was scored by composite "
        "index: 50% vegetation loss + 40% surface change + 10% NDVI anomaly overlap. Monthly "
        "climatology z-scores (|z|>2) flagged 9 anomalous NDVI episodes across 4 ROIs. "
        "Onset detection used a sustained-drop heuristic: baseline from the first 18 months, "
        "threshold = baseline − 1σ, held for ≥2 consecutive months.",
        s_body,
    ))

    # ── Footer ───────────────────────────────────────────────────────────────
    elements.append(Spacer(1, 2 * mm))
    elements.append(HRFlowable(
        width="100%", thickness=0.4, color=HexColor("#dddddd"),
        spaceBefore=1 * mm, spaceAfter=1.5 * mm,
    ))
    elements.append(Paragraph(
        "Data: Copernicus Sentinel-2 (ESA) · Sentinel Hub Process API.  "
        "Contains modified Copernicus Sentinel data [2020–2026].  "
        "|  Pipeline: Python · rasterio · scikit-learn · Leaflet  "
        "|  github.com/a7zain/sar-change-detection",
        s_footer,
    ))

    doc.build(elements)
    print(f"  PDF: {OUT_PDF}")


# ── Main ───────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    t0 = time.time()
    print("Rendering hero map …")
    render_hero_map()
    print("Building PDF …")
    build_pdf()
    elapsed = time.time() - t0
    hero_size = os.path.getsize(HERO_IMG_OUT) / 1024
    pdf_size  = os.path.getsize(OUT_PDF) / 1024
    print(f"\nDone in {elapsed:.1f}s")
    print(f"  report_hero_map.png  {hero_size:.0f} KB")
    print(f"  basira_report.pdf    {pdf_size:.0f} KB")

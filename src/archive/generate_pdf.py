"""
Generate a one-page technical summary PDF using reportlab.

Usage:
    python src/generate_pdf.py
"""

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm, cm
from reportlab.lib.colors import HexColor, black, white
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_JUSTIFY
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Image, Table, TableStyle,
    HRFlowable,
)
from reportlab.lib.utils import ImageReader
import os

OUT_PDF  = "outputs/technical_summary.pdf"
HERO_IMG = "outputs/05_change_hero.png"

PAGE_W, PAGE_H = A4
MARGIN = 18 * mm


def build_pdf():
    os.makedirs("outputs", exist_ok=True)

    doc = SimpleDocTemplate(
        OUT_PDF, pagesize=A4,
        leftMargin=MARGIN, rightMargin=MARGIN,
        topMargin=14 * mm, bottomMargin=14 * mm,
    )

    styles = getSampleStyleSheet()

    # Custom styles
    s_title = ParagraphStyle(
        "Title2", parent=styles["Title"],
        fontSize=16, leading=19, spaceAfter=2 * mm,
        textColor=HexColor("#111111"),
    )
    s_subtitle = ParagraphStyle(
        "Subtitle", parent=styles["Normal"],
        fontSize=10, leading=13, spaceAfter=4 * mm,
        textColor=HexColor("#555555"), alignment=TA_CENTER,
    )
    s_heading = ParagraphStyle(
        "Heading", parent=styles["Heading2"],
        fontSize=11, leading=13, spaceBefore=4 * mm, spaceAfter=1.5 * mm,
        textColor=HexColor("#1a1a1a"),
    )
    s_body = ParagraphStyle(
        "Body2", parent=styles["Normal"],
        fontSize=9, leading=12, spaceAfter=2 * mm,
        alignment=TA_JUSTIFY, textColor=HexColor("#222222"),
    )
    s_bullet = ParagraphStyle(
        "Bullet", parent=s_body,
        leftIndent=8 * mm, bulletIndent=3 * mm,
        spaceAfter=1 * mm,
    )
    s_footer = ParagraphStyle(
        "Footer", parent=styles["Normal"],
        fontSize=7, leading=9, textColor=HexColor("#999999"),
        alignment=TA_CENTER,
    )

    elements = []

    # ── Title block ────────────────────────────────────────
    elements.append(Paragraph(
        "SAR Change Detection — Riyadh Urban Development (2022–2024)",
        s_title,
    ))
    elements.append(Paragraph(
        "Ahmed  |  Electrical Engineer  |  Earth Observation Portfolio  |  April 2026",
        s_subtitle,
    ))
    elements.append(HRFlowable(
        width="100%", thickness=0.5, color=HexColor("#cccccc"),
        spaceAfter=3 * mm,
    ))

    # ── Objective ──────────────────────────────────────────
    elements.append(Paragraph("Objective", s_heading))
    elements.append(Paragraph(
        "Detect and classify urban change across Riyadh, Saudi Arabia between "
        "January 2022 and February 2024 using Sentinel-1 Synthetic Aperture Radar "
        "(SAR) imagery. The goal is to demonstrate an end-to-end SAR processing "
        "pipeline — from raw data ingestion to machine-learning classification — "
        "producing actionable change maps for urban monitoring applications.",
        s_body,
    ))

    # ── Data ───────────────────────────────────────────────
    elements.append(Paragraph("Data", s_heading))

    data_table = Table(
        [
            ["Parameter", "Value"],
            ["Satellite", "Sentinel-1A (ESA Copernicus)"],
            ["Mode / Product", "Interferometric Wide (IW) / GRD-COG"],
            ["Polarisation", "VV (co-polarised)"],
            ["Before scene", "25 Jan 2022  (orbit 41619, rel. orbit 72, ascending)"],
            ["After scene", "20 Feb 2024  (orbit 52644, rel. orbit 72, ascending)"],
            ["AOI", "Riyadh: 24.55–24.85°N, 46.55–46.95°E"],
            ["Pixel resolution", "10 m (UTM Zone 38N, EPSG:32638)"],
            ["Data source", "Copernicus Dataspace (OData API)"],
        ],
        colWidths=[35 * mm, PAGE_W - 2 * MARGIN - 37 * mm],
        hAlign="LEFT",
    )
    data_table.setStyle(TableStyle([
        ("FONTNAME",   (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE",   (0, 0), (-1, -1), 8),
        ("LEADING",    (0, 0), (-1, -1), 11),
        ("TEXTCOLOR",  (0, 0), (-1, -1), HexColor("#222222")),
        ("BACKGROUND", (0, 0), (-1, 0),  HexColor("#f0f0f0")),
        ("GRID",       (0, 0), (-1, -1), 0.4, HexColor("#cccccc")),
        ("VALIGN",     (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING",  (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
    ]))
    elements.append(data_table)
    elements.append(Spacer(1, 2 * mm))

    # ── Methodology ────────────────────────────────────────
    elements.append(Paragraph("Methodology", s_heading))
    bullets = [
        "<b>Georeferencing:</b> Parsed 210 geolocation grid points (GCPs) from "
        "Sentinel-1 annotation XML files and assigned EPSG:4326 CRS to the "
        "measurement TIFFs, which ship with CRS=None in COG format.",
        "<b>Reprojection & alignment:</b> Warped both scenes via GCP-based "
        "transformation onto a common 10 m UTM grid (EPSG:32638) covering the "
        "Riyadh AOI. Verified pixel-to-pixel alignment (identical shapes and transforms).",
        "<b>Speckle filtering:</b> Applied a Lee filter (7×7 window) on linear "
        "amplitude to reduce multiplicative SAR noise while preserving edges, "
        "then converted to decibels (dB).",
        "<b>Change detection:</b> Computed log-ratio difference "
        "(dB<sub>2024</sub> − dB<sub>2022</sub>); classified pixels exceeding ±3 dB as "
        "significant change (≈ factor-of-2 change in backscatter power).",
        "<b>ML classification:</b> Built a 4-band feature stack (dB 2022, dB 2024, "
        "|change|, signed change) and applied K-Means (k=5) and Gaussian Mixture Models. "
        "K-Means achieved a silhouette score of 0.319. Clusters were automatically interpreted "
        "as: stable urban, stable desert, new construction, land clearing, and seasonal variation.",
    ]
    for b in bullets:
        elements.append(Paragraph(f"• {b}", s_bullet))
    elements.append(Spacer(1, 1 * mm))

    # ── Hero map ───────────────────────────────────────────
    elements.append(Paragraph("Key Result", s_heading))
    img_w = PAGE_W - 2 * MARGIN
    img_h = img_w * 0.72  # approximate aspect ratio
    elements.append(Image(HERO_IMG, width=img_w, height=img_h))
    elements.append(Spacer(1, 1 * mm))
    elements.append(Paragraph(
        "<i>Figure 1. SAR backscatter change map (±3 dB threshold). "
        "Red = increased backscatter (new construction); "
        "Blue = decreased backscatter (clearing/demolition). "
        "94.2% stable, 1.4% increase, 4.4% decrease across 9.7M valid pixels.</i>",
        ParagraphStyle("Caption", parent=s_body, fontSize=7.5, leading=10,
                       textColor=HexColor("#666666"), alignment=TA_CENTER),
    ))

    # ── Validation ─────────────────────────────────────────
    elements.append(Paragraph("Validation", s_heading))
    elements.append(Paragraph(
        "Connected-component analysis identified the top 10 change clusters. "
        "Cross-referencing with Google Earth optical imagery confirmed:",
        s_body,
    ))
    val_bullets = [
        "<b>King Salman Park</b> (24.83°N, 46.58°E): 496 ha decrease — massive clearing "
        "for the 13.4 km² mega-project, clearly visible in optical imagery as demolished blocks.",
        "<b>Northern expansion</b> (24.84°N, 46.69°E): 383 ha decrease — new neighbourhood "
        "grading and road infrastructure preparation.",
        "<b>New residential construction</b> (24.72°N, 46.71°E): 33.5 ha increase — "
        "new buildings producing higher radar returns where open land previously existed.",
    ]
    for b in val_bullets:
        elements.append(Paragraph(f"• {b}", s_bullet))

    # ── Conclusion ─────────────────────────────────────────
    elements.append(Paragraph("Conclusion", s_heading))
    elements.append(Paragraph(
        "This project demonstrates that freely available Sentinel-1 SAR data, "
        "combined with proper geocorrection and standard image processing techniques, "
        "can reliably detect and classify urban change at 10 m resolution. The pipeline "
        "runs end-to-end in Python, requires no commercial software, and produces "
        "GIS-ready outputs. SAR's all-weather, day/night imaging capability makes it "
        "particularly valuable for continuous urban monitoring in arid regions like "
        "Riyadh, where cloud cover is rare but optical revisit may still be limited. "
        "The validated results confirm detection of known mega-projects (King Salman Park) "
        "and ongoing suburban expansion, demonstrating practical applicability for "
        "urban planning, infrastructure monitoring, and development tracking.",
        s_body,
    ))

    # ── Footer ─────────────────────────────────────────────
    elements.append(Spacer(1, 3 * mm))
    elements.append(HRFlowable(
        width="100%", thickness=0.4, color=HexColor("#dddddd"),
        spaceBefore=1 * mm, spaceAfter=1 * mm,
    ))
    elements.append(Paragraph(
        "Data: Copernicus Sentinel-1 (ESA). Contains modified Copernicus Sentinel data [2022, 2024].  "
        "|  Pipeline: Python · rasterio · scikit-learn · Folium  |  github.com/a7zain",
        s_footer,
    ))

    doc.build(elements)
    print(f"Saved: {OUT_PDF}")


if __name__ == "__main__":
    build_pdf()

"""PDF report generation with reportlab + matplotlib.

Two reports:
  - watershed report: cover, summary counts, mean WII, map figure with
    markers, top-5/bottom-5 interventions with photo thumbnails, methodology,
    limitations.
  - single-intervention report: photo, AI output, verdict, evidence, impact
    metrics, chart.
"""
import io
import json

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, PageBreak
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

from .. import config

styles = getSampleStyleSheet()
styles.add(ParagraphStyle(name="JSTitle", fontSize=22, leading=26, spaceAfter=6, textColor=colors.HexColor("#0b4a3f")))
styles.add(ParagraphStyle(name="JSSubtitle", fontSize=12, leading=16, textColor=colors.HexColor("#4b5f5a")))
styles.add(ParagraphStyle(name="JSH2", fontSize=15, leading=18, spaceBefore=14, spaceAfter=8, textColor=colors.HexColor("#0b4a3f")))
styles.add(ParagraphStyle(name="JSBody", fontSize=10, leading=14))
styles.add(ParagraphStyle(name="JSSmall", fontSize=8, leading=11, textColor=colors.HexColor("#6b7280")))

VERDICT_COLORS = {"corroborated": "#1f9d55", "mismatch": "#d93025", "inconclusive": "#6b7280"}


def _map_figure(watershed_geojson, streams_geojson, interventions):
    fig, ax = plt.subplots(figsize=(6, 5), dpi=150)
    try:
        geom = watershed_geojson["geometry"]
        if geom["type"] == "Polygon":
            for ring in geom["coordinates"]:
                xs, ys = zip(*ring)
                ax.plot(xs, ys, color="#0b4a3f", linewidth=1.5)
    except Exception:
        pass
    try:
        for feat in streams_geojson.get("features", []):
            geom = feat["geometry"]
            if geom["type"] == "LineString":
                xs, ys = zip(*geom["coordinates"])
                ax.plot(xs, ys, color="#3b82f6", linewidth=0.8)
    except Exception:
        pass
    for iv in interventions:
        color = VERDICT_COLORS.get(iv.get("verdict"), "#6b7280")
        ax.scatter([iv["lon"]], [iv["lat"]], c=color, s=30, edgecolors="black", linewidths=0.4, zorder=5)
    ax.set_title("Watershed overview: interventions by verdict", fontsize=10)
    ax.set_xlabel("Longitude", fontsize=8)
    ax.set_ylabel("Latitude", fontsize=8)
    ax.tick_params(labelsize=7)
    buf = io.BytesIO()
    fig.tight_layout()
    fig.savefig(buf, format="png")
    plt.close(fig)
    buf.seek(0)
    return buf


def _series_chart(series):
    fig, ax = plt.subplots(figsize=(6, 3), dpi=150)
    years = series.get("years", [])
    ax.plot(years, series.get("treated_ndvi", []), label="Treated NDVI", color="#1f9d55", marker="o")
    ax.plot(years, series.get("control_ndvi", []), label="Control NDVI", color="#9ca3af", marker="o", linestyle="--")
    ax.set_xlabel("Year", fontsize=8)
    ax.set_ylabel("NDVI", fontsize=8)
    ax.legend(fontsize=7)
    ax.tick_params(labelsize=7)
    buf = io.BytesIO()
    fig.tight_layout()
    fig.savefig(buf, format="png")
    plt.close(fig)
    buf.seek(0)
    return buf


def _cover(watershed_name, data_source, generated_on):
    elems = [
        Spacer(1, 3 * cm),
        Paragraph("JalSakshya", styles["JSTitle"]),
        Paragraph("Geospatial Watershed Evidence & Impact Report", styles["JSSubtitle"]),
        Spacer(1, 1.5 * cm),
        Paragraph(f"<b>Watershed:</b> {watershed_name}", styles["JSBody"]),
        Paragraph(f"<b>Date generated:</b> {generated_on}", styles["JSBody"]),
        Paragraph(f"<b>Data source:</b> {data_source}", styles["JSBody"]),
    ]
    if data_source == "synthetic":
        elems.append(Spacer(1, 0.3 * cm))
        elems.append(Paragraph(
            "<b>DEMO DATA</b> — satellite layers in this report are synthetically generated "
            "for demonstration; the analysis pipeline itself is real.",
            ParagraphStyle(name="Warn", parent=styles["JSBody"], textColor=colors.HexColor("#b45309"))
        ))
    return elems


def _methodology_and_limits():
    methodology = (
        "Each intervention's impact is estimated using a difference-in-differences (DiD) "
        "design: mean satellite index values (NDVI, water frequency, NDMI) are compared "
        "before vs after the intervention's completion date, for both the treated zone and a "
        "control area of untreated pixels with the same land-cover class and similar slope, "
        "more than 500m from any intervention. DiD = (treated_after - treated_before) - "
        "(control_after - control_before), which cancels out the effect of a good or bad "
        "monsoon common to both areas. The Watershed Impact Index (WII, 0-100) combines "
        "min-max normalised NDVI, water and NDMI DiD values with AI photo-verification "
        "confidence, weighted 35% / 35% / 15% / 15% respectively."
    )
    limits = (
        "Landsat pixels are 30m x 30m (0.09 ha); small structures such as a single check dam "
        "or farm pond bund are smaller than one pixel and cannot be directly resolved. This "
        "report therefore evaluates the surrounding zone (a 3x3-pixel local zone and a ~500m "
        "context zone), not the structure itself. NDMI is reported as a moisture PROXY, not "
        "measured soil moisture. Where satellite and photo evidence are both weak or "
        "conflicting in an undeterminable way, the verdict is explicitly marked Inconclusive "
        "rather than forced to a pass/fail result."
    )
    return [
        Paragraph("Methodology", styles["JSH2"]),
        Paragraph(methodology, styles["JSBody"]),
        Paragraph("Limitations", styles["JSH2"]),
        Paragraph(limits, styles["JSBody"]),
    ]


def build_watershed_report(out_path, watershed_name, data_source, generated_on,
                            watershed_geojson, streams_geojson, interventions, photo_paths_by_id):
    """interventions: list of dicts with id, name, type, lat, lon, verdict, wii, photo_id."""
    doc = SimpleDocTemplate(str(out_path), pagesize=A4,
                             leftMargin=2 * cm, rightMargin=2 * cm, topMargin=2 * cm, bottomMargin=2 * cm)
    elems = _cover(watershed_name, data_source, generated_on)
    elems.append(PageBreak())

    counts = {"corroborated": 0, "mismatch": 0, "inconclusive": 0}
    wiis = []
    for iv in interventions:
        v = iv.get("verdict")
        if v in counts:
            counts[v] += 1
        if iv.get("wii") is not None:
            wiis.append(iv["wii"])
    mean_wii = round(sum(wiis) / len(wiis), 1) if wiis else 0

    elems.append(Paragraph("Summary", styles["JSH2"]))
    summary_table = Table([
        ["Corroborated", "Mismatch", "Inconclusive", "Mean WII"],
        [str(counts["corroborated"]), str(counts["mismatch"]), str(counts["inconclusive"]), str(mean_wii)],
    ], colWidths=[4 * cm] * 4)
    summary_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0b4a3f")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
    ]))
    elems.append(summary_table)

    elems.append(Paragraph("Watershed map", styles["JSH2"]))
    map_buf = _map_figure(watershed_geojson, streams_geojson, interventions)
    elems.append(Image(map_buf, width=14 * cm, height=11.6 * cm))

    ranked = sorted([iv for iv in interventions if iv.get("wii") is not None],
                     key=lambda x: x["wii"], reverse=True)
    top5 = ranked[:5]
    bottom5 = list(reversed(ranked[-5:])) if len(ranked) >= 5 else []

    def _iv_table(rows, heading):
        elems.append(Paragraph(heading, styles["JSH2"]))
        data = [["Name", "Type", "Verdict", "WII"]]
        for iv in rows:
            data.append([iv["name"], iv["type"], iv["verdict"] or "-", str(iv["wii"])])
        t = Table(data, colWidths=[5 * cm, 3.5 * cm, 3.5 * cm, 2 * cm])
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e6f0ee")),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
        ]))
        elems.append(t)

    _iv_table(top5, "Top 5 interventions by WII")
    _iv_table(bottom5, "Bottom 5 interventions by WII")

    elems.append(PageBreak())
    elems.extend(_methodology_and_limits())

    doc.build(elems)
    return out_path


def build_intervention_report(out_path, intervention, photo_path, series, generated_on, data_source):
    doc = SimpleDocTemplate(str(out_path), pagesize=A4,
                             leftMargin=2 * cm, rightMargin=2 * cm, topMargin=2 * cm, bottomMargin=2 * cm)
    elems = [
        Paragraph("JalSakshya — Intervention Report", styles["JSTitle"]),
        Paragraph(f"{intervention['name']} ({intervention['type'].replace('_', ' ')})", styles["JSSubtitle"]),
        Spacer(1, 0.5 * cm),
        Paragraph(f"<b>Generated:</b> {generated_on} &nbsp;&nbsp; <b>Data source:</b> {data_source}", styles["JSBody"]),
    ]

    if photo_path:
        try:
            elems.append(Spacer(1, 0.3 * cm))
            elems.append(Image(str(photo_path), width=10 * cm, height=7.5 * cm))
        except Exception:
            pass

    ai = intervention.get("ai") or {}
    elems.append(Paragraph("AI photo interpretation", styles["JSH2"]))
    ai_table = Table([
        ["Structure", "Water present", "Vegetation", "Land condition", "Confidence"],
        [ai.get("structure_type", "-"), str(ai.get("water_present", "-")),
         ai.get("vegetation_level", "-"), ai.get("land_condition", "-"),
         f"{ai.get('confidence', 0):.2f}"],
    ], colWidths=[3 * cm, 3 * cm, 3 * cm, 3.5 * cm, 2.5 * cm])
    ai_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e6f0ee")),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
    ]))
    elems.append(ai_table)

    verdict = (intervention.get("verdict") or "inconclusive").upper()
    verdict_color = VERDICT_COLORS.get(intervention.get("verdict"), "#6b7280")
    elems.append(Paragraph("Verdict", styles["JSH2"]))
    elems.append(Paragraph(
        f'<font color="{verdict_color}"><b>{verdict}</b></font>', styles["JSBody"]
    ))
    elems.append(Paragraph(intervention.get("verdict_reason") or "", styles["JSBody"]))

    impact = intervention.get("impact") or {}
    elems.append(Paragraph("Impact (control-area DiD)", styles["JSH2"]))
    impact_table = Table([
        ["NDVI DiD", "Water freq. DiD", "Moisture proxy DiD", "WII"],
        [f"{impact.get('ndvi_did', 0):.3f}" if impact.get("ndvi_did") is not None else "-",
         f"{impact.get('water_freq_did', 0):.3f}" if impact.get("water_freq_did") is not None else "-",
         f"{impact.get('ndmi_did', 0):.3f}" if impact.get("ndmi_did") is not None else "-",
         str(impact.get("wii", "-"))],
    ], colWidths=[3.5 * cm] * 4)
    impact_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e6f0ee")),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
    ]))
    elems.append(impact_table)

    if series:
        elems.append(Paragraph("NDVI time series (treated vs control)", styles["JSH2"]))
        chart_buf = _series_chart(series)
        elems.append(Image(chart_buf, width=14 * cm, height=7 * cm))

    elems.append(Spacer(1, 0.5 * cm))
    elems.append(Paragraph(
        "Note: 30m satellite pixels cannot reliably resolve small structures; this analysis "
        "describes the surrounding zone. NDMI is a moisture proxy, not measured soil moisture.",
        styles["JSSmall"]
    ))

    doc.build(elems)
    return out_path

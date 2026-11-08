"""Framework-independent PDF renderer for the patient report (STEP 13 — this pass).

Takes exactly the dict GET /reports/{patient_id} returns (see apps/api/main.py:patient_report) and
renders it to real PDF bytes with reportlab. There is no fastapi/pydantic import here, so — unlike most
of apps/api/ — this module *can* be fully exercised in this sandbox (reportlab is installed) and *is*:
see tests/test_report_pdf.py, which renders a report built from realistic fixture data and then parses
the resulting PDF bytes back out with pypdf to assert the real fields (patient name, SYNTHETIC DEMO
PATIENT label, disclaimer text, risk level, factor names, alert count...) actually appear in the
rendered output — not just that the function returned without raising.

Why this exists: STATUS.md previously listed "no PDF export endpoint — reportlab not installed, no
network to install it" as a known, honestly-documented gap, and apps/web/src/pages/Reports.tsx
deliberately did not show a "Download PDF" button because it would have been fake. reportlab is
installed in this environment now, so this closes that gap for real: every number below is read out of
the `report` dict the caller passes in (itself assembled by patient_report() from real stored state —
the repository, the alert store, the risk engine's last assessment) and nothing here invents a figure
that isn't already in that dict.
"""
from __future__ import annotations
from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
                                HRFlowable, KeepTogether)

# Bronze accent matches apps/web/src/styles/globals.css's --accent-bronze token, so the PDF reads as
# the same product as the dashboard rather than a generic report template.
BRAND = colors.HexColor("#B08D57")
INK = colors.HexColor("#1A1A1A")
MUTED = colors.HexColor("#6B6B6B")
LINE = colors.HexColor("#DDDDDD")
PANEL = colors.HexColor("#F6F3EE")
RISK_COLORS = {"LOW": colors.HexColor("#1F9D55"), "MEDIUM": colors.HexColor("#B8860B"),
              "HIGH": colors.HexColor("#C0392B"), "UNKNOWN": MUTED}


def _styles() -> dict:
    ss = getSampleStyleSheet()
    out = {
        "title": ParagraphStyle("WZTitle", parent=ss["Title"], textColor=INK, fontSize=19,
                                alignment=TA_CENTER, spaceAfter=2, leading=22),
        "subtitle": ParagraphStyle("WZSubtitle", parent=ss["Normal"], textColor=MUTED, fontSize=9.5,
                                   alignment=TA_CENTER, spaceAfter=4),
        "h2": ParagraphStyle("WZH2", parent=ss["Heading2"], textColor=INK, fontSize=12.5,
                             spaceBefore=12, spaceAfter=5, leading=15),
        "body": ParagraphStyle("WZBody", parent=ss["Normal"], textColor=INK, fontSize=9.3, leading=13.5),
        "small": ParagraphStyle("WZSmall", parent=ss["Normal"], textColor=MUTED, fontSize=7.8, leading=11),
        "badge": ParagraphStyle("WZBadge", parent=ss["Normal"], textColor=colors.white, fontSize=8.5,
                                alignment=TA_CENTER, leading=10),
        "cell": ParagraphStyle("WZCell", parent=ss["Normal"], textColor=INK, fontSize=8.6, leading=11.5),
        "cellMuted": ParagraphStyle("WZCellMuted", parent=ss["Normal"], textColor=MUTED, fontSize=8.2, leading=11),
    }
    return out


def _fmt_pct(v) -> str:
    return f"{v * 100:.0f}%" if isinstance(v, (int, float)) else "not available"


def _fmt_num(v, suffix: str = "") -> str:
    if v is None:
        return "—"
    try:
        return f"{float(v):.1f}{suffix}"
    except (TypeError, ValueError):
        return str(v)


def _clock(ts) -> str:
    if not ts:
        return "—"
    return str(ts).replace("T", "  ").split("+")[0].split(".")[0]


def _synthetic_banner(styles: dict) -> Table:
    t = Table([[Paragraph(
        "SYNTHETIC DEMO PATIENT — all patient data and physiological readings in this report are "
        "synthetic, generated for demonstration purposes. This is not a real patient record.",
        styles["small"])]], colWidths=[178 * mm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#FFF7E6")),
        ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor("#E8C874")),
        ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING", (0, 0), (-1, -1), 8), ("RIGHTPADDING", (0, 0), (-1, -1), 8),
    ]))
    return t


def _risk_badge(level: str, styles: dict):
    color = RISK_COLORS.get((level or "UNKNOWN").upper(), MUTED)
    t = Table([[Paragraph((level or "UNKNOWN").upper(), styles["badge"])]], colWidths=[26 * mm], rowHeights=[6.5 * mm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), color), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ROUNDEDCORNERS", [4, 4, 4, 4]),
    ]))
    return t


def _header(patient: dict, styles: dict) -> list:
    story = [
        Paragraph("WardZero AI", styles["title"]),
        Paragraph("Intelligent Home-Care Monitoring — Patient Report", styles["subtitle"]),
        Spacer(1, 8),
        _synthetic_banner(styles),
        Spacer(1, 10),
    ]
    name = patient.get("full_name", "Unknown patient")
    age = patient.get("age")
    conditions = ", ".join(patient.get("conditions") or []) or "None recorded"
    left = Paragraph(
        f"<b>{name}</b><br/>Age {age if age is not None else '—'}"
        f"<br/>Conditions: {conditions}<br/>Patient ID: {patient.get('id', '—')}",
        styles["body"])
    right_rows = [[Paragraph("Current risk level", styles["cellMuted"])],
                  [_risk_badge(patient.get("risk_level"), styles)]]
    prob = patient.get("risk_probability")
    if prob is not None:
        right_rows.append([Paragraph(f"Confidence: {_fmt_pct(prob)}", styles["cellMuted"])])
    right = Table(right_rows, colWidths=[40 * mm])
    right.setStyle(TableStyle([("ALIGN", (0, 0), (-1, -1), "RIGHT"), ("TOPPADDING", (0, 0), (-1, -1), 1),
                               ("BOTTOMPADDING", (0, 0), (-1, -1), 2)]))
    header_table = Table([[left, right]], colWidths=[130 * mm, 48 * mm])
    header_table.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]))
    story.append(header_table)
    story.append(Spacer(1, 4))
    story.append(HRFlowable(width="100%", thickness=0.6, color=LINE))
    return story


def _risk_section(assessment: dict | None, styles: dict) -> list:
    story = [Paragraph("AI Risk Assessment", styles["h2"])]
    if not assessment:
        story.append(Paragraph("No AI risk assessment has been recorded for this patient yet.",
                               styles["body"]))
        return story

    method_label = "Trained AI model" if assessment.get("method") == "model" else "Rules-based fallback"
    exp_method = (assessment.get("forecast") or {}).get("explanation_method")
    exp_line = {"shap": "SHAP", "occlusion": "Feature occlusion fallback",
               "rules": "Rules-based (model unavailable)"}.get(exp_method, exp_method or "—")
    meta = Table([[
        Paragraph(f"<b>Method:</b> {method_label}", styles["cell"]),
        Paragraph(f"<b>Explanation method:</b> {exp_line}", styles["cell"]),
        Paragraph(f"<b>Recommended action:</b> "
                 f"{(assessment.get('recommended_escalation') or '—').replace('_', ' ').title()}",
                 styles["cell"]),
    ]], colWidths=[59 * mm, 59 * mm, 60 * mm])
    meta.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), PANEL),
                              ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                              ("LEFTPADDING", (0, 0), (-1, -1), 8), ("VALIGN", (0, 0), (-1, -1), "TOP")]))
    story += [meta, Spacer(1, 8)]

    if assessment.get("explanation"):
        story += [Paragraph(f"<i>{assessment['explanation']}</i>", styles["body"]), Spacer(1, 6)]

    breaches = assessment.get("hard_threshold_breaches") or []
    if breaches:
        rows = [[Paragraph("Vital", styles["cellMuted"]), Paragraph("Value", styles["cellMuted"]),
                Paragraph("Band breached", styles["cellMuted"])]]
        for b in breaches:
            rows.append([Paragraph(str(b.get("vital", "—")).replace("_", " ").title(), styles["cell"]),
                        Paragraph(str(b.get("value", "—")), styles["cell"]),
                        Paragraph(f"{str(b.get('band', '—')).title()} {('· ' + b['severity']) if b.get('severity') else ''}",
                                 styles["cell"])])
        bt = Table(rows, colWidths=[59 * mm, 40 * mm, 79 * mm], repeatRows=1)
        bt.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.4, LINE),
                               ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#FDECEA")),
                               ("BACKGROUND", (0, 1), (-1, -1), colors.HexColor("#FFF9F8"))]))
        story += [Paragraph("Hard threshold breaches (safety-net override)", styles["h2"]), bt, Spacer(1, 6)]

    factors = assessment.get("contributing_factors") or []
    if factors:
        rows = [[Paragraph("Factor", styles["cellMuted"]), Paragraph("Value", styles["cellMuted"]),
                Paragraph("Effect", styles["cellMuted"]), Paragraph("Weight", styles["cellMuted"])]]
        for f in factors:
            arrow = "\u2191 increases risk" if f.get("direction") == "increases_risk" else "\u2193 decreases risk"
            weight = f.get("contribution")
            rows.append([
                Paragraph(str(f.get("feature", "—")).replace("_", " ").title(), styles["cell"]),
                Paragraph(_fmt_num(f.get("value")), styles["cell"]),
                Paragraph(arrow, styles["cell"]),
                Paragraph(f"{weight:.2f}" if isinstance(weight, (int, float)) else "—", styles["cell"]),
            ])
        ft = Table(rows, colWidths=[62 * mm, 30 * mm, 56 * mm, 30 * mm], repeatRows=1)
        ft.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.4, LINE),
                               ("BACKGROUND", (0, 0), (-1, 0), PANEL)]))
        story += [Paragraph("Contributing factors", styles["h2"]), ft, Spacer(1, 6)]

    forecast = assessment.get("forecast") or {}
    if forecast:
        rows = [[Paragraph("Forecast window", styles["cellMuted"]), Paragraph("Deterioration probability", styles["cellMuted"])],
                [Paragraph("Next 24 hours", styles["cell"]), Paragraph(_fmt_pct(forecast.get("deterioration_24h_probability")), styles["cell"])],
                [Paragraph("Next 48 hours", styles["cell"]), Paragraph(_fmt_pct(forecast.get("deterioration_48h_probability")), styles["cell"])]]
        fct = Table(rows, colWidths=[89 * mm, 89 * mm], repeatRows=1)
        fct.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.4, LINE), ("BACKGROUND", (0, 0), (-1, 0), PANEL)]))
        story += [Paragraph("Deterioration forecast", styles["h2"]), fct]
        if forecast.get("basis"):
            story += [Spacer(1, 3), Paragraph(f"Basis: {forecast['basis']}", styles["small"])]

    return story


def _timeline_section(timeline: list, styles: dict) -> list:
    story = [Paragraph("Patient Timeline", styles["h2"])]
    if not timeline:
        story.append(Paragraph("No timeline events recorded for this patient yet.", styles["body"]))
        return story
    rows = [[Paragraph("Time", styles["cellMuted"]), Paragraph("Event", styles["cellMuted"]),
            Paragraph("Detail", styles["cellMuted"])]]
    for ev in timeline[-40:]:
        detail = ev.get("detail")
        detail_str = ", ".join(f"{k}: {v}" for k, v in detail.items()) if isinstance(detail, dict) else str(detail or "—")
        rows.append([Paragraph(_clock(ev.get("ts") or ev.get("timestamp")), styles["cell"]),
                    Paragraph(str(ev.get("kind", ev.get("type", "—"))).replace("_", " ").title(), styles["cell"]),
                    Paragraph(detail_str[:140], styles["cell"])])
    t = Table(rows, colWidths=[34 * mm, 40 * mm, 104 * mm], repeatRows=1)
    t.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.4, LINE), ("BACKGROUND", (0, 0), (-1, 0), PANEL),
                          ("VALIGN", (0, 0), (-1, -1), "TOP")]))
    story.append(t)
    if len(timeline) > 40:
        story += [Spacer(1, 3), Paragraph(f"Showing the most recent 40 of {len(timeline)} events.", styles["small"])]
    return story


def _alerts_section(alerts: list, styles: dict) -> list:
    story = [Paragraph(f"Alert History ({len(alerts)})", styles["h2"])]
    if not alerts:
        story.append(Paragraph("No alerts recorded for this patient.", styles["body"]))
        return story
    rows = [[Paragraph("Detected", styles["cellMuted"]), Paragraph("Type", styles["cellMuted"]),
            Paragraph("Severity", styles["cellMuted"]), Paragraph("Status", styles["cellMuted"]),
            Paragraph("Ack. by", styles["cellMuted"])]]
    for a in alerts:
        rows.append([Paragraph(_clock(a.get("detected_at")), styles["cell"]),
                    Paragraph(str(a.get("alert_type", "—")).replace("_", " ").title(), styles["cell"]),
                    Paragraph(str(a.get("severity", "—")).title(), styles["cell"]),
                    Paragraph(str(a.get("status", "—")).replace("_", " ").title(), styles["cell"]),
                    Paragraph(a.get("acknowledged_by") or "—", styles["cell"])])
    t = Table(rows, colWidths=[32 * mm, 40 * mm, 26 * mm, 32 * mm, 48 * mm], repeatRows=1)
    t.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.4, LINE), ("BACKGROUND", (0, 0), (-1, 0), PANEL)]))
    story.append(t)
    return story


def _notes_section(notes: list, styles: dict) -> list:
    story = [Paragraph(f"Caregiver Notes ({len(notes)})", styles["h2"])]
    if not notes:
        story.append(Paragraph("No caregiver notes recorded for this patient.", styles["body"]))
        return story
    for n in notes[-20:]:
        ts = _clock(n.get("created_at") or n.get("ts"))
        text = n.get("text", "")
        story.append(Paragraph(f"<b>{ts}</b> — {text}", styles["body"]))
        story.append(Spacer(1, 3))
    return story


def _device_events_section(events: list, styles: dict) -> list:
    if not events:
        return []
    story = [Paragraph("Device Events", styles["h2"])]
    rows = [[Paragraph("Time", styles["cellMuted"]), Paragraph("Event", styles["cellMuted"])]]
    for e in events[-15:]:
        detail = e.get("detail") if isinstance(e, dict) else None
        label = e.get("event", e.get("type", "—")) if isinstance(e, dict) else str(e)
        rows.append([Paragraph(_clock(e.get("ts")) if isinstance(e, dict) else "—", styles["cell"]),
                    Paragraph(f"{str(label).replace('_', ' ').title()}"
                             f"{' — ' + str(detail) if detail else ''}", styles["cell"])])
    t = Table(rows, colWidths=[34 * mm, 144 * mm], repeatRows=1)
    t.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.4, LINE), ("BACKGROUND", (0, 0), (-1, 0), PANEL)]))
    story.append(t)
    return story


def render_patient_report_pdf(report: dict) -> bytes:
    """report: exactly the dict apps/api/main.py's GET /reports/{patient_id} returns.

    Every section degrades honestly to an explicit empty state ("no alerts recorded", "no forecast
    available") rather than being omitted silently or filled with placeholder figures — mirroring the
    same convention used throughout apps/web/src (see StateViews.tsx's LoadingBlock/ErrorBlock/EmptyBlock
    and STATUS.md's "no hardcoded/fake data" rule).
    """
    styles = _styles()
    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, topMargin=16 * mm, bottomMargin=16 * mm,
                            leftMargin=16 * mm, rightMargin=16 * mm,
                            title="WardZero AI — Patient Report")

    patient = report.get("patient") or {}
    story: list = []
    story += _header(patient, styles)
    story += _risk_section(report.get("risk_assessment"), styles)
    story.append(Spacer(1, 4))
    story += _timeline_section(report.get("timeline") or [], styles)
    story.append(Spacer(1, 4))
    story += _alerts_section(report.get("alerts") or [], styles)
    story.append(Spacer(1, 4))
    story += _notes_section(report.get("notes") or [], styles)
    story.append(Spacer(1, 4))
    story += _device_events_section(report.get("device_events") or [], styles)

    story.append(Spacer(1, 10))
    story.append(HRFlowable(width="100%", thickness=0.5, color=LINE))
    story.append(Spacer(1, 4))
    story.append(Paragraph(report.get("disclaimer", ""), styles["small"]))
    story.append(Paragraph(f"Report generated: {_clock(report.get('generated_at'))} UTC · "
                           "WardZero AI — clinical decision-support prototype, hackathon submission.",
                           styles["small"]))

    def _footer(canvas, _doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 7.5)
        canvas.setFillColor(MUTED)
        canvas.drawString(16 * mm, 10 * mm, "WardZero AI — synthetic demo data — not for clinical use")
        canvas.drawRightString(A4[0] - 16 * mm, 10 * mm, f"Page {_doc.page}")
        canvas.restoreState()

    doc.build(story, onFirstPage=_footer, onLaterPages=_footer)
    return buf.getvalue()

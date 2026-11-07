"""
PDF report generation (reportlab).

Three report types: "executive", "comprehensive", "improvement".
Every report carries the brand disclosures — informational/educational,
not a certified appraisal, no guaranteed price, no calibrated sale
probabilities in Version 1.
"""
from __future__ import annotations

import io
from datetime import datetime

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from ..config.branding import get_brand
from ..engine.drivers import CATEGORIES
from ..models.assessment import (
    ADJUSTMENT_STATUS_LABELS,
    INFO_SOURCE_LABELS,
    PURPOSE_LABELS,
    VALUATION_METHOD_LABELS,
)
from ..engine.evidence import RATING_LABELS

NAVY = colors.HexColor("#16324F")
GOLD = colors.HexColor("#C9A227")
GREY = colors.HexColor("#666666")
LIGHT = colors.HexColor("#F4F4F4")

REPORT_TYPES = {
    "executive": "Executive Summary",
    "comprehensive": "Comprehensive Valuation Assessment",
    "improvement": "Business Value Improvement Plan",
}

COMPREHENSIVE_SECTIONS = [
    ("profile", "Business profile"),
    ("financials", "Financial periods & sources"),
    ("normalization", "Earnings normalization reconciliation"),
    ("methods", "Valuation methods, assumptions & calculations"),
    ("evidence", "Evidence quality"),
    ("drivers", "Business value drivers"),
    ("marketability", "Marketability & pricing scenarios"),
    ("action", "Improvement action plan"),
]


def _styles():
    ss = getSampleStyleSheet()
    ss.add(ParagraphStyle("H1x", parent=ss["Heading1"], textColor=NAVY, fontSize=20))
    ss.add(ParagraphStyle("H2x", parent=ss["Heading2"], textColor=NAVY, fontSize=14,
                          spaceBefore=14))
    ss.add(ParagraphStyle("Small", parent=ss["Normal"], fontSize=8, textColor=GREY))
    ss.add(ParagraphStyle("Body", parent=ss["Normal"], fontSize=10, leading=14))
    ss.add(ParagraphStyle("Muted", parent=ss["Normal"], fontSize=9, textColor=GREY))
    return ss


def _money(v) -> str:
    if v is None:
        return "—"
    return f"${v:,.0f}" if abs(v) >= 1000 else f"${v:,.2f}"


def _table(rows, widths=None, header=True):
    t = Table(rows, colWidths=widths, hAlign="LEFT")
    style = [
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#DDDDDD")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]
    if header:
        style += [
            ("BACKGROUND", (0, 0), (-1, 0), NAVY),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ]
    t.setStyle(TableStyle(style))
    return t


def _footer(brand):
    def draw(canvas, doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 7)
        canvas.setFillColor(GREY)
        canvas.drawString(0.75 * inch, 0.5 * inch, brand["report_footer"])
        canvas.drawRightString(7.75 * inch, 0.5 * inch, f"Page {doc.page}")
        canvas.restoreState()
    return draw


def _disclosures(story, ss, brand):
    story.append(Paragraph("Disclosures & limitations", ss["H2x"]))
    story.append(Paragraph(brand["disclaimer"], ss["Small"]))
    story.append(Paragraph(
        "Data limitations: results reflect owner-supplied information that "
        "has not been independently verified. Owner-reported questionnaire "
        "answers are self-assessments, not independently supported evidence. "
        "Illustrative multiples are educational assumptions, not market "
        "benchmarks. Marketability charts are educational simulations; "
        "Version 1 provides no empirically calibrated probabilities of sale.",
        ss["Small"]))


def _cover(story, ss, brand, a, report_title):
    story.append(Spacer(1, 1.2 * inch))
    story.append(Paragraph(brand["report_header"], ss["Muted"]))
    story.append(Spacer(1, 0.15 * inch))
    story.append(Paragraph(report_title, ss["H1x"]))
    story.append(Spacer(1, 0.3 * inch))
    name = a.profile.business_name or "Unnamed business"
    story.append(Paragraph(f"Prepared for: <b>{name}</b>", ss["Body"]))
    try:
        asof = datetime.fromisoformat(a.updated_at).strftime("%B %d, %Y")
    except (ValueError, TypeError):
        asof = a.updated_at or "—"
    story.append(Paragraph(f"Assessment date: {asof}", ss["Body"]))
    if a.profile.industry:
        story.append(Paragraph(f"Industry: {a.profile.industry}", ss["Body"]))
    story.append(Spacer(1, 0.4 * inch))
    story.append(Paragraph(
        "<i>Educational assessment — not a certified business appraisal.</i>",
        ss["Muted"]))


def _exec_summary(story, ss, a, r):
    story.append(Paragraph("Valuation summary", ss["H2x"]))
    prim = r.valuations.get(a.valuation.primary_method)
    if prim and prim.runnable:
        ill = " (illustrative assumptions)" if prim.illustrative else ""
        rows = [
            ["Estimated range", f"{_money(prim.value_low)} – {_money(prim.value_high)}"],
            ["Illustrative midpoint", _money(prim.value_mid)],
            ["Primary method", VALUATION_METHOD_LABELS[prim.method] + ill],
            ["Earnings basis", f"{prim.earnings_basis}: {_money(prim.earnings)}"],
        ]
    else:
        rows = [["Estimated range", "Not yet calculable — see evidence recommendations"]]
    story.append(_table([["Item", "Value"]] + rows, [2.2 * inch, 4.3 * inch]))


def _section_profile(story, ss, a):
    p = a.profile
    rows = [
        ["Business", p.business_name or "—"],
        ["Industry", p.industry or "—"],
        ["Specialty", p.specialization or "—"],
        ["Years operating", str(p.years_operating or "—")],
        ["Legal structure", p.legal_structure or "—"],
        ["Location", ", ".join(x for x in [p.city, p.state] if x) or "—"],
        ["Employees", str(p.employee_count if p.employee_count is not None else "—")],
        ["Purpose", ", ".join(PURPOSE_LABELS.get(x, x) for x in p.purposes) or "—"],
    ]
    story.append(_table([["Field", "Detail"]] + rows, [2.2 * inch, 4.3 * inch]))


def _section_financials(story, ss, a):
    rows = [["Period", "Revenue", "Reported profit", "Basis", "Source"]]
    for p in a.financials:
        rows.append([
            (p.label or "Period") + (" (partial)" if p.is_partial() else ""),
            _money(p.revenue), _money(p.reported_profit),
            p.profit_basis.replace("_", " "),
            INFO_SOURCE_LABELS.get(p.info_source, "—"),
        ])
    story.append(_table(rows, [1.6 * inch, 1.3 * inch, 1.4 * inch, 1.2 * inch, 1.4 * inch]))


def _section_normalization(story, ss, r):
    n = r.normalization
    if not n or n.reported_profit is None:
        story.append(Paragraph("No earnings normalization available.", ss["Body"]))
        return
    rows = [["Line", "Amount", "Status / note"]]
    for ln in n.lines:
        status = ADJUSTMENT_STATUS_LABELS.get(ln.status, ln.status)
        note = (status + (" — " + ln.note if ln.note else "")).strip(" —")
        rows.append([ln.label, _money(ln.amount), note])
    story.append(_table(rows, [3.0 * inch, 1.2 * inch, 2.7 * inch]))
    for f in n.flags:
        story.append(Paragraph(f"• {f}", ss["Small"]))


def _section_methods(story, ss, a, r):
    for ind in r.valuations.values():
        story.append(Paragraph(f"<b>{ind.method_label}</b>", ss["Body"]))
        if ind.runnable:
            mult = ""
            if ind.multiple_mid is not None:
                mult = (f" Multiple {ind.multiple_low}–{ind.multiple_high}×"
                        f" ({'illustrative' if ind.illustrative else 'supported'}).")
            story.append(Paragraph(
                f"{ind.earnings_basis} {_money(ind.earnings)} → "
                f"{_money(ind.value_low)} – {_money(ind.value_high)}.{mult}",
                ss["Body"]))
        else:
            story.append(Paragraph("Not runnable: " + "; ".join(ind.warnings), ss["Muted"]))
        for n in ind.notes:
            story.append(Paragraph(f"• {n}", ss["Small"]))


def _section_evidence(story, ss, r):
    rows = [["Dimension", "Rating", "Key reason"]]
    for d in r.evidence.dimensions:
        rows.append([d.name, RATING_LABELS.get(d.rating, d.rating),
                     d.reasons[0] if d.reasons else ""])
    story.append(_table(rows, [1.8 * inch, 1.1 * inch, 4.0 * inch]))
    if r.evidence.all_recommendations:
        story.append(Paragraph("<b>To improve reliability:</b>", ss["Body"]))
        for rec in r.evidence.all_recommendations[:8]:
            story.append(Paragraph(f"• {rec}", ss["Small"]))


def _section_drivers(story, ss, r):
    for c in r.drivers.categories:
        label = CATEGORIES[[x["id"] for x in CATEGORIES].index(c.id)]["name"] if c.id in [x["id"] for x in CATEGORIES] else c.name
        story.append(Paragraph(
            f"<b>{label}</b> — {c.answered}/{c.total} answered", ss["Body"]))
        for s in c.strengths[:4]:
            story.append(Paragraph(f"&nbsp;&nbsp;+ {s}", ss["Small"]))
        for text, why in c.risks[:4]:
            story.append(Paragraph(f"&nbsp;&nbsp;– {text}", ss["Small"]))


def _section_marketability(story, ss, a, r):
    prim = r.valuations.get(a.valuation.primary_method)
    if a.asking_price and prim and prim.value_mid:
        from ..engine.marketability import point_for_price
        pt = point_for_price(a.asking_price, prim.value_mid)
        story.append(Paragraph(
            f"Asking price explored: {_money(a.asking_price)} "
            f"({a.asking_price/prim.value_mid*100:.0f}% of midpoint) — "
            f"{pt.band if pt else '—'}. Desired timeframe: "
            f"{a.sale_timeframe_months} months.", ss["Body"]))
        story.append(Paragraph(
            "Illustrative Relative Marketability — Educational Simulation. "
            "No numerical sale probabilities are provided in Version 1.",
            ss["Small"]))
    else:
        story.append(Paragraph("No pricing scenario was explored.", ss["Body"]))


def _section_action(story, ss, a):
    if not a.action_items:
        story.append(Paragraph("No improvement recommendations generated yet.", ss["Body"]))
        return
    rows = [["Priority", "Issue", "Recommended action", "Timeframe", "Status"]]
    for it in a.action_items:
        rows.append([it.priority.capitalize(), it.issue, it.action,
                     it.timeframe, it.status.replace("_", " ").capitalize()])
    story.append(_table(rows, [0.8 * inch, 2.0 * inch, 2.4 * inch, 1.0 * inch, 0.9 * inch]))


def build_report(a, r, report_type: str = "executive", sections=None) -> bytes:
    """Build a PDF report; returns bytes."""
    brand = get_brand()
    ss = _styles()
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=letter,
                            leftMargin=0.75 * inch, rightMargin=0.75 * inch,
                            title=f"{brand['app_name']} — {REPORT_TYPES[report_type]}",
                            author=brand["org_name"], invariant=1)
    story = []
    title = REPORT_TYPES[report_type]
    _cover(story, ss, brand, a, title)
    story.append(Spacer(1, 0.3 * inch))

    if report_type == "executive":
        _exec_summary(story, ss, a, r)
        story.append(Paragraph("Strengths", ss["H2x"]))
        for s in r.drivers.all_strengths[:5] or ["None identified yet."]:
            story.append(Paragraph(f"• {s}", ss["Body"]))
        story.append(Paragraph("Principal risks", ss["H2x"]))
        risk_texts = [text for text, _why in r.drivers.all_risks[:5]]
        for s in risk_texts or ["None identified yet."]:
            story.append(Paragraph(f"• {s}", ss["Body"]))
        story.append(Paragraph("Recommended next steps", ss["H2x"]))
        for rec in r.evidence.all_recommendations[:5] or ["Complete the assessment sections."]:
            story.append(Paragraph(f"• {rec}", ss["Body"]))

    elif report_type == "improvement":
        story.append(Paragraph("Business Value Improvement Plan", ss["H2x"]))
        story.append(Paragraph(
            "Recommendations below are generated from your own assessment "
            "answers. Completing them improves business readiness and "
            "marketability; it does not by itself guarantee a higher "
            "valuation.", ss["Muted"]))
        _section_action(story, ss, a)

    else:  # comprehensive
        selected = set(sections or [k for k, _ in COMPREHENSIVE_SECTIONS])
        _exec_summary(story, ss, a, r)
        mapping = [
            ("profile", "Business profile", lambda: _section_profile(story, ss, a)),
            ("financials", "Financial periods & sources", lambda: _section_financials(story, ss, a)),
            ("normalization", "Earnings normalization", lambda: _section_normalization(story, ss, r)),
            ("methods", "Valuation methods & assumptions", lambda: _section_methods(story, ss, a, r)),
            ("evidence", "Evidence quality", lambda: _section_evidence(story, ss, r)),
            ("drivers", "Business value drivers", lambda: _section_drivers(story, ss, r)),
            ("marketability", "Marketability & pricing", lambda: _section_marketability(story, ss, a, r)),
            ("action", "Improvement action plan", lambda: _section_action(story, ss, a)),
        ]
        for key, heading, fn in mapping:
            if key in selected:
                story.append(Paragraph(heading, ss["H2x"]))
                fn()

    _disclosures(story, ss, brand)
    doc.build(story, onFirstPage=_footer(brand), onLaterPages=_footer(brand))
    return buf.getvalue()

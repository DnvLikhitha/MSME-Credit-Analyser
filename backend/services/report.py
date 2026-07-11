"""
PDF Report Generation Service — Phase 5
=========================================
Generates a professional, multi-page PDF credit report for a completed
document assessment using ReportLab.

Report Contents:
  Page 1 — Cover / Summary (Score gauge, risk band, narrative)
  Page 2 — Extracted Financial Metrics table
  Page 3 — Loan Scheme Recommendations
"""
from __future__ import annotations

import io
import logging
import os
from datetime import datetime
from typing import Optional
from uuid import UUID

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm, mm
from reportlab.platypus import (
    HRFlowable,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)
from sqlalchemy.orm import Session

from backend.config import settings
from backend.models.document import Document
from backend.models.extracted_metrics import ExtractedMetrics
from backend.models.loan_recommendation import LoanRecommendation
from backend.models.report import Report
from backend.models.risk_score import RiskScore

logger = logging.getLogger(__name__)

# ── Colour Palette ─────────────────────────────────────────────────────────────
BRAND_NAVY   = colors.HexColor("#0F2D5A")
BRAND_BLUE   = colors.HexColor("#1A73E8")
BAND_LOW     = colors.HexColor("#1E8449")   # green
BAND_MEDIUM  = colors.HexColor("#D4AC0D")   # amber
BAND_HIGH    = colors.HexColor("#C0392B")   # red
ROW_ALT      = colors.HexColor("#F4F6F9")
TABLE_HEADER = colors.HexColor("#1A73E8")
PAGE_BG      = colors.white


def _band_color(band: str) -> colors.Color:
    return {"LOW": BAND_LOW, "MEDIUM": BAND_MEDIUM, "HIGH": BAND_HIGH}.get(band, BRAND_BLUE)


def _fmt_inr(value: Optional[float]) -> str:
    if value is None:
        return "—"
    if value >= 10_000_000:
        return f"₹{value/10_000_000:.2f} Cr"
    if value >= 100_000:
        return f"₹{value/100_000:.2f} L"
    return f"₹{value:,.0f}"


def _fmt_pct(value: Optional[float]) -> str:
    return "—" if value is None else f"{value:.1f}%"


def _fmt_ratio(value: Optional[float]) -> str:
    return "—" if value is None else f"{value:.2f}x"


# ── Styles ─────────────────────────────────────────────────────────────────────

def _build_styles() -> dict:
    base = getSampleStyleSheet()
    s = {}

    s["report_title"] = ParagraphStyle(
        "report_title",
        fontName="Helvetica-Bold",
        fontSize=22,
        textColor=colors.white,
        alignment=TA_CENTER,
        spaceAfter=4,
    )
    s["report_subtitle"] = ParagraphStyle(
        "report_subtitle",
        fontName="Helvetica",
        fontSize=11,
        textColor=colors.HexColor("#BDD7F5"),
        alignment=TA_CENTER,
        spaceAfter=2,
    )
    s["section_heading"] = ParagraphStyle(
        "section_heading",
        fontName="Helvetica-Bold",
        fontSize=13,
        textColor=BRAND_NAVY,
        spaceBefore=14,
        spaceAfter=6,
        borderPad=4,
    )
    s["body"] = ParagraphStyle(
        "body",
        fontName="Helvetica",
        fontSize=9.5,
        textColor=colors.HexColor("#2C3E50"),
        leading=14,
        spaceAfter=4,
    )
    s["label"] = ParagraphStyle(
        "label",
        fontName="Helvetica-Bold",
        fontSize=9,
        textColor=colors.HexColor("#7F8C8D"),
    )
    s["score_big"] = ParagraphStyle(
        "score_big",
        fontName="Helvetica-Bold",
        fontSize=52,
        textColor=BRAND_NAVY,
        alignment=TA_CENTER,
    )
    s["score_sub"] = ParagraphStyle(
        "score_sub",
        fontName="Helvetica",
        fontSize=11,
        textColor=colors.HexColor("#566573"),
        alignment=TA_CENTER,
    )
    s["band_label"] = ParagraphStyle(
        "band_label",
        fontName="Helvetica-Bold",
        fontSize=18,
        alignment=TA_CENTER,
    )
    s["footer"] = ParagraphStyle(
        "footer",
        fontName="Helvetica",
        fontSize=7.5,
        textColor=colors.HexColor("#95A5A6"),
        alignment=TA_CENTER,
    )
    s["rec_rank"] = ParagraphStyle(
        "rec_rank",
        fontName="Helvetica-Bold",
        fontSize=11,
        textColor=BRAND_NAVY,
        spaceBefore=8,
    )
    s["rec_body"] = ParagraphStyle(
        "rec_body",
        fontName="Helvetica",
        fontSize=9,
        textColor=colors.HexColor("#34495E"),
        leading=13,
    )
    return s


# ── Header / Footer Callbacks ──────────────────────────────────────────────────

def _header(canvas, doc, doc_original_filename: str):
    canvas.saveState()
    # Navy bar at top
    canvas.setFillColor(BRAND_NAVY)
    canvas.rect(0, A4[1] - 28 * mm, A4[0], 28 * mm, fill=1, stroke=0)
    canvas.setFont("Helvetica-Bold", 11)
    canvas.setFillColor(colors.white)
    canvas.drawString(20 * mm, A4[1] - 16 * mm, "MSME Credit Intelligence Report")
    canvas.setFont("Helvetica", 9)
    canvas.setFillColor(colors.HexColor("#BDD7F5"))
    canvas.drawRightString(A4[0] - 20 * mm, A4[1] - 16 * mm, doc_original_filename)
    canvas.restoreState()


def _footer(canvas, doc):
    canvas.saveState()
    canvas.setFont("Helvetica", 7.5)
    canvas.setFillColor(colors.HexColor("#95A5A6"))
    now = datetime.utcnow().strftime("%d %b %Y")
    canvas.drawString(20 * mm, 10 * mm, f"Generated: {now}  |  MSME Credit Intelligence Agent  |  Confidential")
    canvas.drawRightString(A4[0] - 20 * mm, 10 * mm, f"Page {doc.page}")
    # thin line above footer
    canvas.setStrokeColor(colors.HexColor("#D5D8DC"))
    canvas.line(20 * mm, 14 * mm, A4[0] - 20 * mm, 14 * mm)
    canvas.restoreState()


# ── Section Builders ───────────────────────────────────────────────────────────

def _section_divider(styles: dict) -> list:
    return [
        Spacer(1, 4),
        HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#D5D8DC")),
        Spacer(1, 6),
    ]


def _build_cover(doc_obj: Document, risk_score: RiskScore, styles: dict) -> list:
    elems = []

    # ── Hero Score Box ─────────────────────────────────────────────────────────
    score = risk_score.overall_score
    band  = risk_score.risk_band
    bc    = _band_color(band)

    score_data = [
        [Paragraph(f"{score:.0f}", styles["score_big"])],
        [Paragraph("out of 100", styles["score_sub"])],
        [Paragraph(f"RISK BAND: {band}", ParagraphStyle(
            "bl", fontName="Helvetica-Bold", fontSize=16, textColor=bc, alignment=TA_CENTER
        ))],
    ]
    score_table = Table(score_data, colWidths=[16 * cm])
    score_table.setStyle(TableStyle([
        ("BOX",         (0, 0), (-1, -1), 1.5, colors.HexColor("#D5D8DC")),
        ("BACKGROUND",  (0, 0), (-1, -1), colors.HexColor("#F8F9FA")),
        ("TOPPADDING",  (0, 0), (-1, -1), 14),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 14),
        ("ALIGN",       (0, 0), (-1, -1), "CENTER"),
        ("ROWBACKGROUNDS", (0, 0), (-1, -1), [colors.HexColor("#F8F9FA")]),
    ]))
    elems.append(Spacer(1, 10))
    elems.append(score_table)

    # ── Factor Breakdown Table ─────────────────────────────────────────────────
    elems.append(Spacer(1, 14))
    elems.append(Paragraph("Factor Breakdown", styles["section_heading"]))

    if risk_score.factor_breakdown:
        header = ["Factor", "Score", "Max", "%", "Key Insights"]
        rows   = [header]
        for f in risk_score.factor_breakdown:
            rows.append([
                f.get("factor", "—"),
                str(f.get("score", "—")),
                str(f.get("max", "—")),
                f"{f.get('pct', 0):.0f}%",
                Paragraph(f.get("explanation", "—"), ParagraphStyle(
                    "small_body", fontName="Helvetica", fontSize=8, leading=11
                )),
            ])

        breakdown_table = Table(rows, colWidths=[4.5*cm, 1.4*cm, 1.2*cm, 1.2*cm, 8.2*cm])
        breakdown_table.setStyle(TableStyle([
            ("BACKGROUND",    (0, 0), (-1, 0), TABLE_HEADER),
            ("TEXTCOLOR",     (0, 0), (-1, 0), colors.white),
            ("FONTNAME",      (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE",      (0, 0), (-1, 0), 9),
            ("ALIGN",         (1, 0), (3, -1), "CENTER"),
            ("FONTNAME",      (0, 1), (-1, -1), "Helvetica"),
            ("FONTSIZE",      (0, 1), (-1, -1), 8.5),
            ("ROWBACKGROUNDS",(0, 1), (-1, -1), [colors.white, ROW_ALT]),
            ("GRID",          (0, 0), (-1, -1), 0.4, colors.HexColor("#D5D8DC")),
            ("TOPPADDING",    (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("LEFTPADDING",   (0, 0), (-1, -1), 6),
        ]))
        elems.append(breakdown_table)

    # ── Narrative Summary ──────────────────────────────────────────────────────
    if risk_score.narrative_summary:
        elems.append(Spacer(1, 14))
        elems.append(Paragraph("Credit Narrative", styles["section_heading"]))
        elems.append(Paragraph(risk_score.narrative_summary, styles["body"]))

    return elems


def _build_metrics_page(metrics: ExtractedMetrics, styles: dict) -> list:
    elems = [PageBreak()]
    elems.append(Paragraph("Extracted Financial Metrics", styles["section_heading"]))
    elems += _section_divider(styles)

    rows = [
        ["Metric", "Value", "Category"],
        ["Annual Revenue",        _fmt_inr(metrics.annual_revenue),        "Revenue"],
        ["Revenue Growth (YoY)",  _fmt_pct(metrics.revenue_growth_yoy),    "Revenue"],
        ["Net Profit Margin",     _fmt_pct(metrics.net_profit_margin),     "Revenue"],
        ["Gross Profit Margin",   _fmt_pct(metrics.gross_profit_margin),   "Revenue"],
        ["Total Liabilities",     _fmt_inr(metrics.total_liabilities),     "Debt"],
        ["Total Assets",          _fmt_inr(metrics.total_assets),          "Debt"],
        ["Debt-to-Income Ratio",  _fmt_ratio(metrics.debt_to_income_ratio),"Debt"],
        ["Current Ratio",         _fmt_ratio(metrics.current_ratio),       "Liquidity"],
        ["Quick Ratio",           _fmt_ratio(metrics.quick_ratio),         "Liquidity"],
        ["GST Filing Consistency",_fmt_pct((metrics.gst_filing_consistency or 0) * 100), "GST"],
        ["Total GST Paid",        _fmt_inr(metrics.total_gst_paid),        "GST"],
        ["GST Turnover",          _fmt_inr(metrics.gst_turnover),          "GST"],
        ["Avg Monthly Balance",   _fmt_inr(metrics.avg_monthly_balance),   "Banking"],
        ["Min Monthly Balance",   _fmt_inr(metrics.min_monthly_balance),   "Banking"],
        ["Balance Trend",         _fmt_ratio(metrics.balance_trend),       "Banking"],
        ["Monthly Transactions",  str(int(metrics.num_monthly_transactions)) if metrics.num_monthly_transactions is not None else "—", "Banking"],
        ["Cheque Bounce Count",   str(int(metrics.cheque_bounce_count)) if metrics.cheque_bounce_count is not None else "—", "Banking"],
    ]

    t = Table(rows, colWidths=[6.5*cm, 4*cm, 3.5*cm])
    t.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, 0), TABLE_HEADER),
        ("TEXTCOLOR",     (0, 0), (-1, 0), colors.white),
        ("FONTNAME",      (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE",      (0, 0), (-1, 0), 9),
        ("FONTNAME",      (0, 1), (-1, -1), "Helvetica"),
        ("FONTSIZE",      (0, 1), (-1, -1), 9),
        ("ALIGN",         (1, 0), (2, -1), "CENTER"),
        ("ROWBACKGROUNDS",(0, 1), (-1, -1), [colors.white, ROW_ALT]),
        ("GRID",          (0, 0), (-1, -1), 0.4, colors.HexColor("#D5D8DC")),
        ("TOPPADDING",    (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING",   (0, 0), (-1, -1), 6),
    ]))
    elems.append(t)
    return elems


def _build_recommendations_page(recs: list[LoanRecommendation], styles: dict) -> list:
    elems = [PageBreak()]
    elems.append(Paragraph("Loan Scheme Recommendations", styles["section_heading"]))
    elems += _section_divider(styles)

    if not recs:
        elems.append(Paragraph("No recommendations generated.", styles["body"]))
        return elems

    for rec in recs:
        rank_style = ParagraphStyle(
            "rr", fontName="Helvetica-Bold", fontSize=11,
            textColor=BRAND_NAVY, spaceBefore=10,
        )
        elems.append(Paragraph(f"#{rec.rank}  {rec.scheme_name}", rank_style))

        meta_rows = []
        if rec.issuing_body:
            meta_rows.append(["Issuing Body:", rec.issuing_body])
        if rec.eligibility_score is not None:
            meta_rows.append(["Eligibility Score:", f"{rec.eligibility_score * 100:.0f} / 100"])
        if rec.scheme_details:
            d = rec.scheme_details
            if d.get("max_loan_amount_inr"):
                meta_rows.append(["Max Loan Amount:", _fmt_inr(d["max_loan_amount_inr"])])
            if d.get("interest_rate_range"):
                meta_rows.append(["Interest Rate:", d["interest_rate_range"]])
            if d.get("tenure"):
                meta_rows.append(["Tenure:", d["tenure"]])
            if d.get("collateral_required") is not None:
                meta_rows.append(["Collateral Required:", "Yes" if d["collateral_required"] else "No"])

        if meta_rows:
            meta_table = Table(meta_rows, colWidths=[4*cm, 10*cm])
            meta_table.setStyle(TableStyle([
                ("FONTNAME",  (0, 0), (0, -1), "Helvetica-Bold"),
                ("FONTNAME",  (1, 0), (1, -1), "Helvetica"),
                ("FONTSIZE",  (0, 0), (-1, -1), 9),
                ("TEXTCOLOR", (0, 0), (0, -1), colors.HexColor("#7F8C8D")),
                ("TOPPADDING",    (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ]))
            elems.append(meta_table)

        if rec.reasoning:
            elems.append(Spacer(1, 4))
            elems.append(Paragraph(
                f"<i>{rec.reasoning}</i>",
                ParagraphStyle("italic_body", fontName="Helvetica-Oblique", fontSize=9,
                               textColor=colors.HexColor("#34495E"), leading=13)
            ))

        elems.append(Spacer(1, 4))
        elems.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#D5D8DC")))

    return elems


# ── Main Generation Function ───────────────────────────────────────────────────

def generate_pdf_report(
    doc_obj: Document,
    metrics: ExtractedMetrics,
    risk_score: RiskScore,
    recs: list[LoanRecommendation],
) -> bytes:
    """
    Build the full PDF in-memory and return raw bytes.
    """
    buffer = io.BytesIO()
    styles = _build_styles()
    original_filename = doc_obj.original_filename

    pdf = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=20 * mm,
        rightMargin=20 * mm,
        topMargin=35 * mm,
        bottomMargin=22 * mm,
    )

    story = []
    story += _build_cover(doc_obj, risk_score, styles)
    story += _build_metrics_page(metrics, styles)
    story += _build_recommendations_page(recs, styles)

    def make_header(canvas, doc):
        _header(canvas, doc, original_filename)
        _footer(canvas, doc)

    pdf.build(story, onFirstPage=make_header, onLaterPages=make_header)
    return buffer.getvalue()


# ── DB Helper ─────────────────────────────────────────────────────────────────

def generate_and_save_report(
    db: Session,
    doc_obj: Document,
    metrics: ExtractedMetrics,
    risk_score: RiskScore,
    recs: list[LoanRecommendation],
) -> Report:
    """
    Generate the PDF, save to disk, and persist a Report row.
    Returns the saved ORM object.
    """
    os.makedirs(settings.REPORTS_DIR, exist_ok=True)

    # Upsert — if report already exists, delete and regenerate
    existing = db.query(Report).filter(Report.document_id == doc_obj.id).first()
    if existing:
        db.delete(existing)
        db.flush()

    # Generate PDF bytes
    logger.info(f"Generating PDF report for document {doc_obj.id}")
    pdf_bytes = generate_pdf_report(doc_obj, metrics, risk_score, recs)

    # Save to disk
    filename = f"credit_report_{doc_obj.id}.pdf"
    file_path = os.path.join(settings.REPORTS_DIR, filename)
    with open(file_path, "wb") as f:
        f.write(pdf_bytes)

    # Persist Report row
    report = Report(
        document_id=doc_obj.id,
        file_path=file_path,
        status="COMPLETE",
    )
    db.add(report)
    db.commit()
    db.refresh(report)

    logger.info(f"PDF report saved to {file_path} ({len(pdf_bytes):,} bytes)")
    return report

"""
Tests for Phase 5 — PDF Credit Report Generation
"""
import os
import uuid
import pytest

from backend.models.document import Document
from backend.models.extracted_metrics import ExtractedMetrics
from backend.models.loan_recommendation import LoanRecommendation
from backend.models.risk_score import RiskScore
from backend.services.report import generate_pdf_report


def _make_doc() -> Document:
    d = Document()
    d.id = uuid.uuid4()
    d.user_id = uuid.uuid4()
    d.original_filename = "bank_statement.pdf"
    d.filename = "uuid_file.pdf"
    d.file_path = "/fake/path.pdf"
    d.status = "COMPLETE"
    return d


def _make_metrics() -> ExtractedMetrics:
    m = ExtractedMetrics()
    m.annual_revenue = 2_500_000
    m.net_profit_margin = 12.5
    m.revenue_growth_yoy = 18.0
    m.total_liabilities = 500_000
    m.total_assets = 1_500_000
    m.debt_to_income_ratio = 0.4
    m.current_ratio = 1.8
    m.quick_ratio = 1.2
    m.gst_filing_consistency = 0.9
    m.total_gst_paid = 85_000
    m.avg_monthly_balance = 150_000
    m.cheque_bounce_count = 0
    m.balance_trend = 0.3
    return m


def _make_risk_score(band="LOW", score=74.0) -> RiskScore:
    rs = RiskScore()
    rs.overall_score = score
    rs.risk_band = band
    rs.narrative_summary = "A solid business eligible for mainstream MSME credit."
    rs.factor_breakdown = [
        {"factor": "Revenue & Profitability", "score": 17, "max": 25, "pct": 68, "explanation": "Revenue >= 10L (+7)"},
        {"factor": "Debt & Liabilities",      "score": 13, "max": 20, "pct": 65, "explanation": "DTI < 0.6 (+8)"},
    ]
    return rs


def _make_rec(rank=1, scheme="MUDRA Kishore") -> LoanRecommendation:
    r = LoanRecommendation()
    r.rank = rank
    r.scheme_name = scheme
    r.scheme_type = "MUDRA"
    r.issuing_body = "Ministry of MSME"
    r.eligibility_score = 0.9
    r.reasoning = "Good fit based on revenue and risk band."
    r.scheme_details = {"max_loan_amount_inr": 500_000, "interest_rate_range": "11-14%", "collateral_required": False}
    return r


class TestPDFGeneration:
    def test_generates_bytes(self):
        """PDF output should be non-empty bytes."""
        pdf = generate_pdf_report(_make_doc(), _make_metrics(), _make_risk_score(), [])
        assert isinstance(pdf, bytes)
        assert len(pdf) > 1000

    def test_pdf_starts_with_pdf_header(self):
        """Valid PDFs always begin with the %%PDF magic bytes."""
        pdf = generate_pdf_report(_make_doc(), _make_metrics(), _make_risk_score(), [])
        assert pdf[:4] == b"%PDF"

    def test_generates_with_all_null_metrics(self):
        """Should not crash when all metrics are None."""
        m = ExtractedMetrics()
        pdf = generate_pdf_report(_make_doc(), m, _make_risk_score(), [])
        assert len(pdf) > 500

    def test_generates_with_recommendations(self):
        """PDF with recommendations should be larger than one without."""
        recs = [_make_rec(1, "MUDRA"), _make_rec(2, "CGTMSE"), _make_rec(3, "PMEGP")]
        pdf_with    = generate_pdf_report(_make_doc(), _make_metrics(), _make_risk_score(), recs)
        pdf_without = generate_pdf_report(_make_doc(), _make_metrics(), _make_risk_score(), [])
        assert len(pdf_with) > len(pdf_without)

    def test_generates_for_each_risk_band(self):
        """Should succeed for all three risk bands."""
        for band, score in [("LOW", 75), ("MEDIUM", 55), ("HIGH", 30)]:
            pdf = generate_pdf_report(_make_doc(), _make_metrics(), _make_risk_score(band, score), [])
            assert len(pdf) > 1000, f"Failed for band={band}"

    def test_long_filename_does_not_crash(self):
        """Very long document names should not break layout."""
        doc = _make_doc()
        doc.original_filename = "a_very_long_financial_statement_document_name_from_axis_bank_q4_2025.pdf"
        pdf = generate_pdf_report(doc, _make_metrics(), _make_risk_score(), [])
        assert len(pdf) > 1000

    def test_full_pipeline_output_size(self):
        """A full report with metrics + breakdown + 3 recs should be at least 5KB."""
        recs = [_make_rec(i, f"Scheme {i}") for i in range(1, 4)]
        pdf = generate_pdf_report(_make_doc(), _make_metrics(), _make_risk_score(), recs)
        assert len(pdf) >= 5_000

    def test_cleanup_temp_file(self, tmp_path):
        """Verify saving to disk works correctly."""
        doc = _make_doc()
        pdf = generate_pdf_report(doc, _make_metrics(), _make_risk_score(), [])
        out = tmp_path / "test_report.pdf"
        out.write_bytes(pdf)
        assert out.exists()
        assert out.stat().st_size > 1000

"""
Tests for Phase 3 — Credit Risk Scoring Engine
"""
import pytest
from backend.models.extracted_metrics import ExtractedMetrics
from backend.services.scoring import (
    compute_risk_score,
    _score_revenue,
    _score_debt,
    _score_liquidity,
    _score_gst,
    _score_banking,
    RISK_BAND_LOW,
    RISK_BAND_MEDIUM,
)


def make_metrics(**kwargs) -> ExtractedMetrics:
    """Helper: create an ExtractedMetrics object with all fields defaulting to None."""
    m = ExtractedMetrics()
    for k, v in kwargs.items():
        setattr(m, k, v)
    return m


# ── Revenue scoring ────────────────────────────────────────────────────────────

class TestRevenueScoring:
    def test_high_revenue_scores_max(self):
        m = make_metrics(annual_revenue=10_000_000, net_profit_margin=20, revenue_growth_yoy=25)
        r = _score_revenue(m)
        assert r.score == r.max_score == 25.0

    def test_medium_revenue(self):
        m = make_metrics(annual_revenue=2_000_000, net_profit_margin=10, revenue_growth_yoy=8)
        r = _score_revenue(m)
        assert r.score == 7 + 7 + 3  # 17

    def test_null_fields_score_zero(self):
        m = make_metrics()
        r = _score_revenue(m)
        assert r.score == 0

    def test_negative_growth_scores_zero(self):
        m = make_metrics(revenue_growth_yoy=-5)
        r = _score_revenue(m)
        assert 0 <= r.score < r.max_score


# ── Debt scoring ───────────────────────────────────────────────────────────────

class TestDebtScoring:
    def test_low_dti_high_coverage_scores_max(self):
        m = make_metrics(debt_to_income_ratio=0.1, total_assets=1_000_000, total_liabilities=200_000)
        r = _score_debt(m)
        assert r.score == r.max_score == 20.0

    def test_high_dti_scores_zero(self):
        m = make_metrics(debt_to_income_ratio=1.5, total_assets=100_000, total_liabilities=200_000)
        r = _score_debt(m)
        # DTI >= 1 = 0, assets < liabilities = 0
        assert r.score == 0

    def test_no_liabilities_full_coverage(self):
        m = make_metrics(debt_to_income_ratio=0.2, total_assets=500_000, total_liabilities=0)
        r = _score_debt(m)
        assert r.score == 12 + 8  # full DTI + full coverage


# ── Liquidity scoring ──────────────────────────────────────────────────────────

class TestLiquidityScoring:
    def test_excellent_liquidity(self):
        m = make_metrics(current_ratio=2.5, quick_ratio=2.0)
        r = _score_liquidity(m)
        assert r.score == r.max_score == 20.0

    def test_illiquid_scores_zero(self):
        m = make_metrics(current_ratio=0.5, quick_ratio=0.3)
        r = _score_liquidity(m)
        assert r.score == 0


# ── GST scoring ────────────────────────────────────────────────────────────────

class TestGSTScoring:
    def test_perfect_gst(self):
        m = make_metrics(gst_filing_consistency=1.0, total_gst_paid=500_000)
        r = _score_gst(m)
        assert r.score == r.max_score == 20.0

    def test_poor_gst(self):
        m = make_metrics(gst_filing_consistency=0.3, total_gst_paid=0)
        r = _score_gst(m)
        assert r.score == 0


# ── Banking scoring ────────────────────────────────────────────────────────────

class TestBankingScoring:
    def test_perfect_banking(self):
        m = make_metrics(avg_monthly_balance=200_000, balance_trend=0.8, cheque_bounce_count=0)
        r = _score_banking(m)
        assert r.score == r.max_score == 15.0

    def test_high_bounce_count_penalized(self):
        m = make_metrics(avg_monthly_balance=200_000, balance_trend=0.8, cheque_bounce_count=5)
        r = _score_banking(m)
        assert r.score == 5 + 5  # no bounce bonus lost


# ── Overall scoring & risk bands ───────────────────────────────────────────────

class TestOverallScoring:
    def test_perfect_score_is_low_risk(self):
        m = make_metrics(
            annual_revenue=10_000_000, net_profit_margin=20, revenue_growth_yoy=25,
            debt_to_income_ratio=0.1, total_assets=2_000_000, total_liabilities=200_000,
            current_ratio=3.0, quick_ratio=2.5,
            gst_filing_consistency=1.0, total_gst_paid=500_000,
            avg_monthly_balance=500_000, balance_trend=0.9, cheque_bounce_count=0,
        )
        result = compute_risk_score(m)
        assert result["overall_score"] == 100.0
        assert result["risk_band"] == "LOW"

    def test_zero_score_is_high_risk(self):
        m = make_metrics()  # all None
        result = compute_risk_score(m)
        assert result["overall_score"] == 0.0
        assert result["risk_band"] == "HIGH"

    def test_medium_risk_band_boundaries(self):
        # Craft a score that lands in MEDIUM range (45-69)
        m = make_metrics(
            # Revenue (17pts): 7+7+3 | Debt (13pts): 8+5 | Liquidity (13pts): 8+5
            # = 43pts, need a few more to get to 45+
            annual_revenue=2_000_000, net_profit_margin=10, revenue_growth_yoy=8,
            debt_to_income_ratio=0.5, total_assets=500_000, total_liabilities=300_000,
            current_ratio=1.6, quick_ratio=1.1,
            gst_filing_consistency=0.75,  # adds 8 pts → total = 51
        )
        result = compute_risk_score(m)
        assert RISK_BAND_MEDIUM <= result["overall_score"] < RISK_BAND_LOW
        assert result["risk_band"] == "MEDIUM"

    def test_narrative_is_non_empty(self):
        m = make_metrics(annual_revenue=5_000_000)
        result = compute_risk_score(m)
        assert isinstance(result["narrative_summary"], str)
        assert len(result["narrative_summary"]) > 20

    def test_factor_breakdown_structure(self):
        m = make_metrics(annual_revenue=1_000_000)
        result = compute_risk_score(m)
        breakdown = result["factor_breakdown"]
        assert len(breakdown) == 5
        for item in breakdown:
            assert "factor" in item
            assert "score" in item
            assert "max" in item
            assert "pct" in item
            assert "explanation" in item

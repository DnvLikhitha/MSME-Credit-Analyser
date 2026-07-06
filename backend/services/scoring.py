"""
Credit Risk Scoring Engine — Phase 3
=====================================
Computes a weighted 0-100 creditworthiness score from extracted financial metrics.

Scoring Factors (total = 100 points):
  Revenue & Profitability  — 25 pts
  Debt & Liabilities       — 20 pts
  Liquidity                — 20 pts
  GST Compliance           — 20 pts
  Banking Behaviour        — 15 pts

Risk Bands:
  LOW    >= 70
  MEDIUM 45–69
  HIGH   <  45
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

from sqlalchemy.orm import Session

from backend.models.extracted_metrics import ExtractedMetrics
from backend.models.risk_score import RiskScore

logger = logging.getLogger(__name__)


# ── Thresholds ─────────────────────────────────────────────────────────────────
RISK_BAND_LOW = 70.0
RISK_BAND_MEDIUM = 45.0


@dataclass
class FactorResult:
    factor: str
    score: float
    max_score: float
    explanation: str


# ── Individual Factor Scorers ──────────────────────────────────────────────────

def _score_revenue(m: ExtractedMetrics) -> FactorResult:
    """
    Revenue & Profitability — 25 points
      annual_revenue        (10 pts): > 50L = 10, > 10L = 7, > 1L = 4, else 0
      net_profit_margin     (10 pts): > 15% = 10, > 8% = 7, > 0% = 4, else 0
      revenue_growth_yoy    ( 5 pts): > 20% = 5, > 5% = 3, > 0% = 1, else 0
    """
    MAX = 25.0
    score = 0.0
    notes = []

    # Annual Revenue (INR)
    rev = m.annual_revenue
    if rev is not None:
        if rev >= 5_000_000:       # >= 50 Lakh
            score += 10; notes.append("Revenue >= 50L (+10)")
        elif rev >= 1_000_000:     # >= 10 Lakh
            score += 7;  notes.append("Revenue >= 10L (+7)")
        elif rev >= 100_000:       # >= 1 Lakh
            score += 4;  notes.append("Revenue >= 1L (+4)")
        else:
            notes.append("Revenue < 1L (+0)")
    else:
        notes.append("Revenue data unavailable (+0)")

    # Net Profit Margin
    npm = m.net_profit_margin
    if npm is not None:
        if npm >= 15:
            score += 10; notes.append("Net margin >= 15% (+10)")
        elif npm >= 8:
            score += 7;  notes.append("Net margin >= 8% (+7)")
        elif npm > 0:
            score += 4;  notes.append("Net margin > 0% (+4)")
        else:
            notes.append("Net margin <= 0% (+0)")
    else:
        notes.append("Net margin data unavailable (+0)")

    # Revenue Growth YoY
    growth = m.revenue_growth_yoy
    if growth is not None:
        if growth >= 20:
            score += 5; notes.append("Revenue growth >= 20% (+5)")
        elif growth >= 5:
            score += 3; notes.append("Revenue growth >= 5% (+3)")
        elif growth > 0:
            score += 1; notes.append("Revenue growth > 0% (+1)")
        else:
            notes.append("Revenue declining (+0)")
    else:
        notes.append("Growth data unavailable (+0)")

    return FactorResult(
        factor="Revenue & Profitability",
        score=score,
        max_score=MAX,
        explanation="; ".join(notes),
    )


def _score_debt(m: ExtractedMetrics) -> FactorResult:
    """
    Debt & Liabilities — 20 points
      debt_to_income_ratio  (12 pts): < 0.3 = 12, < 0.6 = 8, < 1.0 = 4, else 0
      total_assets coverage ( 8 pts): assets/liabilities > 2 = 8, > 1 = 5, else 0
    """
    MAX = 20.0
    score = 0.0
    notes = []

    dti = m.debt_to_income_ratio
    if dti is not None:
        if dti < 0.3:
            score += 12; notes.append("DTI < 0.3 — excellent (+12)")
        elif dti < 0.6:
            score += 8;  notes.append("DTI 0.3–0.6 — good (+8)")
        elif dti < 1.0:
            score += 4;  notes.append("DTI 0.6–1.0 — moderate (+4)")
        else:
            notes.append("DTI >= 1.0 — high risk (+0)")
    else:
        notes.append("DTI data unavailable (+0)")

    assets = m.total_assets
    liabs = m.total_liabilities
    if assets is not None and liabs is not None and liabs > 0:
        coverage = assets / liabs
        if coverage >= 2.0:
            score += 8; notes.append("Asset coverage >= 2x (+8)")
        elif coverage >= 1.0:
            score += 5; notes.append("Asset coverage >= 1x (+5)")
        else:
            notes.append("Assets < Liabilities (+0)")
    elif assets is not None and liabs == 0:
        score += 8; notes.append("No liabilities — excellent (+8)")
    else:
        notes.append("Asset/liability data unavailable (+0)")

    return FactorResult(
        factor="Debt & Liabilities",
        score=score,
        max_score=MAX,
        explanation="; ".join(notes),
    )


def _score_liquidity(m: ExtractedMetrics) -> FactorResult:
    """
    Liquidity — 20 points
      current_ratio  (12 pts): > 2.0 = 12, > 1.5 = 8, > 1.0 = 5, else 0
      quick_ratio    ( 8 pts): > 1.5 = 8, > 1.0 = 5, > 0.5 = 2, else 0
    """
    MAX = 20.0
    score = 0.0
    notes = []

    cr = m.current_ratio
    if cr is not None:
        if cr >= 2.0:
            score += 12; notes.append("Current ratio >= 2.0 (+12)")
        elif cr >= 1.5:
            score += 8;  notes.append("Current ratio >= 1.5 (+8)")
        elif cr >= 1.0:
            score += 5;  notes.append("Current ratio >= 1.0 (+5)")
        else:
            notes.append("Current ratio < 1.0 — illiquid (+0)")
    else:
        notes.append("Current ratio unavailable (+0)")

    qr = m.quick_ratio
    if qr is not None:
        if qr >= 1.5:
            score += 8; notes.append("Quick ratio >= 1.5 (+8)")
        elif qr >= 1.0:
            score += 5; notes.append("Quick ratio >= 1.0 (+5)")
        elif qr >= 0.5:
            score += 2; notes.append("Quick ratio >= 0.5 (+2)")
        else:
            notes.append("Quick ratio < 0.5 (+0)")
    else:
        notes.append("Quick ratio unavailable (+0)")

    return FactorResult(
        factor="Liquidity",
        score=score,
        max_score=MAX,
        explanation="; ".join(notes),
    )


def _score_gst(m: ExtractedMetrics) -> FactorResult:
    """
    GST Compliance — 20 points
      gst_filing_consistency (12 pts): >= 0.9 = 12, >= 0.7 = 8, >= 0.5 = 4, else 0
      total_gst_paid         ( 8 pts): > 1L = 8, > 10K = 5, > 0 = 2, else 0
    """
    MAX = 20.0
    score = 0.0
    notes = []

    consistency = m.gst_filing_consistency
    if consistency is not None:
        if consistency >= 0.9:
            score += 12; notes.append("GST filing >= 90% consistent (+12)")
        elif consistency >= 0.7:
            score += 8;  notes.append("GST filing >= 70% consistent (+8)")
        elif consistency >= 0.5:
            score += 4;  notes.append("GST filing >= 50% consistent (+4)")
        else:
            notes.append("GST filing < 50% — poor compliance (+0)")
    else:
        notes.append("GST filing data unavailable (+0)")

    gst_paid = m.total_gst_paid
    if gst_paid is not None:
        if gst_paid >= 100_000:    # >= 1 Lakh
            score += 8; notes.append("Total GST paid >= 1L (+8)")
        elif gst_paid >= 10_000:   # >= 10K
            score += 5; notes.append("Total GST paid >= 10K (+5)")
        elif gst_paid > 0:
            score += 2; notes.append("Some GST paid (+2)")
        else:
            notes.append("No GST paid (+0)")
    else:
        notes.append("GST payment data unavailable (+0)")

    return FactorResult(
        factor="GST Compliance",
        score=score,
        max_score=MAX,
        explanation="; ".join(notes),
    )


def _score_banking(m: ExtractedMetrics) -> FactorResult:
    """
    Banking Behaviour — 15 points
      avg_monthly_balance   ( 5 pts): > 1L = 5, > 25K = 3, > 0 = 1, else 0
      balance_trend         ( 5 pts): >= 0.5 = 5, > 0 = 3, >= -0.3 = 1, else 0
      cheque_bounce_count   ( 5 pts): 0 = 5, 1 = 3, 2 = 1, > 2 = 0
    """
    MAX = 15.0
    score = 0.0
    notes = []

    avg_bal = m.avg_monthly_balance
    if avg_bal is not None:
        if avg_bal >= 100_000:
            score += 5; notes.append("Avg balance >= 1L (+5)")
        elif avg_bal >= 25_000:
            score += 3; notes.append("Avg balance >= 25K (+3)")
        elif avg_bal > 0:
            score += 1; notes.append("Avg balance > 0 (+1)")
        else:
            notes.append("Avg balance <= 0 (+0)")
    else:
        notes.append("Balance data unavailable (+0)")

    trend = m.balance_trend
    if trend is not None:
        if trend >= 0.5:
            score += 5; notes.append("Balance strongly growing (+5)")
        elif trend > 0:
            score += 3; notes.append("Balance growing (+3)")
        elif trend >= -0.3:
            score += 1; notes.append("Balance stable (+1)")
        else:
            notes.append("Balance declining (+0)")
    else:
        notes.append("Balance trend unavailable (+0)")

    bounces = m.cheque_bounce_count
    if bounces is not None:
        if bounces == 0:
            score += 5; notes.append("No cheque bounces (+5)")
        elif bounces <= 1:
            score += 3; notes.append("1 cheque bounce (+3)")
        elif bounces <= 2:
            score += 1; notes.append("2 cheque bounces (+1)")
        else:
            notes.append(f"{int(bounces)} cheque bounces — red flag (+0)")
    else:
        notes.append("Cheque bounce data unavailable (+0)")

    return FactorResult(
        factor="Banking Behaviour",
        score=score,
        max_score=MAX,
        explanation="; ".join(notes),
    )


# ── Main Scoring Function ──────────────────────────────────────────────────────

def compute_risk_score(metrics: ExtractedMetrics) -> dict:
    """
    Compute the overall credit risk score from extracted metrics.
    Returns a dict ready to be passed to RiskScore(**result).
    """
    factors = [
        _score_revenue(metrics),
        _score_debt(metrics),
        _score_liquidity(metrics),
        _score_gst(metrics),
        _score_banking(metrics),
    ]

    overall_score = round(sum(f.score for f in factors), 2)

    if overall_score >= RISK_BAND_LOW:
        risk_band = "LOW"
    elif overall_score >= RISK_BAND_MEDIUM:
        risk_band = "MEDIUM"
    else:
        risk_band = "HIGH"

    factor_breakdown = [
        {
            "factor": f.factor,
            "score": round(f.score, 2),
            "max": f.max_score,
            "pct": round((f.score / f.max_score) * 100, 1) if f.max_score > 0 else 0,
            "explanation": f.explanation,
        }
        for f in factors
    ]

    logger.info(
        f"Scoring complete: overall={overall_score}/100 band={risk_band} "
        f"factors={[f'{f.factor}:{f.score}/{f.max_score}' for f in factors]}"
    )

    return {
        "overall_score": overall_score,
        "risk_band": risk_band,
        "factor_breakdown": factor_breakdown,
        "narrative_summary": _generate_narrative(overall_score, risk_band, factors),
    }


def _generate_narrative(score: float, band: str, factors: list[FactorResult]) -> str:
    """
    Generate a concise plain-English summary without calling an LLM
    (saves Gemini API quota for actual extraction).
    """
    band_desc = {
        "LOW": "low-risk and creditworthy",
        "MEDIUM": "moderate risk",
        "HIGH": "high-risk",
    }
    weak = [f for f in factors if (f.score / f.max_score) < 0.4]
    strong = [f for f in factors if (f.score / f.max_score) >= 0.8]

    parts = [
        f"This business has an overall credit score of {score:.0f}/100, "
        f"placing it in the {band} risk band ({band_desc.get(band, band)})."
    ]

    if strong:
        parts.append(
            f"Strengths: {', '.join(f.factor for f in strong)}."
        )
    if weak:
        parts.append(
            f"Areas needing improvement: {', '.join(f.factor for f in weak)}."
        )

    if band == "LOW":
        parts.append("This business appears eligible for mainstream MSME credit products.")
    elif band == "MEDIUM":
        parts.append(
            "This business may qualify for government-backed schemes such as MUDRA or CGTMSE "
            "with some conditions."
        )
    else:
        parts.append(
            "This business faces significant credit risk. "
            "Consider PMEGP or micro-finance options, and work on improving financial metrics."
        )

    return " ".join(parts)


# ── DB Helper ─────────────────────────────────────────────────────────────────

def save_risk_score(db: Session, document_id, metrics: ExtractedMetrics) -> RiskScore:
    """Compute and persist a RiskScore row. Returns the saved ORM object."""
    result = compute_risk_score(metrics)

    # Upsert: delete existing if re-scoring
    existing = db.query(RiskScore).filter(RiskScore.document_id == document_id).first()
    if existing:
        db.delete(existing)
        db.flush()

    risk_score = RiskScore(
        document_id=document_id,
        overall_score=result["overall_score"],
        risk_band=result["risk_band"],
        factor_breakdown=result["factor_breakdown"],
        narrative_summary=result["narrative_summary"],
    )
    db.add(risk_score)
    db.commit()
    db.refresh(risk_score)
    return risk_score

"""
Recommendation Service — Phase 4
Generates and persists loan scheme recommendations based on business profile.
"""
import logging
from uuid import UUID

from sqlalchemy.orm import Session

from backend.models.extracted_metrics import ExtractedMetrics
from backend.models.loan_recommendation import LoanRecommendation
from backend.models.risk_score import RiskScore
from backend.services.schemes_knowledge import get_schemes_context
from backend.utils.gemini import match_loan_schemes

logger = logging.getLogger(__name__)


async def generate_and_save_recommendations(
    db: Session, document_id: UUID, metrics: ExtractedMetrics, risk_score: RiskScore
) -> list[LoanRecommendation]:
    """
    Calls the LLM to generate recommendations and persists them to the database.
    """
    logger.info(f"Generating recommendations for document {document_id}")

    # 1. Prepare data for the prompt
    # Convert ORM objects to dicts, excluding internal/SQLAlchemy state
    metrics_dict = {
        c.name: getattr(metrics, c.name) for c in metrics.__table__.columns if c.name not in ["id", "document_id", "created_at", "raw_extraction_json"]
    }
    
    risk_score_dict = {
        "overall_score": risk_score.overall_score,
        "risk_band": risk_score.risk_band,
        "factors": risk_score.factor_breakdown,
    }

    knowledge_base_str = get_schemes_context()

    # 2. Call Gemini for matching
    try:
        recommendations_data = await match_loan_schemes(metrics_dict, risk_score_dict, knowledge_base_str)
    except Exception as e:
        logger.error(f"Failed to generate recommendations: {e}")
        raise

    # 3. Clear existing recommendations for this document (upsert behavior)
    db.query(LoanRecommendation).filter(LoanRecommendation.document_id == document_id).delete()
    db.flush()

    # 4. Save new recommendations
    saved_recs = []
    for idx, rec_data in enumerate(recommendations_data):
        rank = idx + 1
        rec = LoanRecommendation(
            document_id=document_id,
            scheme_name=rec_data.get("scheme_name", "Unknown Scheme"),
            scheme_type=rec_data.get("scheme_type", "OTHER"),
            issuing_body=rec_data.get("issuing_body"),
            eligibility_score=rec_data.get("eligibility_score"),
            rank=rank,
            reasoning=rec_data.get("reasoning"),
            scheme_details=rec_data.get("scheme_details"),
        )
        db.add(rec)
        saved_recs.append(rec)

    db.commit()
    for rec in saved_recs:
        db.refresh(rec)

    logger.info(f"Saved {len(saved_recs)} recommendations for document {document_id}")
    return saved_recs

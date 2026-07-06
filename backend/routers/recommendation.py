"""
Recommendation API Router — Phase 4
====================================
Endpoints:
  GET  /documents/{document_id}/recommendations   → fetch recommendations
  POST /documents/{document_id}/recommend         → (re)trigger recommendation matching
"""
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models.document import Document
from backend.models.extracted_metrics import ExtractedMetrics
from backend.models.loan_recommendation import LoanRecommendation
from backend.models.risk_score import RiskScore
from backend.models.user import User
from backend.routers.auth import get_current_user
from backend.schemas.recommendation import RecommendationListResponse
from backend.services.recommendation import generate_and_save_recommendations

router = APIRouter(prefix="/documents", tags=["Loan Recommendations"])


def _get_owned_document(document_id: UUID, current_user: User, db: Session) -> Document:
    """Fetch a document that belongs to the current user or raise 404."""
    doc = (
        db.query(Document)
        .filter(Document.id == document_id, Document.user_id == current_user.id)
        .first()
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return doc


# ── GET /documents/{id}/recommendations ───────────────────────────────────────

@router.get("/{document_id}/recommendations", response_model=RecommendationListResponse)
def get_recommendations(
    document_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Retrieve the loan scheme recommendations for a document.

    - Returns 200 with the recommendations if processing is complete.
    - Returns 200 with a status message if still processing.
    """
    doc = _get_owned_document(document_id, current_user, db)

    recommendations = (
        db.query(LoanRecommendation)
        .filter(LoanRecommendation.document_id == document_id)
        .order_by(LoanRecommendation.rank.asc())
        .all()
    )

    if recommendations:
        return RecommendationListResponse(
            document_id=doc.id,
            document_status=doc.status,
            recommendations=recommendations,
            message=f"Found {len(recommendations)} recommendations.",
        )

    # Not yet recommended — give helpful status
    status_messages = {
        "PENDING":      "Document is queued. Extraction has not started yet.",
        "EXTRACTING":   "Document text is being extracted.",
        "SCORING":      "Risk scoring is in progress.",
        "RECOMMENDING": "Finding best loan schemes via Gemini AI. Please check back shortly.",
        "FAILED":       f"Processing failed: {doc.error_message or 'Unknown error'}",
        "COMPLETE":     "Processing complete but recommendations are missing. Try re-running.",
    }
    message = status_messages.get(doc.status, f"Document status: {doc.status}")

    return RecommendationListResponse(
        document_id=doc.id,
        document_status=doc.status,
        recommendations=[],
        message=message,
    )


# ── POST /documents/{id}/recommend  (manual re-trigger) ───────────────────────

@router.post("/{document_id}/recommend", response_model=RecommendationListResponse)
async def trigger_recommendation(
    document_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Manually trigger (or re-trigger) the loan scheme recommendation matching.
    Requires extracted metrics and a risk score to already exist.
    """
    doc = _get_owned_document(document_id, current_user, db)

    metrics = (
        db.query(ExtractedMetrics)
        .filter(ExtractedMetrics.document_id == document_id)
        .first()
    )
    if not metrics:
        raise HTTPException(
            status_code=422,
            detail="No extracted metrics found. The document must be processed by the extraction worker first."
        )

    risk_score = (
        db.query(RiskScore)
        .filter(RiskScore.document_id == document_id)
        .first()
    )
    if not risk_score:
        raise HTTPException(
            status_code=422,
            detail="No risk score found. The document must be scored first."
        )

    # Set status to RECOMMENDING
    doc.status = "RECOMMENDING"
    db.commit()

    try:
        # Run the RAG/matching service
        recs = await generate_and_save_recommendations(db, document_id, metrics, risk_score)
        
        # Success!
        doc.status = "COMPLETE"
        db.commit()
        
        return RecommendationListResponse(
            document_id=doc.id,
            document_status=doc.status,
            recommendations=recs,
            message=f"Successfully generated {len(recs)} recommendations.",
        )
    except Exception as e:
        doc.status = "FAILED"
        doc.error_message = f"Recommendation matching failed: {str(e)}"
        db.commit()
        raise HTTPException(
            status_code=500,
            detail=f"Internal error during recommendation generation: {str(e)}"
        )

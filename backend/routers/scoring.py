"""
Risk Score API Router — Phase 3
================================
Endpoints:
  GET  /documents/{document_id}/risk-score   → fetch computed score
  POST /documents/{document_id}/score        → (re)trigger scoring manually
"""
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models.document import Document
from backend.models.extracted_metrics import ExtractedMetrics
from backend.models.risk_score import RiskScore
from backend.models.user import User
from backend.routers.auth import get_current_user
from backend.schemas.risk_score import RiskScoreResponse, ScoreDocumentResponse
from backend.services.scoring import save_risk_score

router = APIRouter(prefix="/documents", tags=["Risk Scoring"])


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


# ── GET /documents/{id}/risk-score ────────────────────────────────────────────

@router.get("/{document_id}/risk-score", response_model=ScoreDocumentResponse)
def get_risk_score(
    document_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Retrieve the computed credit risk score for a document.

    - Returns 200 with the score if processing is complete.
    - Returns 202 with a status message if still processing.
    - Returns 404 if the document does not belong to the user.
    """
    doc = _get_owned_document(document_id, current_user, db)

    risk_score = (
        db.query(RiskScore).filter(RiskScore.document_id == document_id).first()
    )

    if risk_score:
        return ScoreDocumentResponse(
            document_id=doc.id,
            document_status=doc.status,
            risk_score=risk_score,
            message="Risk score computed successfully.",
        )

    # Not yet scored — give helpful status
    status_messages = {
        "PENDING":    "Document is queued. Extraction has not started yet.",
        "EXTRACTING": "Document text is being extracted. Score will be computed next.",
        "SCORING":    "Risk scoring is in progress. Please check back shortly.",
        "FAILED":     f"Processing failed: {doc.error_message or 'Unknown error'}",
        "COMPLETE":   "Processing complete but score record is missing. Try re-scoring.",
    }
    message = status_messages.get(doc.status, f"Document status: {doc.status}")

    return ScoreDocumentResponse(
        document_id=doc.id,
        document_status=doc.status,
        risk_score=None,
        message=message,
    )


# ── POST /documents/{id}/score  (manual re-trigger) ───────────────────────────

@router.post("/{document_id}/score", response_model=ScoreDocumentResponse)
def trigger_scoring(
    document_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Manually trigger (or re-trigger) risk scoring for a document.

    Requires extracted metrics to already exist (document must have been
    processed through the extraction worker first).

    Useful for:
    - Re-scoring after algorithm updates
    - Recovering from a previous SCORING failure
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
            detail=(
                "No extracted metrics found for this document. "
                "The document must be processed by the extraction worker first. "
                f"Current status: {doc.status}"
            ),
        )

    # Run scoring synchronously (fast — pure Python, no API calls)
    risk_score = save_risk_score(db, document_id, metrics)

    # Update document status
    doc.status = "COMPLETE"
    db.commit()

    return ScoreDocumentResponse(
        document_id=doc.id,
        document_status=doc.status,
        risk_score=risk_score,
        message=f"Scoring complete. Risk band: {risk_score.risk_band}. Score: {risk_score.overall_score}/100.",
    )

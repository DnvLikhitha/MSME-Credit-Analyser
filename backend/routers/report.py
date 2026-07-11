"""
Report API Router — Phase 5
=============================
Endpoints:
  GET  /documents/{document_id}/report          → status check
  GET  /documents/{document_id}/report/download → stream PDF file
  POST /documents/{document_id}/report/generate → manually trigger generation
"""
import os
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models.document import Document
from backend.models.extracted_metrics import ExtractedMetrics
from backend.models.loan_recommendation import LoanRecommendation
from backend.models.report import Report
from backend.models.risk_score import RiskScore
from backend.models.user import User
from backend.routers.auth import get_current_user
from backend.schemas.report import ReportStatusResponse
from backend.services.report import generate_and_save_report

router = APIRouter(prefix="/documents", tags=["Credit Report"])


def _get_owned_document(document_id: UUID, current_user: User, db: Session) -> Document:
    doc = (
        db.query(Document)
        .filter(Document.id == document_id, Document.user_id == current_user.id)
        .first()
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return doc


# ── GET /documents/{id}/report ─────────────────────────────────────────────────

@router.get("/{document_id}/report", response_model=ReportStatusResponse)
def get_report_status(
    document_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Check the status of the PDF credit report for a document."""
    doc = _get_owned_document(document_id, current_user, db)
    report = db.query(Report).filter(Report.document_id == document_id).first()

    if report and report.status == "COMPLETE":
        return ReportStatusResponse(
            document_id=doc.id,
            report_id=report.id,
            status="COMPLETE",
            download_url=f"/documents/{document_id}/report/download",
            message="Report is ready for download.",
        )
    if report:
        return ReportStatusResponse(
            document_id=doc.id,
            report_id=report.id,
            status=report.status,
            message=f"Report status: {report.status}",
        )

    status_messages = {
        "PENDING":    "Document is queued for processing.",
        "EXTRACTING": "Extracting document text.",
        "SCORING":    "Running credit risk scoring.",
        "RECOMMENDING": "Generating loan scheme recommendations.",
        "FAILED":     f"Processing failed: {doc.error_message or 'Unknown error'}",
        "COMPLETE":   "Processing complete but report record missing. Try /report/generate.",
    }
    return ReportStatusResponse(
        document_id=doc.id,
        status=doc.status,
        message=status_messages.get(doc.status, f"Document status: {doc.status}"),
    )


# ── GET /documents/{id}/report/download ───────────────────────────────────────

@router.get("/{document_id}/report/download")
def download_report(
    document_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Download the generated PDF credit report.
    Returns the file directly as an application/pdf response.
    """
    doc = _get_owned_document(document_id, current_user, db)
    report = db.query(Report).filter(Report.document_id == document_id).first()

    if not report:
        raise HTTPException(
            status_code=404,
            detail="Report not found. Trigger generation via POST /report/generate first."
        )
    if report.status != "COMPLETE":
        raise HTTPException(
            status_code=409,
            detail=f"Report is not ready yet. Current status: {report.status}"
        )
    if not report.file_path or not os.path.exists(report.file_path):
        raise HTTPException(
            status_code=404,
            detail="Report file not found on disk. Please re-generate."
        )

    safe_name = f"credit_report_{doc.original_filename.rsplit('.', 1)[0]}.pdf"
    return FileResponse(
        path=report.file_path,
        media_type="application/pdf",
        filename=safe_name,
        headers={"Content-Disposition": f'attachment; filename="{safe_name}"'},
    )


# ── POST /documents/{id}/report/generate ──────────────────────────────────────

@router.post("/{document_id}/report/generate", response_model=ReportStatusResponse)
def generate_report(
    document_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Manually trigger (or re-trigger) PDF credit report generation.
    Requires extracted metrics, risk score, and recommendations to exist.
    """
    doc = _get_owned_document(document_id, current_user, db)

    metrics = db.query(ExtractedMetrics).filter(ExtractedMetrics.document_id == document_id).first()
    if not metrics:
        raise HTTPException(status_code=422, detail="No extracted metrics found. Run the extraction worker first.")

    risk_score = db.query(RiskScore).filter(RiskScore.document_id == document_id).first()
    if not risk_score:
        raise HTTPException(status_code=422, detail="No risk score found. Run scoring first.")

    recs = (
        db.query(LoanRecommendation)
        .filter(LoanRecommendation.document_id == document_id)
        .order_by(LoanRecommendation.rank.asc())
        .all()
    )

    report = generate_and_save_report(db, doc, metrics, risk_score, recs)

    return ReportStatusResponse(
        document_id=doc.id,
        report_id=report.id,
        status=report.status,
        download_url=f"/documents/{document_id}/report/download",
        message="Report generated successfully! Use the download_url to get the PDF.",
    )

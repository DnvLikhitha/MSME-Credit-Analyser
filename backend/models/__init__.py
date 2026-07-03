# Re-export all models so `from backend.models import X` works cleanly.
# Also ensures SQLAlchemy can discover all tables when create_all() is called.

from backend.models.user import User
from backend.models.document import Document, DocumentStatus, DocumentType
from backend.models.extracted_metrics import ExtractedMetrics
from backend.models.risk_score import RiskScore
from backend.models.loan_recommendation import LoanRecommendation
from backend.models.report import Report

__all__ = [
    "User",
    "Document",
    "DocumentStatus",
    "DocumentType",
    "ExtractedMetrics",
    "RiskScore",
    "LoanRecommendation",
    "Report",
]

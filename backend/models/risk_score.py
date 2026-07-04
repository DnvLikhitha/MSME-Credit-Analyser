import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, Float, ForeignKey, String, Text, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from backend.database import Base


class RiskBand(str):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class RiskScore(Base):
    """
    Computed creditworthiness score for a document.
    Contains overall score, risk band, and factor-level breakdown for explainability.
    One-to-one with Document.
    """
    __tablename__ = "risk_scores"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id = Column(
        UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True,
    )

    # ── Score ─────────────────────────────────────────────────────────────────
    overall_score = Column(Float, nullable=False)           # 0–100
    risk_band = Column(String(10), nullable=False)          # LOW | MEDIUM | HIGH

    # ── Explainability ────────────────────────────────────────────────────────
    # List of factor dicts:
    # [{"factor": "Revenue Growth", "score": 18, "max": 20, "explanation": "..."}]
    factor_breakdown = Column(JSON, nullable=True)

    # LLM-generated narrative (optional, can be disabled to save API credits)
    narrative_summary = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    document = relationship("Document", back_populates="risk_score")

    def __repr__(self) -> str:
        return f"<RiskScore doc_id={self.document_id} score={self.overall_score} band={self.risk_band}>"

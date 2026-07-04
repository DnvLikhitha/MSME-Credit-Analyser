import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String, Text, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from backend.database import Base


class LoanRecommendation(Base):
    """
    RAG-matched loan scheme recommendation for a document.
    One document can have multiple ranked recommendations.
    """
    __tablename__ = "loan_recommendations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id = Column(
        UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # ── Scheme Identity ───────────────────────────────────────────────────────
    scheme_name = Column(String(255), nullable=False)       # e.g. "MUDRA Shishu Loan"
    scheme_type = Column(String(50), nullable=False)        # MUDRA | SIDBI | PMEGP | CGTMSE | OTHER
    issuing_body = Column(String(255), nullable=True)       # e.g. "Ministry of MSME"

    # ── Match Quality ─────────────────────────────────────────────────────────
    eligibility_score = Column(Float, nullable=True)        # 0.0–1.0 (RAG similarity)
    rank = Column(Integer, nullable=False, default=1)       # 1 = best match
    reasoning = Column(Text, nullable=True)                 # why this scheme was recommended

    # ── Scheme Details ────────────────────────────────────────────────────────
    # {"max_loan_amount": 500000, "interest_rate": "7-8%", "tenure": "5 years", ...}
    scheme_details = Column(JSON, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    document = relationship("Document", back_populates="loan_recommendations")

    def __repr__(self) -> str:
        return f"<LoanRecommendation rank={self.rank} scheme={self.scheme_name}>"

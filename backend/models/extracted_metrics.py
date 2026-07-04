import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, Float, ForeignKey, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from backend.database import Base


class ExtractedMetrics(Base):
    """
    Structured financial metrics extracted from a document via OCR + LLM.
    One-to-one with Document.
    """
    __tablename__ = "extracted_metrics"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id = Column(
        UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True,
    )

    # ── Revenue & Profitability ──────────────────────────────────────────────
    annual_revenue = Column(Float, nullable=True)           # INR
    revenue_growth_yoy = Column(Float, nullable=True)       # percentage e.g. 12.5
    net_profit_margin = Column(Float, nullable=True)        # percentage e.g. 8.2
    gross_profit_margin = Column(Float, nullable=True)      # percentage

    # ── Debt & Liabilities ───────────────────────────────────────────────────
    total_liabilities = Column(Float, nullable=True)        # INR
    total_assets = Column(Float, nullable=True)             # INR
    debt_to_income_ratio = Column(Float, nullable=True)     # ratio e.g. 0.45

    # ── Liquidity ────────────────────────────────────────────────────────────
    current_ratio = Column(Float, nullable=True)            # current assets / current liabilities
    quick_ratio = Column(Float, nullable=True)

    # ── GST Metrics ──────────────────────────────────────────────────────────
    gst_filing_consistency = Column(Float, nullable=True)   # 0.0–1.0 (fraction of months filed)
    total_gst_paid = Column(Float, nullable=True)           # INR
    gst_turnover = Column(Float, nullable=True)             # INR declared in GST

    # ── Banking Metrics ──────────────────────────────────────────────────────
    avg_monthly_balance = Column(Float, nullable=True)      # INR
    min_monthly_balance = Column(Float, nullable=True)      # INR
    balance_trend = Column(Float, nullable=True)            # positive = improving slope
    num_monthly_transactions = Column(Float, nullable=True) # average per month
    cheque_bounce_count = Column(Float, nullable=True)      # red flag metric

    # ── Raw Extraction ───────────────────────────────────────────────────────
    raw_extraction_json = Column(JSON, nullable=True)      # full LLM output

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    document = relationship("Document", back_populates="extracted_metrics")

    def __repr__(self) -> str:
        return f"<ExtractedMetrics doc_id={self.document_id} revenue={self.annual_revenue}>"

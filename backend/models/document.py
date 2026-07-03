import enum
import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from backend.database import Base


class DocumentStatus(str, enum.Enum):
    PENDING = "PENDING"
    EXTRACTING = "EXTRACTING"
    SCORING = "SCORING"
    RECOMMENDING = "RECOMMENDING"
    REPORTING = "REPORTING"
    COMPLETE = "COMPLETE"
    FAILED = "FAILED"


class DocumentType(str, enum.Enum):
    GST_RETURN = "GST_RETURN"
    BANK_STATEMENT = "BANK_STATEMENT"
    ITR = "ITR"
    OTHER = "OTHER"


class Document(Base):
    __tablename__ = "documents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    # File metadata
    filename = Column(String(255), nullable=False)          # stored filename (UUID-based)
    original_filename = Column(String(255), nullable=False)  # user-facing filename
    file_path = Column(String(512), nullable=False)
    file_size = Column(String(20), nullable=True)           # bytes as string
    mime_type = Column(String(100), nullable=True)
    document_type = Column(String(50), default=DocumentType.OTHER, nullable=False)

    # Deduplication
    content_hash = Column(String(64), nullable=True, index=True)  # SHA-256 hex

    # Processing state machine
    status = Column(String(20), default=DocumentStatus.PENDING, nullable=False)
    error_message = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    # Relationships
    owner = relationship("User", back_populates="documents")
    extracted_metrics = relationship("ExtractedMetrics", back_populates="document", uselist=False)
    risk_score = relationship("RiskScore", back_populates="document", uselist=False)
    loan_recommendations = relationship(
        "LoanRecommendation", back_populates="document", order_by="LoanRecommendation.rank"
    )
    report = relationship("Report", back_populates="document", uselist=False)

    def __repr__(self) -> str:
        return f"<Document id={self.id} status={self.status} file={self.original_filename}>"

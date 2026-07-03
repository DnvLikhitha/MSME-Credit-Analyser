import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from backend.database import Base


class ReportStatus(str):
    PENDING = "PENDING"
    GENERATING = "GENERATING"
    COMPLETE = "COMPLETE"
    FAILED = "FAILED"


class Report(Base):
    """
    Generated PDF report for a completed document assessment.
    One-to-one with Document.
    """
    __tablename__ = "reports"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id = Column(
        UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True,
    )

    file_path = Column(String(512), nullable=True)          # local path or GCS URI
    status = Column(String(20), default=ReportStatus.PENDING, nullable=False)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    # Relationships
    document = relationship("Document", back_populates="report")

    def __repr__(self) -> str:
        return f"<Report doc_id={self.document_id} status={self.status}>"

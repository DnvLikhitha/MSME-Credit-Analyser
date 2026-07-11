"""Pydantic schemas for credit report API responses."""
from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel


class ReportStatusResponse(BaseModel):
    document_id: UUID
    report_id: Optional[UUID] = None
    status: str                       # PENDING | GENERATING | COMPLETE | FAILED
    download_url: Optional[str] = None
    message: str

    model_config = {"from_attributes": True}

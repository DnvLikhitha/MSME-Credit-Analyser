from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel


# ── Response Schemas ──────────────────────────────────────────────────────────

class DocumentResponse(BaseModel):
    id: UUID
    filename: str
    original_filename: str
    file_size: Optional[str]
    mime_type: Optional[str]
    document_type: str
    content_hash: Optional[str]
    status: str
    error_message: Optional[str]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class DocumentListResponse(BaseModel):
    documents: list[DocumentResponse]
    total: int


class UploadResponse(BaseModel):
    """Returned immediately after upload — tells the client whether it's a fresh upload or a cache hit."""
    document: DocumentResponse
    is_duplicate: bool
    message: str

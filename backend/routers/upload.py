import hashlib
import os
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from backend.config import settings
from backend.database import get_db
from backend.models.document import Document, DocumentStatus, DocumentType
from backend.models.user import User
from backend.routers.auth import get_current_user
from backend.schemas.document import DocumentListResponse, DocumentResponse, UploadResponse
from backend.utils.rabbitmq import publish_document_processing_task

router = APIRouter(prefix="/documents", tags=["Documents"])

# ── Constants ─────────────────────────────────────────────────────────────────
ALLOWED_MIME_TYPES: dict[str, str] = {
    "application/pdf": ".pdf",
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
    "image/png": ".png",
}

MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB


# ── Helpers ───────────────────────────────────────────────────────────────────

def compute_sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def find_existing_document(db: Session, user_id, content_hash: str) -> Optional[Document]:
    return (
        db.query(Document)
        .filter(Document.content_hash == content_hash, Document.user_id == user_id)
        .first()
    )


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/upload", response_model=UploadResponse, status_code=201)
async def upload_document(
    file: UploadFile = File(..., description="PDF, JPEG, or PNG financial document"),
    document_type: str = Form(
        default=DocumentType.OTHER,
        description="GST_RETURN | BANK_STATEMENT | ITR | OTHER",
    ),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Upload a financial document for MSME credit assessment.

    - Validates file type and size
    - Computes SHA-256 hash for deduplication (same file = returns cached record)
    - Saves file to UPLOAD_DIR
    - Creates a Document record with status=PENDING
    - (Phase 2) Will enqueue an extraction job to RabbitMQ
    """

    # ── 1. Validate MIME type ─────────────────────────────────────────────────
    if file.content_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=415,
            detail=f"Unsupported file type: {file.content_type}. Allowed: PDF, JPEG, PNG",
        )

    # ── 2. Read content ───────────────────────────────────────────────────────
    content = await file.read()

    if len(content) == 0:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")

    if len(content) > MAX_FILE_SIZE_BYTES:
        raise HTTPException(
            status_code=413, detail="File too large. Maximum allowed size is 10 MB"
        )

    # ── 3. Deduplicate by content hash ────────────────────────────────────────
    content_hash = compute_sha256(content)
    existing = find_existing_document(db, current_user.id, content_hash)

    if existing:
        return UploadResponse(
            document=existing,
            is_duplicate=True,
            message="Document already uploaded. Returning existing record.",
        )

    # ── 4. Save file to disk ──────────────────────────────────────────────────
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    ext = ALLOWED_MIME_TYPES[file.content_type]
    safe_filename = f"{uuid.uuid4()}{ext}"
    file_path = os.path.join(settings.UPLOAD_DIR, safe_filename)

    with open(file_path, "wb") as f:
        f.write(content)

    # ── 5. Persist Document record ────────────────────────────────────────────
    document = Document(
        user_id=current_user.id,
        filename=safe_filename,
        original_filename=file.filename or "unknown",
        file_path=file_path,
        file_size=str(len(content)),
        mime_type=file.content_type,
        document_type=document_type,
        content_hash=content_hash,
        status=DocumentStatus.PENDING,
    )
    db.add(document)
    db.commit()
    db.refresh(document)

    # Publish task to RabbitMQ for async processing
    await publish_document_processing_task(str(document.id))

    return UploadResponse(
        document=document,
        is_duplicate=False,
        message="Document uploaded successfully. Processing will begin shortly.",
    )


@router.get("/", response_model=DocumentListResponse)
def list_documents(
    skip: int = 0,
    limit: int = 20,
    status_filter: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List all documents belonging to the authenticated user."""
    query = db.query(Document).filter(Document.user_id == current_user.id)

    if status_filter:
        query = query.filter(Document.status == status_filter.upper())

    total = query.count()
    documents = (
        query.order_by(Document.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )
    return {"documents": documents, "total": total}


@router.get("/{document_id}", response_model=DocumentResponse)
def get_document(
    document_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get a single document by ID (must belong to the authenticated user)."""
    doc = (
        db.query(Document)
        .filter(Document.id == document_id, Document.user_id == current_user.id)
        .first()
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return doc


@router.delete("/{document_id}", status_code=204)
def delete_document(
    document_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Delete a document and its associated file from disk."""
    doc = (
        db.query(Document)
        .filter(Document.id == document_id, Document.user_id == current_user.id)
        .first()
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    # Remove file from disk
    if doc.file_path and os.path.exists(doc.file_path):
        os.remove(doc.file_path)

    db.delete(doc)
    db.commit()

import io
import os
import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("DATABASE_URL", "sqlite:///./test.db")
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-testing-only")

from backend.main import app  # noqa: E402

client = TestClient(app)


def get_auth_token() -> str:
    """Helper: register + login, return Bearer token."""
    client.post("/auth/register", json={
        "email": "uploadtest@msme.com",
        "password": "uploadpass123",
    })
    resp = client.post("/auth/login", data={
        "username": "uploadtest@msme.com",
        "password": "uploadpass123",
    })
    return resp.json()["access_token"]


# ── Upload ────────────────────────────────────────────────────────────────────

def test_upload_pdf():
    token = get_auth_token()
    headers = {"Authorization": f"Bearer {token}"}

    # Create a minimal fake PDF content
    fake_pdf = b"%PDF-1.4 fake content for testing"

    response = client.post(
        "/documents/upload",
        headers=headers,
        files={"file": ("test_gst.pdf", io.BytesIO(fake_pdf), "application/pdf")},
        data={"document_type": "GST_RETURN"},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["document"]["original_filename"] == "test_gst.pdf"
    assert data["document"]["status"] == "PENDING"
    assert data["is_duplicate"] is False


def test_upload_duplicate_returns_cached():
    token = get_auth_token()
    headers = {"Authorization": f"Bearer {token}"}
    fake_pdf = b"%PDF-DUPLICATE-TEST"

    # First upload
    client.post(
        "/documents/upload",
        headers=headers,
        files={"file": ("dup.pdf", io.BytesIO(fake_pdf), "application/pdf")},
        data={"document_type": "ITR"},
    )

    # Second upload of same content
    response = client.post(
        "/documents/upload",
        headers=headers,
        files={"file": ("dup_again.pdf", io.BytesIO(fake_pdf), "application/pdf")},
        data={"document_type": "ITR"},
    )
    assert response.status_code == 201
    assert response.json()["is_duplicate"] is True


def test_upload_invalid_type():
    token = get_auth_token()
    headers = {"Authorization": f"Bearer {token}"}

    response = client.post(
        "/documents/upload",
        headers=headers,
        files={"file": ("malware.exe", io.BytesIO(b"MZ\x90\x00"), "application/octet-stream")},
        data={"document_type": "OTHER"},
    )
    assert response.status_code == 415


def test_upload_without_auth():
    response = client.post(
        "/documents/upload",
        files={"file": ("test.pdf", io.BytesIO(b"content"), "application/pdf")},
    )
    assert response.status_code == 401


def test_list_documents():
    token = get_auth_token()
    headers = {"Authorization": f"Bearer {token}"}
    response = client.get("/documents/", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert "documents" in data
    assert "total" in data

import os
import pytest
from fastapi.testclient import TestClient

# Set a test DATABASE_URL if not already set
os.environ.setdefault("DATABASE_URL", "sqlite:///./test.db")
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-testing-only")

from backend.main import app  # noqa: E402

client = TestClient(app)


# ── Health endpoints ──────────────────────────────────────────────────────────

def test_root():
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "version" in data


def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


# ── Auth: Register ────────────────────────────────────────────────────────────

def test_register_success():
    response = client.post("/auth/register", json={
        "email": "testuser@msme.com",
        "password": "securepass123",
        "full_name": "Test MSME Owner",
    })
    assert response.status_code in [201, 400]  # 400 = already exists (re-runs)
    if response.status_code == 201:
        data = response.json()
        assert data["email"] == "testuser@msme.com"
        assert "id" in data
        assert "hashed_password" not in data  # password must NOT leak


def test_register_weak_password():
    response = client.post("/auth/register", json={
        "email": "weak@msme.com",
        "password": "short",
    })
    assert response.status_code == 422  # Pydantic validation error


def test_register_invalid_email():
    response = client.post("/auth/register", json={
        "email": "not-an-email",
        "password": "strongpassword",
    })
    assert response.status_code == 422


# ── Auth: Login ───────────────────────────────────────────────────────────────

def test_login_invalid_credentials():
    response = client.post("/auth/login", data={
        "username": "nobody@msme.com",
        "password": "wrongpassword",
    })
    assert response.status_code == 401


def test_login_success_and_me():
    # First register
    client.post("/auth/register", json={
        "email": "logintest@msme.com",
        "password": "loginpass456",
    })

    # Then login
    login_resp = client.post("/auth/login", data={
        "username": "logintest@msme.com",
        "password": "loginpass456",
    })
    assert login_resp.status_code == 200
    token = login_resp.json()["access_token"]
    assert token is not None

    # Use token to call /auth/me
    me_resp = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me_resp.status_code == 200
    assert me_resp.json()["email"] == "logintest@msme.com"


# ── Protected route without token ─────────────────────────────────────────────

def test_me_without_token():
    response = client.get("/auth/me")
    assert response.status_code == 401

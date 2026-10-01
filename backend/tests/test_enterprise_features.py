"""
Unit & Integration Tests for Enterprise Features:
- Fernet PDF Password Encryption
- SlowAPI Rate Limiting
- Redis Caching Layer (with graceful offline fallback)
- Semantic RAG Retrieval with ChromaDB & SentenceTransformers
- WebSocket Connection Manager
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from backend.utils.encryption import encrypt_password, decrypt_password
from backend.utils.cache import (
    cache_document_status,
    get_cached_document_status,
    redis_health,
)
from backend.utils.limiter import limiter
from backend.utils.websocket_manager import WebSocketManager
from backend.services.rag_retrieval import build_query_from_profile, retrieve_relevant_schemes


def test_password_encryption_roundtrip():
    secret = "HDFC_Statement_Password_999!"
    encrypted = encrypt_password(secret)
    assert encrypted != secret
    decrypted = decrypt_password(encrypted)
    assert decrypted == secret


def test_password_encryption_empty_or_none():
    assert encrypt_password(None) is None
    assert encrypt_password("") == ""
    assert decrypt_password(None) is None
    assert decrypt_password("") == ""


def test_slowapi_limiter_initialization():
    assert limiter is not None
    assert hasattr(limiter, "limit")


def test_rag_query_building():
    metrics = {
        "annual_revenue": 5000000.0,
        "avg_monthly_balance": 150000.0,
        "cheque_bounce_count": 0,
        "total_assets": 2000000.0,
    }
    risk_score = {
        "overall_score": 75.0,
        "risk_band": "LOW",
    }
    query = build_query_from_profile(metrics, risk_score)
    assert "LOW credit risk" in query
    assert "INR 0.50 crore" in query
    assert "clean banking record" in query


def test_rag_retrieval_returns_valid_schemes():
    metrics = {
        "annual_revenue": 1000000.0,
        "avg_monthly_balance": 30000.0,
        "cheque_bounce_count": 1,
    }
    risk_score = {
        "overall_score": 42.0,
        "risk_band": "HIGH",
    }
    json_result = retrieve_relevant_schemes(metrics, risk_score, top_k=3)
    assert "scheme_name" in json_result


@pytest.mark.asyncio
async def test_websocket_manager_lifecycle():
    manager = WebSocketManager()
    mock_ws = MagicMock()
    mock_ws.accept = AsyncMock()
    mock_ws.send_text = AsyncMock()

    doc_id = "test-doc-1234"
    await manager.connect(mock_ws, doc_id)
    assert doc_id in manager._connections
    assert mock_ws in manager._connections[doc_id]

    await manager.broadcast_status(doc_id, "EXTRACTING", "Extracting...")
    mock_ws.send_text.assert_called_once()

    manager.disconnect(mock_ws, doc_id)
    assert doc_id not in manager._connections


@pytest.mark.asyncio
async def test_redis_graceful_fallback_when_offline():
    # Even if Redis server is down/not connected, helpers should not raise uncaught exceptions
    await cache_document_status("dummy-id", "PENDING")
    res = await get_cached_document_status("dummy-id")
    # Returns None or dict, does not crash
    assert res is None or isinstance(res, dict)

    health = await redis_health()
    assert "status" in health

"""
Redis Cache Layer — Phase 6
============================
Provides a shared async Redis connection and helper functions for:
  - Caching document status (avoids DB hit for every frontend poll)
  - Caching extracted metrics JSON (avoids re-fetch for scoring/recommendation)
  - Deduplication by content hash (idempotency — prevents re-processing same file)
  - WebSocket session tracking (which clients are connected for which document)

TTLs:
  - Document status: 300 s (5 min) — refreshed on every status update
  - Extracted metrics: 3600 s (1 hour)
  - Content hash dedupe: 86400 s (24 hours)
"""
import json
import logging
from typing import Optional

import redis.asyncio as aioredis

from backend.config import settings

logger = logging.getLogger(__name__)

# Global Redis connection pool (initialized at app startup)
_redis_client: Optional[aioredis.Redis] = None

# ── TTL constants ─────────────────────────────────────────────────────────────
TTL_STATUS = 300       # 5 minutes — document processing status
TTL_METRICS = 3600     # 1 hour   — extracted financial metrics
TTL_DEDUP = 86400      # 24 hours — content-hash deduplication key
TTL_SCORE = 3600       # 1 hour   — risk score cache

# ── Key prefixes ──────────────────────────────────────────────────────────────
KEY_STATUS  = "doc:status:"     # doc:status:{document_id}
KEY_METRICS = "doc:metrics:"    # doc:metrics:{document_id}
KEY_SCORE   = "doc:score:"      # doc:score:{document_id}
KEY_DEDUP   = "dedup:hash:"     # dedup:hash:{content_hash}


async def connect_redis() -> None:
    """Initialize Redis connection pool (called at FastAPI startup)."""
    global _redis_client
    try:
        _redis_client = aioredis.from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=True,
            socket_connect_timeout=3,
        )
        await _redis_client.ping()
        logger.info(f"[*] Connected to Redis at {settings.REDIS_URL}")
    except Exception as e:
        logger.warning(f"[!] Redis connection failed (non-fatal): {e}. Caching disabled.")
        _redis_client = None


async def close_redis() -> None:
    """Close Redis connection (called at FastAPI shutdown)."""
    global _redis_client
    if _redis_client:
        await _redis_client.aclose()
        logger.info("[*] Closed Redis connection")


def _client() -> Optional[aioredis.Redis]:
    """Return the Redis client, or None if unavailable."""
    return _redis_client


# ── Document Status ───────────────────────────────────────────────────────────

async def cache_document_status(document_id: str, status: str, error: Optional[str] = None) -> None:
    """Cache current document processing status (refreshed on every state transition)."""
    client = _client()
    if not client:
        return
    payload = json.dumps({"status": status, "error": error})
    try:
        await client.setex(f"{KEY_STATUS}{document_id}", TTL_STATUS, payload)
    except Exception:
        pass


async def get_cached_document_status(document_id: str) -> Optional[dict]:
    """Get cached document status. Returns None if not cached."""
    client = _client()
    if not client:
        return None
    try:
        raw = await client.get(f"{KEY_STATUS}{document_id}")
        return json.loads(raw) if raw else None
    except Exception:
        return None


async def invalidate_document_status(document_id: str) -> None:
    """Remove document status from cache (e.g., when document is deleted)."""
    client = _client()
    if not client:
        return
    try:
        await client.delete(f"{KEY_STATUS}{document_id}")
    except Exception:
        pass


# ── Risk Score ────────────────────────────────────────────────────────────────

async def cache_risk_score(document_id: str, score_data: dict) -> None:
    """Cache computed risk score dict."""
    client = _client()
    if not client:
        return
    try:
        await client.setex(f"{KEY_SCORE}{document_id}", TTL_SCORE, json.dumps(score_data))
    except Exception:
        pass


async def get_cached_risk_score(document_id: str) -> Optional[dict]:
    """Return cached risk score or None."""
    client = _client()
    if not client:
        return None
    try:
        raw = await client.get(f"{KEY_SCORE}{document_id}")
        return json.loads(raw) if raw else None
    except Exception:
        return None


# ── Content Hash Deduplication ────────────────────────────────────────────────

async def check_content_hash(content_hash: str) -> Optional[str]:
    """Return cached document_id for a content hash, or None."""
    client = _client()
    if not client:
        return None
    try:
        return await client.get(f"{KEY_DEDUP}{content_hash}")
    except Exception:
        return None


async def set_content_hash(content_hash: str, document_id: str) -> None:
    """Cache the content_hash → document_id mapping."""
    client = _client()
    if not client:
        return
    try:
        await client.setex(f"{KEY_DEDUP}{content_hash}", TTL_DEDUP, document_id)
    except Exception:
        pass


async def delete_content_hash(content_hash: str) -> None:
    """Remove content hash (used when document is deleted)."""
    client = _client()
    if not client:
        return
    try:
        await client.delete(f"{KEY_DEDUP}{content_hash}")
    except Exception:
        pass


# ── Health / Diagnostics ──────────────────────────────────────────────────────

async def redis_health() -> dict:
    """Return Redis health status for the /health endpoint."""
    client = _client()
    if not client:
        return {"status": "disabled", "url": settings.REDIS_URL}
    try:
        await client.ping()
        info = await client.info("server")
        return {
            "status": "healthy",
            "url": settings.REDIS_URL,
            "version": info.get("redis_version", "unknown"),
        }
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}

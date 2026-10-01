"""
WebSocket Connection Manager — Phase 5
========================================
Manages active WebSocket connections keyed by document_id.
Allows the extraction worker to push real-time status updates to connected
frontend clients instead of relying on polling.

Usage:
  - Frontend connects to WS /ws/documents/{document_id}
  - Worker calls ws_manager.broadcast_status(document_id, status) on each stage
  - Frontend receives JSON like: {"document_id": "...", "status": "SCORING", "message": "..."}
"""
import json
import logging
from collections import defaultdict
from typing import DefaultDict, Set

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class WebSocketManager:
    """Thread-safe WebSocket connection manager keyed by document_id."""

    def __init__(self):
        # document_id (str) → set of connected WebSocket objects
        self._connections: DefaultDict[str, Set[WebSocket]] = defaultdict(set)

    async def connect(self, websocket: WebSocket, document_id: str) -> None:
        """Accept and register a new WebSocket connection."""
        await websocket.accept()
        self._connections[document_id].add(websocket)
        logger.info(f"[WS] Client connected for document {document_id}. "
                    f"Total connections: {self._total()}")

    def disconnect(self, websocket: WebSocket, document_id: str) -> None:
        """Remove a disconnected WebSocket."""
        self._connections[document_id].discard(websocket)
        if not self._connections[document_id]:
            del self._connections[document_id]
        logger.info(f"[WS] Client disconnected from document {document_id}.")

    async def broadcast_status(
        self,
        document_id: str,
        status: str,
        message: str = "",
        extra: dict = None,
    ) -> None:
        """
        Send a status update to all clients watching the given document_id.
        Silently removes any disconnected clients encountered.
        """
        payload = json.dumps({
            "document_id": document_id,
            "status": status,
            "message": message,
            **(extra or {}),
        })

        dead = set()
        for ws in list(self._connections.get(document_id, [])):
            try:
                await ws.send_text(payload)
            except Exception:
                dead.add(ws)

        for ws in dead:
            self._connections[document_id].discard(ws)

    def _total(self) -> int:
        return sum(len(s) for s in self._connections.values())


# Singleton instance — imported by routers and workers
ws_manager = WebSocketManager()

"""Pydantic schemas for risk score API responses."""
from __future__ import annotations

from datetime import datetime
from typing import Any, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class FactorBreakdownItem(BaseModel):
    factor: str
    score: float
    max: float
    pct: float
    explanation: str


class RiskScoreResponse(BaseModel):
    id: UUID
    document_id: UUID
    overall_score: float = Field(..., ge=0, le=100, description="0–100 creditworthiness score")
    risk_band: str = Field(..., description="LOW | MEDIUM | HIGH")
    factor_breakdown: Optional[List[FactorBreakdownItem]] = None
    narrative_summary: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class ScoreDocumentResponse(BaseModel):
    """Combined document status + risk score."""
    document_id: UUID
    document_status: str
    risk_score: Optional[RiskScoreResponse] = None
    message: str

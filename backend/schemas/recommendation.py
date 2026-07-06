"""Pydantic schemas for loan recommendation API responses."""
from __future__ import annotations

from datetime import datetime
from typing import Any, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class SchemeDetails(BaseModel):
    max_loan_amount_inr: Optional[float] = None
    interest_rate_range: Optional[str] = None
    tenure: Optional[str] = None
    collateral_required: Optional[bool] = None


class LoanRecommendationResponse(BaseModel):
    id: UUID
    document_id: UUID
    scheme_name: str
    scheme_type: str
    issuing_body: Optional[str] = None
    eligibility_score: Optional[float] = Field(None, ge=0.0, le=1.0)
    rank: int
    reasoning: Optional[str] = None
    scheme_details: Optional[SchemeDetails] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class RecommendationListResponse(BaseModel):
    """Combined document status + list of recommendations."""
    document_id: UUID
    document_status: str
    recommendations: List[LoanRecommendationResponse] = []
    message: str

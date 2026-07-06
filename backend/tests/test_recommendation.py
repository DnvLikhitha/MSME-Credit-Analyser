"""
Tests for Phase 4 — Loan Scheme Recommendation Engine
"""
from unittest.mock import patch, AsyncMock
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.database import SessionLocal
from backend.models.document import Document
from backend.models.extracted_metrics import ExtractedMetrics
from backend.models.loan_recommendation import LoanRecommendation
from backend.models.risk_score import RiskScore
from backend.models.user import User
from backend.services.recommendation import generate_and_save_recommendations

client = TestClient(app)

MOCK_RECOMMENDATION_DATA = [
    {
        "scheme_name": "MUDRA (Kishore)",
        "scheme_type": "MUDRA",
        "issuing_body": "Ministry of MSME",
        "eligibility_score": 0.9,
        "reasoning": "Good fit for expansion with current metrics.",
        "scheme_details": {
            "max_loan_amount_inr": 500000,
            "collateral_required": False
        }
    },
    {
        "scheme_name": "CGTMSE",
        "scheme_type": "CGTMSE",
        "issuing_body": "SIDBI",
        "eligibility_score": 0.75,
        "reasoning": "Eligible for collateral-free guarantee.",
        "scheme_details": {
            "max_loan_amount_inr": 50000000,
            "collateral_required": False
        }
    }
]

@pytest.fixture
def test_db():
    """Provides a database session for testing."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@pytest.fixture
def mock_db_data(test_db):
    """Creates a user, document, metrics, and risk score in the test database."""
    unique_email = f"test_rec_{uuid4()}@example.com"
    user = User(
        id=uuid4(),
        email=unique_email,
        hashed_password="hashed",
        full_name="Rec Tester"
    )
    test_db.add(user)
    
    doc = Document(
        id=uuid4(),
        user_id=user.id,
        filename="test_rec.pdf",
        original_filename="test_rec.pdf",
        file_path="/fake/path",
        status="COMPLETE"
    )
    test_db.add(doc)
    
    metrics = ExtractedMetrics(
        id=uuid4(),
        document_id=doc.id,
        annual_revenue=1500000,
        net_profit_margin=12.5
    )
    test_db.add(metrics)
    
    risk_score = RiskScore(
        id=uuid4(),
        document_id=doc.id,
        overall_score=75.0,
        risk_band="LOW",
        factor_breakdown=[]
    )
    test_db.add(risk_score)
    
    test_db.commit()
    return user, doc, metrics, risk_score


@pytest.mark.asyncio
@patch("backend.services.recommendation.match_loan_schemes", new_callable=AsyncMock)
async def test_generate_and_save_recommendations(mock_match, test_db, mock_db_data):
    # Setup mock return value
    mock_match.return_value = MOCK_RECOMMENDATION_DATA
    
    user, doc, metrics, risk_score = mock_db_data
    
    # Run service
    saved_recs = await generate_and_save_recommendations(test_db, doc.id, metrics, risk_score)
    
    # Verify mock was called
    mock_match.assert_called_once()
    
    # Verify DB persistence
    assert len(saved_recs) == 2
    assert saved_recs[0].scheme_name == "MUDRA (Kishore)"
    assert saved_recs[0].rank == 1
    assert saved_recs[0].eligibility_score == 0.9
    
    assert saved_recs[1].scheme_name == "CGTMSE"
    assert saved_recs[1].rank == 2
    
    # Verify DB query works
    db_recs = test_db.query(LoanRecommendation).filter_by(document_id=doc.id).all()
    assert len(db_recs) == 2


@pytest.mark.asyncio
async def test_get_recommendations_endpoint(test_db, mock_db_data):
    user, doc, metrics, risk_score = mock_db_data
    
    # Manually insert the mock recommendations into the DB
    rec1 = LoanRecommendation(
        document_id=doc.id, scheme_name="MUDRA", scheme_type="MUDRA", rank=1
    )
    rec2 = LoanRecommendation(
        document_id=doc.id, scheme_name="CGTMSE", scheme_type="CGTMSE", rank=2
    )
    test_db.add_all([rec1, rec2])
    test_db.commit()
    
    # Override dependencies
    from backend.database import get_db
    from backend.routers.auth import get_current_user
    
    app.dependency_overrides[get_db] = lambda: test_db
    app.dependency_overrides[get_current_user] = lambda: user
    
    response = client.get(f"/documents/{doc.id}/recommendations")
    
    app.dependency_overrides.clear()
    
    assert response.status_code == 200
    data = response.json()
    
    assert data["document_id"] == str(doc.id)
    assert len(data["recommendations"]) == 2
    assert data["recommendations"][0]["scheme_name"] == "MUDRA"

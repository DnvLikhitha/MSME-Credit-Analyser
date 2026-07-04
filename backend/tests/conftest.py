import os
import pytest
from sqlalchemy import create_engine

# Must set before importing anything from backend
os.environ["DATABASE_URL"] = "sqlite:///./test.db"
os.environ["SECRET_KEY"] = "test-secret-key-for-testing-only"

from backend.database import Base, engine

@pytest.fixture(scope="session", autouse=True)
def setup_test_db():
    """Create all tables in the test SQLite database before running tests."""
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)
    
    # Remove the sqlite file after tests complete
    if os.path.exists("./test.db"):
        try:
            os.remove("./test.db")
        except Exception:
            pass

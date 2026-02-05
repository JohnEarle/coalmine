"""
Integration tests for canary lifecycle operations.

These tests verify create, rotate, and delete canary workflows
with mocked cloud providers.
"""
import pytest
import os
from unittest.mock import MagicMock, patch
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.models import Base, CanaryResource, ResourceHistory, ResourceType, ResourceStatus
from src import tasks

# Use SQLite for testing
TEST_DATABASE_URL = "sqlite:///./test.db"
engine = create_engine(TEST_DATABASE_URL)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

@pytest.fixture
def db():
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.mark.integration
@patch("src.tasks.canary.SessionLocal")
@patch("src.tasks.canary.TofuManager")
def test_create_canary(MockTofuManager, MockSessionLocal, db):
    # Prevent the task from closing the session so we can inspect it
    db.close = MagicMock()
    MockSessionLocal.return_value = db
    
    mock_manager = MockTofuManager.return_value
    mock_manager.init.return_value = "Init Success"
    mock_manager.apply.return_value = "Apply Success"
    
    # Run the task synchronously (bypassing celery)
    tasks.create_canary("test-canary", "AWS_BUCKET", 3600)
    
    # Verify DB
    canary = db.query(CanaryResource).filter_by(name="test-canary").first()
    assert canary is not None
    assert canary.resource_type == ResourceType.AWS_BUCKET
    assert canary.status == ResourceStatus.ACTIVE
    
    # Verify Tofu calls
    mock_manager.init.assert_called_once()
    mock_manager.apply.assert_called_once()
    
    # Verify History
    history = db.query(ResourceHistory).filter_by(resource_id=canary.id).first()
    assert history is not None
    assert history.action.value == "CREATE"

@pytest.mark.integration
@patch("src.tasks.canary.SessionLocal")
@patch("src.tasks.canary.TofuManager")
def test_rotate_canary(MockTofuManager, MockSessionLocal, db):
    # Prevent the task from closing the session so we can inspect it
    db.close = MagicMock()
    MockSessionLocal.return_value = db
    
    # Pre-seed a canary
    canary = CanaryResource(
        name="rotate-me", 
        resource_type=ResourceType.GCP_BUCKET,
        interval_seconds=300, 
        status=ResourceStatus.ACTIVE
    )
    db.add(canary)
    db.commit()
    resource_id = str(canary.id) # Capture ID before potential session detach issues
    
    mock_manager = MockTofuManager.return_value
    mock_manager.apply.return_value = "Apply Success (Rotated)"

    # Run rotation
    tasks.rotate_canary(resource_id)
    
    # Verify DB update
    db.refresh(canary)
    assert canary.name == "rotate-me" # Logical name should be unchanged
    assert "rotate-me-" in canary.current_resource_id # Physical name should have suffix
    
    # Verify History
    history = db.query(ResourceHistory).filter_by(resource_id=canary.id, action=tasks.ActionType.ROTATE).first()
    assert history is not None

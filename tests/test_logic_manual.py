import pytest
import uuid
from unittest.mock import MagicMock, patch
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.models import Base, CanaryResource, ResourceHistory, ResourceType, ResourceStatus
from src import tasks

# Use SQLite for testing
TEST_DATABASE_URL = "sqlite:///./test_manual.db"
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
        # cleanup
        Base.metadata.drop_all(bind=engine)

@patch("src.tasks.SessionLocal")
@patch("src.tasks.TofuManager")
def test_rotate_canary_specific_name(MockTofuManager, MockSessionLocal, db):
    # Prevent the task from closing the session
    db.close = MagicMock()
    MockSessionLocal.return_value = db
    
    # Pre-seed a canary
    canary = CanaryResource(
        name="tmp_bk_1",
        resource_type=ResourceType.AWS_BUCKET,
        current_resource_id="tmp_bk_1-20250101",
        interval_seconds=3600,
        status=ResourceStatus.ACTIVE
    )
    db.add(canary)
    db.commit()
    resource_id = str(canary.id) 
    
    mock_manager = MockTofuManager.return_value
    mock_manager.apply.return_value = "Apply Success (Renamed)"

    # Run rotation with explicit name
    tasks.rotate_canary(resource_id, new_name="prod_test_3")
    
    # Verify DB update
    db.refresh(canary)
    assert canary.name == "prod_test_3"
    assert canary.current_resource_id == "prod_test_3"
    
    # Verify History
    history = db.query(ResourceHistory).filter_by(resource_id=canary.id, action=tasks.ActionType.ROTATE).order_by(ResourceHistory.timestamp.desc()).first()
    assert history is not None
    assert history.details['new_physical_name'] == "prod_test_3"

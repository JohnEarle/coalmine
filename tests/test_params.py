import pytest
import uuid
import json
from unittest.mock import MagicMock, patch
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.models import Base, CanaryResource, ResourceHistory, ResourceType
from src import tasks

# Use SQLite for testing
TEST_DATABASE_URL = "sqlite:///./test_params.db"
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
        Base.metadata.drop_all(bind=engine)

@patch("src.tasks.SessionLocal")
@patch("src.tasks.TofuManager")
def test_params_persistence_and_usage(MockTofuManager, MockSessionLocal, db):
    db.close = MagicMock()
    MockSessionLocal.return_value = db
    
    mock_manager = MockTofuManager.return_value
    mock_manager.init.return_value = "Init"
    mock_manager.apply.return_value = "Apply"

    params = {"versioning": "true", "custom_tag": "abc"}
    
    # 1. Test Creation
    tasks.create_canary("param-canary", "AWS_BUCKET", 3600, module_params=params)
    
    # Verify DB
    canary = db.query(CanaryResource).filter_by(name="param-canary").first()
    assert canary is not None
    assert canary.module_params == params
    
    # Verify Apply was called with kwargs merging the params
    # We need to check the call args of apply
    # apply(vars_dict, env=...)
    name, args, kwargs = mock_manager.apply.mock_calls[0]
    vars_dict = args[0]
    assert vars_dict["versioning"] == "true"
    assert vars_dict["custom_tag"] == "abc"

    # 2. Test Rotation (Reuse params)
    resource_id = str(canary.id)
    mock_manager.reset_mock()
    
    tasks.rotate_canary(resource_id)
    
    # Verify params reused in rotation apply
    name, args, kwargs = mock_manager.apply.mock_calls[0]
    vars_dict = args[0]
    assert vars_dict["versioning"] == "true"
    assert vars_dict["custom_tag"] == "abc"

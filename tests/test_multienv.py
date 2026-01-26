import pytest
import uuid
from unittest.mock import MagicMock, patch
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.models import Base, CanaryResource, ResourceHistory, ResourceType, ResourceStatus, CloudEnvironment
from src import tasks
import os

# Use SQLite for testing
TEST_DATABASE_URL = "sqlite:///./test_multienv.db"
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
def test_create_canary_with_environment(MockTofuManager, MockSessionLocal, db):
    db.close = MagicMock()
    MockSessionLocal.return_value = db
    
    # Create Environment
    env = CloudEnvironment(
        name="Test AWS",
        provider_type="AWS",
        credentials={"AWS_ACCESS_KEY_ID": "test-key", "AWS_SECRET_ACCESS_KEY": "test-secret"},
        config={"region": "us-west-2"}
    )
    db.add(env)
    db.commit()
    env_id = str(env.id)

    mock_manager = MockTofuManager.return_value
    mock_manager.init.return_value = "Init Success"
    mock_manager.apply.return_value = "Apply Success"
    
    # Run task
    tasks.create_canary("env-canary", "AWS_BUCKET", 3600, env_id)
    
    # Verify DB
    canary = db.query(CanaryResource).filter_by(name="env-canary").first()
    assert canary is not None
    assert str(canary.environment_id) == env_id
    
    # Verify Tofu Calls
    # Check that init was called with env vars from credentials
    # Inspect arguments of last call to init
    name, args, kwargs = mock_manager.init.mock_calls[0]
    passed_env = kwargs.get('env')
    assert passed_env["AWS_ACCESS_KEY_ID"] == "test-key"
    
    # Check that apply was called with config and env
    name, args, kwargs = mock_manager.apply.mock_calls[0]
    passed_vars = args[0]
    passed_env = kwargs.get('env')
    
    assert passed_vars["region"] == "us-west-2"
    assert passed_env["AWS_SECRET_ACCESS_KEY"] == "test-secret"

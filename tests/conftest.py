import pytest
import os
import uuid
import sys
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Add src to path to ensure imports work
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from src.models import Base, CloudEnvironment, LoggingResource, LoggingProviderType, ResourceStatus

# =============================================================================
# Unit Test Fixtures (In-Memory SQLite - Fast, Isolated)
# =============================================================================

@pytest.fixture
def isolated_db():
    """
    Creates a fresh in-memory SQLite database for each test.
    Use this for fast, isolated unit tests that don't need real DB.
    """
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


# =============================================================================
# Integration Test Fixtures (PostgreSQL - Shared with App)
# =============================================================================

# Use the same DB URL as the app
DATABASE_URL = os.getenv("DATABASE_URL")

@pytest.fixture(scope="session")
def engine():
    return create_engine(DATABASE_URL)

@pytest.fixture(scope="session")
def tables(engine):
    # Ensure tables exist (fast check)
    Base.metadata.create_all(bind=engine)
    yield
    # We don't drop tables to preserve dev state

@pytest.fixture
def db_session(engine, tables):
    """Returns a session for the test."""
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()

@pytest.fixture
def test_env_aws(db_session):
    """Ensures a test AWS environment exists and is cleaned up."""
    env_name = "e2e-test-aws"
    env = db_session.query(CloudEnvironment).filter_by(name=env_name).first()
    
    clean_up = False
    if not env:
        clean_up = True
        env = CloudEnvironment(
            name=env_name,
            provider_type="AWS",
            credentials={
                "AWS_ACCESS_KEY_ID": os.getenv("AWS_ACCESS_KEY_ID", "test-key"),
                "AWS_SECRET_ACCESS_KEY": os.getenv("AWS_SECRET_ACCESS_KEY", "test-secret"),
                "AWS_REGION": os.getenv("AWS_DEFAULT_REGION", "us-east-1")
            },
            config={"region": "us-east-1"}
        )
        db_session.add(env)
        db_session.commit()
    
    yield env
    
    # Refresh to ensure we have latest state/association awareness before delete
    # But usually good practice to clean up what we created.
    # For E2E, we might want to leave it if it fails? No, clean up.
    if clean_up:
        # Re-query to avoid detached instance issues
        env_to_del = db_session.query(CloudEnvironment).filter_by(name=env_name).first()
        if env_to_del:
            db_session.delete(env_to_del)
            db_session.commit()

@pytest.fixture
def test_logging_resource(db_session, test_env_aws):
    """Ensures a test logging resource exists."""
    log_name = "e2e-test-logging"
    log_res = db_session.query(LoggingResource).filter_by(name=log_name).first()
    
    clean_up = False
    if not log_res:
        clean_up = True
        log_res = LoggingResource(
            name=log_name,
            provider_type=LoggingProviderType.AWS_CLOUDTRAIL,
            environment_id=test_env_aws.id,
            status=ResourceStatus.ACTIVE,
            configuration={"trail_name": "test-trail"}
        )
        db_session.add(log_res)
        db_session.commit()
        
    yield log_res
    
    if clean_up:
        log_to_del = db_session.query(LoggingResource).filter_by(name=log_name).first()
        if log_to_del:
            db_session.delete(log_to_del)
            db_session.commit()

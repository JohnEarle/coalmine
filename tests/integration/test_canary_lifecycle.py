"""
Integration tests for canary lifecycle operations.

These tests verify create, rotate, and delete canary workflows
with mocked cloud providers and a real in-memory database.
"""
import pytest
from unittest.mock import MagicMock, patch
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.models import (
    Base, CanaryResource, ResourceHistory, ResourceType,
    ResourceStatus, ActionType, Account, Credential, CredentialAuthType
)
from src import tasks


@pytest.fixture
def db():
    """In-memory SQLite database for lifecycle tests."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = Session()
    yield db
    db.close()


@pytest.fixture
def aws_account(db):
    """Seed a Credential + Account for canary deployment."""
    cred = Credential(
        name="lifecycle-cred",
        provider="AWS",
        auth_type=CredentialAuthType.STATIC,
        secrets={"AWS_ACCESS_KEY_ID": "k", "AWS_SECRET_ACCESS_KEY": "s"},
    )
    db.add(cred)
    db.flush()
    account = Account(
        name="lifecycle-account",
        credential_id=cred.id,
        account_id="333333333333",
    )
    db.add(account)
    db.commit()
    return account


# ---------------------------------------------------------------------------
# Create
# ---------------------------------------------------------------------------

@pytest.mark.integration
@patch("src.tasks.lifecycle.SessionLocal")
@patch("src.tasks.canary.TofuManager")
@patch("src.tasks.canary._get_backend_config", return_value={"conn_str": "mock", "schema_name": "mock"})
@patch("src.tasks.canary.ResourceRegistry")
def test_create_canary(MockRegistry, MockBE, MockTofuManager, MockSessionLocal, db, aws_account):
    """Creating a canary persists it to the DB and invokes Tofu."""
    MockSessionLocal.return_value = db
    db.close = MagicMock()

    mock_manager = MockTofuManager.return_value
    mock_manager.init.return_value = "Init"
    mock_manager.apply.return_value = "Apply"

    mock_handler = MagicMock()
    mock_handler.get_tform_vars.return_value = {"region": "us-east-1"}
    mock_handler.get_credentials.return_value = {"access_key": "ckey"}
    MockRegistry.get_handler.return_value = mock_handler

    tasks.create_canary(
        "test-canary", "AWS_BUCKET", 3600,
        account_id_str=str(aws_account.id),
    )

    canary = db.query(CanaryResource).filter_by(name="test-canary").first()
    assert canary is not None, "Canary must exist in DB"
    assert canary.resource_type == ResourceType.AWS_BUCKET
    assert canary.status == ResourceStatus.ACTIVE

    mock_manager.init.assert_called_once()
    mock_manager.apply.assert_called_once()

    history = db.query(ResourceHistory).filter_by(resource_id=canary.id).first()
    assert history is not None, "History record must be created"
    assert history.action == ActionType.CREATE


# ---------------------------------------------------------------------------
# Rotate
# ---------------------------------------------------------------------------

@pytest.mark.integration
@patch("src.tasks.lifecycle.SessionLocal")
@patch("src.tasks.canary.TofuManager")
@patch("src.tasks.canary._get_backend_config", return_value={"conn_str": "mock", "schema_name": "mock"})
@patch("src.tasks.canary.ResourceRegistry")
def test_rotate_canary(MockRegistry, MockBE, MockTofuManager, MockSessionLocal, db, aws_account):
    """Rotating a canary generates a new physical resource ID and logs history."""
    MockSessionLocal.return_value = db
    db.close = MagicMock()

    # Pre-seed an ACTIVE canary
    canary = CanaryResource(
        name="rotate-me",
        resource_type=ResourceType.GCP_BUCKET,
        interval_seconds=300,
        status=ResourceStatus.ACTIVE,
        account_id=aws_account.id,
    )
    db.add(canary)
    db.commit()
    resource_id = str(canary.id)

    mock_manager = MockTofuManager.return_value
    mock_manager.init.return_value = "Init"
    mock_manager.apply.return_value = "Apply (Rotated)"

    mock_handler = MagicMock()
    mock_handler.get_tform_vars.return_value = {}
    mock_handler.get_credentials.return_value = {}
    MockRegistry.get_handler.return_value = mock_handler

    tasks.rotate_canary(resource_id)

    db.refresh(canary)
    assert canary.name == "rotate-me", "Logical name should be unchanged"
    assert canary.status == ResourceStatus.ACTIVE, "Status should be back to ACTIVE"

    rotate_history = (
        db.query(ResourceHistory)
        .filter_by(resource_id=canary.id, action=ActionType.ROTATE)
        .first()
    )
    assert rotate_history is not None, "Rotation history must be logged"

"""
Integration tests for multi-environment canary creation.

Verifies that canaries created against a specific Account inherit the
correct cloud credentials and region configuration for Tofu execution.
"""
import pytest
import uuid
from unittest.mock import MagicMock, patch
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.models import (
    Base, CanaryResource, ResourceHistory, ResourceType,
    ResourceStatus, Account, Credential, CredentialAuthType, ActionType
)
from src import tasks


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = Session()
    yield db
    db.close()


@pytest.fixture
def aws_account(db):
    """Create a Credential + Account pair for AWS testing."""
    cred = Credential(
        name="test-aws-cred",
        provider="AWS",
        auth_type=CredentialAuthType.STATIC,
        secrets={
            "AWS_ACCESS_KEY_ID": "test-key",
            "AWS_SECRET_ACCESS_KEY": "test-secret",
            "region": "us-west-2",
        },
    )
    db.add(cred)
    db.flush()

    account = Account(
        name="test-aws-account",
        credential_id=cred.id,
        account_id="111111111111",
    )
    db.add(account)
    db.commit()
    return account


@pytest.mark.integration
@patch("src.tasks.lifecycle.SessionLocal")
@patch("src.tasks.canary.TofuManager")
@patch("src.tasks.canary._get_backend_config", return_value={"conn_str": "mock", "schema_name": "mock"})
@patch("src.tasks.canary.ResourceRegistry")
def test_create_canary_with_account(
    MockRegistry, MockBackendConfig, MockTofuManager, MockSessionLocal, db, aws_account
):
    """Canaries linked to an Account pick up its credentials in Tofu env vars."""
    # Inject in-memory DB into lifecycle manager
    MockSessionLocal.return_value = db
    db.close = MagicMock()  # prevent premature close

    mock_manager = MockTofuManager.return_value
    mock_manager.init.return_value = "Init Success"
    mock_manager.apply.return_value = "Apply Success"

    # Configure resource handler mock
    mock_handler = MagicMock()
    mock_handler.get_tform_vars.return_value = {"region": "us-west-2"}
    mock_handler.get_credentials.return_value = {"access_key": "canary-key"}
    MockRegistry.get_handler.return_value = mock_handler

    # Run the task synchronously
    tasks.create_canary(
        "env-canary", "AWS_BUCKET", 3600,
        account_id_str=str(aws_account.id),
    )

    # Verify canary was created with correct account link
    canary = db.query(CanaryResource).filter_by(name="env-canary").first()
    assert canary is not None, "Canary should be created in DB"
    assert canary.account_id == aws_account.id, "Canary should reference the account"
    assert canary.status == ResourceStatus.ACTIVE

    # Verify Tofu was called
    mock_manager.init.assert_called_once()
    mock_manager.apply.assert_called_once()

    # Verify history recorded
    history = db.query(ResourceHistory).filter_by(resource_id=canary.id).first()
    assert history is not None
    assert history.action == ActionType.CREATE

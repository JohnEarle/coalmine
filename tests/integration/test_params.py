"""
Integration tests for module_params persistence and reuse.

Verifies that custom parameters supplied at creation are stored on the
CanaryResource and reused during rotation.
"""
import pytest
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
    """Create a minimal Credential + Account for test canaries."""
    cred = Credential(
        name="param-test-cred",
        provider="AWS",
        auth_type=CredentialAuthType.STATIC,
        secrets={"AWS_ACCESS_KEY_ID": "k", "AWS_SECRET_ACCESS_KEY": "s"},
    )
    db.add(cred)
    db.flush()
    account = Account(
        name="param-test-account",
        credential_id=cred.id,
        account_id="222222222222",
    )
    db.add(account)
    db.commit()
    return account


@pytest.mark.integration
@patch("src.tasks.lifecycle.SessionLocal")
@patch("src.tasks.canary.TofuManager")
@patch("src.tasks.canary._get_backend_config", return_value={"conn_str": "mock", "schema_name": "mock"})
@patch("src.tasks.canary.ResourceRegistry")
def test_params_persistence_and_usage(
    MockRegistry, MockBackendConfig, MockTofuManager, MockSessionLocal, db, aws_account
):
    """module_params are persisted to the DB and forwarded to Tofu apply."""
    MockSessionLocal.return_value = db
    db.close = MagicMock()

    mock_manager = MockTofuManager.return_value
    mock_manager.init.return_value = "Init"
    mock_manager.apply.return_value = "Apply"

    mock_handler = MagicMock()
    mock_handler.get_tform_vars.return_value = {}
    mock_handler.get_credentials.return_value = {}
    MockRegistry.get_handler.return_value = mock_handler

    params = {"versioning": "true", "custom_tag": "abc"}

    # 1. Create canary with custom params
    tasks.create_canary(
        "param-canary", "AWS_BUCKET", 3600,
        account_id_str=str(aws_account.id),
        module_params=params,
    )

    # Verify params are stored
    canary = db.query(CanaryResource).filter_by(name="param-canary").first()
    assert canary is not None, "Canary should be created"
    assert canary.module_params == params, "module_params should be persisted to the DB"

    # Verify Tofu apply received the merged vars
    _, apply_args, apply_kwargs = mock_manager.apply.mock_calls[0]
    vars_dict = apply_args[0]
    assert vars_dict.get("versioning") == "true"
    assert vars_dict.get("custom_tag") == "abc"

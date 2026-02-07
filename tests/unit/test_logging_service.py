"""
Stability tests for LoggingResourceService CRUD operations.

Create mocks the Celery task since it's async.
"""
import pytest
from unittest.mock import patch, MagicMock
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.models import (
    Base, LoggingResource, LoggingProviderType, Account, Credential,
    CredentialAuthType, ResourceStatus
)
from src.services.logging_resources import LoggingResourceService


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


@pytest.fixture
def seed(db):
    cred = Credential(
        name="test-cred", provider="AWS",
        auth_type=CredentialAuthType.STATIC, secrets={},
    )
    db.add(cred)
    db.flush()
    acct = Account(name="test-acct", credential_id=cred.id, account_id="111111111111")
    db.add(acct)
    db.flush()
    lr = LoggingResource(
        name="existing-trail",
        provider_type=LoggingProviderType.AWS_CLOUDTRAIL,
        account_id=acct.id,
        status=ResourceStatus.ACTIVE,
    )
    db.add(lr)
    db.commit()
    return {"cred": cred, "acct": acct, "lr": lr}


# ---------------------------------------------------------------------------

class TestLoggingResourceCreate:
    @patch("src.tasks.create_logging_resource")
    def test_create_queues_task(self, mock_task, db, seed):
        mock_task.delay.return_value.id = "test-task-id"
        svc = LoggingResourceService(db=db)
        result = svc.create(
            name="new-trail",
            provider_type="AWS_CLOUDTRAIL",
            account_id=str(seed["acct"].id),
        )
        assert result.success
        mock_task.delay.assert_called_once()

    def test_create_invalid_provider_fails(self, db, seed):
        svc = LoggingResourceService(db=db)
        result = svc.create(
            name="bad",
            provider_type="INVALID_TYPE",
            account_id=str(seed["acct"].id),
        )
        assert not result.success

    def test_create_bad_account_fails(self, db):
        svc = LoggingResourceService(db=db)
        result = svc.create(
            name="orphan",
            provider_type="AWS_CLOUDTRAIL",
            account_id="nonexistent",
        )
        assert not result.success


class TestLoggingResourceList:
    def test_list_empty(self, db):
        svc = LoggingResourceService(db=db)
        result = svc.list()
        assert result.total == 0

    def test_list_returns_all(self, db, seed):
        svc = LoggingResourceService(db=db)
        result = svc.list()
        assert result.total == 1


class TestLoggingResourceGet:
    def test_get_by_name(self, db, seed):
        svc = LoggingResourceService(db=db)
        result = svc.get("existing-trail")
        assert result.success

    def test_get_by_uuid(self, db, seed):
        svc = LoggingResourceService(db=db)
        result = svc.get(str(seed["lr"].id))
        assert result.success

    def test_get_nonexistent(self, db):
        svc = LoggingResourceService(db=db)
        result = svc.get("ghost")
        assert not result.success

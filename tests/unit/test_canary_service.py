"""
Stability tests for CanaryService CRUD operations.

Create/delete mock the Celery task since they're async.
List/get/credentials tested with real in-memory DB.
"""
import pytest
from unittest.mock import patch, MagicMock
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.models import (
    Base, CanaryResource, Account, Credential,
    ResourceType, ResourceStatus, CredentialAuthType
)
from src.services.canaries import CanaryService


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

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
    canary = CanaryResource(
        name="test-canary", resource_type=ResourceType.AWS_BUCKET,
        account_id=acct.id, status=ResourceStatus.ACTIVE,
        canary_credentials={"aws_access_key_id": "AKIAEXAMPLE"},
    )
    db.add(canary)
    db.commit()
    return {"cred": cred, "acct": acct, "canary": canary}


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestCanaryCreate:
    @patch("src.tasks.create_canary")
    def test_create_queues_task(self, mock_task, db, seed):
        mock_result = MagicMock()
        mock_result.id = "fake-task-id-create"
        mock_task.delay = MagicMock(return_value=mock_result)
        svc = CanaryService(db=db)
        result = svc.create(
            name="new-canary",
            resource_type="AWS_BUCKET",
            account_id=str(seed["acct"].id),
            logging_id="some-logging-id",
        )
        assert result.success
        assert result.data["status"] == "queued"
        assert result.data["task_id"] == "fake-task-id-create"

    def test_create_bad_account_fails(self, db):
        svc = CanaryService(db=db)
        result = svc.create(
            name="orphan", resource_type="AWS_BUCKET",
            account_id="nonexistent", logging_id="x",
        )
        assert not result.success


class TestCanaryList:
    def test_list_empty(self, db):
        svc = CanaryService(db=db)
        result = svc.list()
        assert result.total == 0

    def test_list_returns_all(self, db, seed):
        svc = CanaryService(db=db)
        result = svc.list()
        assert result.total == 1


class TestCanaryGet:
    def test_get_by_name(self, db, seed):
        svc = CanaryService(db=db)
        result = svc.get("test-canary")
        assert result.success
        assert result.data.name == "test-canary"

    def test_get_by_uuid(self, db, seed):
        svc = CanaryService(db=db)
        result = svc.get(str(seed["canary"].id))
        assert result.success

    def test_get_nonexistent(self, db):
        svc = CanaryService(db=db)
        result = svc.get("ghost")
        assert not result.success


class TestCanaryDelete:
    @patch("src.tasks.delete_canary")
    def test_delete_queues_task(self, mock_task, db, seed):
        mock_result = MagicMock()
        mock_result.id = "fake-task-id-delete"
        mock_task.delay = MagicMock(return_value=mock_result)
        svc = CanaryService(db=db)
        result = svc.delete("test-canary")
        assert result.success
        assert result.data["status"] == "queued"
        assert result.data["task_id"] == "fake-task-id-delete"

    def test_delete_nonexistent(self, db):
        svc = CanaryService(db=db)
        result = svc.delete("ghost")
        assert not result.success


class TestCanaryCredentials:
    def test_get_credentials(self, db, seed):
        svc = CanaryService(db=db)
        result = svc.get_credentials("test-canary")
        assert result.success
        assert "aws_access_key_id" in result.data["credentials"]

    def test_get_credentials_nonexistent(self, db):
        svc = CanaryService(db=db)
        result = svc.get_credentials("ghost")
        assert not result.success

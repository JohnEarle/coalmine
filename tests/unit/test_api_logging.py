"""
Stability tests for Logging Resource API routes.

Verifies the REST contract for logging resource CRUD operations.
"""
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from src.api.main import app
from src.api.auth import SessionAuth
from src.models import (
    Base, LoggingResource, LoggingProviderType, Account, Credential,
    CredentialAuthType, ResourceStatus
)


# --- Fixtures ----------------------------------------------------------------

_mock_auth = SessionAuth(
    username="test", role="admin",
    permissions=["read", "write", "delete", "admin"],
    scopes=["all"],
)


@pytest.fixture
def engine():
    eng = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=eng)
    return eng


@pytest.fixture
def client(engine):
    TestSession = sessionmaker(bind=engine)
    with patch("src.services.base.SessionLocal", TestSession), \
         patch("src.api.auth.get_current_auth", new_callable=AsyncMock, return_value=_mock_auth):
        yield TestClient(app, raise_server_exceptions=False)


@pytest.fixture
def seed_account(engine):
    Session = sessionmaker(bind=engine)
    db = Session()
    cred = Credential(name="log-api-cred", provider="AWS",
                      auth_type=CredentialAuthType.STATIC, secrets={})
    db.add(cred)
    db.flush()
    acct = Account(name="log-api-acct", credential_id=cred.id, account_id="111")
    db.add(acct)
    db.commit()
    db.refresh(acct)
    yield acct
    db.close()


@pytest.fixture
def seed_logging_resource(engine, seed_account):
    Session = sessionmaker(bind=engine)
    db = Session()
    lr = LoggingResource(
        name="existing-trail",
        provider_type=LoggingProviderType.AWS_CLOUDTRAIL,
        account_id=seed_account.id,
        status=ResourceStatus.ACTIVE,
    )
    db.add(lr)
    db.commit()
    db.refresh(lr)
    yield lr
    db.close()


# --- Tests --------------------------------------------------------------------

class TestCreateLoggingResource:
    @patch("src.tasks.create_logging_resource")
    def test_create_success(self, mock_task, client, seed_account):
        mock_task.delay.return_value.id = "test-task-id"
        resp = client.post("/api/v1/logging-resources/", json={
            "name": "new-trail",
            "provider_type": "AWS_CLOUDTRAIL",
            "account_id": str(seed_account.id),
        })
        assert resp.status_code == 200

    def test_create_bad_provider(self, client, seed_account):
        resp = client.post("/api/v1/logging-resources/", json={
            "name": "bad",
            "provider_type": "INVALID",
            "account_id": str(seed_account.id),
        })
        assert resp.status_code == 400


class TestListLoggingResources:
    def test_list_empty(self, client):
        resp = client.get("/api/v1/logging-resources/")
        assert resp.status_code == 200
        assert resp.json()["total"] == 0

    def test_list_with_data(self, client, seed_logging_resource):
        resp = client.get("/api/v1/logging-resources/")
        assert resp.status_code == 200
        assert resp.json()["total"] >= 1


class TestGetLoggingResource:
    def test_get_by_uuid(self, client, seed_logging_resource):
        resp = client.get(f"/api/v1/logging-resources/{seed_logging_resource.id}")
        assert resp.status_code == 200
        assert resp.json()["name"] == "existing-trail"

    def test_get_nonexistent(self, client):
        resp = client.get("/api/v1/logging-resources/ghost")
        assert resp.status_code == 404

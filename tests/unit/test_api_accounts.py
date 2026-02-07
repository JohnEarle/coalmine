"""
Stability tests for Account API routes.

Verifies the REST contract for account CRUD operations using FastAPI's TestClient.
Auth is bypassed by patching get_current_auth at the module level.
Uses StaticPool to share the SQLite in-memory DB across threads.
"""
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from src.api.main import app
from src.api.auth import SessionAuth
from src.models import Base, Account, Credential, CredentialAuthType


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
    """TestClient that bypasses auth and uses in-memory DB."""
    TestSession = sessionmaker(bind=engine)
    with patch("src.services.base.SessionLocal", TestSession), \
         patch("src.api.auth.get_current_auth", new_callable=AsyncMock, return_value=_mock_auth):
        yield TestClient(app, raise_server_exceptions=False)


@pytest.fixture
def seed_credential(engine):
    Session = sessionmaker(bind=engine)
    db = Session()
    cred = Credential(
        name="api-cred", provider="AWS",
        auth_type=CredentialAuthType.STATIC, secrets={},
    )
    db.add(cred)
    db.commit()
    db.refresh(cred)
    yield cred
    db.close()


@pytest.fixture
def seed_account(engine, seed_credential):
    Session = sessionmaker(bind=engine)
    db = Session()
    acct = Account(
        name="api-account",
        credential_id=seed_credential.id,
        account_id="111111111111",
    )
    db.add(acct)
    db.commit()
    db.refresh(acct)
    yield acct
    db.close()


# --- Tests --------------------------------------------------------------------

class TestCreateAccount:
    def test_create_success(self, client, seed_credential):
        resp = client.post("/api/v1/accounts/", json={
            "name": "new-acct",
            "credential_id": str(seed_credential.id),
            "account_id": "222222222222",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "new-acct"
        assert data["account_id"] == "222222222222"

    def test_create_bad_credential(self, client):
        resp = client.post("/api/v1/accounts/", json={
            "name": "bad",
            "credential_id": "nonexistent",
            "account_id": "333",
        })
        assert resp.status_code == 400


class TestListAccounts:
    def test_list_empty(self, client):
        resp = client.get("/api/v1/accounts/")
        assert resp.status_code == 200
        assert resp.json()["total"] == 0

    def test_list_with_data(self, client, seed_account):
        resp = client.get("/api/v1/accounts/")
        assert resp.status_code == 200
        assert resp.json()["total"] >= 1


class TestGetAccount:
    def test_get_by_name(self, client, seed_account):
        resp = client.get(f"/api/v1/accounts/{seed_account.name}")
        assert resp.status_code == 200
        assert resp.json()["name"] == seed_account.name

    def test_get_nonexistent(self, client):
        resp = client.get("/api/v1/accounts/ghost")
        assert resp.status_code == 404


class TestUpdateAccount:
    def test_update_success(self, client, seed_account):
        resp = client.patch(f"/api/v1/accounts/{seed_account.name}", json={
            "role_override": "arn:aws:iam::role/Test",
        })
        assert resp.status_code == 200
        assert resp.json()["role_override"] == "arn:aws:iam::role/Test"


class TestDeleteAccount:
    def test_delete_success(self, client, seed_account):
        resp = client.delete(f"/api/v1/accounts/{seed_account.name}")
        assert resp.status_code == 200

    def test_delete_nonexistent(self, client):
        resp = client.delete("/api/v1/accounts/ghost")
        assert resp.status_code == 400

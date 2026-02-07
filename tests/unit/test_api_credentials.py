"""
Stability tests for Credential API routes.

Verifies the REST contract for credential CRUD operations.
"""
import pytest
from unittest.mock import patch, AsyncMock
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from src.api.main import app
from src.api.auth import SessionAuth
from src.models import Base, Credential, CredentialAuthType


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
def seed_credential(engine):
    Session = sessionmaker(bind=engine)
    db = Session()
    cred = Credential(
        name="existing-cred", provider="AWS",
        auth_type=CredentialAuthType.STATIC, secrets={"key": "val"},
    )
    db.add(cred)
    db.commit()
    db.refresh(cred)
    yield cred
    db.close()


# --- Tests --------------------------------------------------------------------

class TestCreateCredential:
    def test_create_success(self, client):
        resp = client.post("/api/v1/credentials/", json={
            "name": "new-cred",
            "provider": "AWS",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "new-cred"
        assert data["provider"] == "AWS"

    def test_create_duplicate(self, client, seed_credential):
        resp = client.post("/api/v1/credentials/", json={
            "name": seed_credential.name,
            "provider": "GCP",
        })
        assert resp.status_code == 400


class TestListCredentials:
    def test_list_empty(self, client):
        resp = client.get("/api/v1/credentials/")
        assert resp.status_code == 200
        assert resp.json()["total"] == 0

    def test_list_with_data(self, client, seed_credential):
        resp = client.get("/api/v1/credentials/")
        assert resp.status_code == 200
        assert resp.json()["total"] >= 1


class TestGetCredential:
    def test_get_by_name(self, client, seed_credential):
        resp = client.get(f"/api/v1/credentials/{seed_credential.name}")
        assert resp.status_code == 200
        assert resp.json()["name"] == seed_credential.name

    def test_get_nonexistent(self, client):
        resp = client.get("/api/v1/credentials/ghost")
        assert resp.status_code == 404


class TestUpdateCredential:
    def test_update_secrets(self, client, seed_credential):
        resp = client.patch(f"/api/v1/credentials/{seed_credential.name}", json={
            "secrets": {"new_key": "new_val"},
        })
        assert resp.status_code == 200

    def test_update_nonexistent(self, client):
        resp = client.patch("/api/v1/credentials/ghost", json={
            "secrets": {},
        })
        assert resp.status_code == 400


class TestDeleteCredential:
    def test_delete_success(self, client, seed_credential):
        resp = client.delete(f"/api/v1/credentials/{seed_credential.name}")
        assert resp.status_code == 200

    def test_delete_nonexistent(self, client):
        resp = client.delete("/api/v1/credentials/ghost")
        assert resp.status_code == 400

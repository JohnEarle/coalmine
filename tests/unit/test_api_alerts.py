"""
Stability tests for Alert API routes.

Verifies the REST contract for alert listing and lookup.
"""
import pytest
import datetime
import uuid
from unittest.mock import patch, AsyncMock
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from src.api.main import app
from src.api.auth import SessionAuth
from src.models import (
    Base, Alert, AlertStatus, CanaryResource, Account, Credential,
    CredentialAuthType, ResourceType, ResourceStatus
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
def seed_alert(engine):
    """Create full Credential → Account → Canary → Alert chain."""
    Session = sessionmaker(bind=engine)
    db = Session()
    cred = Credential(name="alert-api-cred", provider="AWS",
                      auth_type=CredentialAuthType.STATIC, secrets={})
    db.add(cred)
    db.flush()
    acct = Account(name="alert-api-acct", credential_id=cred.id, account_id="111")
    db.add(acct)
    db.flush()
    canary = CanaryResource(name="alert-api-canary", resource_type=ResourceType.AWS_BUCKET,
                            account_id=acct.id, status=ResourceStatus.ACTIVE)
    db.add(canary)
    db.flush()
    alert = Alert(canary_id=canary.id, external_id=f"ext-{uuid.uuid4()}",
                  timestamp=datetime.datetime.utcnow(), event_name="GetObject",
                  source_ip="1.2.3.4", status=AlertStatus.NEW)
    db.add(alert)
    db.commit()
    db.refresh(alert)
    db.refresh(canary)
    yield {"alert": alert, "canary": canary}
    db.close()


# --- Tests --------------------------------------------------------------------

class TestListAlerts:
    def test_list_empty(self, client):
        resp = client.get("/api/v1/alerts/")
        assert resp.status_code == 200
        assert resp.json()["total"] == 0

    def test_list_with_data(self, client, seed_alert):
        resp = client.get("/api/v1/alerts/")
        assert resp.status_code == 200
        assert resp.json()["total"] >= 1

    def test_list_filter_by_canary(self, client, seed_alert):
        canary_name = seed_alert["canary"].name
        resp = client.get(f"/api/v1/alerts/?canary={canary_name}")
        assert resp.status_code == 200
        assert resp.json()["total"] == 1


class TestGetAlert:
    def test_get_by_uuid(self, client, seed_alert):
        alert_id = str(seed_alert["alert"].id)
        resp = client.get(f"/api/v1/alerts/{alert_id}")
        assert resp.status_code == 200
        assert resp.json()["id"] == alert_id

    def test_get_nonexistent(self, client):
        resp = client.get("/api/v1/alerts/does-not-exist")
        assert resp.status_code == 404

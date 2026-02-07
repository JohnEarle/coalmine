"""
Stability tests for AlertService CRUD operations.

Guards against regressions in alert listing (with filters) and lookup
(by UUID and external_id).
"""
import pytest
import datetime
import uuid
from src.services.alerts import AlertService
from src.models import (
    Alert, AlertStatus, CanaryResource, Account, Credential,
    CredentialAuthType, ResourceType, ResourceStatus
)


@pytest.fixture
def seeded_db(isolated_db):
    """Seed the DB with Credential → Account → Canary → Alerts."""
    cred = Credential(
        name="alert-cred", provider="AWS",
        auth_type=CredentialAuthType.STATIC, secrets={},
    )
    isolated_db.add(cred)
    isolated_db.flush()

    acct = Account(name="alert-acct", credential_id=cred.id, account_id="111")
    isolated_db.add(acct)
    isolated_db.flush()

    canary = CanaryResource(
        name="alert-canary", resource_type=ResourceType.AWS_BUCKET,
        account_id=acct.id, status=ResourceStatus.ACTIVE,
    )
    isolated_db.add(canary)
    isolated_db.commit()

    return {"db": isolated_db, "account": acct, "credential": cred, "canary": canary}


def _make_alert(db, canary, event_name="GetObject", ext_id=None, status=AlertStatus.NEW):
    """Helper to create an alert inline."""
    alert = Alert(
        canary_id=canary.id,
        external_id=ext_id or str(uuid.uuid4()),
        timestamp=datetime.datetime.utcnow(),
        event_name=event_name,
        source_ip="1.2.3.4",
        status=status,
    )
    db.add(alert)
    db.commit()
    return alert


class TestAlertList:
    """Tests for AlertService.list()."""

    def test_list_empty(self, isolated_db):
        svc = AlertService(db=isolated_db)
        result = svc.list()
        assert result.total == 0

    def test_list_returns_all(self, seeded_db):
        db = seeded_db["db"]
        canary = seeded_db["canary"]
        _make_alert(db, canary, event_name="GetObject")
        _make_alert(db, canary, event_name="PutObject")

        svc = AlertService(db=db)
        result = svc.list()
        assert result.total == 2

    def test_list_filter_by_canary(self, seeded_db):
        db = seeded_db["db"]
        canary = seeded_db["canary"]

        # Create a second canary with its own alert
        canary2 = CanaryResource(
            name="other-canary", resource_type=ResourceType.AWS_IAM_USER,
            account_id=seeded_db["account"].id, status=ResourceStatus.ACTIVE,
        )
        db.add(canary2)
        db.commit()

        _make_alert(db, canary, event_name="Event1")
        _make_alert(db, canary2, event_name="Event2")

        svc = AlertService(db=db)
        result = svc.list(canary="alert-canary")
        assert result.total == 1
        assert result.items[0].event_name == "Event1"

    def test_list_filter_by_nonexistent_canary(self, seeded_db):
        db = seeded_db["db"]
        _make_alert(db, seeded_db["canary"])

        svc = AlertService(db=db)
        result = svc.list(canary="ghost-canary")
        assert result.total == 0

    def test_list_filter_by_status(self, seeded_db):
        db = seeded_db["db"]
        canary = seeded_db["canary"]
        _make_alert(db, canary, status=AlertStatus.NEW)
        _make_alert(db, canary, status=AlertStatus.ACKNOWLEDGED)

        svc = AlertService(db=db)
        result = svc.list(status="NEW")
        assert result.total == 1


class TestAlertGet:
    """Tests for AlertService.get()."""

    def test_get_by_uuid(self, seeded_db):
        db = seeded_db["db"]
        alert = _make_alert(db, seeded_db["canary"])

        svc = AlertService(db=db)
        result = svc.get(str(alert.id))
        assert result.success is True
        assert result.data.id == alert.id

    def test_get_by_external_id(self, seeded_db):
        db = seeded_db["db"]
        alert = _make_alert(db, seeded_db["canary"], ext_id="cloudtrail-event-123")

        svc = AlertService(db=db)
        result = svc.get("cloudtrail-event-123")
        assert result.success is True
        assert result.data.external_id == "cloudtrail-event-123"

    def test_get_nonexistent(self, isolated_db):
        svc = AlertService(db=isolated_db)
        result = svc.get("does-not-exist")
        assert result.success is False

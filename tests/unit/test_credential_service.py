"""
Stability tests for CredentialService CRUD operations.

Guards against regressions in credential creation, lookup, update, and deletion.
Uses a real in-memory SQLite database — no session mocking.
"""
import pytest
from unittest.mock import patch
from src.services.credentials import CredentialService
from src.models import Credential, Account, CredentialAuthType, ResourceStatus


class TestCredentialCreate:
    """Tests for CredentialService.create()."""

    def test_create_credential(self, isolated_db):
        svc = CredentialService(db=isolated_db)
        result = svc.create(name="my-cred", provider="AWS")
        assert result.success is True
        assert result.data.name == "my-cred"
        assert result.data.provider == "AWS"
        assert result.data.auth_type == CredentialAuthType.STATIC

        # Persisted to DB
        cred = isolated_db.query(Credential).filter_by(name="my-cred").first()
        assert cred is not None
        assert cred.status == ResourceStatus.ACTIVE

    def test_create_with_secrets(self, isolated_db):
        svc = CredentialService(db=isolated_db)
        secrets = {"AWS_ACCESS_KEY_ID": "AKIA...", "AWS_SECRET_ACCESS_KEY": "secret"}
        result = svc.create(name="secret-cred", provider="AWS", secrets=secrets)
        assert result.success is True
        assert result.data.secrets == secrets

    def test_create_gcp_credential(self, isolated_db):
        svc = CredentialService(db=isolated_db)
        result = svc.create(name="gcp-cred", provider="GCP", auth_type="STATIC")
        assert result.success is True
        assert result.data.provider == "GCP"

    def test_create_duplicate_name_fails(self, isolated_db):
        svc = CredentialService(db=isolated_db)
        svc.create(name="dup-cred", provider="AWS")
        result = svc.create(name="dup-cred", provider="GCP")
        assert result.success is False
        assert "dup-cred" in result.error


class TestCredentialList:
    """Tests for CredentialService.list()."""

    def test_list_empty(self, isolated_db):
        svc = CredentialService(db=isolated_db)
        result = svc.list()
        assert result.total == 0
        assert result.items == []

    def test_list_returns_all(self, isolated_db):
        svc = CredentialService(db=isolated_db)
        svc.create(name="cred-a", provider="AWS")
        svc.create(name="cred-b", provider="GCP")
        result = svc.list()
        assert result.total == 2
        names = {c.name for c in result.items}
        assert names == {"cred-a", "cred-b"}


class TestCredentialGet:
    """Tests for CredentialService.get()."""

    def test_get_by_name(self, isolated_db):
        svc = CredentialService(db=isolated_db)
        svc.create(name="find-me", provider="AWS")
        result = svc.get("find-me")
        assert result.success is True
        assert result.data.name == "find-me"

    def test_get_by_uuid(self, isolated_db):
        svc = CredentialService(db=isolated_db)
        created = svc.create(name="uuid-cred", provider="AWS")
        result = svc.get(str(created.data.id))
        assert result.success is True
        assert result.data.name == "uuid-cred"

    def test_get_nonexistent_fails(self, isolated_db):
        svc = CredentialService(db=isolated_db)
        result = svc.get("does-not-exist")
        assert result.success is False


class TestCredentialUpdate:
    """Tests for CredentialService.update()."""

    def test_update_secrets(self, isolated_db):
        svc = CredentialService(db=isolated_db)
        svc.create(name="upd-cred", provider="AWS", secrets={"old": "val"})
        result = svc.update("upd-cred", secrets={"new": "val"})
        assert result.success is True
        assert result.data.secrets == {"new": "val"}

    def test_update_nonexistent_fails(self, isolated_db):
        svc = CredentialService(db=isolated_db)
        result = svc.update("ghost", secrets={})
        assert result.success is False


class TestCredentialDelete:
    """Tests for CredentialService.delete()."""

    def test_delete_credential(self, isolated_db):
        svc = CredentialService(db=isolated_db)
        svc.create(name="del-cred", provider="AWS")
        result = svc.delete("del-cred")
        assert result.success is True

        cred = isolated_db.query(Credential).filter_by(name="del-cred").first()
        assert cred is None

    def test_delete_with_accounts_fails(self, isolated_db):
        """Deleting a credential with associated accounts should fail (without force)."""
        svc = CredentialService(db=isolated_db)
        svc.create(name="busy-cred", provider="AWS")
        cred = isolated_db.query(Credential).filter_by(name="busy-cred").first()

        # Add an account referencing this credential
        acct = Account(name="linked-acct", credential_id=cred.id, account_id="111")
        isolated_db.add(acct)
        isolated_db.commit()

        result = svc.delete("busy-cred")
        assert result.success is False

    def test_delete_nonexistent_fails(self, isolated_db):
        svc = CredentialService(db=isolated_db)
        result = svc.delete("nope")
        assert result.success is False

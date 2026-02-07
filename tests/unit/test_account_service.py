"""
Stability tests for AccountService CRUD operations.

Guards against regressions in account creation, lookup, update, enable/disable,
and deletion. Uses a real in-memory SQLite database — no session mocking.
"""
import pytest
from src.services.accounts import AccountService
from src.models import Account, Credential, CredentialAuthType, ResourceStatus, CanaryResource, ResourceType


class TestAccountCreate:
    """Tests for AccountService.create()."""

    def test_create_account(self, isolated_db, make_credential):
        cred = make_credential(name="acct-cred")
        svc = AccountService(db=isolated_db)
        result = svc.create(
            name="my-account",
            credential_id=str(cred.id),
            account_id="111111111111",
        )
        assert result.success is True
        assert result.data.name == "my-account"
        assert result.data.account_id == "111111111111"
        assert result.data.credential_id == cred.id

    def test_create_with_role_override(self, isolated_db, make_credential):
        cred = make_credential(name="role-cred")
        svc = AccountService(db=isolated_db)
        result = svc.create(
            name="role-account",
            credential_id=str(cred.id),
            account_id="222222222222",
            role_override="arn:aws:iam::role/Deployer",
        )
        assert result.success is True
        assert result.data.role_override == "arn:aws:iam::role/Deployer"

    def test_create_requires_valid_credential(self, isolated_db):
        svc = AccountService(db=isolated_db)
        result = svc.create(
            name="no-cred-account",
            credential_id="nonexistent",
            account_id="333333333333",
        )
        assert result.success is False

    def test_create_duplicate_name_fails(self, isolated_db, make_credential):
        cred = make_credential(name="dup-cred")
        svc = AccountService(db=isolated_db)
        svc.create(name="dup-acct", credential_id=str(cred.id), account_id="111")
        result = svc.create(name="dup-acct", credential_id=str(cred.id), account_id="222")
        assert result.success is False


class TestAccountList:
    """Tests for AccountService.list()."""

    def test_list_empty(self, isolated_db):
        svc = AccountService(db=isolated_db)
        result = svc.list()
        assert result.total == 0

    def test_list_returns_all(self, isolated_db, make_credential):
        cred = make_credential(name="list-cred")
        svc = AccountService(db=isolated_db)
        svc.create(name="a1", credential_id=str(cred.id), account_id="111")
        svc.create(name="a2", credential_id=str(cred.id), account_id="222")
        result = svc.list()
        assert result.total == 2
        names = {a.name for a in result.items}
        assert names == {"a1", "a2"}

    def test_list_filter_by_provider(self, isolated_db):
        aws_cred = Credential(name="aws", provider="AWS", auth_type=CredentialAuthType.STATIC, secrets={})
        gcp_cred = Credential(name="gcp", provider="GCP", auth_type=CredentialAuthType.STATIC, secrets={})
        isolated_db.add_all([aws_cred, gcp_cred])
        isolated_db.flush()

        a1 = Account(name="aws-acct", credential_id=aws_cred.id, account_id="111")
        a2 = Account(name="gcp-acct", credential_id=gcp_cred.id, account_id="proj")
        isolated_db.add_all([a1, a2])
        isolated_db.commit()

        svc = AccountService(db=isolated_db)
        result = svc.list(provider="AWS")
        assert result.total == 1
        assert result.items[0].name == "aws-acct"


class TestAccountGet:
    """Tests for AccountService.get()."""

    def test_get_by_name(self, isolated_db, make_credential):
        cred = make_credential(name="get-name-cred")
        svc = AccountService(db=isolated_db)
        svc.create(name="find-me", credential_id=str(cred.id), account_id="111")
        result = svc.get("find-me")
        assert result.success is True
        assert result.data.name == "find-me"

    def test_get_by_uuid(self, isolated_db, make_credential):
        cred = make_credential(name="get-uuid-cred")
        svc = AccountService(db=isolated_db)
        created = svc.create(name="uuid-acct", credential_id=str(cred.id), account_id="111")
        result = svc.get(str(created.data.id))
        assert result.success is True
        assert result.data.name == "uuid-acct"

    def test_get_nonexistent(self, isolated_db):
        svc = AccountService(db=isolated_db)
        result = svc.get("ghost")
        assert result.success is False


class TestAccountUpdate:
    """Tests for AccountService.update()."""

    def test_update_role_override(self, isolated_db, make_credential):
        cred = make_credential(name="upd-cred")
        svc = AccountService(db=isolated_db)
        svc.create(name="upd-acct", credential_id=str(cred.id), account_id="111")
        result = svc.update("upd-acct", role_override="new-role")
        assert result.success is True
        assert result.data.role_override == "new-role"

    def test_enable_disable(self, isolated_db, make_credential):
        cred = make_credential(name="toggle-cred")
        svc = AccountService(db=isolated_db)
        svc.create(name="toggle-acct", credential_id=str(cred.id), account_id="111")

        result = svc.disable("toggle-acct")
        assert result.success is True

        result = svc.enable("toggle-acct")
        assert result.success is True


class TestAccountDelete:
    """Tests for AccountService.delete()."""

    def test_delete_account(self, isolated_db, make_credential):
        cred = make_credential(name="del-cred")
        svc = AccountService(db=isolated_db)
        svc.create(name="del-acct", credential_id=str(cred.id), account_id="111")
        result = svc.delete("del-acct")
        assert result.success is True
        assert isolated_db.query(Account).filter_by(name="del-acct").first() is None

    def test_delete_with_canaries_blocked(self, isolated_db, make_credential):
        """Deletion should fail when account has active canaries."""
        cred = make_credential(name="busy-del-cred")
        svc = AccountService(db=isolated_db)
        created = svc.create(name="busy-acct", credential_id=str(cred.id), account_id="111")
        acct = created.data

        canary = CanaryResource(
            name="blocking-canary",
            resource_type=ResourceType.AWS_BUCKET,
            account_id=acct.id,
            status=ResourceStatus.ACTIVE,
        )
        isolated_db.add(canary)
        isolated_db.commit()

        result = svc.delete("busy-acct")
        assert result.success is False
        assert "canaries" in result.error.lower()

    def test_delete_nonexistent(self, isolated_db):
        svc = AccountService(db=isolated_db)
        result = svc.delete("nope")
        assert result.success is False

import pytest
import os
import uuid
import sys
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Add src to path to ensure imports work
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from src.models import (
    Base, Account, Credential, CanaryResource, LoggingResource, Alert,
    LoggingProviderType, ResourceStatus, ResourceType, CredentialAuthType,
    ActionType, AlertStatus, AccountSource
)

# =============================================================================
# Unit Test Fixtures (In-Memory SQLite - Fast, Isolated)
# =============================================================================

@pytest.fixture
def isolated_db():
    """
    Creates a fresh in-memory SQLite database for each test.
    Use this for fast, isolated unit tests that don't need real DB.
    """
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


# =============================================================================
# Factory Fixtures (for building test objects concisely)
# =============================================================================

@pytest.fixture
def make_credential(isolated_db):
    """Factory for Credential objects."""
    def _make(name="test-cred", provider="AWS", auth_type=CredentialAuthType.STATIC,
              secrets=None, **kwargs):
        cred = Credential(
            name=name,
            provider=provider,
            auth_type=auth_type,
            secrets=secrets or {"AWS_ACCESS_KEY_ID": "k", "AWS_SECRET_ACCESS_KEY": "s"},
            **kwargs
        )
        isolated_db.add(cred)
        isolated_db.commit()
        return cred
    return _make


@pytest.fixture
def make_account(isolated_db, make_credential):
    """Factory for Account objects (auto-creates a credential if none given)."""
    def _make(name="test-account", credential=None, account_id="111111111111", **kwargs):
        cred = credential or make_credential()
        account = Account(
            name=name,
            credential_id=cred.id,
            account_id=account_id,
            **kwargs
        )
        isolated_db.add(account)
        isolated_db.commit()
        return account
    return _make


@pytest.fixture
def make_logging_resource(isolated_db, make_account):
    """Factory for LoggingResource objects."""
    def _make(name="test-logging", provider_type=LoggingProviderType.AWS_CLOUDTRAIL,
              account=None, **kwargs):
        acct = account or make_account()
        lr = LoggingResource(
            name=name,
            provider_type=provider_type,
            account_id=acct.id,
            status=ResourceStatus.ACTIVE,
            **kwargs
        )
        isolated_db.add(lr)
        isolated_db.commit()
        return lr
    return _make


@pytest.fixture
def make_canary(isolated_db, make_account, make_logging_resource):
    """Factory for CanaryResource objects."""
    def _make(name="test-canary", resource_type=ResourceType.AWS_BUCKET,
              account=None, logging_resource=None, status=ResourceStatus.ACTIVE, **kwargs):
        acct = account or make_account(name=f"acct-for-{name}")
        canary = CanaryResource(
            name=name,
            resource_type=resource_type,
            account_id=acct.id,
            logging_resource_id=logging_resource.id if logging_resource else None,
            status=status,
            **kwargs
        )
        isolated_db.add(canary)
        isolated_db.commit()
        return canary
    return _make


@pytest.fixture
def make_alert(isolated_db, make_canary):
    """Factory for Alert objects."""
    import datetime
    _counter = [0]

    def _make(canary=None, event_name="GetObject", **kwargs):
        _counter[0] += 1
        c = canary or make_canary(name=f"canary-for-alert-{_counter[0]}")
        alert = Alert(
            canary_id=c.id,
            external_id=kwargs.pop("external_id", f"ext-{uuid.uuid4()}"),
            timestamp=kwargs.pop("timestamp", datetime.datetime.utcnow()),
            event_name=event_name,
            source_ip=kwargs.pop("source_ip", "1.2.3.4"),
            status=kwargs.pop("status", AlertStatus.NEW),
            **kwargs
        )
        isolated_db.add(alert)
        isolated_db.commit()
        return alert
    return _make


# =============================================================================
# Integration Test Fixtures (PostgreSQL - Shared with App)
# =============================================================================

# Use the same DB URL as the app
DATABASE_URL = os.getenv("DATABASE_URL")


@pytest.fixture(scope="session")
def engine():
    if not DATABASE_URL:
        pytest.skip("DATABASE_URL not set — skipping integration tests")
    return create_engine(DATABASE_URL)


@pytest.fixture(scope="session")
def tables(engine):
    Base.metadata.create_all(bind=engine)
    yield


@pytest.fixture
def db_session(engine, tables):
    """Returns a session for the test."""
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


@pytest.fixture
def test_env_aws(db_session):
    """Ensures a test AWS Account+Credential exists and is cleaned up."""
    env_name = "e2e-test-aws"
    env = db_session.query(Account).filter_by(name=env_name).first()

    clean_up = False
    if not env:
        clean_up = True
        cred = Credential(
            name="e2e-test-cred",
            provider="AWS",
            auth_type=CredentialAuthType.STATIC,
            secrets={
                "AWS_ACCESS_KEY_ID": os.getenv("AWS_ACCESS_KEY_ID", "test-key"),
                "AWS_SECRET_ACCESS_KEY": os.getenv("AWS_SECRET_ACCESS_KEY", "test-secret"),
                "region": os.getenv("AWS_DEFAULT_REGION", "us-east-1"),
            },
        )
        db_session.add(cred)
        db_session.flush()

        env = Account(
            name=env_name,
            credential_id=cred.id,
            account_id=os.getenv("AWS_ACCOUNT_ID", "000000000000"),
        )
        db_session.add(env)
        db_session.commit()

    yield env

    if clean_up:
        env_to_del = db_session.query(Account).filter_by(name=env_name).first()
        if env_to_del:
            db_session.delete(env_to_del)
            db_session.commit()
        cred_to_del = db_session.query(Credential).filter_by(name="e2e-test-cred").first()
        if cred_to_del:
            db_session.delete(cred_to_del)
            db_session.commit()


@pytest.fixture
def test_logging_resource(db_session, test_env_aws):
    """Ensures a test logging resource exists."""
    log_name = "e2e-test-logging"
    log_res = db_session.query(LoggingResource).filter_by(name=log_name).first()

    clean_up = False
    if not log_res:
        clean_up = True
        log_res = LoggingResource(
            name=log_name,
            provider_type=LoggingProviderType.AWS_CLOUDTRAIL,
            account_id=test_env_aws.id,
            status=ResourceStatus.ACTIVE,
            configuration={"trail_name": "test-trail"},
        )
        db_session.add(log_res)
        db_session.commit()

    yield log_res

    if clean_up:
        log_to_del = db_session.query(LoggingResource).filter_by(name=log_name).first()
        if log_to_del:
            db_session.delete(log_to_del)
            db_session.commit()

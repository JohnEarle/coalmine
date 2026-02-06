from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, Enum as SqlEnum, create_engine, JSON
from sqlalchemy.orm import declarative_base, relationship, sessionmaker
from sqlalchemy.dialects.postgresql import UUID, ENUM as PgEnum
import uuid
import datetime
import enum
import os

Base = declarative_base()

# Database Setup - define early so we can use it for type selection
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    DATABASE_URL = "sqlite:///./test.db"

_is_postgres = DATABASE_URL.startswith("postgresql")


class ResourceType(enum.Enum):
    AWS_BUCKET = "AWS_BUCKET"
    GCP_BUCKET = "GCP_BUCKET"
    GCP_SERVICE_ACCOUNT = "GCP_SERVICE_ACCOUNT"
    AWS_IAM_USER = "AWS_IAM_USER"


class LoggingProviderType(enum.Enum):
    AWS_CLOUDTRAIL = "AWS_CLOUDTRAIL"
    GCP_AUDIT_LOG = "GCP_AUDIT_LOG"
    GCP_AUDIT_SINK = "GCP_AUDIT_SINK"


class ResourceStatus(enum.Enum):
    CREATING = "CREATING"
    ACTIVE = "ACTIVE"
    ROTATING = "ROTATING"
    DELETING = "DELETING"
    DELETED = "DELETED"
    ERROR = "ERROR"
    DRIFT = "DRIFT"


class ActionType(enum.Enum):
    CREATE = "CREATE"
    ROTATE = "ROTATE"
    DELETE = "DELETE"
    ALERT = "ALERT"


class AlertStatus(enum.Enum):
    NEW = "NEW"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    RESOLVED = "RESOLVED"


class CredentialAuthType(enum.Enum):
    """How the credential authenticates to cloud providers."""
    STATIC = "STATIC"           # Direct access keys / SA JSON
    ASSUME_ROLE = "ASSUME_ROLE" # AWS: assume into target accounts
    IMPERSONATE = "IMPERSONATE" # GCP: impersonate target SAs


class CredentialScope(enum.Enum):
    """What accounts this credential can access."""
    SINGLE = "SINGLE"           # One account only
    MULTI = "MULTI"             # Specific list of accounts
    ORGANIZATION = "ORGANIZATION"  # All accounts in org (with discovery)


class AccountSource(enum.Enum):
    """How the account was added to Coalmine."""
    MANUAL = "MANUAL"           # User added manually
    DISCOVERED = "DISCOVERED"   # Auto-discovered from org
    MIGRATED = "MIGRATED"       # Migrated from CloudEnvironment


# For PostgreSQL, we use SqlEnum with create_constraint=False to prevent auto-creation
# of the type (we handle that in init_db to avoid race conditions).
# For SQLite, we use the default SqlEnum behavior.

def _make_enum_column(py_enum, pg_type_name):
    """Create an enum type that works with both PostgreSQL and SQLite."""
    if _is_postgres:
        return SqlEnum(
            py_enum,
            name=pg_type_name,
            create_constraint=False,
            native_enum=True,
        )
    else:
        return SqlEnum(py_enum)

# Pre-create the column types for reuse
_resource_type_col = lambda: _make_enum_column(ResourceType, 'resourcetype')
_logging_provider_type_col = lambda: _make_enum_column(LoggingProviderType, 'loggingprovidertype')
_resource_status_col = lambda: _make_enum_column(ResourceStatus, 'resourcestatus')
_action_type_col = lambda: _make_enum_column(ActionType, 'actiontype')
_alert_status_col = lambda: _make_enum_column(AlertStatus, 'alertstatus')
_credential_auth_type_col = lambda: _make_enum_column(CredentialAuthType, 'credentialauthtype')
_credential_scope_col = lambda: _make_enum_column(CredentialScope, 'credentialscope')
_account_source_col = lambda: _make_enum_column(AccountSource, 'accountsource')

# Keep PgEnum definitions for explicit type creation in init_db()
if _is_postgres:
    _pg_resource_type = PgEnum(
        *[e.value for e in ResourceType],
        name='resourcetype',
        create_type=False
    )
    _pg_logging_provider_type = PgEnum(
        *[e.value for e in LoggingProviderType],
        name='loggingprovidertype',
        create_type=False
    )
    _pg_resource_status = PgEnum(
        *[e.value for e in ResourceStatus],
        name='resourcestatus',
        create_type=False
    )
    _pg_action_type = PgEnum(
        *[e.value for e in ActionType],
        name='actiontype',
        create_type=False
    )
    _pg_alert_status = PgEnum(
        *[e.value for e in AlertStatus],
        name='alertstatus',
        create_type=False
    )
    _pg_credential_auth_type = PgEnum(
        *[e.value for e in CredentialAuthType],
        name='credentialauthtype',
        create_type=False
    )
    _pg_credential_scope = PgEnum(
        *[e.value for e in CredentialScope],
        name='credentialscope',
        create_type=False
    )
    _pg_account_source = PgEnum(
        *[e.value for e in AccountSource],
        name='accountsource',
        create_type=False
    )
else:
    _pg_resource_type = None
    _pg_logging_provider_type = None
    _pg_resource_status = None
    _pg_action_type = None
    _pg_alert_status = None
    _pg_credential_auth_type = None
    _pg_credential_scope = None
    _pg_account_source = None


# =============================================================================
# NEW: Credential/Account Abstraction for Multi-Account Support
# =============================================================================

class Credential(Base):
    """
    A reusable authentication source that can access one or more cloud accounts.
    
    Credentials are managed separately from deployment targets (Accounts).
    One credential can authenticate to many accounts (1:N relationship).
    
    The scope of a credential (single account vs organization) is auto-detected
    by attempting organization API calls during discovery.
    """
    __tablename__ = 'credentials'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, nullable=False, unique=True)  # "aws-org-admin", "gcp-corp-sa"
    provider = Column(String, nullable=False)  # "AWS", "GCP", "AZURE"
    
    # Auth type determines how credentials are used
    auth_type = Column(_credential_auth_type_col(), nullable=False, default=CredentialAuthType.STATIC)
    
    # Encrypted secrets (access keys, SA JSON, etc.)
    secrets = Column(JSON, nullable=True)
    
    # Discovery configuration (optional)
    # e.g., {"role_name": "CoalmineDeployer", "include_ous": [...], "org_id": "..."}
    discovery_config = Column(JSON, nullable=True)
    
    status = Column(_resource_status_col(), default=ResourceStatus.ACTIVE)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    
    # Relationships
    accounts = relationship("Account", back_populates="credential", cascade="all, delete-orphan")


class Account(Base):
    """
    A deployment target: AWS account, GCP project, or Azure subscription.
    
    Accounts can be manually defined or auto-discovered from an organization.
    Each account references a Credential for authentication.
    """
    __tablename__ = 'accounts'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    credential_id = Column(UUID(as_uuid=True), ForeignKey('credentials.id'), nullable=False)
    
    # Identifiers
    name = Column(String, nullable=False, unique=True)  # Human-readable: "prod-east", "dev-sandbox"
    account_id = Column(String, nullable=False)  # Cloud ID: "111111111111" or "my-project-id"
    
    # How was this account added?
    source = Column(_account_source_col(), nullable=False, default=AccountSource.MANUAL)
    
    # Optional: Override default role/SA for this specific account
    # If null, uses the credential's default (e.g., discovery_config.role_name)
    role_override = Column(String, nullable=True)
    
    # Auto-discovered metadata (tags, OU path, project labels, etc.)
    account_metadata = Column(JSON, nullable=True)  # tags, OU path, project labels
    
    # Is this account enabled for canary deployment?
    is_enabled = Column(String, nullable=False, default="true")  # Using String for SQLite compat
    
    status = Column(_resource_status_col(), default=ResourceStatus.ACTIVE)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    
    # Relationships
    credential = relationship("Credential", back_populates="accounts")
    canaries = relationship("CanaryResource", back_populates="account")
    logging_resources = relationship("LoggingResource", back_populates="account")


class LoggingResource(Base):
    __tablename__ = 'logging_resources'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, nullable=False) # e.g. "central-trail-01"
    provider_type = Column(_logging_provider_type_col(), nullable=False)
    
    # Link to Account for deployment target
    account_id = Column(UUID(as_uuid=True), ForeignKey('accounts.id'), nullable=True)
    account = relationship("Account", back_populates="logging_resources")
    
    # Configuration (e.g. Trail Name, Log Group Path, Project ID)
    configuration = Column(JSON, nullable=True)
    
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    status = Column(_resource_status_col(), default=ResourceStatus.ACTIVE)

    canaries = relationship("CanaryResource", back_populates="logging_resource")

class CanaryResource(Base):
    __tablename__ = 'canary_resources'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, nullable=False)
    resource_type = Column(_resource_type_col(), nullable=False)
    
    # Link to Account for deployment target
    account_id = Column(UUID(as_uuid=True), ForeignKey('accounts.id'), nullable=True)
    account = relationship("Account", back_populates="canaries")

    # Logging Association
    logging_resource_id = Column(UUID(as_uuid=True), ForeignKey('logging_resources.id'), nullable=True)
    logging_resource = relationship("LoggingResource", back_populates="canaries")

    current_resource_id = Column(String, nullable=True) 
    module_params = Column(JSON, nullable=True)

    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    expires_at = Column(DateTime, nullable=True)
    last_checked_at = Column(DateTime, nullable=True)
    canary_credentials = Column(JSON, nullable=True) # Standardized storage for generated secrets
    interval_seconds = Column(Integer, default=3600*24)
    
    status = Column(_resource_status_col(), default=ResourceStatus.ACTIVE)
    tf_state_path = Column(String, nullable=True)

    history = relationship("ResourceHistory", back_populates="resource", cascade="all, delete-orphan")
    alerts = relationship("Alert", back_populates="canary", cascade="all, delete-orphan")


class Alert(Base):
    __tablename__ = 'alerts'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    canary_id = Column(UUID(as_uuid=True), ForeignKey('canary_resources.id'))
    
    # Unique ID from source (e.g. CloudTrail EventId) for deduplication
    external_id = Column(String, unique=True, nullable=False)
    
    timestamp = Column(DateTime, nullable=False)
    source_ip = Column(String, nullable=True)
    user_agent = Column(String, nullable=True)
    event_name = Column(String, nullable=True)
    
    raw_data = Column(JSON, nullable=True)
    status = Column(_alert_status_col(), default=AlertStatus.NEW)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    canary = relationship("CanaryResource", back_populates="alerts")

class ResourceHistory(Base):
    __tablename__ = 'resource_history'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    resource_id = Column(UUID(as_uuid=True), ForeignKey('canary_resources.id'))
    action = Column(_action_type_col(), nullable=False)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)
    details = Column(JSON, nullable=True)

    resource = relationship("CanaryResource", back_populates="history")

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def _create_pg_enums_if_not_exist(connection):
    """Create PostgreSQL ENUM types if they don't exist (handles race conditions)."""
    from sqlalchemy import text
    
    enum_types = [
        (_pg_resource_type, 'resourcetype'),
        (_pg_logging_provider_type, 'loggingprovidertype'),
        (_pg_resource_status, 'resourcestatus'),
        (_pg_action_type, 'actiontype'),
        (_pg_alert_status, 'alertstatus'),
        (_pg_credential_auth_type, 'credentialauthtype'),
        (_pg_credential_scope, 'credentialscope'),
        (_pg_account_source, 'accountsource'),
    ]
    
    for pg_enum, type_name in enum_types:
        # Check if type already exists
        result = connection.execute(
            text("SELECT 1 FROM pg_type WHERE typname = :name"),
            {"name": type_name}
        )
        if result.fetchone() is None:
            try:
                pg_enum.create(connection, checkfirst=True)
            except Exception:
                # Type may have been created by another process, ignore
                pass

def init_db():
    # For PostgreSQL, create ENUM types first with proper existence checking
    if DATABASE_URL and DATABASE_URL.startswith("postgresql"):
        with engine.connect() as connection:
            _create_pg_enums_if_not_exist(connection)
            connection.commit()
    
    Base.metadata.create_all(bind=engine)

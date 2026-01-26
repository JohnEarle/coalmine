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
else:
    _pg_resource_type = None
    _pg_logging_provider_type = None
    _pg_resource_status = None
    _pg_action_type = None
    _pg_alert_status = None

class CloudEnvironment(Base):
    __tablename__ = 'cloud_environments'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, nullable=False, unique=True)
    provider_type = Column(String, nullable=False) 
    credentials = Column(JSON, nullable=True)
    config = Column(JSON, nullable=True)

    resources = relationship("CanaryResource", back_populates="environment")
    logging_resources = relationship("LoggingResource", back_populates="environment")

class LoggingResource(Base):
    __tablename__ = 'logging_resources'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, nullable=False) # e.g. "central-trail-01"
    provider_type = Column(_logging_provider_type_col(), nullable=False)
    
    environment_id = Column(UUID(as_uuid=True), ForeignKey('cloud_environments.id'), nullable=True)
    environment = relationship("CloudEnvironment", back_populates="logging_resources")
    
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
    
    environment_id = Column(UUID(as_uuid=True), ForeignKey('cloud_environments.id'), nullable=True)
    environment = relationship("CloudEnvironment", back_populates="resources")

    # Logging Association
    logging_resource_id = Column(UUID(as_uuid=True), ForeignKey('logging_resources.id'), nullable=True)
    logging_resource = relationship("LoggingResource", back_populates="canaries")

    current_resource_id = Column(String, nullable=True) 
    module_params = Column(JSON, nullable=True)

    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    expires_at = Column(DateTime, nullable=True)
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

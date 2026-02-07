"""
Shared helper functions and constants for Coalmine tasks.
"""
from ..models import SessionLocal, ResourceType
from ..tofu_manager import TofuManager
from ..logging_config import get_logger
import os

logger = get_logger(__name__)

# Constants
TOFU_BASE_DIR = os.getenv("TOFU_BASE_DIR", "/app/tofu_templates")
STATE_BASE_DIR = os.getenv("STATE_BASE_DIR", "/app/tofu_state")


def get_db():
    """Database session context manager."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _get_execution_env(account) -> dict:
    """
    Construct environment variables for Tofu execution from Account model.

    Delegates to credentials.get_credentials_for_account for the actual
    credential resolution, then appends task-specific env vars (IAC token).
    """
    if not account:
        return {}

    from ..credentials import get_credentials_for_account
    env = get_credentials_for_account(account)

    # Append secret UA token so monitoring can filter out self-generated events
    iac_token = os.getenv("COALMINE_IAC_UA_TOKEN")
    if iac_token:
        env["TF_APPEND_USER_AGENT"] = f"coalmine-iac/{iac_token}"

    return env



def _get_template_name(resource_type) -> str:
    """
    Map resource type to Tofu template directory name.
    
    Accepts ResourceType or LoggingProviderType (Enum or string).
    """
    val = resource_type.value if hasattr(resource_type, "value") else str(resource_type)
    
    # Explicit Mappings
    if val == "AWS_CLOUDTRAIL":
        return "aws_central_trail"
    
    # Global Config Lookup
    from ..config_loader import get_template_name
    return get_template_name(val)


import re
from sqlalchemy import text
from urllib.parse import urlparse

_SAFE_SCHEMA_RE = re.compile(r"^[a-z0-9_]+$")


def _ensure_schema_exists(schema_name: str):
    """Create the Postgres schema if it doesn't exist."""
    if not _SAFE_SCHEMA_RE.match(schema_name):
        raise ValueError(f"Invalid schema name: {schema_name!r}")
    db = SessionLocal()
    try:
        db.execute(text(f"CREATE SCHEMA IF NOT EXISTS {schema_name}"))
        db.commit()
    except Exception as e:
        logger.error(f"Error creating schema {schema_name}: {e}")
        db.rollback()
    finally:
        db.close()


def _get_backend_config(key_name: str) -> dict:
    """
    Returns the backend config dictionary for Postgres state.
    We convert the URI to a keyword=value string for better compatibility with Tofu/libpq.
    """
    db_url = os.getenv("DATABASE_URL", "postgresql://canary_user:canary_password@postgres:5432/canary_inventory")
    
    conn_str = db_url
    try:
        parsed = urlparse(db_url)
        dbname = parsed.path.lstrip('/')
        conn_str = (
            f"host={parsed.hostname} "
            f"port={parsed.port or 5432} "
            f"user={parsed.username} "
            f"password={parsed.password} "
            f"dbname={dbname} "
            f"sslmode=disable"
        )
    except Exception as e:
        logger.error(f"Error parsing DB URL: {e}, using fallback with disable SSL.")
        if "?" in db_url:
            conn_str = f"{db_url}&sslmode=disable"
        else:
            conn_str = f"{db_url}?sslmode=disable"

    schema_name = f"state_{key_name.replace('-', '_')}"
    _ensure_schema_exists(schema_name)

    return {
        "conn_str": conn_str,
        "schema_name": schema_name
    }

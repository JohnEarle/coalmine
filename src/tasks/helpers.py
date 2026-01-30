"""
Shared helper functions and constants for Coalmine tasks.
"""
from ..models import SessionLocal, CloudEnvironment, ResourceType
from ..tofu_manager import TofuManager
from ..logging_config import get_logger
import os
import json
import hashlib

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


def _write_gcp_creds(creds_dict) -> str:
    """Write GCP credentials to a temp file and return path."""
    if isinstance(creds_dict, str):
        content = creds_dict
    else:
        content = json.dumps(creds_dict, indent=2)
        
    h = hashlib.md5(content.encode()).hexdigest()
    path = f"/tmp/gcp_creds_{h}.json"
    if not os.path.exists(path):
        with open(path, "w") as f:
            f.write(content)
    return path


def _build_env_vars(environment: CloudEnvironment) -> dict:
    """
    Construct environment variables for Tofu based on CloudEnvironment credentials.
    
    Clears conflicting cloud credentials to ensure isolation between environments.
    Each canary uses ONLY the credentials from its associated CloudEnvironment.
    """
    env = os.environ.copy()
    
    # Clear all cloud provider credentials to prevent cross-contamination
    # This ensures we only use credentials explicitly set from the environment
    aws_keys = ["AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_SESSION_TOKEN",
                "AWS_REGION", "AWS_DEFAULT_REGION", "AWS_PROFILE"]
    gcp_keys = ["GOOGLE_APPLICATION_CREDENTIALS", "GOOGLE_CREDENTIALS", 
                "GCLOUD_PROJECT", "GOOGLE_CLOUD_PROJECT", "CLOUDSDK_CORE_PROJECT"]
    
    for key in aws_keys + gcp_keys:
        env.pop(key, None)
    
    if not environment:
        logger.warning("No environment provided - Tofu will have no cloud credentials")
        return env
    
    creds = environment.credentials or {}
    
    if environment.provider_type == "AWS":
        # Support both uppercase and lowercase credential keys
        access_key = creds.get("AWS_ACCESS_KEY_ID") or creds.get("aws_access_key_id")
        secret_key = creds.get("AWS_SECRET_ACCESS_KEY") or creds.get("aws_secret_access_key")
        session_token = creds.get("AWS_SESSION_TOKEN") or creds.get("aws_session_token")
        region = creds.get("AWS_REGION") or creds.get("region") or creds.get("aws_region")
        
        if access_key:
            env["AWS_ACCESS_KEY_ID"] = access_key
        if secret_key:
            env["AWS_SECRET_ACCESS_KEY"] = secret_key
        if session_token:
            env["AWS_SESSION_TOKEN"] = session_token
        if region:
            env["AWS_REGION"] = region
            env["AWS_DEFAULT_REGION"] = region
            
    elif environment.provider_type == "GCP":
        # Support inline JSON credentials or a path
        # Check for various key names
        json_content = (creds.get("service_account_json") or 
                       creds.get("GOOGLE_CREDENTIALS_JSON") or 
                       creds.get("google_credentials_json"))
        
        path_val = (creds.get("GOOGLE_APPLICATION_CREDENTIALS") or 
                   creds.get("google_application_credentials"))

        if json_content:
            path = _write_gcp_creds(json_content)
            env["GOOGLE_APPLICATION_CREDENTIALS"] = path
            
            # ECONOMIES OF MECHANISM: Extract project_id from the JSON
            # This avoids requiring the user to specify it twice (once in JSON, once in config)
            try:
                if isinstance(json_content, str):
                    data = json.loads(json_content)
                else:
                    data = json_content
                
                extracted_project = data.get("project_id")
                if extracted_project and "GOOGLE_CLOUD_PROJECT" not in env:
                    env["GOOGLE_CLOUD_PROJECT"] = extracted_project
                    env["CLOUDSDK_CORE_PROJECT"] = extracted_project
            except Exception as e:
                logger.warning(f"Failed to parse GCP credentials JSON for project_id: {e}")

        elif path_val:
            env["GOOGLE_APPLICATION_CREDENTIALS"] = path_val
        
        # Explicit override takes precedence (or acts as fallback if JSON parsing failed)
        project = creds.get("project_id") or creds.get("GOOGLE_CLOUD_PROJECT")
        if project:
            env["GOOGLE_CLOUD_PROJECT"] = project
            env["CLOUDSDK_CORE_PROJECT"] = project
            
    return env


def _get_execution_env(environment: CloudEnvironment) -> dict:
    """
    Construct environment variables for Tofu execution.
    Returns ONLY the variables defined in the CloudEnvironment, 
    intended for use with TofuManager's clean_env=True mode.
    """
    if not environment:
        return {}
    
    env = {}
    creds = environment.credentials or {}
    
    if environment.provider_type == "AWS":
        # Support both uppercase and lowercase credential keys
        access_key = creds.get("AWS_ACCESS_KEY_ID") or creds.get("aws_access_key_id")
        secret_key = creds.get("AWS_SECRET_ACCESS_KEY") or creds.get("aws_secret_access_key")
        session_token = creds.get("AWS_SESSION_TOKEN") or creds.get("aws_session_token")
        region = creds.get("AWS_REGION") or creds.get("region") or creds.get("aws_region")
        
        if access_key:
            env["AWS_ACCESS_KEY_ID"] = access_key
        if secret_key:
            env["AWS_SECRET_ACCESS_KEY"] = secret_key
        if session_token:
            env["AWS_SESSION_TOKEN"] = session_token
        if region:
            env["AWS_REGION"] = region
            env["AWS_DEFAULT_REGION"] = region
            
    elif environment.provider_type == "GCP":
        json_content = (creds.get("service_account_json") or 
                       creds.get("GOOGLE_CREDENTIALS_JSON") or 
                       creds.get("google_credentials_json"))
        
        path_val = (creds.get("GOOGLE_APPLICATION_CREDENTIALS") or 
                   creds.get("google_application_credentials"))

        if json_content:
            path = _write_gcp_creds(json_content)
            env["GOOGLE_APPLICATION_CREDENTIALS"] = path
            
            try:
                if isinstance(json_content, str):
                    data = json.loads(json_content)
                else:
                    data = json_content
                
                extracted_project = data.get("project_id")
                if extracted_project:
                    env["GOOGLE_CLOUD_PROJECT"] = extracted_project
                    env["CLOUDSDK_CORE_PROJECT"] = extracted_project
            except Exception as e:
                logger.warning(f"Failed to parse GCP credentials JSON for project_id: {e}")

        elif path_val:
            env["GOOGLE_APPLICATION_CREDENTIALS"] = path_val
        
        project = creds.get("project_id") or creds.get("GOOGLE_CLOUD_PROJECT")
        if project:
            env["GOOGLE_CLOUD_PROJECT"] = project
            env["CLOUDSDK_CORE_PROJECT"] = project
            
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


from sqlalchemy import text
from urllib.parse import urlparse


def _ensure_schema_exists(schema_name: str):
    """Create the Postgres schema if it doesn't exist."""
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

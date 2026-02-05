"""Shared utilities for CLI commands."""
import json
import uuid
from src.models import SessionLocal, CanaryResource, CloudEnvironment


def get_db_session():
    """Get a new database session."""
    return SessionLocal()


def parse_json_arg(value: str, arg_name: str) -> dict:
    """
    Parse a JSON string argument.
    
    Args:
        value: JSON string to parse
        arg_name: Name of the argument (for error messages)
        
    Returns:
        Parsed dictionary
        
    Raises:
        SystemExit: If JSON is invalid
    """
    if not value:
        return None
    try:
        return json.loads(value)
    except json.JSONDecodeError as e:
        print(f"Error: --{arg_name} must be valid JSON: {e}")
        raise SystemExit(1)


def resolve_canary(db, name_or_id: str) -> CanaryResource:
    """
    Find a canary by name or UUID.
    
    Args:
        db: Database session
        name_or_id: Canary name or UUID string
        
    Returns:
        CanaryResource or None if not found
    """
    # Try UUID first
    try:
        canary = db.query(CanaryResource).filter(
            CanaryResource.id == uuid.UUID(name_or_id)
        ).first()
        if canary:
            return canary
    except ValueError:
        pass
    
    # Fall back to name
    return db.query(CanaryResource).filter(
        CanaryResource.name == name_or_id
    ).first()


def resolve_environment(db, name_or_id: str) -> CloudEnvironment:
    """
    Find an environment by name or UUID.
    
    Args:
        db: Database session
        name_or_id: Environment name or UUID string
        
    Returns:
        CloudEnvironment or None if not found
    """
    # Try UUID first
    try:
        env = db.query(CloudEnvironment).filter(
            CloudEnvironment.id == uuid.UUID(name_or_id)
        ).first()
        if env:
            return env
    except ValueError:
        pass
    
    # Fall back to name
    return db.query(CloudEnvironment).filter(
        CloudEnvironment.name == name_or_id
    ).first()


def print_custom_help():
    """Print detailed usage guide."""
    help_text = """
Coalmine CLI - Usage Guide
================================

COMMAND STRUCTURE:
  coalmine <resource> <action> [options]

RESOURCES:

  canary     Manage canary token resources
  env        Manage cloud environments  
  logs       Manage logging resources
  alerts     View security alerts

CANARY COMMANDS:
  canary create <name> <type> --env <id> --logging-id <id> [--interval <sec>] [--params <json>]
      Create a new canary resource.
      Types: AWS_IAM_USER, AWS_BUCKET, GCP_SERVICE_ACCOUNT, GCP_BUCKET
  
  canary list
      List all active canaries.
  
  canary delete <name_or_id>
      Delete an existing canary.
  
  canary creds <name>
      Retrieve credentials for a canary (e.g. Access Keys).
  
  canary trigger <name_or_id>
      Manually trigger a test alert.

ENVIRONMENT COMMANDS:
  env create <name> <provider> --credentials <json> [--config <json>]
      Register a new cloud environment (AWS/GCP).
  
  env list
      List registered environments.
  
  env sync [--dry-run] [--force] [--validate]
      Sync environments from config/environments.yaml.
      Supports ${VAR}, ${VAR:-default}, ${VAR:?error} syntax.

LOGGING COMMANDS:
  logs create <name> <type> --env <id> [--config <json>]
      Create a logging resource (CloudTrail, GCP Audit Sink).
  
  logs list
      List configured logging resources.
  
  logs scan --env <id>
      Scan an AWS account for existing CloudTrails.

ALERT COMMANDS:
  alerts list [--canary <name>] [--env <name>]
      View security alerts detected by the system.

EXAMPLES:
  coalmine canary list
  coalmine canary create prod-canary AWS_IAM_USER --env abc123 --logging-id def456
  coalmine env sync --dry-run
  coalmine alerts list --canary prod-canary
"""
    print(help_text)

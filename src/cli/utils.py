"""Shared utilities for CLI commands."""
import json
import uuid
from src.models import SessionLocal, CanaryResource, Account


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


def resolve_account(db, name_or_id: str) -> Account:
    """
    Find an account by name or UUID.
    
    Args:
        db: Database session
        name_or_id: Account name or UUID string
        
    Returns:
        Account or None if not found
    """
    # Try UUID first
    try:
        account = db.query(Account).filter(
            Account.id == uuid.UUID(name_or_id)
        ).first()
        if account:
            return account
    except ValueError:
        pass
    
    # Fall back to name
    return db.query(Account).filter(
        Account.name == name_or_id
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
  accounts   Manage cloud accounts (deployment targets)
  creds      Manage credentials
  logs       Manage logging resources
  alerts     View security alerts

CANARY COMMANDS:
  canary create <name> <type> --account <id> --logging-id <id> [--interval <sec>] [--params <json>]
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

ACCOUNT COMMANDS:
  accounts create <name> <credential> [--account-id <cloud_id>] [--metadata <json>]
      Register a new cloud account (deployment target).
  
  accounts list
      List registered accounts.

CREDENTIAL COMMANDS:
  creds create <name> <provider> --secrets <json>
      Create a new credential (AWS/GCP).
  
  creds list
      List registered credentials.
  
  creds discover <credential_name>
      Discover accounts accessible via a credential.

LOGGING COMMANDS:
  logs create <name> <type> --account <id> [--config <json>]
      Create a logging resource (CloudTrail, GCP Audit Sink).
  
  logs list
      List configured logging resources.
  
  logs scan --account <id>
      Scan an account for existing CloudTrails.

ALERT COMMANDS:
  alerts list [--canary <name>] [--account <name>]
      View security alerts detected by the system.

EXAMPLES:
  coalmine canary list
  coalmine canary create prod-canary AWS_IAM_USER --account abc123 --logging-id def456
  coalmine creds discover my-org-creds
  coalmine alerts list --canary prod-canary
"""
    print(help_text)

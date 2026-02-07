"""
Credential Synchronization Module

Synchronizes cloud credentials and accounts from YAML to database.

Conflict Resolution:
    Database wins. If a credential with the same name exists in both
    YAML and database, the database version is preserved and the YAML
    entry is skipped.

Usage:
    from src.credential_sync import sync_credentials_from_yaml
    
    # Preview changes
    result = sync_credentials_from_yaml(dry_run=True)
    
    # Apply changes
    result = sync_credentials_from_yaml()
    
    # Force overwrite existing (dangerous)
    result = sync_credentials_from_yaml(force=True)
"""
from typing import Dict, List, Any, Optional
from .models import SessionLocal, Credential, Account, CredentialAuthType, AccountSource
from .config_loader import _load_yaml, _expand_env_vars_recursive
from .logging_config import get_logger

logger = get_logger(__name__)


def get_credentials_config(expand_env_vars: bool = True) -> Dict[str, Dict]:
    """
    Get credential configurations from credentials.yaml.
    
    Args:
        expand_env_vars: If True, expand ${...} expressions.
    
    Returns:
        Dict mapping credential names to their config.
    """
    config = _load_yaml("credentials.yaml")
    raw_creds = config.get("credentials", {})
    
    if expand_env_vars:
        return _expand_env_vars_recursive(raw_creds)
    return raw_creds


def sync_credentials_from_yaml(
    dry_run: bool = False,
    force: bool = False
) -> Dict[str, List]:
    """
    Sync credentials from config/credentials.yaml to the database.
    
    Args:
        dry_run: If True, only report what would be done without making changes.
        force: If True, update existing database entries from YAML.
               WARNING: This will overwrite manual configuration changes.
    
    Returns:
        Dict with keys:
            - created_credentials: List of credential names that were created
            - created_accounts: List of account names that were created
            - updated: List of credential names that were updated (force mode only)
            - skipped: List of credential names skipped (DB exists, no force)
            - errors: List of dicts with 'name' and 'error' keys
    """
    result = {
        "created_credentials": [],
        "created_accounts": [],
        "updated": [],
        "skipped": [],
        "errors": []
    }
    
    try:
        yaml_creds = get_credentials_config()
    except (ValueError, Exception) as e:
        logger.error(f"Failed to load credentials.yaml: {e}")
        result["errors"].append({"name": "_config", "error": str(e)})
        return result
    
    if not yaml_creds:
        logger.info("No credentials defined in credentials.yaml")
        return result
    
    db = SessionLocal()
    
    try:
        for name, config in yaml_creds.items():
            try:
                _sync_single_credential(
                    db=db,
                    name=name,
                    config=config,
                    dry_run=dry_run,
                    force=force,
                    result=result
                )
            except Exception as e:
                logger.error(f"Failed to sync credential '{name}': {e}")
                result["errors"].append({"name": name, "error": str(e)})
                db.rollback()
        
        return result
        
    finally:
        db.close()


def _sync_single_credential(
    db,
    name: str,
    config: Dict,
    dry_run: bool,
    force: bool,
    result: Dict[str, List]
) -> None:
    """
    Sync a single credential from YAML config to database.
    
    Args:
        db: Database session
        name: Credential name
        config: Credential configuration from YAML
        dry_run: If True, don't make changes
        force: If True, update existing entries
        result: Result dict to update
    """
    existing = db.query(Credential).filter(
        Credential.name == name
    ).first()
    
    provider = config.get("provider", "AWS").upper()
    auth_type_str = config.get("auth_type", "STATIC").upper()
    secrets = config.get("secrets", {})
    discovery_config = config.get("discovery_config")
    accounts_config = config.get("accounts", [])
    
    try:
        auth_type = CredentialAuthType[auth_type_str]
    except KeyError:
        raise ValueError(f"Invalid auth_type: {auth_type_str}")
    
    if existing:
        if force:
            # Update existing entry
            if dry_run:
                logger.info(f"[DRY RUN] Would update credential '{name}'")
                result["updated"].append(name)
            else:
                existing.provider = provider
                existing.auth_type = auth_type
                existing.secrets = secrets
                existing.discovery_config = discovery_config
                db.commit()
                logger.info(f"Updated credential '{name}' from YAML config")
                result["updated"].append(name)
                
            # Sync accounts for existing credential
            _sync_credential_accounts(db, existing, accounts_config, dry_run, result)
        else:
            # DB wins - skip YAML config
            logger.info(f"Credential '{name}' exists in DB, skipping YAML config")
            result["skipped"].append(name)
    else:
        # Create new entry
        if dry_run:
            logger.info(f"[DRY RUN] Would create credential '{name}'")
            result["created_credentials"].append(name)
            for acc in accounts_config:
                result["created_accounts"].append(acc.get("name", "unnamed"))
        else:
            new_cred = Credential(
                name=name,
                provider=provider,
                auth_type=auth_type,
                secrets=secrets,
                discovery_config=discovery_config
            )
            db.add(new_cred)
            db.commit()
            logger.info(f"Created credential '{name}' from YAML config (ID: {new_cred.id})")
            result["created_credentials"].append(name)
            
            # Sync accounts for new credential
            _sync_credential_accounts(db, new_cred, accounts_config, dry_run, result)


def _sync_credential_accounts(
    db,
    credential: Credential,
    accounts_config: List[Dict],
    dry_run: bool,
    result: Dict[str, List]
) -> None:
    """
    Sync accounts for a credential from YAML config.
    
    Args:
        db: Database session
        credential: Parent credential
        accounts_config: List of account configs from YAML
        dry_run: If True, don't make changes
        result: Result dict to update
    """
    for acc_config in accounts_config:
        acc_name = acc_config.get("name")
        acc_id = acc_config.get("account_id")
        role_override = acc_config.get("role_override")
        metadata = acc_config.get("metadata")
        
        if not acc_name or not acc_id:
            logger.warning(f"Skipping account with missing name or account_id")
            continue
        
        # Check if account exists (by name or by account_id under this credential)
        existing = db.query(Account).filter(
            Account.name == acc_name
        ).first()
        
        if existing:
            logger.info(f"Account '{acc_name}' already exists, skipping")
            continue
        
        # Also check by account_id under this credential
        existing_by_id = db.query(Account).filter(
            Account.credential_id == credential.id,
            Account.account_id == acc_id
        ).first()
        
        if existing_by_id:
            logger.info(f"Account with ID '{acc_id}' already exists under credential, skipping")
            continue
        
        if dry_run:
            logger.info(f"[DRY RUN] Would create account '{acc_name}'")
            result["created_accounts"].append(acc_name)
        else:
            new_account = Account(
                name=acc_name,
                credential_id=credential.id,
                account_id=acc_id,
                source=AccountSource.MANUAL,
                role_override=role_override,
                account_metadata=metadata
            )
            db.add(new_account)
            db.commit()
            logger.info(f"Created account '{acc_name}' (ID: {new_account.id})")
            result["created_accounts"].append(acc_name)


def validate_credentials_yaml() -> Dict[str, Any]:
    """
    Validate that all required environment variables are set.
    
    Returns:
        Dict with:
            - valid: bool indicating if all credentials are valid
            - credentials: Dict mapping cred names to validation results
    """
    raw_creds = get_credentials_config(expand_env_vars=False)
    results = {"valid": True, "credentials": {}}
    
    for name, config in raw_creds.items():
        try:
            # Try to expand - will raise if required vars missing
            _expand_env_vars_recursive(config)
            results["credentials"][name] = {"valid": True}
        except ValueError as e:
            results["valid"] = False
            results["credentials"][name] = {"valid": False, "error": str(e)}
    
    return results

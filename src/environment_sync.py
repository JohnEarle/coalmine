"""
Environment Synchronization Module

Synchronizes cloud environment configurations from YAML to database.

Conflict Resolution:
    Database wins. If an environment with the same name exists in both
    YAML and database, the database version is preserved and the YAML
    entry is skipped.

Usage:
    from src.environment_sync import sync_environments_from_yaml
    
    # Preview changes
    result = sync_environments_from_yaml(dry_run=True)
    
    # Apply changes
    result = sync_environments_from_yaml()
    
    # Force overwrite existing (dangerous)
    result = sync_environments_from_yaml(force=True)
"""
from typing import Dict, List, Any
from .config_loader import get_environments, reload_configs
from .models import SessionLocal, CloudEnvironment
from .logging_config import get_logger

logger = get_logger(__name__)


def sync_environments_from_yaml(
    dry_run: bool = False,
    force: bool = False
) -> Dict[str, List]:
    """
    Sync environments from config/environments.yaml to the database.
    
    Args:
        dry_run: If True, only report what would be done without making changes.
        force: If True, update existing database entries from YAML.
               WARNING: This will overwrite manual configuration changes.
    
    Returns:
        Dict with keys:
            - created: List of environment names that were created
            - updated: List of environment names that were updated (force mode only)
            - skipped: List of environment names skipped (DB exists, no force)
            - errors: List of dicts with 'name' and 'error' keys
    
    Raises:
        ValueError: If YAML config has missing required environment variables
    """
    # Force reload to get fresh config
    reload_configs()
    
    result = {
        "created": [],
        "updated": [],
        "skipped": [],
        "errors": []
    }
    
    try:
        yaml_envs = get_environments()
    except ValueError as e:
        # Missing environment variable
        logger.error(f"Failed to load environments.yaml: {e}")
        result["errors"].append({"name": "_config", "error": str(e)})
        return result
    
    if not yaml_envs:
        logger.info("No environments defined in environments.yaml")
        return result
    
    db = SessionLocal()
    
    try:
        for name, config in yaml_envs.items():
            try:
                _sync_single_environment(
                    db=db,
                    name=name,
                    config=config,
                    dry_run=dry_run,
                    force=force,
                    result=result
                )
            except Exception as e:
                logger.error(f"Failed to sync environment '{name}': {e}")
                result["errors"].append({"name": name, "error": str(e)})
                # Continue with other environments
                db.rollback()
        
        return result
        
    finally:
        db.close()


def _sync_single_environment(
    db,
    name: str,
    config: Dict[str, Any],
    dry_run: bool,
    force: bool,
    result: Dict[str, List]
) -> None:
    """
    Sync a single environment from YAML config to database.
    
    Args:
        db: Database session
        name: Environment name
        config: Environment configuration from YAML
        dry_run: If True, don't make changes
        force: If True, update existing entries
        result: Result dict to update
    """
    existing = db.query(CloudEnvironment).filter(
        CloudEnvironment.name == name
    ).first()
    
    provider = config.get("provider", "AWS")
    credentials = config.get("credentials", {})
    env_config = config.get("config", {})
    
    if existing:
        if force:
            # Update existing entry
            if dry_run:
                logger.info(f"[DRY RUN] Would update environment '{name}'")
                result["updated"].append(name)
            else:
                existing.provider_type = provider
                existing.credentials = credentials
                existing.config = env_config
                db.commit()
                logger.info(f"Updated environment '{name}' from YAML config")
                result["updated"].append(name)
        else:
            # DB wins - skip YAML config
            logger.info(f"Environment '{name}' exists in DB, skipping YAML config")
            result["skipped"].append(name)
    else:
        # Create new entry
        if dry_run:
            logger.info(f"[DRY RUN] Would create environment '{name}'")
            result["created"].append(name)
        else:
            new_env = CloudEnvironment(
                name=name,
                provider_type=provider,
                credentials=credentials,
                config=env_config
            )
            db.add(new_env)
            db.commit()
            logger.info(f"Created environment '{name}' from YAML config (ID: {new_env.id})")
            result["created"].append(name)


def list_yaml_environments() -> Dict[str, Dict]:
    """
    List environments defined in YAML without expanding env vars.
    
    Useful for showing what's configured without requiring all
    environment variables to be set.
    
    Returns:
        Dict of environment names to their raw config
    """
    return get_environments(expand_env_vars=False)


def validate_yaml_environments() -> Dict[str, Any]:
    """
    Validate that all required environment variables are set.
    
    Returns:
        Dict with:
            - valid: bool indicating if all environments are valid
            - environments: Dict mapping env names to validation results
    """
    raw_envs = get_environments(expand_env_vars=False)
    results = {"valid": True, "environments": {}}
    
    for name, config in raw_envs.items():
        try:
            # Try to expand - will raise if required vars missing
            from .config_loader import _expand_env_vars_recursive
            _expand_env_vars_recursive(config)
            results["environments"][name] = {"valid": True}
        except ValueError as e:
            results["valid"] = False
            results["environments"][name] = {"valid": False, "error": str(e)}
    
    return results

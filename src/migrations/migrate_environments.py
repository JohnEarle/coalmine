"""
Migration script: CloudEnvironment -> Credential + Account

Migrates existing CloudEnvironment data to the new Credential/Account model.
Each CloudEnvironment becomes:
  - One Credential (STATIC type, SINGLE scope)
  - One Account linked to that credential

Usage:
    docker compose exec app python -m src.migrations.migrate_environments
    docker compose exec app python -m src.migrations.migrate_environments --dry-run
"""
import argparse
from sqlalchemy.orm import Session

from ..models import (
    SessionLocal, 
    CloudEnvironment, 
    Credential, 
    Account,
    CredentialAuthType, 
    CredentialScope,
    AccountSource,
    ResourceStatus
)
from ..logging_config import get_logger

logger = get_logger(__name__)


def migrate_environments(dry_run: bool = False) -> dict:
    """
    Migrate CloudEnvironment records to Credential + Account.
    
    Args:
        dry_run: If True, preview without making changes
        
    Returns:
        Summary of migration results
    """
    db = SessionLocal()
    try:
        environments = db.query(CloudEnvironment).all()
        
        results = {
            "total": len(environments),
            "migrated": 0,
            "skipped": 0,
            "errors": []
        }
        
        for env in environments:
            try:
                # Check if already migrated (credential with same name exists)
                existing_cred = db.query(Credential).filter(
                    Credential.name == f"{env.name}-cred"
                ).first()
                
                existing_account = db.query(Account).filter(
                    Account.name == env.name
                ).first()
                
                if existing_cred or existing_account:
                    logger.info(f"Skipping {env.name} - already migrated")
                    results["skipped"] += 1
                    continue
                
                # Extract account_id from config if available
                config = env.config or {}
                account_id = (
                    config.get("account_id") or 
                    config.get("project_id") or 
                    config.get("subscription_id") or
                    "unknown"
                )
                
                # For GCP, try to extract project_id from service account JSON
                if env.provider_type == "GCP" and account_id == "unknown":
                    creds = env.credentials or {}
                    sa_json = creds.get("service_account_json")
                    if sa_json:
                        import json
                        try:
                            if isinstance(sa_json, str):
                                sa_data = json.loads(sa_json)
                            else:
                                sa_data = sa_json
                            account_id = sa_data.get("project_id", "unknown")
                        except Exception:
                            pass
                
                if dry_run:
                    logger.info(f"[DRY-RUN] Would migrate: {env.name} -> Credential + Account (account_id: {account_id})")
                    results["migrated"] += 1
                    continue
                
                # Create Credential
                credential = Credential(
                    name=f"{env.name}-cred",
                    provider=env.provider_type,
                    auth_type=CredentialAuthType.STATIC,
                    scope=CredentialScope.SINGLE,
                    secrets=env.credentials,
                    status=env.status if env.status else ResourceStatus.ACTIVE
                )
                db.add(credential)
                db.flush()  # Get credential.id
                
                # Create Account
                account = Account(
                    name=env.name,
                    credential_id=credential.id,
                    account_id=account_id,
                    source=AccountSource.MIGRATED,
                    account_metadata={
                        "migrated_from": "CloudEnvironment",
                        "original_config": config
                    },
                    status=env.status if env.status else ResourceStatus.ACTIVE
                )
                db.add(account)
                
                logger.info(f"Migrated: {env.name} -> {credential.name} + {account.name}")
                results["migrated"] += 1
                
            except Exception as e:
                logger.error(f"Error migrating {env.name}: {e}")
                results["errors"].append({
                    "environment": env.name,
                    "error": str(e)
                })
        
        if not dry_run:
            db.commit()
            logger.info(f"Migration complete. Committed {results['migrated']} records.")
        else:
            logger.info(f"[DRY-RUN] Would migrate {results['migrated']} records.")
        
        return results
        
    except Exception as e:
        db.rollback()
        logger.error(f"Migration failed: {e}")
        raise
    finally:
        db.close()


def main():
    parser = argparse.ArgumentParser(description="Migrate CloudEnvironments to Credential/Account")
    parser.add_argument("--dry-run", action="store_true", help="Preview changes without applying")
    args = parser.parse_args()
    
    print("=" * 60)
    print("CloudEnvironment -> Credential/Account Migration")
    print("=" * 60)
    
    results = migrate_environments(dry_run=args.dry_run)
    
    print(f"\nResults:")
    print(f"  Total environments: {results['total']}")
    print(f"  Migrated: {results['migrated']}")
    print(f"  Skipped: {results['skipped']}")
    print(f"  Errors: {len(results['errors'])}")
    
    if results["errors"]:
        print("\nErrors:")
        for err in results["errors"]:
            print(f"  - {err['environment']}: {err['error']}")


if __name__ == "__main__":
    main()

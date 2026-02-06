#!/usr/bin/env python3
"""
Migration Script: CloudEnvironment → Account + Credential

This script migrates existing CloudEnvironment data to the new
Account + Credential model, then updates all CanaryResource and
LoggingResource records to use account_id instead of environment_id.

Run with: python -m scripts.migrate_environments [--dry-run]
"""
import argparse
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.models import (
    SessionLocal, CloudEnvironment, Credential, Account, 
    CanaryResource, LoggingResource, CredentialAuthType, AccountSource
)


def migrate_environments(dry_run: bool = False):
    """
    Migrate CloudEnvironment records to Credential + Account.
    
    For each CloudEnvironment:
    1. Create a Credential with the same credentials
    2. Create an Account linked to that Credential
    3. Update CanaryResource.account_id to point to the new Account
    4. Update LoggingResource.account_id to point to the new Account
    """
    db = SessionLocal()
    
    try:
        # Get all CloudEnvironments
        envs = db.query(CloudEnvironment).all()
        
        if not envs:
            print("No CloudEnvironment records found. Nothing to migrate.")
            return
        
        print(f"Found {len(envs)} CloudEnvironment records to migrate.")
        print()
        
        migrated_accounts = {}  # env.id -> account
        
        for env in envs:
            print(f"Processing: {env.name} (provider: {env.provider_type})")
            
            # Check if already migrated (Credential with same name exists)
            cred_name = f"{env.name}-cred"
            existing_cred = db.query(Credential).filter(
                Credential.name == cred_name
            ).first()
            
            if existing_cred:
                print(f"  Credential '{cred_name}' already exists, checking account...")
                existing_account = db.query(Account).filter(
                    Account.credential_id == existing_cred.id
                ).first()
                
                if existing_account:
                    print(f"  Account '{existing_account.name}' already exists. Skipping.")
                    migrated_accounts[env.id] = existing_account
                    continue
            
            if dry_run:
                print(f"  [DRY RUN] Would create Credential: {cred_name}")
                print(f"  [DRY RUN] Would create Account: {env.name}")
                continue
            
            # Create Credential
            if not existing_cred:
                cred = Credential(
                    name=cred_name,
                    provider=env.provider_type,
                    auth_type=CredentialAuthType.STATIC,
                    secrets=env.credentials,
                    status=env.status
                )
                db.add(cred)
                db.flush()
                print(f"  Created Credential: {cred.name} ({cred.id})")
            else:
                cred = existing_cred
            
            # Create Account
            # Use project_id/account_id from config if available
            config = env.config or {}
            creds = env.credentials or {}
            account_id = (
                config.get("account_id") or 
                config.get("project_id") or
                creds.get("project_id") or
                "unknown"
            )
            
            account = Account(
                name=env.name,
                credential_id=cred.id,
                account_id=account_id,
                source=AccountSource.MIGRATED,
                account_metadata=env.config,
                is_enabled="true",
                status=env.status
            )
            db.add(account)
            db.flush()
            print(f"  Created Account: {account.name} ({account.id})")
            
            migrated_accounts[env.id] = account
        
        if dry_run:
            print("\n[DRY RUN] No changes made.")
            return
        
        # Now update CanaryResource and LoggingResource records
        print("\nUpdating CanaryResource records...")
        canaries = db.query(CanaryResource).filter(
            CanaryResource.environment_id.isnot(None),
            CanaryResource.account_id.is_(None)
        ).all()
        
        updated_canaries = 0
        for canary in canaries:
            if canary.environment_id in migrated_accounts:
                canary.account_id = migrated_accounts[canary.environment_id].id
                updated_canaries += 1
        
        print(f"  Updated {updated_canaries} canary records.")
        
        print("\nUpdating LoggingResource records...")
        logs = db.query(LoggingResource).filter(
            LoggingResource.environment_id.isnot(None),
            LoggingResource.account_id.is_(None)
        ).all()
        
        updated_logs = 0
        for log in logs:
            if log.environment_id in migrated_accounts:
                log.account_id = migrated_accounts[log.environment_id].id
                updated_logs += 1
        
        print(f"  Updated {updated_logs} logging resource records.")
        
        # Commit all changes
        db.commit()
        print("\nMigration complete!")
        print(f"  - Created {len(migrated_accounts)} Account records")
        print(f"  - Updated {updated_canaries} CanaryResource records")
        print(f"  - Updated {updated_logs} LoggingResource records")
        
    except Exception as e:
        db.rollback()
        print(f"\nError during migration: {e}")
        raise
    finally:
        db.close()


def main():
    parser = argparse.ArgumentParser(
        description="Migrate CloudEnvironment to Account + Credential model"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be migrated without making changes"
    )
    
    args = parser.parse_args()
    migrate_environments(dry_run=args.dry_run)


if __name__ == "__main__":
    main()

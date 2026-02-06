"""
Credential Service

Provides business logic for managing cloud credentials.
"""
import json
from typing import Optional, List

from .base import BaseService, ServiceResult, ListResult
from src.models import Credential, Account, CredentialAuthType, ResourceStatus


class CredentialService(BaseService):
    """
    Service for managing cloud credentials.
    
    Credentials are reusable authentication sources that can access
    one or more cloud accounts.
    """
    
    def create(
        self,
        name: str,
        provider: str,
        auth_type: str = "STATIC",
        secrets: Optional[dict] = None,
        discovery_config: Optional[dict] = None
    ) -> ServiceResult[Credential]:
        """
        Create a new credential.
        
        Args:
            name: Display name for the credential
            provider: Cloud provider (AWS, GCP)
            auth_type: Authentication type (STATIC, ASSUME_ROLE, IMPERSONATE)
            secrets: Credential secrets (access keys, SA JSON, etc.)
            discovery_config: Configuration for account discovery
            
        Returns:
            ServiceResult containing the created Credential or error
        """
        try:
            # Validate auth type
            try:
                auth_type_enum = CredentialAuthType[auth_type]
            except KeyError:
                valid_types = [t.name for t in CredentialAuthType]
                return ServiceResult.fail(
                    f"Invalid auth_type '{auth_type}'. Valid types: {valid_types}"
                )
            
            # Check for existing
            existing = self.db.query(Credential).filter(
                Credential.name == name
            ).first()
            if existing:
                return ServiceResult.fail(f"Credential '{name}' already exists")
            
            cred = Credential(
                name=name,
                provider=provider.upper(),
                auth_type=auth_type_enum,
                secrets=secrets,
                discovery_config=discovery_config
            )
            self.db.add(cred)
            self._commit_and_refresh(cred)
            
            return ServiceResult.ok(cred)
            
        except Exception as e:
            self.db.rollback()
            return ServiceResult.fail(f"Error creating credential: {e}")
    
    def list(self) -> ListResult[Credential]:
        """
        List all credentials.
        
        Returns:
            ListResult containing all credentials
        """
        creds = self.db.query(Credential).all()
        return ListResult(items=creds, total=len(creds))
    
    def get(self, identifier: str) -> ServiceResult[Credential]:
        """
        Get a specific credential by ID or name.
        
        Args:
            identifier: Credential UUID or name
            
        Returns:
            ServiceResult containing the Credential or error
        """
        cred = self._resolve_by_id_or_name(Credential, identifier)
        if not cred:
            return ServiceResult.fail(f"Credential '{identifier}' not found")
        return ServiceResult.ok(cred)
    
    def update(
        self,
        identifier: str,
        auth_type: Optional[str] = None,
        secrets: Optional[dict] = None,
        discovery_config: Optional[dict] = None
    ) -> ServiceResult[Credential]:
        """
        Update an existing credential.
        
        Args:
            identifier: Credential UUID or name
            auth_type: Update authentication type
            secrets: Update secrets
            discovery_config: Update discovery configuration
            
        Returns:
            ServiceResult containing the updated Credential or error
        """
        try:
            cred = self._resolve_by_id_or_name(Credential, identifier)
            if not cred:
                return ServiceResult.fail(f"Credential '{identifier}' not found")
            
            updated = False
            
            if auth_type:
                try:
                    cred.auth_type = CredentialAuthType[auth_type]
                    updated = True
                except KeyError:
                    return ServiceResult.fail(f"Invalid auth_type: {auth_type}")
            
            if secrets is not None:
                cred.secrets = secrets
                updated = True
            
            if discovery_config is not None:
                cred.discovery_config = discovery_config
                updated = True
            
            if updated:
                self._commit_and_refresh(cred)
            
            return ServiceResult.ok(cred)
            
        except Exception as e:
            self.db.rollback()
            return ServiceResult.fail(f"Error updating credential: {e}")
    
    def delete(self, identifier: str, force: bool = False) -> ServiceResult[None]:
        """
        Delete a credential.
        
        Args:
            identifier: Credential UUID or name
            force: If True, also delete associated accounts
            
        Returns:
            ServiceResult indicating success or error
        """
        try:
            cred = self._resolve_by_id_or_name(Credential, identifier)
            if not cred:
                return ServiceResult.fail(f"Credential '{identifier}' not found")
            
            account_count = len(cred.accounts) if cred.accounts else 0
            if account_count > 0 and not force:
                return ServiceResult.fail(
                    f"Credential has {account_count} associated accounts. "
                    "Use force=True to delete credential and all associated accounts."
                )
            
            name = cred.name
            self.db.delete(cred)
            self.db.commit()
            
            return ServiceResult.ok(None)
            
        except Exception as e:
            self.db.rollback()
            return ServiceResult.fail(f"Error deleting credential: {e}")
    
    def validate(self, identifier: str) -> ServiceResult[tuple]:
        """
        Validate credential health.
        
        Args:
            identifier: Credential UUID or name
            
        Returns:
            ServiceResult containing (is_healthy, message) tuple
        """
        from src.health import CredentialHealthCheck
        
        cred = self._resolve_by_id_or_name(Credential, identifier)
        if not cred:
            return ServiceResult.fail(f"Credential '{identifier}' not found")
        
        try:
            checker = CredentialHealthCheck()
            is_healthy, message = checker.check(cred)
            return ServiceResult.ok((is_healthy, message))
        except Exception as e:
            return ServiceResult.fail(f"Error validating credential: {e}")
    
    def sync(
        self,
        dry_run: bool = False,
        force: bool = False,
        validate_only: bool = False
    ) -> ServiceResult[dict]:
        """
        Sync credentials from YAML configuration.
        
        Args:
            dry_run: If True, show what would be synced without making changes
            force: If True, overwrite existing DB entries
            validate_only: If True, only validate environment variables
            
        Returns:
            ServiceResult containing sync results dictionary
        """
        from src.credential_sync import sync_credentials_from_yaml, validate_credentials_yaml
        
        try:
            if validate_only:
                result = validate_credentials_yaml()
                return ServiceResult.ok(result)
            
            result = sync_credentials_from_yaml(dry_run=dry_run, force=force)
            return ServiceResult.ok(result)
        except Exception as e:
            return ServiceResult.fail(f"Error syncing credentials: {e}")
    
    def discover_accounts(self, identifier: str) -> ServiceResult[dict]:
        """
        Discover accounts accessible by this credential.
        
        Args:
            identifier: Credential UUID or name
            
        Returns:
            ServiceResult containing discovery results
        """
        from src.discovery import discover_accounts as do_discover
        from dataclasses import asdict
        
        cred = self._resolve_by_id_or_name(Credential, identifier)
        if not cred:
            return ServiceResult.fail(f"Credential '{identifier}' not found")
        
        try:
            # Perform discovery - returns list of DiscoveredAccount dataclasses
            discovered = do_discover(cred)
            
            # Create accounts for new discoveries
            created = []
            skipped = []
            
            for acc in discovered:
                existing = self.db.query(Account).filter(
                    Account.credential_id == cred.id,
                    Account.account_id == acc.account_id
                ).first()
                
                if existing:
                    skipped.append(acc.account_id)
                    continue
                
                # Generate name
                name = f"{cred.name}-{acc.account_id[:8]}"
                
                account = Account(
                    name=name,
                    credential_id=cred.id,
                    account_id=acc.account_id,
                    source="DISCOVERED",
                    account_metadata=acc.metadata
                )
                self.db.add(account)
                created.append(acc.account_id)
            
            self.db.commit()
            
            # Convert DiscoveredAccount dataclasses to dicts for JSON response
            account_dicts = [asdict(acc) for acc in discovered]
            
            return ServiceResult.ok({
                "credential_name": cred.name,
                "discovered": len(discovered),
                "created": len(created),
                "skipped": len(skipped),
                "accounts": account_dicts
            })
            
        except Exception as e:
            self.db.rollback()
            return ServiceResult.fail(f"Error discovering accounts: {e}")
    
    def preview_discoverable_accounts(self, identifier: str) -> ServiceResult[dict]:
        """
        Preview accounts that can be discovered (read-only).
        
        Args:
            identifier: Credential UUID or name
            
        Returns:
            ServiceResult containing preview results
        """
        from src.discovery import discover_accounts as do_discover
        from dataclasses import asdict
        
        cred = self._resolve_by_id_or_name(Credential, identifier)
        if not cred:
            return ServiceResult.fail(f"Credential '{identifier}' not found")
        
        try:
            # Returns list of DiscoveredAccount dataclasses
            discovered = do_discover(cred)
            
            # Mark which already exist and convert to dicts
            accounts_with_status = []
            for acc in discovered:
                existing = self.db.query(Account).filter(
                    Account.credential_id == cred.id,
                    Account.account_id == acc.account_id
                ).first()
                
                acc_dict = asdict(acc)
                acc_dict["already_exists"] = existing is not None
                accounts_with_status.append(acc_dict)
            
            return ServiceResult.ok({
                "credential_name": cred.name,
                "provider": cred.provider,
                "accounts": accounts_with_status,
                "total": len(accounts_with_status)
            })
            
        except Exception as e:
            return ServiceResult.ok({
                "credential_name": cred.name,
                "provider": cred.provider,
                "accounts": [],
                "total": 0,
                "error": str(e)
            })

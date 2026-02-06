"""
Account Service

Provides business logic for managing cloud accounts (deployment targets).
"""
import uuid as uuid_module
from typing import Optional, List

from .base import BaseService, ServiceResult, ListResult
from src.models import Account, Credential, AccountSource, ResourceStatus


class AccountService(BaseService):
    """
    Service for managing cloud accounts.
    
    Accounts are deployment targets (AWS accounts, GCP projects) linked to credentials.
    """
    
    def create(
        self,
        name: str,
        credential_id: str,
        account_id: str,
        role_override: Optional[str] = None,
        metadata: Optional[dict] = None,
        source: AccountSource = AccountSource.MANUAL
    ) -> ServiceResult[Account]:
        """
        Create a new cloud account.
        
        Args:
            name: Display name for the account
            credential_id: UUID or name of the credential to use
            account_id: Cloud account ID (AWS account ID or GCP project ID)
            role_override: Optional role/service account override
            metadata: Optional metadata dictionary
            source: Source of the account (MANUAL or DISCOVERED)
            
        Returns:
            ServiceResult containing the created Account or error
        """
        try:
            # Check for existing account with same name
            existing = self.db.query(Account).filter(
                Account.name == name
            ).first()
            if existing:
                return ServiceResult.fail(f"Account '{name}' already exists")
            
            # Find credential
            cred = self._resolve_credential(credential_id)
            if not cred:
                return ServiceResult.fail(f"Credential '{credential_id}' not found")
            
            # Check for duplicate account_id under same credential
            duplicate = self.db.query(Account).filter(
                Account.credential_id == cred.id,
                Account.account_id == account_id
            ).first()
            if duplicate:
                return ServiceResult.fail(
                    f"Account ID '{account_id}' already exists under credential '{cred.name}'"
                )
            
            account = Account(
                name=name,
                credential_id=cred.id,
                account_id=account_id,
                source=source,
                role_override=role_override,
                account_metadata=metadata
            )
            self.db.add(account)
            self._commit_and_refresh(account)
            
            return ServiceResult.ok(account)
            
        except Exception as e:
            self.db.rollback()
            return ServiceResult.fail(f"Error creating account: {e}")
    
    def list(
        self,
        credential: Optional[str] = None,
        provider: Optional[str] = None
    ) -> ListResult[Account]:
        """
        List all accounts with optional filtering.
        
        Args:
            credential: Filter by credential name or ID
            provider: Filter by provider (AWS, GCP)
            
        Returns:
            ListResult containing matching accounts
        """
        query = self.db.query(Account)
        
        if credential:
            cred = self._resolve_credential(credential)
            if cred:
                query = query.filter(Account.credential_id == cred.id)
            else:
                return ListResult(items=[], total=0)
        
        if provider:
            query = query.join(Credential).filter(
                Credential.provider == provider.upper()
            )
        
        accounts = query.all()
        return ListResult(items=accounts, total=len(accounts))
    
    def get(self, identifier: str) -> ServiceResult[Account]:
        """
        Get a specific account by ID or name.
        
        Args:
            identifier: Account UUID or name
            
        Returns:
            ServiceResult containing the Account or error
        """
        account = self._resolve_by_id_or_name(Account, identifier)
        if not account:
            return ServiceResult.fail(f"Account '{identifier}' not found")
        return ServiceResult.ok(account)
    
    def update(
        self,
        identifier: str,
        is_enabled: Optional[bool] = None,
        role_override: Optional[str] = None,
        metadata: Optional[dict] = None
    ) -> ServiceResult[Account]:
        """
        Update an existing account.
        
        Args:
            identifier: Account UUID or name
            is_enabled: Enable/disable the account
            role_override: Update role override (pass empty string to clear)
            metadata: Update metadata
            
        Returns:
            ServiceResult containing the updated Account or error
        """
        try:
            account = self._resolve_by_id_or_name(Account, identifier)
            if not account:
                return ServiceResult.fail(f"Account '{identifier}' not found")
            
            updated = False
            
            if is_enabled is not None:
                account.is_enabled = "true" if is_enabled else "false"
                updated = True
            
            if role_override is not None:
                account.role_override = role_override if role_override else None
                updated = True
            
            if metadata is not None:
                account.account_metadata = metadata
                updated = True
            
            if updated:
                self._commit_and_refresh(account)
            
            return ServiceResult.ok(account)
            
        except Exception as e:
            self.db.rollback()
            return ServiceResult.fail(f"Error updating account: {e}")
    
    def enable(self, identifier: str) -> ServiceResult[Account]:
        """Enable an account."""
        return self.update(identifier, is_enabled=True)
    
    def disable(self, identifier: str) -> ServiceResult[Account]:
        """Disable an account."""
        return self.update(identifier, is_enabled=False)
    
    def delete(self, identifier: str) -> ServiceResult[None]:
        """
        Delete an account.
        
        Args:
            identifier: Account UUID or name
            
        Returns:
            ServiceResult indicating success or error
        """
        try:
            account = self._resolve_by_id_or_name(Account, identifier)
            if not account:
                return ServiceResult.fail(f"Account '{identifier}' not found")
            
            # TODO: Check for canaries once migration is complete
            # if account.canaries:
            #     return ServiceResult.fail(
            #         f"Cannot delete account with {len(account.canaries)} deployed canaries"
            #     )
            
            name = account.name
            self.db.delete(account)
            self.db.commit()
            
            return ServiceResult.ok(None)
            
        except Exception as e:
            self.db.rollback()
            return ServiceResult.fail(f"Error deleting account: {e}")
    
    def validate(self, identifier: str) -> ServiceResult[tuple]:
        """
        Validate account health.
        
        Args:
            identifier: Account UUID or name
            
        Returns:
            ServiceResult containing (is_healthy, message) tuple
        """
        from src.health import AccountHealthCheck
        
        account = self._resolve_by_id_or_name(Account, identifier)
        if not account:
            return ServiceResult.fail(f"Account '{identifier}' not found")
        
        try:
            checker = AccountHealthCheck()
            is_healthy, message = checker.check(account)
            return ServiceResult.ok((is_healthy, message))
        except Exception as e:
            return ServiceResult.fail(f"Error validating account: {e}")
    
    def _resolve_credential(self, identifier: str) -> Optional[Credential]:
        """Find credential by name or ID."""
        return self._resolve_by_id_or_name(Credential, identifier)

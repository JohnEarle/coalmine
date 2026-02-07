"""
User Management Service

Provides business logic for user lifecycle management:
- List, create, update, delete users
- List available roles from RBAC policy

Both CLI and API use this service for all user operations.
"""
from dataclasses import dataclass
from typing import Optional, List

from .base import BaseService, ServiceResult, ListResult
from ..logging_config import get_logger

logger = get_logger(__name__)


@dataclass
class UserInfo:
    """User metadata for service consumers."""
    id: str
    email: str
    role: str
    is_active: bool
    is_verified: bool
    is_superuser: bool
    display_name: Optional[str] = None


class UserService(BaseService):
    """
    Service for managing user accounts.
    
    Wraps database operations on the User model with
    validation, password hashing, and consistent error handling.
    """
    
    def list(self) -> ListResult[UserInfo]:
        """
        List all users.
        
        Returns:
            ListResult containing UserInfo items.
        """
        from ..models import User
        
        users = self.db.query(User).all()
        items = [
            UserInfo(
                id=str(u.id),
                email=u.email,
                role=u.role,
                is_active=u.is_active,
                is_verified=u.is_verified,
                is_superuser=u.is_superuser,
                display_name=u.display_name,
            )
            for u in users
        ]
        return ListResult(items=items, total=len(items))
    
    def get(self, identifier: str) -> ServiceResult[UserInfo]:
        """
        Get a user by UUID or email.
        
        Args:
            identifier: User UUID or email address
            
        Returns:
            ServiceResult containing UserInfo or error
        """
        user = self._resolve_user(identifier)
        if not user:
            return ServiceResult.fail(f"User '{identifier}' not found")
        return ServiceResult.ok(self._to_info(user))
    
    def create(
        self,
        email: str,
        password: str,
        role: str = "viewer",
        display_name: Optional[str] = None,
        is_superuser: bool = False,
    ) -> ServiceResult[UserInfo]:
        """
        Create a new user.
        
        Args:
            email: User email (must be unique)
            password: Plain-text password (will be hashed)
            role: Role name (must exist in RBAC policy)
            display_name: Optional display name
            is_superuser: Whether user is a superuser
            
        Returns:
            ServiceResult containing created UserInfo or error
        """
        from ..models import User
        from fastapi_users.password import PasswordHelper
        
        # Validate role
        valid_roles = self.list_roles().items
        if valid_roles and role not in valid_roles:
            return ServiceResult.fail(
                f"Invalid role '{role}'. Valid roles: {', '.join(valid_roles)}"
            )
        
        # Check for duplicate email
        existing = self.db.query(User).filter(User.email == email).first()
        if existing:
            return ServiceResult.fail(f"User with email '{email}' already exists")
        
        # Hash password
        password_helper = PasswordHelper()
        hashed = password_helper.hash(password)
        
        user = User(
            email=email,
            hashed_password=hashed,
            is_active=True,
            is_verified=True,
            is_superuser=is_superuser,
            role=role,
            display_name=display_name,
        )
        
        self.db.add(user)
        self._commit_and_refresh(user)
        
        logger.info(f"Created user: {email} (role={role})")
        return ServiceResult.ok(self._to_info(user))
    
    def update(
        self,
        identifier: str,
        role: Optional[str] = None,
        display_name: Optional[str] = None,
        is_active: Optional[bool] = None,
        is_superuser: Optional[bool] = None,
    ) -> ServiceResult[UserInfo]:
        """
        Update a user's attributes.
        
        Args:
            identifier: User UUID or email
            role: New role (validated against RBAC policy)
            display_name: New display name
            is_active: Activate/deactivate user
            is_superuser: Grant/revoke superuser
            
        Returns:
            ServiceResult containing updated UserInfo or error
        """
        user = self._resolve_user(identifier)
        if not user:
            return ServiceResult.fail(f"User '{identifier}' not found")
        
        if role is not None:
            valid_roles = self.list_roles().items
            if valid_roles and role not in valid_roles:
                return ServiceResult.fail(
                    f"Invalid role '{role}'. Valid roles: {', '.join(valid_roles)}"
                )
            user.role = role
        
        if display_name is not None:
            user.display_name = display_name
        
        if is_active is not None:
            user.is_active = is_active
        
        if is_superuser is not None:
            user.is_superuser = is_superuser
        
        self._commit_and_refresh(user)
        
        logger.info(f"Updated user: {user.email}")
        return ServiceResult.ok(self._to_info(user))
    
    def delete(self, identifier: str) -> ServiceResult[dict]:
        """
        Delete a user.
        
        Args:
            identifier: User UUID or email
            
        Returns:
            ServiceResult indicating success/failure
        """
        user = self._resolve_user(identifier)
        if not user:
            return ServiceResult.fail(f"User '{identifier}' not found")
        
        email = user.email
        self.db.delete(user)
        self.db.commit()
        
        logger.info(f"Deleted user: {email}")
        return ServiceResult.ok({"email": email, "deleted": True})
    
    def list_roles(self) -> ListResult[str]:
        """
        List available roles from the RBAC policy.
        
        Returns:
            ListResult containing role name strings,
            ordered from most to least privileged.
        """
        try:
            from ..auth.rbac import get_roles
            roles = get_roles()
        except Exception as e:
            logger.warning(f"Could not load roles from Casbin: {e}")
            roles = ["superuser", "admin", "operator", "viewer"]
        
        return ListResult(items=roles, total=len(roles))
    
    def _resolve_user(self, identifier: str):
        """Find a user by UUID or email."""
        from ..models import User
        return self._resolve_by_id_or_name(User, identifier, name_field="email")
    
    @staticmethod
    def _to_info(user) -> UserInfo:
        """Convert a User model to UserInfo dataclass."""
        return UserInfo(
            id=str(user.id),
            email=user.email,
            role=user.role,
            is_active=user.is_active,
            is_verified=user.is_verified,
            is_superuser=user.is_superuser,
            display_name=user.display_name,
        )

"""
Auth Service

Provides lifecycle management for authentication entities:
- API keys (create, revoke, list)
- Sessions (list, revoke)
- RBAC policy (reload)
"""
import secrets
import hashlib
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from pathlib import Path

from .base import BaseService, ServiceResult, ListResult
from ..logging_config import get_logger

logger = get_logger(__name__)


@dataclass
class ApiKeyInfo:
    """API key metadata (without exposing actual key)."""
    name: str
    description: str
    permissions: List[str]
    scopes: List[str]
    expires_at: Optional[str] = None
    has_ip_allowlist: bool = False
    owner: Optional[str] = None
    is_active: bool = True


@dataclass
class SessionInfo:
    """Session metadata."""
    session_id: str
    username: str
    role: str
    auth_method: str
    created_at: Optional[str] = None


class AuthService(BaseService):
    """
    Service for managing authentication lifecycle.
    
    Handles API keys, sessions, and RBAC policies.
    """
    
    def __init__(self, db=None):
        super().__init__(db)
        self._api_keys_file = self._find_api_keys_file()
    
    def _find_api_keys_file(self) -> Path:
        """Find the api_keys.yaml config file."""
        # Try Docker path first
        docker_path = Path("/app/config/api_keys.yaml")
        if docker_path.exists():
            return docker_path
        
        # Try project root
        project_root = Path(__file__).parent.parent.parent
        local_path = project_root / "config" / "api_keys.yaml"
        if local_path.exists():
            return local_path
        
        return local_path  # Return even if doesn't exist
    
    # =========================================================================
    # API Key Management
    # =========================================================================
    
    def list_api_keys(self) -> ListResult[ApiKeyInfo]:
        """
        List all configured API keys (metadata only).
        
        Returns:
            ListResult containing ApiKeyInfo items.
        """
        try:
            from ..api_keys_loader import get_api_keys, _check_expiration
            
            keys = get_api_keys()
            items = []
            
            for name, config in keys.items():
                is_active = _check_expiration(config.expires_at)
                items.append(ApiKeyInfo(
                    name=name,
                    description=config.description,
                    permissions=config.permissions,
                    scopes=config.scopes,
                    expires_at=config.expires_at,
                    has_ip_allowlist=len(config.ip_allowlist) > 0,
                    owner=config.owner,
                    is_active=is_active
                ))
            
            return ListResult(items=items, total=len(items))
        except Exception as e:
            logger.warning(f"Could not load API keys: {e}")
            return ListResult(items=[], total=0)
    
    def list_user_api_keys(self, username: str) -> ListResult[ApiKeyInfo]:
        """
        List API keys owned by a specific user.
        
        Args:
            username: Owner username to filter by.
            
        Returns:
            ListResult containing ApiKeyInfo items owned by the user.
        """
        all_keys = self.list_api_keys()
        user_keys = [k for k in all_keys.items if k.owner == username]
        return ListResult(items=user_keys, total=len(user_keys))
    
    def create_api_key(
        self,
        name: str,
        permissions: List[str],
        scopes: List[str],
        description: str = "",
        expires_at: Optional[str] = None,
        ip_allowlist: Optional[List[str]] = None,
        owner: Optional[str] = None
    ) -> ServiceResult[Dict[str, Any]]:
        """
        Create a new API key.
        
        Note: This appends to api_keys.yaml. The actual key value is generated
        and returned only once - it cannot be retrieved later.
        
        Args:
            name: Unique name for the key
            permissions: List of permissions (read, write, admin)
            scopes: List of scopes (canaries, credentials, all, etc.)
            description: Human-readable description
            expires_at: Optional ISO 8601 expiration datetime
            ip_allowlist: Optional list of allowed IPs/CIDRs
            owner: Optional username to tie key to
            
        Returns:
            ServiceResult containing the generated key (shown only once)
        """
        import yaml
        from ..api_keys_loader import get_api_keys, reload_api_keys
        
        # Check name doesn't exist
        existing = get_api_keys()
        if name in existing:
            return ServiceResult.fail(f"API key '{name}' already exists")
        
        # Generate secure key
        key_value = f"cm_{secrets.token_urlsafe(32)}"
        
        # Build config entry
        key_config = {
            "key": key_value,
            "permissions": permissions,
            "scopes": scopes,
            "description": description,
        }
        
        if expires_at:
            key_config["expires_at"] = expires_at
        if ip_allowlist:
            key_config["ip_allowlist"] = ip_allowlist
        if owner:
            key_config["owner"] = owner
        
        # Append to YAML file
        try:
            with open(self._api_keys_file, "r") as f:
                content = yaml.safe_load(f) or {}
            
            if "api_keys" not in content:
                content["api_keys"] = {}
            
            content["api_keys"][name] = key_config
            
            with open(self._api_keys_file, "w") as f:
                yaml.dump(content, f, default_flow_style=False, sort_keys=False)
            
            # Reload cache
            reload_api_keys()
            
            logger.info(f"Created API key: {name}")
            
            return ServiceResult.ok({
                "name": name,
                "key": key_value,  # Only time the key is returned
                "message": "Save this key securely - it cannot be retrieved later"
            })
            
        except Exception as e:
            logger.error(f"Error creating API key: {e}")
            return ServiceResult.fail(f"Error creating API key: {e}")
    
    def revoke_api_key(self, name: str) -> ServiceResult[Dict[str, Any]]:
        """
        Revoke (delete) an API key.
        
        Args:
            name: Name of the key to revoke
            
        Returns:
            ServiceResult indicating success/failure
        """
        import yaml
        from ..api_keys_loader import get_api_keys, reload_api_keys
        
        # Check key exists
        existing = get_api_keys()
        if name not in existing:
            return ServiceResult.fail(f"API key '{name}' not found")
        
        # Remove from YAML file
        try:
            with open(self._api_keys_file, "r") as f:
                content = yaml.safe_load(f) or {}
            
            if "api_keys" in content and name in content["api_keys"]:
                del content["api_keys"][name]
            
            with open(self._api_keys_file, "w") as f:
                yaml.dump(content, f, default_flow_style=False, sort_keys=False)
            
            # Reload cache
            reload_api_keys()
            
            logger.info(f"Revoked API key: {name}")
            
            return ServiceResult.ok({
                "name": name,
                "status": "revoked"
            })
            
        except Exception as e:
            logger.error(f"Error revoking API key: {e}")
            return ServiceResult.fail(f"Error revoking API key: {e}")
    
    # =========================================================================
    # Session Management
    # =========================================================================
    
    def list_sessions(self) -> ListResult[SessionInfo]:
        """
        List active user sessions.
        
        Since authentication uses stateless JWTs (coalmine_auth cookie),
        there is no server-side session store to enumerate. Instead, this
        returns recently-active database users as a proxy.
        
        Returns:
            ListResult containing SessionInfo items.
        """
        try:
            from ..models import User, SessionLocal
            with SessionLocal() as db:
                users = db.query(User).filter(User.is_active == True).all()
                sessions = [
                    SessionInfo(
                        session_id=str(u.id)[:8] + "...",
                        username=u.email,
                        role=u.role or "viewer",
                        auth_method="jwt",
                    )
                    for u in users
                ]
            return ListResult(items=sessions, total=len(sessions))
        except Exception as e:
            logger.warning(f"Error listing users: {e}")
            return ListResult(items=[], total=0)
    
    def revoke_session(self, session_id_prefix: str) -> ServiceResult[Dict[str, Any]]:
        """
        Revoke a user session by deactivating the user account.
        
        Since JWTs are stateless, the only way to force-logout is to
        deactivate the user. The JWT will still be valid until expiry,
        but `get_current_auth` checks `is_active` on every request.
        
        Args:
            session_id_prefix: First 8+ characters of user UUID
            
        Returns:
            ServiceResult indicating success/failure
        """
        try:
            from ..models import User, SessionLocal
            with SessionLocal() as db:
                user = db.query(User).filter(
                    User.id.cast(db.bind.dialect.name == 'postgresql' and __import__('sqlalchemy').String or __import__('sqlalchemy').String).like(f"{session_id_prefix}%")
                ).first()
                
                if not user:
                    return ServiceResult.fail(f"No user found matching '{session_id_prefix}'")
                
                user.is_active = False
                db.commit()
                
                logger.info(f"Deactivated user: {user.email}")
                
                return ServiceResult.ok({
                    "username": user.email,
                    "status": "deactivated",
                    "note": "JWT remains valid until expiry but will be rejected on next request"
                })
        except Exception as e:
            logger.error(f"Error revoking session: {e}")
            return ServiceResult.fail(f"Error revoking session: {e}")
    
    # =========================================================================
    # RBAC Policy Management
    # =========================================================================
    
    def reload_rbac(self) -> ServiceResult[Dict[str, Any]]:
        """
        Reload RBAC policies from disk.
        
        This clears the Casbin enforcer cache and forces a reload
        of the model and policy files.
        
        Returns:
            ServiceResult indicating success/failure
        """
        try:
            from ..auth.rbac import reload_enforcer, get_enforcer
            
            reload_enforcer()
            
            # Verify reload by getting enforcer
            enforcer = get_enforcer()
            policy_count = len(enforcer.get_policy())
            
            logger.info(f"Reloaded RBAC policies ({policy_count} rules)")
            
            return ServiceResult.ok({
                "status": "reloaded",
                "policy_count": policy_count
            })
            
        except Exception as e:
            logger.error(f"Error reloading RBAC: {e}")
            return ServiceResult.fail(f"Error reloading RBAC policies: {e}")

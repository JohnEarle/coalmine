"""
Admin Routes

Provides admin-only endpoints for:
- Session management (list, revoke)
- RBAC policy management (reload)
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import List, Optional

from ...services import AuthService
from ..auth import require_role, AuthConfig

router = APIRouter(prefix="/admin", tags=["admin"])


class SessionInfo(BaseModel):
    """Session information."""
    session_id: str
    username: str
    role: str
    auth_method: str
    created_at: Optional[str] = None


class SessionListResponse(BaseModel):
    """Response for listing sessions."""
    sessions: List[SessionInfo]
    total: int


class RbacReloadResponse(BaseModel):
    """Response for RBAC reload."""
    status: str
    policy_count: int


@router.get("/sessions", response_model=SessionListResponse)
async def list_sessions(
    auth: AuthConfig = Depends(require_role("admin"))
):
    """
    List all active sessions (admin only).
    """
    with AuthService() as svc:
        result = svc.list_sessions()
        
        sessions = [
            SessionInfo(
                session_id=s.session_id,
                username=s.username,
                role=s.role,
                auth_method=s.auth_method,
                created_at=s.created_at
            )
            for s in result.items
        ]
        
        return SessionListResponse(
            sessions=sessions,
            total=result.total
        )


@router.delete("/sessions/{session_prefix}")
async def revoke_session(
    session_prefix: str,
    auth: AuthConfig = Depends(require_role("admin"))
):
    """
    Revoke sessions matching a prefix (admin only).
    
    Args:
        session_prefix: First 8+ characters of session ID.
    """
    with AuthService() as svc:
        result = svc.revoke_session(session_prefix)
        
        if not result.success:
            raise HTTPException(status_code=404, detail=result.error)
        
        return {
            "status": "revoked",
            "prefix": session_prefix,
            "revoked_count": result.data["revoked_count"]
        }


@router.post("/rbac/reload", response_model=RbacReloadResponse)
async def reload_rbac(
    auth: AuthConfig = Depends(require_role("admin"))
):
    """
    Reload RBAC policies from disk (admin only).
    
    Forces reload of Casbin model and policy files.
    """
    with AuthService() as svc:
        result = svc.reload_rbac()
        
        if not result.success:
            raise HTTPException(status_code=500, detail=result.error)
        
        return RbacReloadResponse(
            status=result.data["status"],
            policy_count=result.data["policy_count"]
        )

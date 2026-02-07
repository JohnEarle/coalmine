"""
Session Authentication Status for WebUI

Thin wrapper providing auth status and logout endpoints.
All authentication is handled by fastapi-users (JWT cookies).
"""
from fastapi import APIRouter, Request, Response
from pydantic import BaseModel
from typing import Optional

from ..logging_config import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])


class SessionUser(BaseModel):
    """Current session user information."""
    username: str
    role: str


class AuthStatusResponse(BaseModel):
    """Response for auth status check."""
    authenticated: bool
    user: Optional[SessionUser] = None
    oidc_enabled: bool = False
    oidc_provider_name: Optional[str] = None


@router.get("/status", response_model=AuthStatusResponse)
async def get_auth_status(request: Request):
    """
    Check authentication status without throwing errors.
    
    Used by the WebUI to check if user is logged in on page load.
    Also includes OIDC availability for SSO button rendering.
    
    Checks the fastapi-users coalmine_auth JWT cookie.
    """
    # Check OIDC availability
    try:
        from ..auth.oidc import is_oidc_enabled, get_oidc_provider_name
        oidc_enabled = is_oidc_enabled()
        oidc_provider = get_oidc_provider_name() if oidc_enabled else None
    except Exception:
        oidc_enabled = False
        oidc_provider = None
    
    # Check fastapi-users JWT cookie
    cookie = request.cookies.get("coalmine_auth")
    if cookie:
        try:
            from .auth import decode_coalmine_jwt
            from ..auth.users import async_session_maker
            from ..models import User
            from sqlalchemy import select
            
            user_id = decode_coalmine_jwt(cookie)
            if user_id:
                async with async_session_maker() as session:
                    result = await session.execute(
                        select(User).where(User.id == user_id)
                    )
                    user = result.unique().scalar_one_or_none()
                    if user and user.is_active:
                        return AuthStatusResponse(
                            authenticated=True,
                            user=SessionUser(
                                username=user.email,
                                role=user.role
                            ),
                            oidc_enabled=oidc_enabled,
                            oidc_provider_name=oidc_provider
                        )
        except Exception as e:
            logger.debug(f"Auth status check failed: {e}")
    
    return AuthStatusResponse(
        authenticated=False,
        oidc_enabled=oidc_enabled,
        oidc_provider_name=oidc_provider
    )


@router.post("/logout")
async def logout(request: Request, response: Response):
    """Clear JWT cookie and logout user."""
    cookie = request.cookies.get("coalmine_auth")
    if cookie:
        try:
            from .auth import decode_coalmine_jwt
            user_id = decode_coalmine_jwt(cookie)
            logger.info(f"User {user_id} logged out")
        except Exception:
            pass
    
    response.delete_cookie("coalmine_auth")
    
    return {"success": True, "message": "Logged out successfully"}

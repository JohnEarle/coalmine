"""
OIDC/OAuth2 SSO Integration using Authlib

Provides OAuth2 client setup and callback handling for external identity providers.
Supports generic OIDC as well as popular providers (Okta, Auth0, Azure AD, Google).
"""
from authlib.integrations.starlette_client import OAuth, OAuthError
from starlette.config import Config as StarletteConfig
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import RedirectResponse
from typing import Optional, Dict, Any
import secrets

from . import get_auth_config
from ..logging_config import get_logger

logger = get_logger(__name__)

# OAuth client instance (configured lazily)
oauth = OAuth()
_oidc_configured = False


def configure_oidc() -> bool:
    """
    Configure OIDC provider from auth.yaml settings.
    
    Returns:
        True if OIDC is enabled and configured, False otherwise.
    """
    global _oidc_configured
    
    if _oidc_configured:
        return True
    
    try:
        config = get_auth_config()
    except Exception as e:
        logger.warning(f"Could not load auth config for OIDC: {e}")
        return False
    
    if not config.oidc.enabled:
        logger.info("OIDC is disabled in configuration")
        return False
    
    if not config.oidc.issuer or not config.oidc.client_id:
        logger.warning("OIDC enabled but missing issuer or client_id")
        return False
    
    # Register the OIDC provider
    # Authlib auto-discovers endpoints via .well-known/openid-configuration
    oauth.register(
        name="oidc",
        client_id=config.oidc.client_id,
        client_secret=config.oidc.client_secret,
        server_metadata_url=f"{config.oidc.issuer.rstrip('/')}/.well-known/openid-configuration",
        client_kwargs={
            "scope": " ".join(config.oidc.scopes)
        }
    )
    
    _oidc_configured = True
    logger.info(f"OIDC configured with provider: {config.oidc.provider_name}")
    return True


def is_oidc_enabled() -> bool:
    """Check if OIDC is enabled in configuration."""
    try:
        config = get_auth_config()
        return config.oidc.enabled and bool(config.oidc.issuer)
    except Exception:
        return False


def get_oidc_provider_name() -> str:
    """Get the display name for the OIDC provider."""
    try:
        config = get_auth_config()
        return config.oidc.provider_name
    except Exception:
        return "SSO"


def map_claims_to_role(claims: Dict[str, Any]) -> str:
    """
    Map OIDC claims to a Coalmine role.
    
    Uses the role_claim and role_map from configuration.
    
    Args:
        claims: User info claims from the OIDC provider
        
    Returns:
        Coalmine role (admin, operator, viewer)
    """
    try:
        config = get_auth_config()
    except Exception:
        return "viewer"
    
    role_claim = config.oidc.role_claim
    role_map = config.oidc.role_map
    default_role = config.oidc.default_role
    
    # Get the claim value (could be a string or list)
    claim_value = claims.get(role_claim, [])
    
    # Normalize to list
    if isinstance(claim_value, str):
        claim_values = [claim_value]
    else:
        claim_values = list(claim_value) if claim_value else []
    
    # Check each mapping (first match wins, order matters)
    for group_pattern, role in role_map.items():
        for value in claim_values:
            if group_pattern in str(value):
                logger.debug(f"Mapped claim '{value}' to role '{role}'")
                return role
    
    logger.debug(f"No role mapping found for claims, using default: {default_role}")
    return default_role


# =============================================================================
# OIDC Router (mounted in session_auth.py)
# =============================================================================

router = APIRouter(prefix="/auth/oidc", tags=["auth"])


@router.get("/login")
async def oidc_login(request: Request):
    """
    Initiate OIDC login flow.
    
    Redirects to the OIDC provider's authorization endpoint.
    """
    if not configure_oidc():
        raise HTTPException(status_code=503, detail="OIDC is not configured")
    
    # Generate redirect URI back to our callback
    redirect_uri = str(request.url_for("oidc_callback"))
    
    # Store state for CSRF protection
    state = secrets.token_urlsafe(32)
    request.session["oauth_state"] = state
    
    return await oauth.oidc.authorize_redirect(request, redirect_uri, state=state)


@router.get("/callback")
async def oidc_callback(request: Request):
    """
    Handle OIDC callback after user authenticates.
    
    Creates or finds a fastapi-users database user and issues
    a coalmine_auth JWT cookie. No legacy session store involved.
    """
    if not configure_oidc():
        raise HTTPException(status_code=503, detail="OIDC is not configured")
    
    try:
        token = await oauth.oidc.authorize_access_token(request)
    except OAuthError as e:
        logger.error(f"OIDC callback error: {e}")
        raise HTTPException(status_code=401, detail=f"Authentication failed: {e.description}")
    
    user_info = token.get("userinfo")
    if not user_info:
        user_info = await oauth.oidc.userinfo(token=token)
    
    if not user_info:
        raise HTTPException(status_code=401, detail="Could not retrieve user info")
    
    # Extract email (required for fastapi-users)
    email = user_info.get("email")
    if not email:
        email = user_info.get("preferred_username")
    if not email:
        raise HTTPException(status_code=401, detail="OIDC provider did not return an email")
    
    role = map_claims_to_role(user_info)
    
    logger.info(f"OIDC login successful: {email} with role {role}")
    
    # Find or create user in fastapi-users database
    from .users import async_session_maker, get_jwt_strategy
    from ..models import User
    from sqlalchemy import select
    
    async with async_session_maker() as session:
        result = await session.execute(
            select(User).where(User.email == email)
        )
        user = result.unique().scalar_one_or_none()
        
        if not user:
            # Auto-provision OIDC user
            user = User(
                email=email,
                hashed_password="!oidc-managed",  # Cannot login via password
                is_active=True,
                is_superuser=(role == "admin"),
                is_verified=True,
                role=role,
                display_name=user_info.get("name", email),
            )
            session.add(user)
            await session.commit()
            await session.refresh(user)
            logger.info(f"Auto-provisioned OIDC user: {email}")
        else:
            # Update role from IdP on each login
            user.role = role
            user.is_superuser = (role == "admin")
            await session.commit()
    
    # Issue JWT via fastapi-users strategy
    strategy = get_jwt_strategy()
    jwt_token = await strategy.write_token(user)
    
    import os
    response = RedirectResponse(url="/ui", status_code=302)
    response.set_cookie(
        key="coalmine_auth",
        value=jwt_token,
        max_age=3600 * 24,
        httponly=True,
        samesite="lax",
        secure=os.getenv("ENVIRONMENT", "development") == "production",
        path="/",
    )
    
    return response


@router.get("/status")
async def oidc_status():
    """
    Check OIDC configuration status.
    
    Useful for WebUI to determine if SSO button should be shown.
    """
    enabled = is_oidc_enabled()
    return {
        "enabled": enabled,
        "provider_name": get_oidc_provider_name() if enabled else None
    }

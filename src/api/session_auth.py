"""
Session-based Authentication for WebUI

Provides login/logout endpoints and session middleware for browser-based access.
Designed to be fully independent from API key authentication.

This module is intentionally isolated - it uses Redis for session storage
when available (for production), or falls back to in-memory storage for
development. This allows easy extraction to a separate container later.
"""
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel
from typing import Optional, Dict, Any
import secrets
import hashlib
import os
import json

from ..logging_config import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])

# Session configuration
SESSION_COOKIE_NAME = "coalmine_session"
SESSION_MAX_AGE = 86400  # 24 hours


class SessionStore:
    """
    Abstraction for session storage.
    Uses Redis if available, falls back to in-memory for development.
    """
    
    def __init__(self):
        self._memory_store: Dict[str, Dict[str, Any]] = {}
        self._redis = None
        self._init_redis()
    
    def _init_redis(self):
        """Try to connect to Redis for session storage."""
        redis_url = os.getenv("CELERY_BROKER_URL")
        if redis_url:
            try:
                import redis
                # Use a different DB for sessions (db=1) to separate from Celery
                self._redis = redis.from_url(redis_url.replace("/0", "/1"))
                self._redis.ping()
                logger.info("Session store using Redis")
            except Exception as e:
                logger.warning(f"Redis not available for sessions, using memory: {e}")
                self._redis = None
        else:
            logger.info("Session store using in-memory (development mode)")
    
    def get(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve session data."""
        if self._redis:
            try:
                data = self._redis.get(f"session:{session_id}")
                return json.loads(data) if data else None
            except Exception:
                return None
        return self._memory_store.get(session_id)
    
    def set(self, session_id: str, data: Dict[str, Any], ttl: int = SESSION_MAX_AGE):
        """Store session data."""
        if self._redis:
            try:
                self._redis.setex(f"session:{session_id}", ttl, json.dumps(data))
                return
            except Exception as e:
                logger.warning(f"Redis session write failed: {e}")
        self._memory_store[session_id] = data
    
    def delete(self, session_id: str):
        """Remove session data."""
        if self._redis:
            try:
                self._redis.delete(f"session:{session_id}")
                return
            except Exception:
                pass
        self._memory_store.pop(session_id, None)


# Global session store instance
_session_store = SessionStore()


def _get_webui_users() -> Dict[str, Dict[str, Any]]:
    """
    Load WebUI user credentials from environment.
    
    Supports single admin user via env vars for simplicity.
    Can be extended to load from database or YAML config.
    """
    users = {}
    
    # Primary admin user
    admin_user = os.getenv("WEBUI_ADMIN_USER", "admin")
    admin_pass = os.getenv("WEBUI_ADMIN_PASSWORD")
    
    if admin_pass:
        users[admin_user] = {
            "password_hash": hashlib.sha256(admin_pass.encode()).hexdigest(),
            "role": "admin"
        }
    
    return users


class LoginRequest(BaseModel):
    """Login request body (alternative to form data)."""
    username: str
    password: str


class LoginResponse(BaseModel):
    """Response for login attempts."""
    success: bool
    message: str
    user: Optional[str] = None
    role: Optional[str] = None


class SessionUser(BaseModel):
    """Current session user information."""
    username: str
    role: str


class AuthStatusResponse(BaseModel):
    """Response for auth status check."""
    authenticated: bool
    user: Optional[SessionUser] = None


@router.post("/login", response_model=LoginResponse)
async def login(
    response: Response,
    form_data: OAuth2PasswordRequestForm = Depends()
):
    """
    Authenticate user and create session.
    
    Accepts OAuth2 password form for compatibility with standard clients.
    Sets an HTTP-only cookie for session management.
    """
    users = _get_webui_users()
    
    if not users:
        logger.warning("WebUI login attempted but no users configured")
        raise HTTPException(
            status_code=503,
            detail="WebUI authentication not configured. Set WEBUI_ADMIN_PASSWORD environment variable."
        )
    
    user_data = users.get(form_data.username)
    if not user_data:
        logger.warning(f"Login failed: unknown user '{form_data.username}'")
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    password_hash = hashlib.sha256(form_data.password.encode()).hexdigest()
    if password_hash != user_data["password_hash"]:
        logger.warning(f"Login failed: invalid password for user '{form_data.username}'")
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    # Create session
    session_id = secrets.token_urlsafe(32)
    session_data = {
        "username": form_data.username,
        "role": user_data["role"]
    }
    _session_store.set(session_id, session_data)
    
    # Set HTTP-only cookie
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=session_id,
        httponly=True,
        samesite="lax",
        max_age=SESSION_MAX_AGE,
        secure=os.getenv("WEBUI_SECURE_COOKIES", "false").lower() == "true"
    )
    
    logger.info(f"User '{form_data.username}' logged in successfully")
    
    return LoginResponse(
        success=True,
        message="Login successful",
        user=form_data.username,
        role=user_data["role"]
    )


@router.post("/logout")
async def logout(request: Request, response: Response):
    """Clear session and logout user."""
    session_id = request.cookies.get(SESSION_COOKIE_NAME)
    
    if session_id:
        session = _session_store.get(session_id)
        if session:
            logger.info(f"User '{session.get('username')}' logged out")
        _session_store.delete(session_id)
    
    response.delete_cookie(SESSION_COOKIE_NAME)
    
    return {"success": True, "message": "Logged out successfully"}


@router.get("/me", response_model=SessionUser)
async def get_current_user(request: Request):
    """
    Get current session user.
    
    Returns 401 if not authenticated.
    """
    session_id = request.cookies.get(SESSION_COOKIE_NAME)
    
    if not session_id:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    session = _session_store.get(session_id)
    if not session:
        raise HTTPException(status_code=401, detail="Session expired")
    
    return SessionUser(
        username=session["username"],
        role=session["role"]
    )


@router.get("/status", response_model=AuthStatusResponse)
async def get_auth_status(request: Request):
    """
    Check authentication status without throwing errors.
    
    Useful for WebUI to check if user is logged in on page load.
    """
    session_id = request.cookies.get(SESSION_COOKIE_NAME)
    
    if not session_id:
        return AuthStatusResponse(authenticated=False)
    
    session = _session_store.get(session_id)
    if not session:
        return AuthStatusResponse(authenticated=False)
    
    return AuthStatusResponse(
        authenticated=True,
        user=SessionUser(
            username=session["username"],
            role=session["role"]
        )
    )


# Dependency functions for use in other routes

def get_session_user(request: Request) -> Optional[SessionUser]:
    """
    Dependency for optionally getting session user.
    
    Returns None if not authenticated (non-throwing).
    """
    session_id = request.cookies.get(SESSION_COOKIE_NAME)
    if session_id:
        session = _session_store.get(session_id)
        if session:
            return SessionUser(
                username=session["username"],
                role=session["role"]
            )
    return None


def require_session(request: Request) -> SessionUser:
    """
    Dependency for routes that require session authentication.
    
    Raises 401 if not authenticated.
    """
    user = get_session_user(request)
    if not user:
        raise HTTPException(
            status_code=401,
            detail="Session authentication required"
        )
    return user

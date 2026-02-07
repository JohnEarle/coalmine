"""
FastAPI-Users Configuration

Provides user authentication with:
- Email/password login
- JWT tokens for API access
- Cookie-based sessions for WebUI
- OAuth/OIDC support
"""
import os
import uuid
from typing import Optional

from fastapi import Depends, Request
from fastapi_users import BaseUserManager, FastAPIUsers, UUIDIDMixin
from fastapi_users.authentication import (
    AuthenticationBackend,
    BearerTransport,
    CookieTransport,
    JWTStrategy,
)
from fastapi_users.db import SQLAlchemyUserDatabase
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from ..models import User, OAuthAccount, DATABASE_URL
from ..logging_config import get_logger

logger = get_logger(__name__)

# Secret for JWT signing — loaded from config/auth.yaml (single source of truth)
def _get_jwt_secret() -> str:
    """Load JWT secret from auth config, falling back to env var."""
    try:
        from . import get_auth_config
        return get_auth_config().jwt.secret_key
    except Exception:
        return os.getenv("SECRET_KEY", "coalmine-dev-secret-change-in-production")

SECRET = _get_jwt_secret()


# =============================================================================
# Database Adapter
# =============================================================================

# Convert sync URL to async (postgresql -> postgresql+asyncpg)
def get_async_database_url():
    """Convert sync DATABASE_URL to async variant."""
    url = DATABASE_URL
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+asyncpg://")
    elif url.startswith("sqlite:"):
        return url.replace("sqlite:///", "sqlite+aiosqlite:///")
    return url


# Create async engine and session
async_engine = create_async_engine(get_async_database_url())
async_session_maker = sessionmaker(async_engine, class_=AsyncSession, expire_on_commit=False)


async def get_async_session() -> AsyncSession:
    """Dependency for getting an async database session."""
    async with async_session_maker() as session:
        yield session


async def get_user_db(session: AsyncSession = Depends(get_async_session)):
    """Dependency for getting the SQLAlchemy user database."""
    yield SQLAlchemyUserDatabase(session, User, OAuthAccount)


# =============================================================================
# User Manager
# =============================================================================

class UserManager(UUIDIDMixin, BaseUserManager[User, uuid.UUID]):
    """
    Custom user manager with Coalmine-specific logic.
    """
    reset_password_token_secret = SECRET
    verification_token_secret = SECRET

    async def on_after_register(self, user: User, request: Optional[Request] = None):
        """Called after user registration."""
        logger.info(f"User {user.email} registered with role {user.role}")

    async def on_after_login(
        self,
        user: User,
        request: Optional[Request] = None,
        response=None,
    ):
        """Called after successful login."""
        logger.info(f"User {user.email} logged in")

    async def on_after_forgot_password(
        self, user: User, token: str, request: Optional[Request] = None
    ):
        """Called after password reset token generated."""
        logger.info(f"Password reset requested for {user.email}")

    async def on_after_request_verify(
        self, user: User, token: str, request: Optional[Request] = None
    ):
        """Called after email verification token generated."""
        logger.info(f"Verification requested for {user.email}")


async def get_user_manager(user_db=Depends(get_user_db)):
    """Dependency for getting the user manager."""
    yield UserManager(user_db)


# =============================================================================
# Authentication Backends
# =============================================================================

def get_jwt_strategy() -> JWTStrategy:
    """JWT strategy for API authentication."""
    return JWTStrategy(secret=SECRET, lifetime_seconds=3600 * 24)  # 24 hours


# Bearer token transport (for API clients)
bearer_transport = BearerTransport(tokenUrl="/auth/jwt/login")

# Cookie transport (for WebUI)
cookie_transport = CookieTransport(
    cookie_name="coalmine_auth",
    cookie_max_age=3600 * 24,  # 24 hours
    cookie_httponly=True,
    cookie_samesite="lax",
    cookie_secure=os.getenv("ENVIRONMENT", "development") == "production",
    cookie_path="/",  # Send cookie to all paths, not just /auth/*
)

# JWT backend for API
jwt_backend = AuthenticationBackend(
    name="jwt",
    transport=bearer_transport,
    get_strategy=get_jwt_strategy,
)

# Cookie backend for WebUI
cookie_backend = AuthenticationBackend(
    name="cookie",
    transport=cookie_transport,
    get_strategy=get_jwt_strategy,
)


# =============================================================================
# FastAPI-Users Instance
# =============================================================================

fastapi_users = FastAPIUsers[User, uuid.UUID](
    get_user_manager,
    [jwt_backend, cookie_backend],
)

# Dependency shortcuts
current_active_user = fastapi_users.current_user(active=True)
current_superuser = fastapi_users.current_user(active=True, superuser=True)


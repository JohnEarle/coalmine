"""
Guarded User Registration

Registration is open only when zero users exist (first-run bootstrap).
After the first user, registration requires superuser authentication.
"""
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, EmailStr
from sqlalchemy import select, func

from ...logging_config import get_logger

logger = get_logger(__name__)

router = APIRouter()


class RegisterRequest(BaseModel):
    """Registration payload."""
    email: EmailStr
    password: str


class RegisterResponse(BaseModel):
    """Registration result."""
    id: str
    email: str
    is_active: bool
    role: str


@router.post("/register", response_model=RegisterResponse)
async def guarded_register(payload: RegisterRequest, request: Request):
    """
    Register a new user.

    - If no users exist: open registration (bootstrap)
    - Otherwise: requires superuser session
    """
    from ...auth.users import async_session_maker, get_user_manager, UserManager
    from ...models import User

    # Count existing users
    async with async_session_maker() as session:
        result = await session.execute(select(func.count(User.id)))
        user_count = result.scalar()

    if user_count > 0:
        # Require superuser authentication
        from ..auth import decode_coalmine_jwt
        cookie = request.cookies.get("coalmine_auth")
        if not cookie:
            raise HTTPException(status_code=401, detail="Authentication required")

        user_id = decode_coalmine_jwt(cookie)
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid session")

        async with async_session_maker() as session:
            result = await session.execute(
                select(User).where(User.id == user_id)
            )
            caller = result.unique().scalar_one_or_none()

            if not caller or not caller.is_active or not caller.is_superuser:
                raise HTTPException(
                    status_code=403,
                    detail="Only superusers can register new users"
                )

    # Create user via fastapi-users password helper
    from fastapi_users.password import PasswordHelper
    password_helper = PasswordHelper()

    new_user = User(
        email=payload.email,
        hashed_password=password_helper.hash(payload.password),
        is_active=True,
        is_superuser=False,
        is_verified=True,
        role="viewer",
    )

    async with async_session_maker() as session:
        # Check for duplicate email
        existing = await session.execute(
            select(User).where(User.email == payload.email)
        )
        if existing.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="Email already registered")

        session.add(new_user)
        await session.commit()
        await session.refresh(new_user)

    logger.info(f"Registered user: {new_user.email} (bootstrap={user_count == 0})")

    return RegisterResponse(
        id=str(new_user.id),
        email=new_user.email,
        is_active=new_user.is_active,
        role=new_user.role,
    )

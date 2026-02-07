"""
User Management Routes

Thin API layer over UserService for user CRUD operations.
fastapi-users handles /me and /{id} PATCH/DELETE (password, email, etc.).
"""
from fastapi import APIRouter, Depends
from typing import List
from pydantic import BaseModel
import uuid

from ..auth import require_role, AuthConfig
from ...services import UserService

router = APIRouter(prefix="/users", tags=["users"])


class UserListItem(BaseModel):
    """User info for list display."""
    id: str
    email: str
    role: str
    is_active: bool
    is_verified: bool
    is_superuser: bool
    display_name: str | None = None


@router.get("", response_model=List[UserListItem])
async def list_users(
    auth: AuthConfig = Depends(require_role("admin")),
):
    """
    List all users (admin only).
    
    Returns user metadata for management UI.
    """
    with UserService() as svc:
        result = svc.list()
        return [
            UserListItem(
                id=u.id,
                email=u.email,
                role=u.role,
                is_active=u.is_active,
                is_verified=u.is_verified,
                is_superuser=u.is_superuser,
                display_name=u.display_name,
            )
            for u in result.items
        ]

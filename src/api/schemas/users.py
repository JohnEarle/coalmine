"""User schemas for fastapi-users integration."""
import uuid
from fastapi_users.schemas import BaseUser, BaseUserCreate, BaseUserUpdate
from pydantic import ConfigDict


class UserRead(BaseUser[uuid.UUID]):
    role: str
    display_name: str | None = None
    model_config = ConfigDict(from_attributes=True)


class UserCreate(BaseUserCreate):
    role: str = "viewer"
    display_name: str | None = None


class UserUpdate(BaseUserUpdate):
    role: str | None = None
    display_name: str | None = None

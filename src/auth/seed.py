"""
Admin User Seeding

Creates an admin user on first startup if no users exist in the database.
Reads configuration from config/seed.yaml.
"""
from typing import Optional

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import User
from ..logging_config import get_logger
from .users import async_session_maker

logger = get_logger(__name__)


async def seed_admin_if_needed() -> Optional[User]:
    """
    Create admin user if no users exist in database.
    
    Reads credentials from config/seed.yaml (supports env var expansion).
    Skips silently if users already exist or password is not configured.
    
    Returns:
        Created User if seeded, None if users already exist.
    """
    from . import get_seed_config
    config = get_seed_config()
    
    async with async_session_maker() as session:
        # Check if any users exist
        result = await session.execute(select(func.count(User.id)))
        user_count = result.scalar()
        
        if user_count > 0:
            logger.debug(f"Database has {user_count} users, skipping seed")
            return None
        
        if not config.admin_password:
            logger.warning(
                "No users in database and admin_password not set in seed.yaml. "
                "Set ADMIN_PASSWORD to create initial admin user."
            )
            return None
        
        # Create admin user using fastapi-users compatible password hashing
        from fastapi_users.password import PasswordHelper
        password_helper = PasswordHelper()
        hashed_password = password_helper.hash(config.admin_password)
        
        admin_user = User(
            email=config.admin_email,
            hashed_password=hashed_password,
            is_active=True,
            is_superuser=True,
            is_verified=True,
            role=config.admin_role,
            display_name=config.admin_display_name,
        )
        
        session.add(admin_user)
        await session.commit()
        await session.refresh(admin_user)
        
        logger.info(f"Created admin user: {config.admin_email}")
        return admin_user

"""
Unit tests for admin seeding logic.

Tests the seed_admin_if_needed function from src/auth/seed.py.
"""
import pytest
from unittest.mock import patch, AsyncMock, MagicMock


class TestSeedAdminIfNeeded:
    """Tests for seed_admin_if_needed function."""

    @pytest.mark.asyncio
    async def test_seed_creates_admin_when_db_empty(self):
        """When no users exist and password is configured, seed creates admin."""
        mock_config = MagicMock()
        mock_config.admin_email = "admin@coalmine.io"
        mock_config.admin_password = "test-password"
        mock_config.admin_role = "admin"
        mock_config.admin_display_name = "Administrator"

        mock_session = AsyncMock()
        # user_count = 0 (empty DB)
        mock_result = MagicMock()
        mock_result.scalar.return_value = 0
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.commit = AsyncMock()
        mock_session.refresh = AsyncMock()

        mock_session_ctx = AsyncMock()
        mock_session_ctx.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_ctx.__aexit__ = AsyncMock(return_value=False)

        with patch("src.auth.get_seed_config", return_value=mock_config):
            with patch("src.auth.seed.async_session_maker", return_value=mock_session_ctx):
                from src.auth.seed import seed_admin_if_needed
                result = await seed_admin_if_needed()

        # Should have added a user and committed
        mock_session.add.assert_called_once()
        mock_session.commit.assert_called_once()

        # Check the User object that was added
        created_user = mock_session.add.call_args[0][0]
        assert created_user.email == "admin@coalmine.io"
        assert created_user.is_superuser is True
        assert created_user.is_active is True
        assert created_user.role == "admin"
        assert created_user.display_name == "Administrator"

    @pytest.mark.asyncio
    async def test_seed_skips_when_users_exist(self):
        """When users already exist, seed does nothing."""
        mock_config = MagicMock()
        mock_config.admin_password = "test-password"

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar.return_value = 3  # 3 users already exist
        mock_session.execute = AsyncMock(return_value=mock_result)

        mock_session_ctx = AsyncMock()
        mock_session_ctx.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_ctx.__aexit__ = AsyncMock(return_value=False)

        with patch("src.auth.get_seed_config", return_value=mock_config):
            with patch("src.auth.seed.async_session_maker", return_value=mock_session_ctx):
                from src.auth.seed import seed_admin_if_needed
                result = await seed_admin_if_needed()

        assert result is None
        mock_session.add.assert_not_called()

    @pytest.mark.asyncio
    async def test_seed_skips_when_no_password(self):
        """When ADMIN_PASSWORD is empty, seed warns and skips."""
        mock_config = MagicMock()
        mock_config.admin_password = ""  # Not set

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar.return_value = 0  # Empty DB
        mock_session.execute = AsyncMock(return_value=mock_result)

        mock_session_ctx = AsyncMock()
        mock_session_ctx.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_ctx.__aexit__ = AsyncMock(return_value=False)

        with patch("src.auth.get_seed_config", return_value=mock_config):
            with patch("src.auth.seed.async_session_maker", return_value=mock_session_ctx):
                from src.auth.seed import seed_admin_if_needed
                result = await seed_admin_if_needed()

        assert result is None
        mock_session.add.assert_not_called()

    @pytest.mark.asyncio
    async def test_seed_uses_config_from_yaml(self):
        """Seed reads email, role, and display name from config."""
        mock_config = MagicMock()
        mock_config.admin_email = "custom@example.com"
        mock_config.admin_password = "secure-pass"
        mock_config.admin_role = "superuser"
        mock_config.admin_display_name = "Custom Admin"

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar.return_value = 0
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.commit = AsyncMock()
        mock_session.refresh = AsyncMock()

        mock_session_ctx = AsyncMock()
        mock_session_ctx.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_ctx.__aexit__ = AsyncMock(return_value=False)

        with patch("src.auth.get_seed_config", return_value=mock_config):
            with patch("src.auth.seed.async_session_maker", return_value=mock_session_ctx):
                from src.auth.seed import seed_admin_if_needed
                result = await seed_admin_if_needed()

        created_user = mock_session.add.call_args[0][0]
        assert created_user.email == "custom@example.com"
        assert created_user.role == "superuser"
        assert created_user.display_name == "Custom Admin"


class TestDecodeCoalmineJWT:
    """Tests for the single JWT decode helper."""

    def test_valid_jwt_returns_uuid(self):
        """Valid JWT returns user UUID."""
        import jwt as pyjwt
        import uuid

        user_id = uuid.uuid4()
        secret = "test-secret"
        token = pyjwt.encode(
            {"sub": str(user_id), "aud": "fastapi-users:auth"},
            secret,
            algorithm="HS256"
        )

        with patch("src.api.auth._get_jwt_secret", return_value=secret):
            from src.api.auth import decode_coalmine_jwt
            result = decode_coalmine_jwt(token)

        assert result == user_id

    def test_expired_jwt_returns_none(self):
        """Expired JWT returns None."""
        import jwt as pyjwt
        import uuid
        import time

        secret = "test-secret"
        token = pyjwt.encode(
            {"sub": str(uuid.uuid4()), "exp": int(time.time()) - 100},
            secret,
            algorithm="HS256"
        )

        with patch("src.api.auth._get_jwt_secret", return_value=secret):
            from src.api.auth import decode_coalmine_jwt
            result = decode_coalmine_jwt(token)

        assert result is None

    def test_wrong_secret_returns_none(self):
        """JWT signed with wrong secret returns None."""
        import jwt as pyjwt
        import uuid

        token = pyjwt.encode(
            {"sub": str(uuid.uuid4())},
            "wrong-secret",
            algorithm="HS256"
        )

        with patch("src.api.auth._get_jwt_secret", return_value="correct-secret"):
            from src.api.auth import decode_coalmine_jwt
            result = decode_coalmine_jwt(token)

        assert result is None

    def test_garbage_input_returns_none(self):
        """Non-JWT string returns None."""
        with patch("src.api.auth._get_jwt_secret", return_value="secret"):
            from src.api.auth import decode_coalmine_jwt
            result = decode_coalmine_jwt("not-a-jwt")

        assert result is None

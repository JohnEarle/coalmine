"""
API route integration tests.

These tests verify the REST API endpoints work correctly with mocked dependencies.
Uses FastAPI TestClient for synchronous testing.
"""
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from src.api.main import app
from src.api_keys_loader import ApiKeyConfig


@pytest.fixture
def mock_valid_api_key():
    """Mock a valid API key configuration."""
    return ApiKeyConfig(
        key="test-api-key-12345",
        permissions=["read", "write"],
        scopes=["all"]
    )


@pytest.fixture
def mock_read_only_api_key():
    """Mock a read-only API key configuration."""
    return ApiKeyConfig(
        key="read-only-key",
        permissions=["read"],
        scopes=["all"]
    )


@pytest.fixture
def client():
    """Create a test client for the FastAPI app."""
    return TestClient(app)


@pytest.mark.unit
class TestHealthEndpoint:
    """Tests for health check endpoint."""

    def test_health_check_returns_healthy(self, client):
        """Health endpoint should return healthy status."""
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "healthy"}


@pytest.mark.unit
class TestCanariesEndpointAuth:
    """Tests verifying canary endpoints require authentication."""

    def test_list_canaries_requires_auth(self, client):
        """GET /canaries without API key should return 401."""
        response = client.get("/api/v1/canaries")
        assert response.status_code == 401
        assert "Authentication required" in response.json().get("detail", "")

    def test_list_canaries_rejects_invalid_key(self, client):
        """GET /canaries with invalid API key should return 403."""
        with patch("src.api.auth.validate_api_key", return_value=None):
            response = client.get(
                "/api/v1/canaries",
                headers={"X-API-Key": "invalid-key"}
            )
            assert response.status_code == 403
            assert "Invalid" in response.json().get("detail", "")

    @patch("src.api.routes.canaries.CanaryService")
    @patch("src.api.auth.validate_api_key")
    def test_list_canaries_with_valid_key(self, mock_auth, mock_svc_cls, client, mock_valid_api_key):
        """GET /canaries with valid API key should return 200."""
        mock_auth.return_value = mock_valid_api_key
        
        mock_svc = mock_svc_cls.return_value
        mock_svc.__enter__.return_value = mock_svc
        mock_svc.list.return_value = MagicMock(items=[], total=0)

        response = client.get(
            "/api/v1/canaries",
            headers={"X-API-Key": "test-api-key-12345"}
        )
        assert response.status_code == 200
        assert "canaries" in response.json()
        assert response.json()["total"] == 0

    def test_create_canary_requires_write_permission(self, client, mock_read_only_api_key):
        """POST /canaries with read-only key should return 403."""
        with patch("src.api.auth.validate_api_key", return_value=mock_read_only_api_key):
            response = client.post(
                "/api/v1/canaries",
                headers={"X-API-Key": "read-only-key"},
                json={
                    "name": "test-canary",
                    "resource_type": "AWS_IAM_USER",
                    "environment_id": "abc-123",
                    "logging_id": "def-456"
                }
            )
            assert response.status_code == 403
            assert "write" in response.json().get("detail", "")


@pytest.mark.unit
class TestCanariesCRUD:
    """Tests for canary CRUD operations."""

    @patch("src.api.routes.canaries.CanaryService")
    @patch("src.api.auth.validate_api_key")
    def test_create_canary_queues_task(self, mock_auth, mock_svc_cls, client, mock_valid_api_key):
        """POST /canaries should queue a Celery task."""
        mock_auth.return_value = mock_valid_api_key
        
        mock_svc = mock_svc_cls.return_value
        mock_svc.__enter__.return_value = mock_svc
        mock_svc.create.return_value = MagicMock(success=True, data={"status": "queued", "name": "api-test-canary"})

        response = client.post(
            "/api/v1/canaries",
            headers={"X-API-Key": "test-api-key-12345"},
            json={
                "name": "api-test-canary",
                "resource_type": "AWS_IAM_USER",
                "account_id": "env-123",
                "logging_id": "log-456"
            }
        )
        
        assert response.status_code == 200
        assert response.json()["status"] == "queued"
        assert response.json()["name"] == "api-test-canary"
        mock_svc.create.assert_called_once()

    @patch("src.api.routes.canaries.CanaryService")
    @patch("src.api.auth.validate_api_key")
    def test_get_single_canary_returns_details(
        self, mock_auth, mock_svc_cls, client, mock_valid_api_key
    ):
        """GET /canaries/{id} should return canary details."""
        mock_auth.return_value = mock_valid_api_key
        
        mock_canary = MagicMock()
        mock_canary.id = "canary-uuid-123"
        mock_canary.name = "my-test-canary"
        mock_canary.resource_type.value = "AWS_IAM_USER"
        mock_canary.status.value = "ACTIVE"
        mock_canary.current_resource_id = "my-test-canary-20240101"
        mock_canary.expires_at = None
        mock_canary.created_at = None
        mock_canary.account.name = "test-account"

        mock_svc = mock_svc_cls.return_value
        mock_svc.__enter__.return_value = mock_svc
        mock_svc.get.return_value = MagicMock(success=True, data=mock_canary)
        
        response = client.get(
            "/api/v1/canaries/my-test-canary",
            headers={"X-API-Key": "test-api-key-12345"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "my-test-canary"
        assert data["resource_type"] == "AWS_IAM_USER"
        assert data["status"] == "ACTIVE"

    @patch("src.api.routes.canaries.CanaryService")
    @patch("src.api.auth.validate_api_key")
    def test_get_nonexistent_canary_returns_404(
        self, mock_auth, mock_svc_cls, client, mock_valid_api_key
    ):
        """GET /canaries/{id} for missing canary should return 404."""
        mock_auth.return_value = mock_valid_api_key

        mock_svc = mock_svc_cls.return_value
        mock_svc.__enter__.return_value = mock_svc
        mock_svc.get.return_value = MagicMock(success=False, error="Canary not found")
        
        response = client.get(
            "/api/v1/canaries/nonexistent",
            headers={"X-API-Key": "test-api-key-12345"}
        )
        
        assert response.status_code == 404
        assert "not found" in response.json()["detail"]



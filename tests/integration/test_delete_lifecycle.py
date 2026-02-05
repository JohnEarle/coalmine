"""
Integration tests for the delete canary lifecycle.

Tests verify the delete workflow with mocked cloud providers.
"""
import pytest
from unittest.mock import MagicMock, patch
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.models import (
    Base, CanaryResource, ResourceHistory, ResourceType,
    ResourceStatus, ActionType, CloudEnvironment, LoggingResource,
    LoggingProviderType
)
from src import tasks


# Use SQLite for testing
TEST_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(TEST_DATABASE_URL)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture
def db():
    """Create a fresh database for each test."""
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture
def test_environment(db):
    """Create a test AWS environment."""
    env = CloudEnvironment(
        name="delete-test-env",
        provider_type="AWS",
        credentials={"AWS_ACCESS_KEY_ID": "test", "AWS_SECRET_ACCESS_KEY": "test"},
        config={"region": "us-east-1"}
    )
    db.add(env)
    db.commit()
    return env


@pytest.fixture
def test_logging_resource(db, test_environment):
    """Create a test logging resource."""
    log_res = LoggingResource(
        name="delete-test-trail",
        provider_type=LoggingProviderType.AWS_CLOUDTRAIL,
        environment_id=test_environment.id,
        status=ResourceStatus.ACTIVE,
        configuration={"trail_name": "delete-test-trail"}
    )
    db.add(log_res)
    db.commit()
    return log_res


@pytest.fixture
def active_canary(db, test_environment, test_logging_resource):
    """Create an active canary for deletion testing."""
    canary = CanaryResource(
        name="delete-me",
        resource_type=ResourceType.AWS_BUCKET,
        environment_id=test_environment.id,
        logging_resource_id=test_logging_resource.id,
        current_resource_id="delete-me-20240101",
        interval_seconds=3600,
        status=ResourceStatus.ACTIVE,
        tf_state_path="/tmp/fake/state"
    )
    db.add(canary)
    db.commit()
    return canary


@pytest.mark.integration
class TestDeleteCanaryLifecycle:
    """Tests for canary deletion workflow."""

    @patch("src.tasks.canary.SessionLocal")
    @patch("src.tasks.canary.TofuManager")
    @patch("src.tasks.canary.ResourceRegistry")
    @patch("os.path.exists")
    def test_delete_canary_transitions_to_deleted(
        self, mock_exists, mock_registry, MockTofuManager, MockSessionLocal, db, active_canary
    ):
        """Delete should transition canary to DELETED status."""
        # Prevent the task from closing the session so we can inspect it
        db.close = MagicMock()
        MockSessionLocal.return_value = db

        # Mock file existence and tofu manager
        mock_exists.return_value = True
        mock_manager = MockTofuManager.return_value
        mock_manager.init.return_value = "Init Success"
        mock_manager.destroy.return_value = "Destroy Success"

        # Mock handler
        mock_handler = MagicMock()
        mock_handler.get_tform_vars.return_value = {"bucket_name": "delete-me-20240101"}
        mock_handler.disable_logging.return_value = None
        mock_registry.get_handler.return_value = mock_handler

        resource_id = str(active_canary.id)

        # Run the delete task
        tasks.delete_canary(resource_id)

        # Verify status transition
        db.refresh(active_canary)
        assert active_canary.status == ResourceStatus.DELETED

        # Verify history entry
        history = db.query(ResourceHistory).filter_by(
            resource_id=active_canary.id,
            action=ActionType.DELETE
        ).first()
        assert history is not None
        assert history.details.get("status") == "success"

        # Verify Tofu destroy was called
        mock_manager.destroy.assert_called_once()

    @patch("src.tasks.canary.SessionLocal")
    @patch("src.tasks.canary.TofuManager")
    @patch("src.tasks.canary.ResourceRegistry")
    @patch("os.path.exists")
    def test_delete_unregisters_from_logging(
        self, mock_exists, mock_registry, MockTofuManager, MockSessionLocal, db, active_canary
    ):
        """Delete should unregister canary from logging resource."""
        db.close = MagicMock()
        MockSessionLocal.return_value = db
        mock_exists.return_value = True

        mock_manager = MockTofuManager.return_value
        mock_manager.init.return_value = "Init Success"
        mock_manager.destroy.return_value = "Destroy Success"

        mock_handler = MagicMock()
        mock_handler.get_tform_vars.return_value = {"bucket_name": "delete-me-20240101"}
        mock_registry.get_handler.return_value = mock_handler

        resource_id = str(active_canary.id)
        tasks.delete_canary(resource_id)

        # Verify disable_logging was called
        mock_handler.disable_logging.assert_called_once()
        call_args = mock_handler.disable_logging.call_args[0]
        assert call_args[0] == "delete-me-20240101"  # physical resource ID

    @patch("src.tasks.canary.SessionLocal")
    def test_delete_already_deleted_canary_is_noop(self, MockSessionLocal, db, active_canary):
        """Deleting an already DELETED canary should be a no-op."""
        db.close = MagicMock()
        MockSessionLocal.return_value = db

        # Pre-set to DELETED
        active_canary.status = ResourceStatus.DELETED
        db.commit()

        resource_id = str(active_canary.id)

        # Should not raise
        tasks.delete_canary(resource_id)

        # Status should remain DELETED
        db.refresh(active_canary)
        assert active_canary.status == ResourceStatus.DELETED

    @patch("src.tasks.canary.SessionLocal")
    @patch("src.tasks.canary.TofuManager")
    @patch("src.tasks.canary.ResourceRegistry")
    @patch("os.path.exists")
    def test_delete_failure_transitions_to_error(
        self, mock_exists, mock_registry, MockTofuManager, MockSessionLocal, db, active_canary
    ):
        """Failed deletion should transition to ERROR status."""
        db.close = MagicMock()
        MockSessionLocal.return_value = db
        mock_exists.return_value = True

        mock_manager = MockTofuManager.return_value
        mock_manager.init.return_value = "Init Success"
        mock_manager.destroy.side_effect = Exception("Tofu destroy failed")

        mock_handler = MagicMock()
        mock_handler.get_tform_vars.return_value = {"bucket_name": "delete-me-20240101"}
        mock_handler.disable_logging.return_value = None
        mock_registry.get_handler.return_value = mock_handler

        resource_id = str(active_canary.id)

        # Should raise and set ERROR status
        with pytest.raises(Exception) as exc_info:
            tasks.delete_canary(resource_id)

        assert "destroy failed" in str(exc_info.value)

        # Verify status transition to ERROR
        db.refresh(active_canary)
        assert active_canary.status == ResourceStatus.ERROR

        # Verify error history
        history = db.query(ResourceHistory).filter_by(
            resource_id=active_canary.id,
            action=ActionType.DELETE
        ).first()
        assert history is not None
        assert "error" in history.details

    @patch("src.tasks.canary.SessionLocal")
    def test_delete_nonexistent_canary_is_noop(self, MockSessionLocal, db):
        """Deleting a non-existent canary should not raise."""
        db.close = MagicMock()
        MockSessionLocal.return_value = db

        fake_id = "00000000-0000-0000-0000-000000000000"

        # Should not raise
        tasks.delete_canary(fake_id)

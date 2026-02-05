"""
Unit tests for canary rotation logic.

Migrated from test_logic_manual.py - properly structured with in-memory DB.
"""
import pytest
from unittest.mock import MagicMock, patch
from src.models import (
    Base, CanaryResource, ResourceHistory, ResourceType, 
    ResourceStatus, ActionType
)


@pytest.mark.unit
@patch("src.tasks.canary.SessionLocal")
@patch("src.tasks.canary.TofuManager")
def test_rotate_canary_with_explicit_name(MockTofuManager, MockSessionLocal, isolated_db):
    """Rotation with explicit new_name should update the canary's logical name."""
    from src import tasks
    
    # Prevent the task from closing the session
    isolated_db.close = MagicMock()
    MockSessionLocal.return_value = isolated_db

    # Pre-seed a canary
    canary = CanaryResource(
        name="tmp_bk_1",
        resource_type=ResourceType.AWS_BUCKET,
        current_resource_id="tmp_bk_1-20250101",
        interval_seconds=3600,
        status=ResourceStatus.ACTIVE
    )
    isolated_db.add(canary)
    isolated_db.commit()
    resource_id = str(canary.id)

    mock_manager = MockTofuManager.return_value
    mock_manager.apply.return_value = "Apply Success (Renamed)"

    # Run rotation with explicit name
    tasks.rotate_canary(resource_id, new_name="prod_test_3")

    # Verify DB update
    isolated_db.refresh(canary)
    assert canary.name == "prod_test_3"
    assert canary.current_resource_id == "prod_test_3"

    # Verify History entry was created
    history = isolated_db.query(ResourceHistory).filter_by(
        resource_id=canary.id, 
        action=ActionType.ROTATE
    ).order_by(ResourceHistory.timestamp.desc()).first()
    
    assert history is not None
    assert history.details['new_physical_name'] == "prod_test_3"


@pytest.mark.unit
@patch("src.tasks.canary.SessionLocal")
@patch("src.tasks.canary.TofuManager")
def test_rotate_canary_generates_timestamp_suffix(MockTofuManager, MockSessionLocal, isolated_db):
    """Rotation without new_name should generate a timestamped physical name."""
    from src import tasks
    
    isolated_db.close = MagicMock()
    MockSessionLocal.return_value = isolated_db

    canary = CanaryResource(
        name="my-canary",
        resource_type=ResourceType.AWS_BUCKET,
        current_resource_id="my-canary-old",
        interval_seconds=3600,
        status=ResourceStatus.ACTIVE
    )
    isolated_db.add(canary)
    isolated_db.commit()
    resource_id = str(canary.id)

    mock_manager = MockTofuManager.return_value
    mock_manager.apply.return_value = "Apply Success"

    tasks.rotate_canary(resource_id)

    isolated_db.refresh(canary)
    # Logical name should be unchanged
    assert canary.name == "my-canary"
    # Physical name should have timestamp suffix
    assert canary.current_resource_id.startswith("my-canary-")
    assert len(canary.current_resource_id) > len("my-canary-")

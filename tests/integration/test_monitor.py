import pytest
from datetime import datetime
from unittest.mock import MagicMock, patch
from src.monitors.base import Alert
from src import tasks
from src.models import CanaryResource, ResourceStatus, Account, ResourceType

@patch("src.tasks.monitoring.SessionLocal")
@patch("src.tasks.monitoring.monitor_factory")
def test_monitor_active_canaries(MockFactory, MockSessionLocal):
    # Setup Mock DB
    db = MagicMock()
    MockSessionLocal.return_value = db
    
    # Mock Canary with Account
    cred = MagicMock()
    cred.provider = "AWS"
    cred.secrets = {"access_key_id": "test", "secret_access_key": "test"}
    account = MagicMock(spec=Account)
    account.credential = cred
    account.account_id = "123456789012"
    canary = CanaryResource(
        id="canary-1", 
        name="test-canary", 
        status=ResourceStatus.ACTIVE,
    )
    canary.account = account
    db.query.return_value.filter.return_value.all.return_value = [canary]
    
    # Mock Monitor
    mock_monitor = MagicMock()
    MockFactory.get_monitor.return_value = mock_monitor
    
    # Mock Alerts found
    alert = Alert(
        resource_name="bucket-1",
        event_time=datetime.utcnow(),
        event_name="GetObject",
        source_ip="1.2.3.4",
        user_agent="Boto3"
    )
    mock_monitor.check.return_value = [alert]
    
    # Run task
    tasks.monitor_active_canaries()
    
    # Verify Monitor check called
    mock_monitor.check.assert_called_once()
    
    # Verify Alert logged to DB
    # We expect db.add(history) to be called
    assert db.add.called
    args, _ = db.add.call_args
    history = args[0]
    assert history.details['alert']['event'] == "GetObject"
    assert history.details['alert']['ip'] == "1.2.3.4"

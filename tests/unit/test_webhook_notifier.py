"""
Unit tests for webhook notifier.

Migrated from repro_webhook.py - properly structured without aggressive module mocking.
"""
import pytest
import uuid
from datetime import datetime
from unittest.mock import MagicMock, patch

from src.notifications.webhook import WebhookNotifier
from src.notifications.registry import NotificationRegistry


@pytest.fixture
def mock_alert():
    """Create a mock alert object for testing."""
    alert = MagicMock()
    alert.id = uuid.uuid4()
    alert.external_id = "ext-123"
    alert.canary = MagicMock()
    alert.canary.name = "test-canary"
    alert.canary.id = uuid.uuid4()
    alert.event_name = "TEST_EVENT"
    alert.timestamp = datetime.utcnow()
    alert.source_ip = "127.0.0.1"
    alert.user_agent = "TestAgent"
    alert.raw_data = "{}"
    return alert


@pytest.mark.unit
class TestWebhookNotifier:
    """Tests for WebhookNotifier class."""

    @patch('requests.post')
    def test_sends_with_configured_timeout(self, mock_post, mock_alert):
        """Webhook should respect configured timeout value."""
        mock_post.return_value.status_code = 200

        config = {
            "type": "webhook",
            "url": "http://example.com/hook",
            "timeout": 42,
            "name": "webhook_timeout_test"
        }

        notifier = WebhookNotifier(config)
        notifier.send_alert(mock_alert)

        mock_post.assert_called_once()
        assert mock_post.call_args.kwargs['timeout'] == 42

    @patch('requests.post')
    def test_sends_with_custom_user_agent(self, mock_post, mock_alert):
        """Webhook should use custom User-Agent header if configured."""
        mock_post.return_value.status_code = 200

        config = {
            "type": "webhook",
            "url": "http://example.com/hook",
            "user_agent": "MyCustomAgent/9000",
            "name": "webhook_ua_test"
        }

        notifier = WebhookNotifier(config)
        notifier.send_alert(mock_alert)

        headers = mock_post.call_args.kwargs['headers']
        assert headers['User-Agent'] == "MyCustomAgent/9000"

    @patch('requests.post')
    def test_uses_default_timeout(self, mock_post, mock_alert):
        """Webhook should have a sensible default timeout."""
        mock_post.return_value.status_code = 200

        config = {
            "type": "webhook",
            "url": "http://example.com/hook",
            "name": "webhook_default_test"
        }

        notifier = WebhookNotifier(config)
        notifier.send_alert(mock_alert)

        mock_post.assert_called_once()
        # Should have some timeout set (implementation dependent)
        assert 'timeout' in mock_post.call_args.kwargs


@pytest.mark.unit
class TestNotificationRegistry:
    """Tests for NotificationRegistry class."""

    @patch('src.notifications.registry.get_alert_outputs')
    def test_injects_name_into_notifier_config(self, mock_config):
        """Registry should inject the config key as 'name' into each notifier."""
        mock_config.return_value = {
            "webhook_security": {
                "type": "webhook",
                "url": "http://localhost/1",
                "enabled": True
            },
            "webhook_audit": {
                "type": "webhook",
                "url": "http://localhost/2",
                "enabled": True
            }
        }

        notifiers = NotificationRegistry.get_notifiers()
        
        assert len(notifiers) == 2
        names = sorted([n.name for n in notifiers])
        assert names == ["webhook_audit", "webhook_security"]

    @patch('src.notifications.registry.get_alert_outputs')
    def test_skips_disabled_notifiers(self, mock_config):
        """Registry should not instantiate disabled notifiers."""
        mock_config.return_value = {
            "active_webhook": {
                "type": "webhook",
                "url": "http://localhost/active",
                "enabled": True
            },
            "disabled_webhook": {
                "type": "webhook",
                "url": "http://localhost/disabled",
                "enabled": False
            }
        }

        notifiers = NotificationRegistry.get_notifiers()
        
        assert len(notifiers) == 1
        assert notifiers[0].name == "active_webhook"

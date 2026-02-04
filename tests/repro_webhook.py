import sys
import os
import unittest
from unittest.mock import MagicMock, patch

# Add root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# MOCK EVERYTHING to avoid dependency hell
sys.modules['sqlalchemy'] = MagicMock()
sys.modules['src.models'] = MagicMock()
# We need to ensure src.models.Alert and src.models.Canary are available
mock_models = sys.modules['src.models']
mock_models.Alert = MagicMock()
mock_models.Canary = MagicMock()

# Now we can import the code under test
# Note: we must import them using the path we set up
# Since we are running from root, and added root to path, 'src' is a package
from src.notifications.registry import NotificationRegistry
from src.notifications.webhook import WebhookNotifier
# We don't import Alert/Canary from src.models anymore, we use the mocks or simple objects

class TestWebhookStability(unittest.TestCase):
    def setUp(self):
        # Mock alert object
        self.alert = MagicMock()
        self.alert.id = uuid.uuid4()
        self.alert.external_id = "ext-123"
        self.alert.canary.name = "test-canary" 
        self.alert.canary.id = uuid.uuid4()
        self.alert.event_name = "TEST_EVENT"
        self.alert.timestamp = datetime.utcnow()
        self.alert.source_ip = "127.0.0.1"
        self.alert.user_agent = "TestAgent"
        self.alert.raw_data = "{}"

    def test_registry_injects_name(self):
        # Mock get_alert_outputs - need to patch it where it is imported in registry.py
        # registry.py imports it from ..config_loader
        # But since we import src.notifications.registry, it's inside that module.
        # Wait, registry.py: `from ..config_loader import get_alert_outputs`
        # So we patch 'src.notifications.registry.get_alert_outputs'
        
        with patch('src.notifications.registry.get_alert_outputs') as mock_config:
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
            self.assertEqual(len(notifiers), 2)
            
            names = sorted([n.name for n in notifiers])
            self.assertEqual(names, ["webhook_audit", "webhook_security"])

    @patch('requests.post')
    def test_webhook_timeout_config(self, mock_post):
        mock_post.return_value.status_code = 200
        
        config = {
            "type": "webhook",
            "url": "http://example.com",
            "timeout": 42,
            "name": "webhook_timeout_test"
        }
        
        notifier = WebhookNotifier(config)
        notifier.send_alert(self.alert)
        
        mock_post.assert_called_once()
        self.assertEqual(mock_post.call_args.kwargs['timeout'], 42)

    @patch('requests.post')
    def test_webhook_user_agent_config(self, mock_post):
        mock_post.return_value.status_code = 200
        
        config = {
            "type": "webhook",
            "url": "http://example.com",
            "user_agent": "MyCustomAgent/9000",
            "name": "webhook_ua_test"
        }
        
        notifier = WebhookNotifier(config)
        notifier.send_alert(self.alert)
        
        headers = mock_post.call_args.kwargs['headers']
        self.assertEqual(headers['User-Agent'], "MyCustomAgent/9000")

if __name__ == '__main__':
    unittest.main()

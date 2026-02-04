import requests
import json
from typing import Dict, Any
from .base import Notifier
from ..models import Alert
from ..logging_config import get_logger

logger = get_logger(__name__)

class WebhookNotifier(Notifier):
    def send_alert(self, alert: Alert):
        if not self.config.get("enabled", True):
            return

        url = self.config.get("url")
        if not url:
            logger.error(f"Webhook notifier '{self.name}' configured without URL.")
            return

        timeout = self.config.get("timeout", 10)
        user_agent = self.config.get("user_agent", "Coalmine-Alert-Bot/1.0")

        headers = self.config.get("headers", {})
        headers.setdefault("User-Agent", user_agent)
        
        payload = {
            "alert_id": str(alert.id),
            "external_id": alert.external_id,
            "resource": alert.canary.name,
            "resource_id": str(alert.canary.id),
            "event": alert.event_name,
            "timestamp": alert.timestamp.isoformat(),
            "source_ip": alert.source_ip,
            "user_agent": alert.user_agent,
            "raw_data": alert.raw_data
        }

        try:
            resp = requests.post(url, json=payload, headers=headers, timeout=timeout)
            resp.raise_for_status()
            logger.info(f"Webhook alert '{self.name}' sent to {url}")
        except requests.exceptions.HTTPError as e:
            logger.error(f"Failed to send webhook alert '{self.name}': {e}. Response: {e.response.text}")
            raise
        except Exception as e:
            logger.error(f"Failed to send webhook alert '{self.name}': {e}")
            raise

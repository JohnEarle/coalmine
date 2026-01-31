from abc import ABC, abstractmethod
from typing import Dict, Any
from ..models import Alert

class Notifier(ABC):
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.name = config.get("name", "unknown")

    @abstractmethod
    def send_alert(self, alert: Alert):
        """Send an alert to the configured output."""
        pass

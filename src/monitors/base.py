from abc import ABC, abstractmethod
from typing import List, Dict
from datetime import datetime
import uuid
from ..models import CanaryResource, Account

class Alert:
    def __init__(self, resource_name: str, event_time: datetime, event_name: str, source_ip: str, user_agent: str, external_id: str = None, raw_data: dict = None):
        self.resource_name = resource_name
        self.event_time = event_time
        self.event_name = event_name
        self.source_ip = source_ip
        self.user_agent = user_agent
        self.external_id = external_id or str(uuid.uuid4()) # Fallback if none provided
        self.raw_data = raw_data or {}
    
    def to_dict(self):
        return {
            "resource": self.resource_name,
            "time": self.event_time.isoformat(),
            "event": self.event_name,
            "ip": self.source_ip,
            "ua": self.user_agent
        }

class AccessMonitor(ABC):
    def __init__(self, account: Account):
        self.account = account

    @abstractmethod
    def check(self, resource: CanaryResource, start_time: datetime, end_time: datetime) -> List[Alert]:
        """
        Check for access events for the given resource within the time window.
        """
        pass


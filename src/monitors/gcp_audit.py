from datetime import datetime, timedelta
from typing import List
from .base import AccessMonitor, Alert
from ..models import CanaryResource, ResourceType
from ..logging_config import get_logger
from google.cloud import logging

from .registry import get_strategy

logger = get_logger(__name__)

class GcpAuditMonitor(AccessMonitor):
    def _get_client(self):
        # We need to construct client from credentials dict if present
        account = self.account
        if not account or not account.credential:
            return logging.Client()
        
        secrets = account.credential.secrets or {}
        
        # Support both uppercase and lowercase credential keys
        creds_json = (secrets.get("GOOGLE_CREDENTIALS_JSON") or 
                      secrets.get("google_credentials_json") or
                      secrets.get("service_account_json"))
        
        if creds_json:
             import json
             from google.oauth2 import service_account
             
             info = creds_json
             if isinstance(info, str):
                 info = json.loads(info)
                 
             credentials = service_account.Credentials.from_service_account_info(info)
             return logging.Client(credentials=credentials)
             
        # Fallback to direct check if the wrapper IS the creds (legacy or different setup)
        if "type" in secrets and secrets["type"] == "service_account":
             from google.oauth2 import service_account
             credentials = service_account.Credentials.from_service_account_info(secrets)
             return logging.Client(credentials=credentials)
        
        return logging.Client()

    def check(self, resource: CanaryResource, start_time: datetime, end_time: datetime) -> List[Alert]:
        alerts = []
        client = self._get_client()
        
        strategy = get_strategy(resource.resource_type)
        if not strategy:
            logger.warning(f"No detection strategy found for {resource.resource_type}")
            return []

        try:
             alerts = strategy.detect(client, resource, start_time, end_time)
        except Exception as e:
             logger.error(f"Error executing strategy for {resource.name}: {e}")

        return alerts

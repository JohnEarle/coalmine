import boto3
from datetime import datetime, timedelta
from typing import List
from .base import AccessMonitor, Alert
from ..models import CanaryResource, ResourceType
from ..logging_config import get_logger

from . import registry

logger = get_logger(__name__)

class AwsCloudTrailMonitor(AccessMonitor):
    def _get_client(self, service="cloudtrail"):
        account = self.account
        if not account or not account.credential:
            return boto3.client(service)
        
        secrets = account.credential.secrets or {}
        
        # Support both uppercase and lowercase credential keys
        access_key = secrets.get("AWS_ACCESS_KEY_ID") or secrets.get("aws_access_key_id")
        secret_key = secrets.get("AWS_SECRET_ACCESS_KEY") or secrets.get("aws_secret_access_key")
        session_token = secrets.get("AWS_SESSION_TOKEN") or secrets.get("aws_session_token")
        region = secrets.get("AWS_REGION") or secrets.get("region") or secrets.get("aws_region") or "us-east-1"
        
        client_kwargs = {
            "aws_access_key_id": access_key,
            "aws_secret_access_key": secret_key,
            "region_name": region
        }
        
        if session_token:
            client_kwargs["aws_session_token"] = session_token
        
        return boto3.client(service, **client_kwargs)

    def check(self, resource: CanaryResource, start_time: datetime, end_time: datetime) -> List[Alert]:
        alerts = []
        strategy = registry.get_strategy(resource.resource_type)
        
        if not strategy:
            logger.warning(f"No detection strategy found for {resource.resource_type}")
            return []

        try:
            service = strategy.get_service_name()
            client = self._get_client(service)
            alerts = strategy.detect(client, resource, start_time, end_time)
        except Exception as e:
             logger.error(f"Error executing strategy for {resource.name}: {e}")
             
        return alerts

import json
def json_extract(json_str, key):
    try:
        if not json_str: return None
        data = json.loads(json_str)
        return data.get(key)
    except:
        return None

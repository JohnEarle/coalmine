import boto3
from datetime import datetime, timedelta
from typing import List
from .base import AccessMonitor, Alert
from ..models import CanaryResource, ResourceType
from ..logging_config import get_logger

from . import registry

logger = get_logger(__name__)

class AwsCloudTrailMonitor(AccessMonitor):
    def _get_client(self, service="cloudtrail", region_override=None):
        account = self.account
        if not account or not account.credential:
            return boto3.client(service)
        
        secrets = account.credential.secrets or {}
        
        # Support uppercase, lowercase, and non-prefixed credential keys
        access_key = secrets.get("AWS_ACCESS_KEY_ID") or secrets.get("aws_access_key_id") or secrets.get("access_key_id")
        secret_key = secrets.get("AWS_SECRET_ACCESS_KEY") or secrets.get("aws_secret_access_key") or secrets.get("secret_access_key")
        session_token = secrets.get("AWS_SESSION_TOKEN") or secrets.get("aws_session_token")
        region = region_override or secrets.get("AWS_REGION") or secrets.get("region") or secrets.get("aws_region") or "us-east-1"
        
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
            
            # For CloudWatch Logs queries, use the logging resource's region
            region_override = None
            if service == "logs" and resource.logging_resource:
                lconf = resource.logging_resource.configuration or {}
                region_override = lconf.get("region")
                if not region_override and "trail_arn" in lconf:
                    arn_parts = lconf["trail_arn"].split(":")
                    if len(arn_parts) >= 4:
                        region_override = arn_parts[3]
            
            client = self._get_client(service, region_override=region_override)
            alerts = strategy.detect(client, resource, start_time, end_time)

            # CloudTrail Lookup: also query us-east-1 for global-service events
            # (IAM, STS, etc. are logged in us-east-1 regardless of caller region)
            if service == "cloudtrail":
                account_region = (self.account.credential.secrets or {}).get("region") or \
                                 (self.account.credential.secrets or {}).get("AWS_REGION") or \
                                 (self.account.credential.secrets or {}).get("aws_region") or "us-east-1"
                if account_region != "us-east-1":
                    seen_ids = {a.external_id for a in alerts}
                    global_client = self._get_client(service, region_override="us-east-1")
                    global_alerts = strategy.detect(global_client, resource, start_time, end_time)
                    for a in global_alerts:
                        if a.external_id not in seen_ids:
                            alerts.append(a)
                            seen_ids.add(a.external_id)
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

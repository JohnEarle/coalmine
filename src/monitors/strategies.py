from abc import ABC, abstractmethod
from typing import List, Any
from datetime import datetime
import json
from .base import Alert
from ..logging_config import get_logger
from ..config_loader import get_ua_exclusion_tokens

logger = get_logger(__name__)


def _is_self_generated(user_agent: str) -> bool:
    """Return True if the user-agent contains a known exclusion token."""
    if not user_agent:
        return False
    for token in get_ua_exclusion_tokens():
        if token in user_agent:
            return True
    return False

class DetectionStrategy(ABC):
    @abstractmethod
    def detect(self, client: Any, resource: Any, start_time: datetime, end_time: datetime) -> List[Alert]:
        """
        Executes the detection logic using the provided client.
        """
        pass
    
    @abstractmethod
    def get_service_name(self) -> str:
        """Returns 'logs' or 'cloudtrail'"""
        pass

class CloudWatchLogsQuery(DetectionStrategy):
    def __init__(self, filter_pattern: str):
        self.filter_pattern = filter_pattern
        
    def get_service_name(self) -> str:
        return "logs"

    def detect(self, client: Any, resource: Any, start_time: datetime, end_time: datetime) -> List[Alert]:
        alerts = []
        phys_name = resource.current_resource_id
        
        # Log Group Resolution Logic
        log_group_name = None
        
        # 1. Prefer Linked Logging Resource
        if resource.logging_resource:
            lconf = resource.logging_resource.configuration or {}
            if "log_group_name" in lconf:
                    log_group_name = lconf["log_group_name"]
            elif "trail_name" in lconf:
                    trail = lconf["trail_name"]
                    log_group_name = f"/aws/cloudtrail/{trail}"
            else:
                    log_group_name = f"/aws/cloudtrail/{resource.logging_resource.name}"

        # 2. Fallback to Params
        if not log_group_name:
            params = resource.module_params or {}
            ct_id = params.get("ct_id") or params.get("log_group_name")
            if ct_id:
                if ct_id.startswith("/"):
                    log_group_name = ct_id
                else:
                    log_group_name = f"/aws/cloudtrail/{ct_id}"
        
        # 3. Default
        if not log_group_name:
                log_group_name = f"/aws/cloudtrail/canary/{phys_name}"

        try:
            start_ts = int(start_time.timestamp() * 1000)
            end_ts = int(end_time.timestamp() * 1000)
            
            # Format pattern with resource ID if placeholder exists
            # Use replace to avoid conflicts with CloudWatch filter braces
            pattern = self.filter_pattern.replace("{resource_id}", phys_name)
            
            response = client.filter_log_events(
                logGroupName=log_group_name,
                startTime=start_ts, 
                endTime=end_ts,
                filterPattern=pattern,
                limit=100  # Limit results to prevent memory issues
            )
            
            for event in response.get('events', []):
                try:
                    ct_event = json.loads(event.get('message'))
                    ua = ct_event.get('userAgent') or "Unknown"
                    if _is_self_generated(ua):
                        continue
                    alerts.append(Alert(
                        resource_name=phys_name,
                        event_time=datetime.fromtimestamp(event.get('timestamp')/1000.0),
                        event_name=ct_event.get('eventName'),
                        source_ip=ct_event.get('sourceIPAddress') or "Unknown",
                        user_agent=ua,
                        external_id=event.get('eventId'),
                        raw_data=ct_event
                    ))
                except Exception as e:
                    logger.warning(f"Error parsing log event: {e}")
                    
        except client.exceptions.ResourceNotFoundException:
            logger.warning(f"Log group '{log_group_name}' not found for {resource.name}")
        except Exception as e:
            logger.error(f"Error checking logs for {resource.name}: {e}")

        return alerts

class CloudTrailLookup(DetectionStrategy):
    def __init__(self, lookup_attr_keys: List[str], event_names: List[str] = None):
        self.lookup_attr_keys = lookup_attr_keys
        self.event_names = event_names
        
    def get_service_name(self) -> str:
        return "cloudtrail"

    def detect(self, client: Any, resource: Any, start_time: datetime, end_time: datetime) -> List[Alert]:
        alerts = []
        phys_name = resource.current_resource_id
        seen_event_ids = set()
        
        # Import here to avoid circular imports
        from ..models import ResourceType
        
        for key in self.lookup_attr_keys:
            try:
                # Build lookup value - for S3 buckets with ResourceName, use ARN format
                lookup_value = phys_name
                if key == "ResourceName" and resource.resource_type == ResourceType.AWS_BUCKET:
                    lookup_value = f"arn:aws:s3:::{phys_name}"
                

                response = client.lookup_events(
                        LookupAttributes=[
                        {'AttributeKey': key, 'AttributeValue': lookup_value}
                    ],
                    StartTime=start_time,
                    EndTime=end_time,
                    MaxResults=50  # Limit results to prevent memory issues
                )
                for event in response.get('Events', []):
                    event_id = event.get('EventId')
                    event_name = event.get('EventName')
                    
                    if self.event_names and event_name not in self.event_names:
                        continue
                        
                    if event_id and event_id in seen_event_ids:
                        continue
                    if event_id:
                        seen_event_ids.add(event_id)
                        
                    ct_event = json.loads(event.get('CloudTrailEvent') or '{}')
                    ua = ct_event.get('userAgent') or "Unknown"
                    if _is_self_generated(ua):
                        continue
                    alerts.append(Alert(
                        resource_name=phys_name,
                        event_time=event.get('EventTime'),
                        event_name=event_name,
                        source_ip=ct_event.get('sourceIPAddress') or "Unknown",
                        user_agent=ua,
                        external_id=event_id,
                        raw_data=ct_event
                    ))
            except Exception as e:
                logger.error(f"Error lookup events for {resource.name} with key {key}: {e}")
            
        return alerts

class GcpAuditLogQuery(DetectionStrategy):
    def __init__(self, filter_template: str):
        """
        :param filter_template: A python format string e.g. 'protoPayload.resourceName="{resource_id}"'
        """
        self.filter_template = filter_template
        
    def get_service_name(self) -> str:
        return "gcp_audit"

    def detect(self, client: Any, resource: Any, start_time: datetime, end_time: datetime) -> List[Alert]:
        alerts = []
        phys_name = resource.current_resource_id
        
        # Build filter from template
        filter_str = self.filter_template.format(
            resource_id=phys_name,
            start_time=start_time.isoformat() + "Z",
            end_time=end_time.isoformat() + "Z"
        )
        
        try:
            # client is expected to be google.cloud.logging.Client
            # Limit to 100 entries to prevent memory issues
            count = 0
            for entry in client.list_entries(filter_=filter_str, max_results=100):
                if count >= 100:
                    break
                count += 1
                payload = entry.payload
                method = payload.get('methodName')
                ip = "Unknown"
                ua = "Unknown"
                
                if 'requestMetadata' in payload:
                    ip = payload['requestMetadata'].get('callerIp', 'Unknown')
                    ua = payload['requestMetadata'].get('callerSuppliedUserAgent', 'Unknown')
                
                if _is_self_generated(ua):
                    continue

                # Try to extract clearer event info if available (e.g. for SA auth)
                if 'authenticationInfo' in payload:
                    principal = payload['authenticationInfo'].get('principalEmail')
                    if principal:
                        # Append principal to UA or separate field if Alert model supported it
                        ua = f"{ua} (Principal: {principal})"

                alerts.append(Alert(
                    resource_name=phys_name,
                    event_time=entry.timestamp,
                    event_name=method,
                    source_ip=ip,
                    user_agent=ua,
                    external_id=entry.insert_id,
                    raw_data=payload
                ))
        except Exception as e:
            logger.error(f"Error checking GCP Audit Logs for {resource.name}: {e}")
            
        return alerts

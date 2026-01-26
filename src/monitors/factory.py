from ..models import CloudEnvironment
from .base import AccessMonitor
from .aws_cloudtrail import AwsCloudTrailMonitor
from .gcp_audit import GcpAuditMonitor

def get_monitor(environment: CloudEnvironment) -> AccessMonitor:
    if environment.provider_type == "AWS":
        return AwsCloudTrailMonitor(environment)
    elif environment.provider_type == "GCP":
        return GcpAuditMonitor(environment)
    else:
        raise ValueError(f"No monitor implementation for provider {environment.provider_type}")

from ..models import Account
from .base import AccessMonitor
from .aws_cloudtrail import AwsCloudTrailMonitor
from .gcp_audit import GcpAuditMonitor

def get_monitor(account: Account) -> AccessMonitor:
    cred = account.credential
    if not cred:
        raise ValueError(f"Account {account.name} has no credential")
    
    if cred.provider == "AWS":
        return AwsCloudTrailMonitor(account)
    elif cred.provider == "GCP":
        return GcpAuditMonitor(account)
    else:
        raise ValueError(f"No monitor implementation for provider {cred.provider}")


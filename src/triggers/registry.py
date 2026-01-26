from typing import Optional, Type
from ..models import ResourceType
from .base import CanaryTrigger
from .aws_iam import AwsIamTrigger
from .gcp_sa import GcpSaTrigger
from .bucket import BucketTrigger

TRIGGER_MAP = {
    ResourceType.AWS_IAM_USER: AwsIamTrigger,
    ResourceType.GCP_SERVICE_ACCOUNT: GcpSaTrigger,
    ResourceType.AWS_BUCKET: BucketTrigger,
    ResourceType.GCP_BUCKET: BucketTrigger
}

def get_trigger(resource_type: ResourceType) -> Optional[CanaryTrigger]:
    trigger_cls = TRIGGER_MAP.get(resource_type)
    if trigger_cls:
        return trigger_cls()
    return None

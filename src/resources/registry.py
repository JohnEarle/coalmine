from typing import Dict, Type, Union
from ..models import ResourceType, LoggingProviderType
from .base import ResourceManager
from .aws_iam_user import AwsIamUserHandler
from .aws_bucket import AwsBucketHandler
from .gcp_service_account import GcpServiceAccountHandler
from .gcp_bucket import GcpBucketHandler
from .logging import AwsCloudTrailHandler, GcpAuditSinkHandler

class ResourceRegistry:
    _registry: Dict[Union[ResourceType, LoggingProviderType], Type[ResourceManager]] = {
        ResourceType.AWS_IAM_USER: AwsIamUserHandler,
        ResourceType.AWS_BUCKET: AwsBucketHandler,
        ResourceType.GCP_SERVICE_ACCOUNT: GcpServiceAccountHandler,
        ResourceType.GCP_BUCKET: GcpBucketHandler,
        LoggingProviderType.AWS_CLOUDTRAIL: AwsCloudTrailHandler,
        LoggingProviderType.GCP_AUDIT_SINK: GcpAuditSinkHandler,
    }

    @classmethod
    def register(cls, resource_type: ResourceType, handler_class: Type[ResourceManager]):
        """
        Register a handler class for a specific resource type.
        """
        cls._registry[resource_type] = handler_class

    @classmethod
    def get_handler(cls, resource_type: ResourceType) -> ResourceManager:
        """
        Get an instance of the handler for the given resource type.
        """
        handler_cls = cls._registry.get(resource_type)
        if not handler_cls:
            raise ValueError(f"No handler registered for resource type: {resource_type}")
        return handler_cls()

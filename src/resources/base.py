from abc import ABC, abstractmethod
from typing import Dict, Any, Optional

class ResourceManager(ABC):
    """
    Abstract base class for managing resource-specific logic.
    """

    @abstractmethod
    def get_tform_vars(self, physical_id: str, env_config: Dict[str, Any], module_params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Constructs the dictionary of variables required for the Tofu/Terraform module.
        
        Args:
            physical_id: The actual physical ID/name of the resource (e.g., IAM user name, bucket name).
            env_config: Configuration dictionary from the Account (includes project_id, etc.).
            module_params: Additional module parameters from the CanaryResource.
            
        Returns:
            Dict[str, Any]: variables to pass to Tofu.
        """
        pass

    def enable_logging(self, resource_val: str, log_resource: Any, env_obj: Any) -> None:
        """
        Register the resource with the logging provider (e.g. add to CloudTrail selectors or Sink filter).
        
        Args:
            resource_val: The identifier to filter on (e.g. ARN, Bucket Name, Service Account Email).
            log_resource: The LoggingResource ORM object.
            env_obj: The Account ORM object.
        """
        pass

    def disable_logging(self, resource_val: str, log_resource: Any, env_obj: Any) -> None:
        """
        Unregister the resource from the logging provider.
        
        Args:
            resource_val: The identifier to filter on.
            log_resource: The LoggingResource ORM object.
            env_obj: The Account ORM object.
        """
        pass

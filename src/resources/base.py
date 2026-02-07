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

    def resolve_env_config(self, account: Any, exec_env: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        """
        Extracts environment configuration from the Account object.

        Args:
            account: The Account ORM object.
            exec_env: Optional dictionary of environment variables (e.g. OS environ).

        Returns:
            Dict[str, Any]: Configuration dictionary (e.g., project_id, aws_region).
        """
        env_conf = {}
        if account:
            cred = account.credential
            if cred and cred.secrets:
                # AWS Region Extraction
                region = (cred.secrets.get("region") or
                         cred.secrets.get("aws_region") or
                         cred.secrets.get("AWS_REGION"))
                if region:
                    env_conf["aws_region"] = region

                # GCP Project ID Extraction
                if "project_id" in cred.secrets:
                    env_conf["project_id"] = cred.secrets["project_id"]

            # Fallback for GCP project_id from Account ID
            if "project_id" not in env_conf and account.account_id:
                env_conf["project_id"] = account.account_id

        # Fallback for GCP project_id from Execution Environment
        if exec_env:
            if "project_id" not in env_conf and "GOOGLE_CLOUD_PROJECT" in exec_env:
                env_conf["project_id"] = exec_env["GOOGLE_CLOUD_PROJECT"]

        return env_conf

    def validate(self, account: Any, module_params: Optional[Dict[str, Any]] = None, logging_resource: Optional[Any] = None) -> None:
        """
        Validate the resource configuration before creation.

        Args:
            account: The Account ORM object.
            module_params: The module parameters.
            logging_resource: The LoggingResource ORM object (optional).

        Raises:
            ValueError: If validation fails.
        """
        pass

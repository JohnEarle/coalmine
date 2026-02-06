"""
Credential Health Check

Validates that stored credentials can successfully authenticate to the cloud provider.
Economy of mechanism: Reuses same cloud SDK patterns as environment checks.
"""
from typing import Tuple
import boto3
from botocore.exceptions import ClientError

from .base import HealthCheck
from ..models import Credential


class CredentialHealthCheck(HealthCheck):
    """Checks validity of cloud credentials."""

    def check(self, resource: Credential) -> Tuple[bool, str]:
        """
        Validate that the credential can authenticate to the cloud provider.
        
        Args:
            resource: The Credential model instance to check.
            
        Returns:
            Tuple[bool, str]: (is_healthy, message)
        """
        if not resource.secrets:
            return False, "No secrets configured for credential"
        
        try:
            if resource.provider == "AWS":
                return self._check_aws(resource)
            elif resource.provider == "GCP":
                return self._check_gcp(resource)
            else:
                return False, f"Unknown provider: {resource.provider}"
        except Exception as e:
            return False, f"Health check failed: {str(e)}"

    def _check_aws(self, credential: Credential) -> Tuple[bool, str]:
        """Validate AWS credentials via STS GetCallerIdentity."""
        secrets = credential.secrets or {}
        
        try:
            session = boto3.Session(
                aws_access_key_id=secrets.get("access_key_id"),
                aws_secret_access_key=secrets.get("secret_access_key"),
                aws_session_token=secrets.get("session_token"),
                region_name=secrets.get("region", "us-east-1")
            )
            sts = session.client("sts")
            identity = sts.get_caller_identity()
            
            return True, f"AWS credentials valid. Account: {identity.get('Account')}, ARN: {identity.get('Arn')}"
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "Unknown")
            return False, f"AWS authentication failed: {error_code}"
        except Exception as e:
            return False, f"AWS check failed: {str(e)}"

    def _check_gcp(self, credential: Credential) -> Tuple[bool, str]:
        """Validate GCP credentials via ResourceManager."""
        secrets = credential.secrets or {}
        
        try:
            from google.oauth2 import service_account
            from google.cloud import resourcemanager_v3
            
            # Get service account JSON from secrets
            sa_json = secrets.get("service_account_json")
            if not sa_json:
                return False, "Missing service_account_json in secrets"
            
            # Parse the JSON if it's a string
            if isinstance(sa_json, str):
                import json
                try:
                    sa_info = json.loads(sa_json)
                except json.JSONDecodeError:
                    return False, "Invalid service_account_json format"
            else:
                sa_info = sa_json
            
            # Create credentials from service account info
            creds = service_account.Credentials.from_service_account_info(sa_info)
            project_id = sa_info.get("project_id")
            
            if not project_id:
                return False, "Missing project_id in service account JSON"
            
            # Use ResourceManager to validate
            client = resourcemanager_v3.ProjectsClient(credentials=creds)
            request = resourcemanager_v3.GetProjectRequest(name=f"projects/{project_id}")
            project = client.get_project(request=request)
            
            return True, f"GCP credentials valid. Project: {project.display_name} ({project.state.name})"
            
        except Exception as e:
            return False, f"GCP check failed: {str(e)}"

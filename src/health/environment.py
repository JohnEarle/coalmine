from typing import Tuple
import boto3
from botocore.exceptions import ClientError
from google.cloud import resourcemanager_v3
from google.auth import load_credentials_from_file

from .base import HealthCheck
from ..models import CloudEnvironment
from ..tasks.helpers import _get_execution_env
import os

class EnvironmentHealthCheck(HealthCheck):
    """Checks validity of cloud environment credentials."""

    def check(self, resource: CloudEnvironment) -> Tuple[bool, str]:
        env_vars = _get_execution_env(resource)
        
        # Inject env vars into this process temporarily (or use specific client init)
        # Using specific client initialization is safer than modifying os.environ globally in a shared worker
        
        try:
            if resource.provider_type == "AWS":
                return self._check_aws(env_vars)
            elif resource.provider_type == "GCP":
                return self._check_gcp(env_vars)
            else:
                return False, f"Unknown provider: {resource.provider_type}"
        except Exception as e:
            return False, str(e)

    def _check_aws(self, env: dict) -> Tuple[bool, str]:
        try:
            session = boto3.Session(
                aws_access_key_id=env.get("AWS_ACCESS_KEY_ID"),
                aws_secret_access_key=env.get("AWS_SECRET_ACCESS_KEY"),
                aws_session_token=env.get("AWS_SESSION_TOKEN"),
                region_name=env.get("AWS_REGION", "us-east-1")
            )
            sts = session.client("sts")
            identity = sts.get_caller_identity()
            return True, f"AWS Credentials Valid. Account: {identity.get('Account')}, ARN: {identity.get('Arn')}"
        except ClientError as e:
            return False, f"AWS Error: {e}"
        except Exception as e:
             return False, f"AWS Check Failed: {e}"

    def _check_gcp(self, env: dict) -> Tuple[bool, str]:
        try:
            creds_path = env.get("GOOGLE_APPLICATION_CREDENTIALS")
            project_id = env.get("GOOGLE_CLOUD_PROJECT")
            
            if not creds_path:
                return False, "Missing GOOGLE_APPLICATION_CREDENTIALS"

            # Use ResourceManager to list projects as a check
            # We need to manually construct the client using the credentials file
            from google.oauth2 import service_account
            
            creds = service_account.Credentials.from_service_account_file(creds_path)
            client = resourcemanager_v3.ProjectsClient(credentials=creds)
            
            request = resourcemanager_v3.GetProjectRequest(name=f"projects/{project_id}")
            project = client.get_project(request=request)
            
            return True, f"GCP Credentials Valid. Project: {project.display_name} ({project.state.name})"
            
        except Exception as e:
            return False, f"GCP Check Failed: {e}"

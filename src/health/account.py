"""
Account Health Check

Validates that an account can be accessed using its associated credential.
Economy of mechanism: Reuses same patterns as credential checks, but validates
access to the specific account ID.
"""
from typing import Tuple
import boto3
from botocore.exceptions import ClientError

from .base import HealthCheck
from ..models import Account


class AccountHealthCheck(HealthCheck):
    """Checks that an account is accessible with its credential."""

    def check(self, resource: Account) -> Tuple[bool, str]:
        """
        Validate that the account is accessible via its credential.
        
        Args:
            resource: The Account model instance to check.
            
        Returns:
            Tuple[bool, str]: (is_healthy, message)
        """
        if not resource.is_enabled:
            return False, "Account is disabled"
        
        credential = resource.credential
        if not credential:
            return False, "No credential associated with account"
        
        if not credential.secrets:
            return False, "Credential has no secrets configured"
        
        try:
            if credential.provider == "AWS":
                return self._check_aws(resource, credential)
            elif credential.provider == "GCP":
                return self._check_gcp(resource, credential)
            else:
                return False, f"Unknown provider: {credential.provider}"
        except Exception as e:
            return False, f"Health check failed: {str(e)}"

    def _check_aws(self, account: Account, credential) -> Tuple[bool, str]:
        """Validate AWS account access - optionally via AssumeRole."""
        secrets = credential.secrets or {}
        discovery_config = credential.discovery_config or {}
        
        try:
            # Create base session from credential
            session = boto3.Session(
                aws_access_key_id=secrets.get("access_key_id"),
                aws_secret_access_key=secrets.get("secret_access_key"),
                aws_session_token=secrets.get("session_token"),
                region_name=secrets.get("region", "us-east-1")
            )
            
            # Determine role to assume
            role_name = account.role_override or discovery_config.get("member_role_name")
            
            if role_name and account.account_id:
                # Assume role into the target account
                sts = session.client("sts")
                role_arn = f"arn:aws:iam::{account.account_id}:role/{role_name}"
                
                try:
                    assumed = sts.assume_role(
                        RoleArn=role_arn,
                        RoleSessionName="CoalmineHealthCheck"
                    )
                    creds = assumed["Credentials"]
                    
                    # Create new session with assumed credentials
                    target_session = boto3.Session(
                        aws_access_key_id=creds["AccessKeyId"],
                        aws_secret_access_key=creds["SecretAccessKey"],
                        aws_session_token=creds["SessionToken"]
                    )
                    target_sts = target_session.client("sts")
                    identity = target_sts.get_caller_identity()
                    
                    return True, f"AWS account accessible via {role_name}. Account: {identity.get('Account')}"
                except ClientError as e:
                    error_code = e.response.get("Error", {}).get("Code", "Unknown")
                    return False, f"Failed to assume role {role_name}: {error_code}"
            else:
                # Direct access - verify we can reach the account
                sts = session.client("sts")
                identity = sts.get_caller_identity()
                caller_account = identity.get("Account")
                
                if account.account_id and caller_account != account.account_id:
                    return False, f"Credential authenticates to account {caller_account}, not {account.account_id}"
                
                return True, f"AWS account accessible. Account: {caller_account}"
                
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "Unknown")
            return False, f"AWS access failed: {error_code}"
        except Exception as e:
            return False, f"AWS check failed: {str(e)}"

    def _check_gcp(self, account: Account, credential) -> Tuple[bool, str]:
        """Validate GCP project access."""
        secrets = credential.secrets or {}
        
        try:
            from google.oauth2 import service_account
            from google.cloud import resourcemanager_v3
            
            # Get service account JSON from secrets
            sa_json = secrets.get("service_account_json")
            if not sa_json:
                return False, "Missing service_account_json in credential secrets"
            
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
            
            # Use the account's project ID
            project_id = account.account_id
            if not project_id:
                return False, "Account has no project ID configured"
            
            # Validate project access via ResourceManager
            client = resourcemanager_v3.ProjectsClient(credentials=creds)
            request = resourcemanager_v3.GetProjectRequest(name=f"projects/{project_id}")
            project = client.get_project(request=request)
            
            return True, f"GCP project accessible. Project: {project.display_name} ({project.state.name})"
            
        except Exception as e:
            return False, f"GCP check failed: {str(e)}"

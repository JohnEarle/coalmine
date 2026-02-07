"""
Credential Resolution Module

Economy of mechanism: One function handles all credential types.
Returns environment variables ready for subprocess/SDK use.

Supports:
- STATIC: Direct access keys / service account JSON
- ASSUME_ROLE: AWS cross-account role assumption
- IMPERSONATE: GCP service account impersonation
"""
import json
import hashlib
import os
import boto3
from typing import Dict

from .models import Account, Credential, CredentialAuthType
from .logging_config import get_logger

logger = get_logger(__name__)


def get_credentials_for_account(account: Account) -> Dict[str, str]:
    """
    Resolve executable credentials for a given account.
    
    This is the single entry point for all credential resolution.
    Returns a dict of environment variables ready for subprocess use.
    
    Args:
        account: The Account to get credentials for
        
    Returns:
        Dict of environment variables (AWS_ACCESS_KEY_ID, etc.)
    """
    cred = account.credential
    
    if cred.auth_type == CredentialAuthType.STATIC:
        return _build_static_env(cred, account)
    
    elif cred.auth_type == CredentialAuthType.ASSUME_ROLE:
        return _assume_role_for_account(cred, account)
    
    elif cred.auth_type == CredentialAuthType.IMPERSONATE:
        return _impersonate_for_account(cred, account)
    
    raise ValueError(f"Unknown auth_type: {cred.auth_type}")


def _resolve_secret(secrets: dict, *keys) -> str | None:
    """Look up a value by multiple possible key names."""
    for key in keys:
        val = secrets.get(key)
        if val:
            return val
    return None


def _build_static_env(cred: Credential, account: Account) -> Dict[str, str]:
    """
    Build env vars from static credentials.
    
    Handles flexible key formats (with/without provider prefix, case variations)
    to support credentials created via CLI, YAML sync, or direct API.
    """
    env = {}
    secrets = cred.secrets or {}
    
    if cred.provider == "AWS":
        access_key = _resolve_secret(secrets, "access_key_id", "AWS_ACCESS_KEY_ID", "aws_access_key_id")
        secret_key = _resolve_secret(secrets, "secret_access_key", "AWS_SECRET_ACCESS_KEY", "aws_secret_access_key")
        session_token = _resolve_secret(secrets, "session_token", "AWS_SESSION_TOKEN", "aws_session_token")
        region = _resolve_secret(secrets, "region", "AWS_REGION", "aws_region")
        
        if access_key:
            env["AWS_ACCESS_KEY_ID"] = access_key
        if secret_key:
            env["AWS_SECRET_ACCESS_KEY"] = secret_key
        if session_token:
            env["AWS_SESSION_TOKEN"] = session_token
        if region:
            env["AWS_REGION"] = region
            env["AWS_DEFAULT_REGION"] = region
            
    elif cred.provider == "GCP":
        json_content = _resolve_secret(
            secrets, "service_account_json", "GOOGLE_CREDENTIALS_JSON", "google_credentials_json"
        )
        path_val = _resolve_secret(
            secrets, "GOOGLE_APPLICATION_CREDENTIALS", "google_application_credentials"
        )

        if json_content:
            path = _write_gcp_creds(json_content)
            env["GOOGLE_APPLICATION_CREDENTIALS"] = path
            
            try:
                data = json.loads(json_content) if isinstance(json_content, str) else json_content
                if data.get("project_id"):
                    env["GOOGLE_CLOUD_PROJECT"] = data["project_id"]
                    env["CLOUDSDK_CORE_PROJECT"] = data["project_id"]
            except Exception as e:
                logger.warning(f"Failed to parse GCP creds JSON: {e}")
        elif path_val:
            env["GOOGLE_APPLICATION_CREDENTIALS"] = path_val
        
        # Account's account_id overrides extracted project
        if account.account_id and account.account_id != "unknown":
            env["GOOGLE_CLOUD_PROJECT"] = account.account_id
            env["CLOUDSDK_CORE_PROJECT"] = account.account_id
    
    return env


def _assume_role_for_account(cred: Credential, account: Account) -> Dict[str, str]:
    """
    Use base credentials to assume role in target account.
    
    AWS cross-account pattern:
    1. Use orchestrator credentials from cred.secrets
    2. Assume role in target account
    3. Return temporary credentials
    """
    secrets = cred.secrets or {}
    discovery_config = cred.discovery_config or {}
    
    # Determine role ARN
    if account.role_override:
        role_arn = account.role_override
    else:
        role_name = discovery_config.get("member_role_name", "CoalmineDeployer")
        role_arn = f"arn:aws:iam::{account.account_id}:role/{role_name}"
    
    # Create STS client with base credentials
    sts = boto3.client(
        'sts',
        aws_access_key_id=secrets.get("access_key_id"),
        aws_secret_access_key=secrets.get("secret_access_key"),
        region_name=secrets.get("region", "us-east-1")
    )
    
    # Assume role
    assume_params = {
        "RoleArn": role_arn,
        "RoleSessionName": discovery_config.get("session_name", "coalmine-session"),
        "DurationSeconds": discovery_config.get("duration_seconds", 3600)
    }
    
    if discovery_config.get("external_id"):
        assume_params["ExternalId"] = discovery_config["external_id"]
    
    logger.info(f"Assuming role {role_arn} for account {account.name}")
    response = sts.assume_role(**assume_params)
    
    return {
        "AWS_ACCESS_KEY_ID": response['Credentials']['AccessKeyId'],
        "AWS_SECRET_ACCESS_KEY": response['Credentials']['SecretAccessKey'],
        "AWS_SESSION_TOKEN": response['Credentials']['SessionToken'],
        "AWS_REGION": secrets.get("region", "us-east-1"),
        "AWS_DEFAULT_REGION": secrets.get("region", "us-east-1")
    }


def _impersonate_for_account(cred: Credential, account: Account) -> Dict[str, str]:
    """
    Use base service account to impersonate target SA in another project.
    
    GCP impersonation pattern:
    1. Use org-level SA from cred.secrets
    2. Impersonate project-level SA
    3. Return credentials file path
    """
    from google.auth import impersonated_credentials
    from google.oauth2 import service_account
    
    secrets = cred.secrets or {}
    discovery_config = cred.discovery_config or {}
    
    # Parse base credentials
    json_content = secrets.get("service_account_json")
    if not json_content:
        raise ValueError("GCP impersonation requires service_account_json in secrets")
    
    base_creds_path = _write_gcp_creds(json_content)
    base_creds = service_account.Credentials.from_service_account_file(base_creds_path)
    
    # Determine target service account
    if account.role_override:
        target_sa = account.role_override
    else:
        pattern = discovery_config.get(
            "deployer_sa_pattern",
            "coalmine@{project_id}.iam.gserviceaccount.com"
        )
        target_sa = pattern.format(project_id=account.account_id)
    
    logger.info(f"Impersonating {target_sa} for project {account.account_id}")
    
    # Create impersonated credentials
    impersonated = impersonated_credentials.Credentials(
        source_credentials=base_creds,
        target_principal=target_sa,
        target_scopes=['https://www.googleapis.com/auth/cloud-platform'],
        delegates=discovery_config.get("delegates", [])
    )
    
    # Write impersonated credentials to temp file
    # Note: This creates a credentials file that uses impersonation
    impersonated_config = {
        "type": "impersonated_service_account",
        "source_credentials": json.loads(json_content) if isinstance(json_content, str) else json_content,
        "service_account_impersonation_url": f"https://iamcredentials.googleapis.com/v1/projects/-/serviceAccounts/{target_sa}:generateAccessToken",
        "delegates": discovery_config.get("delegates", []),
    }
    
    impersonated_path = _write_gcp_creds(impersonated_config, prefix="impersonated")
    
    return {
        "GOOGLE_APPLICATION_CREDENTIALS": impersonated_path,
        "GOOGLE_CLOUD_PROJECT": account.account_id,
        "CLOUDSDK_CORE_PROJECT": account.account_id
    }


def _write_gcp_creds(creds_data, prefix: str = "gcp_creds") -> str:
    """Write GCP credentials to a temp file and return path."""
    if isinstance(creds_data, str):
        content = creds_data
    else:
        content = json.dumps(creds_data, indent=2)
    
    h = hashlib.md5(content.encode()).hexdigest()
    path = f"/tmp/{prefix}_{h}.json"
    if not os.path.exists(path):
        with open(path, "w") as f:
            f.write(content)
    return path


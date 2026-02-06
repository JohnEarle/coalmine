"""
AWS Organizations Discovery

Discovers AWS accounts using AWS Organizations API.
Supports filtering by OUs and excluding specific accounts.
"""
import boto3
from botocore.exceptions import ClientError
from typing import List, Optional

from . import OrganizationDiscovery, DiscoveredAccount, register_discovery
from ..logging_config import get_logger

logger = get_logger(__name__)


@register_discovery("AWS")
class AWSOrganizationDiscovery(OrganizationDiscovery):
    """
    Discover AWS accounts using AWS Organizations API.
    
    Required IAM permissions:
    - organizations:ListAccounts
    - organizations:ListAccountsForParent
    - organizations:DescribeOrganization
    - sts:AssumeRole (for each member account)
    """
    
    def _get_session(self) -> boto3.Session:
        """Create boto3 session from credential secrets."""
        secrets = self.credential.secrets or {}
        return boto3.Session(
            aws_access_key_id=secrets.get("access_key_id"),
            aws_secret_access_key=secrets.get("secret_access_key"),
            aws_session_token=secrets.get("session_token"),
            region_name=secrets.get("region", "us-east-1")
        )
    
    def validate_access(self) -> tuple[bool, str]:
        """Validate organization access."""
        try:
            session = self._get_session()
            org_client = session.client("organizations")
            
            # Try to describe the organization
            response = org_client.describe_organization()
            org_id = response["Organization"]["Id"]
            master_account = response["Organization"]["MasterAccountId"]
            
            return True, f"Connected to AWS Organization {org_id} (master: {master_account})"
        except ClientError as e:
            return False, f"AWS Organizations access failed: {e}"
        except Exception as e:
            return False, f"Validation error: {e}"
    
    def discover(self) -> List[DiscoveredAccount]:
        """
        Discover all accounts in the AWS Organization.
        
        Respects discovery_config:
        - include_ous: List of OU IDs to include (if specified, only these OUs)
        - exclude_accounts: List of account IDs to exclude
        """
        session = self._get_session()
        org_client = session.client("organizations")
        
        include_ous = self.discovery_config.get("include_ous", [])
        exclude_accounts = set(self.discovery_config.get("exclude_accounts", []))
        
        discovered = []
        
        try:
            if include_ous:
                # Discover only from specified OUs
                for ou_id in include_ous:
                    accounts = self._list_accounts_for_ou(org_client, ou_id)
                    discovered.extend(accounts)
            else:
                # Discover all accounts in the organization
                paginator = org_client.get_paginator("list_accounts")
                for page in paginator.paginate():
                    for account in page["Accounts"]:
                        if account["Status"] != "ACTIVE":
                            continue
                        
                        if account["Id"] in exclude_accounts:
                            logger.info(f"Skipping excluded account: {account['Id']}")
                            continue
                        
                        discovered.append(DiscoveredAccount(
                            account_id=account["Id"],
                            name=account["Name"],
                            metadata={
                                "email": account.get("Email"),
                                "arn": account.get("Arn"),
                                "joined_method": account.get("JoinedMethod"),
                                "joined_timestamp": str(account.get("JoinedTimestamp", ""))
                            }
                        ))
            
            # Filter out excluded accounts
            discovered = [a for a in discovered if a.account_id not in exclude_accounts]
            
            logger.info(f"Discovered {len(discovered)} AWS accounts")
            return discovered
            
        except ClientError as e:
            logger.error(f"AWS discovery failed: {e}")
            raise
    
    def _list_accounts_for_ou(self, client, ou_id: str) -> List[DiscoveredAccount]:
        """List all accounts in a specific OU (including nested OUs)."""
        accounts = []
        
        try:
            # List accounts directly in this OU
            paginator = client.get_paginator("list_accounts_for_parent")
            for page in paginator.paginate(ParentId=ou_id):
                for account in page["Accounts"]:
                    if account["Status"] != "ACTIVE":
                        continue
                    
                    accounts.append(DiscoveredAccount(
                        account_id=account["Id"],
                        name=account["Name"],
                        metadata={
                            "email": account.get("Email"),
                            "arn": account.get("Arn"),
                            "ou_id": ou_id
                        }
                    ))
            
            # Recursively list child OUs
            child_paginator = client.get_paginator("list_organizational_units_for_parent")
            for page in child_paginator.paginate(ParentId=ou_id):
                for child_ou in page["OrganizationalUnits"]:
                    child_accounts = self._list_accounts_for_ou(client, child_ou["Id"])
                    # Update metadata to include OU path
                    for acc in child_accounts:
                        acc.metadata["ou_path"] = f"{ou_id}/{child_ou['Id']}"
                    accounts.extend(child_accounts)
                    
        except ClientError as e:
            logger.warning(f"Failed to list accounts for OU {ou_id}: {e}")
        
        return accounts
    
    def _default_role(self) -> str:
        """Default role name for AWS cross-account access."""
        return "CoalmineDeployer"

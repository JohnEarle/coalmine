"""
Logging utility functions for Coalmine.
"""
from .models import ResourceType
from .logging_config import get_logger
import boto3
import json
import os

logger = get_logger(__name__)

def _update_trail_selectors(account, trail_name, resource_arn, add: bool = True):
    """
    Dynamically update CloudTrail Advanced Event Selectors to include/exclude a resource.
    """
    if not account:
        return
    
    cred = account.credential
    if not cred or cred.provider != "AWS":
        return

    secrets = cred.secrets or {}
    region = secrets.get("AWS_REGION") or secrets.get("region", "us-east-1")
    
    try:
        client = boto3.client(
            "cloudtrail",
            aws_access_key_id=secrets.get("AWS_ACCESS_KEY_ID") or secrets.get("aws_access_key_id"),
            aws_secret_access_key=secrets.get("AWS_SECRET_ACCESS_KEY") or secrets.get("aws_secret_access_key"),
            region_name=region
        )
        
        resp = client.get_event_selectors(TrailName=trail_name)
        advanced_selectors = resp.get("AdvancedEventSelectors", [])
        
        updated = False
        target_selector = None
        for sel in advanced_selectors:
             for fs in sel.get("FieldSelectors", []):
                 if fs.get("Field") == "resources.type":
                     is_s3 = False
                     for eq in fs.get("Equals", []):
                         if "S3" in eq:
                             is_s3 = True
                             break
                     if is_s3:
                         target_selector = sel
                         break
        
        if not target_selector:
             logger.warning(f"No S3 Data selector found in trail {trail_name}")
             return

        arn_field = None
        for f in target_selector["FieldSelectors"]:
            if f["Field"] == "resources.ARN":
                arn_field = f
                break
        
        if not arn_field:
            arn_field = {"Field": "resources.ARN", "Equals": []}
            target_selector["FieldSelectors"].append(arn_field)
            
        if "Equals" not in arn_field:
            arn_field["Equals"] = []
            
        s3_resource_arn = resource_arn
        if not s3_resource_arn.endswith("/"):
             s3_resource_arn += "/"
             
        if add:
            if s3_resource_arn not in arn_field["Equals"]:
                arn_field["Equals"].append(s3_resource_arn)
                updated = True
        else:
            if s3_resource_arn in arn_field["Equals"]:
                arn_field["Equals"].remove(s3_resource_arn)
                updated = True
                
        if updated:
            client.put_event_selectors(
                TrailName=trail_name,
                AdvancedEventSelectors=advanced_selectors
            )
            logger.info(f"Updated trail {trail_name}: {'Added' if add else 'Removed'} {s3_resource_arn}")
            
    except Exception as e:
        logger.error(f"Error updating trail selectors: {e}")


def _update_gcp_sink_filter(account, sink_name, resource_val, resource_type: ResourceType, add: bool = True):
    """
    Dynamically update GCP Log Sink filter to include/exclude a resource.
    For SA: protoPayload.authenticationInfo.principalEmail="{email}"
    For Bucket: protoPayload.resourceName:"{bucket_name}"
    """
    if not account:
        return
    
    cred = account.credential
    if not cred or cred.provider != "GCP":
        return

    secrets = cred.secrets or {}
    
    # Get project_id from account.account_id (for GCP this is the project ID)
    project_id = account.account_id
    if not project_id and "project_id" in secrets:
         project_id = secrets["project_id"]
         
    if not project_id:
        logger.warning("Cannot update GCP sink: No project_id found.")
        return

    try:
        from google.cloud import logging
        from google.oauth2 import service_account
        
        credentials = None
        json_content = secrets.get("service_account_json") or secrets.get("GOOGLE_CREDENTIALS_JSON")
        if json_content:
             if isinstance(json_content, str):
                 json_content = json.loads(json_content)
             credentials = service_account.Credentials.from_service_account_info(json_content)
        elif "type" in secrets and secrets["type"] == "service_account":
             credentials = service_account.Credentials.from_service_account_info(secrets)
        
        client = logging.Client(project=project_id, credentials=credentials)
        sink = client.sink(sink_name)
        
        # Reload to get current filter
        sink.reload()
        current_filter = sink.filter_ or ""
        
        # Construct Filter Fragment
        fragment = ""
        if resource_type == ResourceType.GCP_SERVICE_ACCOUNT:
            email = resource_val
            if "@" not in email and project_id:
                email = f"{resource_val}@{project_id}.iam.gserviceaccount.com"
            # Expanded filter to capture usage (principalEmail) AND management (resourceName)
            fragment = f'(protoPayload.authenticationInfo.principalEmail="{email}" OR protoPayload.resourceName:"{resource_val}")'
            
        elif resource_type == ResourceType.GCP_BUCKET:
             fragment = f'protoPayload.resourceName:"{resource_val}"'
        
        if not fragment:
            return

        updated = False
        if add:
            if fragment not in current_filter:
                stripped = current_filter.strip()
                if stripped.endswith(")"):
                     new_filter = stripped[:-1] + f" OR {fragment}\n)"
                else:
                     new_filter = f"{stripped} OR {fragment}"
                
                sink.filter_ = new_filter
                updated = True
        else:
            # Remove
            if fragment in current_filter:
                # Basic removal, could be improved with regex but keeping it simple
                new_filter = current_filter.replace(f" OR {fragment}", "").replace(fragment, "")
                sink.filter_ = new_filter
                updated = True

        if updated:
            sink.update(unique_writer_identity=True)
            logger.info(f"Updated GCP sink {sink_name}: {'Added' if add else 'Removed'} {resource_val}")

    except Exception as e:
        logger.error(f"Error updating GCP sink: {e}")


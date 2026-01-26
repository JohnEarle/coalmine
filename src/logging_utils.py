"""
Logging utility functions for Coalmine.
"""
from .models import ResourceType
from .logging_config import get_logger
import boto3
import json
import os

logger = get_logger(__name__)

def _update_trail_selectors(env_obj, trail_name, resource_arn, add: bool = True):
    """
    Dynamically update CloudTrail Advanced Event Selectors to include/exclude a resource.
    """
    if not env_obj or env_obj.provider_type != "AWS":
        return

    creds = env_obj.credentials or {}
    region = env_obj.config.get("region", "us-east-1")
    
    try:
        client = boto3.client(
            "cloudtrail",
            aws_access_key_id=creds.get("AWS_ACCESS_KEY_ID"),
            aws_secret_access_key=creds.get("AWS_SECRET_ACCESS_KEY"),
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


def _update_gcp_sink_filter(env_obj, sink_name, resource_val, resource_type: ResourceType, add: bool = True):
    """
    Dynamically update GCP Log Sink filter to include/exclude a resource.
    For SA: protoPayload.authenticationInfo.principalEmail="{email}"
    For Bucket: protoPayload.resourceName:"{bucket_name}"
    """
    if not env_obj or env_obj.provider_type != "GCP":
        return

    creds_wrapper = env_obj.credentials or {}
    
    project_id = None
    if env_obj.config:
         project_id = env_obj.config.get("project_id")
    if not project_id and "project_id" in creds_wrapper:
         project_id = creds_wrapper["project_id"]
         
    if not project_id:
        logger.warning("Cannot update GCP sink: No project_id found.")
        return

    try:
        from google.cloud import logging
        from google.oauth2 import service_account
        
        credentials = None
        if "GOOGLE_CREDENTIALS_JSON" in creds_wrapper:
             info = creds_wrapper["GOOGLE_CREDENTIALS_JSON"]
             if isinstance(info, str):
                 info = json.loads(info)
             credentials = service_account.Credentials.from_service_account_info(info)
        elif "type" in creds_wrapper and creds_wrapper["type"] == "service_account":
             credentials = service_account.Credentials.from_service_account_info(creds_wrapper)
        
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

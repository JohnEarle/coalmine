import sys
import os
import json
import requests
from google.auth.transport.requests import Request
from google.oauth2 import service_account
from google.cloud import logging_v2

sys.path.append(os.getcwd())
from src.models import SessionLocal, CanaryResource

def configure_exclusion(canary_name):
    db = SessionLocal()
    try:
        canary = db.query(CanaryResource).filter(CanaryResource.name == canary_name).first()
        if not canary:
            print(f"Canary {canary_name} not found")
            return

        env = canary.environment
        creds_wrapper = env.credentials or {}
        
        info = None
        if "GOOGLE_CREDENTIALS_JSON" in creds_wrapper:
             info = creds_wrapper["GOOGLE_CREDENTIALS_JSON"]
             if isinstance(info, str):
                 info = json.loads(info)
        elif "type" in creds_wrapper:
            info = creds_wrapper
            
        if not info:
            print("No valid GCP credentials found in environment.")
            return

        print(f"Using credentials for {info.get('client_email')}")
        creds = service_account.Credentials.from_service_account_info(info)
        
        project_id = info.get('project_id')
        parent = f"projects/{project_id}"
        
        client = logging_v2.ConfigServiceV2Client(credentials=creds)
        
        # Define the exclusion filter
        # We want to EXCLUDE Data Access logs that are NOT related to our canaries.
        # This assumes "canary" is in the name. Better strictly, we might iterate all active canaries?
        # For now, let's use the substring "canary" as a heuristic for the project.
        
        exclusion_name = "exclude-non-canary-data-access"
        description = "Exclude Data Access logs not related to canary resources to save costs."
        
        # Filter: Matches Data Access logs that do NOT mention 'canary'
        filter_str = (
            'log_id("cloudaudit.googleapis.com/data_access") AND '
            'NOT protoPayload.authenticationInfo.principalEmail:"canary" AND '
            'NOT protoPayload.resourceName:"canary"'
        )
        
        exclusion = logging_v2.LogExclusion(
            name=exclusion_name,
            description=description,
            filter=filter_str,
            disabled=False
        )
        
        print(f"Configuring exclusion '{exclusion_name}' on {parent}...")
        
        try:
            client.create_exclusion(parent=parent, exclusion=exclusion)
            print("Exclusion created successfully.")
        except Exception as e:
            if "already exists" in str(e):
                print("Exclusion already exists, updating...")
                client.update_exclusion(name=f"{parent}/exclusions/{exclusion_name}", exclusion=exclusion)
                print("Exclusion updated successfully.")
            else:
                print(f"Failed to configure exclusion: {e}")

    finally:
        db.close()

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python scripts/configure_log_exclusion.py <canary_name_for_creds>")
        sys.exit(1)
    configure_exclusion(sys.argv[1])

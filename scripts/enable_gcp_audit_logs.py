import sys
import os
import json
import requests
from google.auth.transport.requests import Request
from google.oauth2 import service_account

sys.path.append(os.getcwd())
from src.models import SessionLocal, CanaryResource

def enable_audit_logs(canary_name):
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
        scoped_creds = creds.with_scopes(['https://www.googleapis.com/auth/cloud-platform'])
        scoped_creds.refresh(Request())
        token = scoped_creds.token
        
        project_id = info.get('project_id')
        
        # 0. Enable Cloud Resource Manager API
        print("Enabling Cloud Resource Manager API...")
        su_url = f"https://serviceusage.googleapis.com/v1/projects/{project_id}/services/cloudresourcemanager.googleapis.com:enable"
        su_resp = requests.post(su_url, headers={"Authorization": f"Bearer {token}"})
        if su_resp.status_code not in [200, 201]: # 200 OK or 201 Created (Long running op)
             # If async, we might need to wait, but usually RM API is fast or we can try immediately.
             # Actually it returns an Operation.
             print(f"Warning: Enable API returned {su_resp.status_code}. It might already be enabled or failed.")
        else:
             print("API Enable request sent.")
             # Simple wait usually enough for small APIs, or retry loop for getIamPolicy
             import time
             time.sleep(5) 
        
        # 1. Get Policy
        print(f"Getting IAM Policy for project {project_id}...")
        url = f"https://cloudresourcemanager.googleapis.com/v1/projects/{project_id}:getIamPolicy"
        resp = requests.post(url, headers={"Authorization": f"Bearer {token}"}, json={})
        
        if resp.status_code != 200:
            print(f"Failed to get policy: {resp.status_code} {resp.text}")
            return
            
        policy = resp.json()
        
        # 2. Update Audit Config
        # We want to enable DATA_READ and DATA_WRITE for specific services
        # Services: "storage.googleapis.com", "iam.googleapis.com"
        
        target_services = ["storage.googleapis.com", "iam.googleapis.com"]
        audit_configs = policy.get('auditConfigs', [])
        
        updated = False
        for svc in target_services:
            # Check if exists
            exists = False
            for ac in audit_configs:
                if ac.get('service') == svc:
                    exists = True
                    # Check types
                    types = [t['logType'] for t in ac.get('auditLogConfigs', [])]
                    if 'DATA_READ' not in types:
                        ac.setdefault('auditLogConfigs', []).append({'logType': 'DATA_READ'})
                        updated = True
                    if 'DATA_WRITE' not in types:
                        ac.setdefault('auditLogConfigs', []).append({'logType': 'DATA_WRITE'})
                        updated = True
                    if 'ADMIN_READ' not in types:
                        ac.setdefault('auditLogConfigs', []).append({'logType': 'ADMIN_READ'})
                        updated = True
            
            if not exists:
                audit_configs.append({
                    "service": svc,
                    "auditLogConfigs": [
                        {"logType": "ADMIN_READ"},
                        {"logType": "DATA_WRITE"},
                        {"logType": "DATA_READ"}
                    ]
                })
                updated = True
        
        policy['auditConfigs'] = audit_configs
        
        if not updated:
            print("Audit Logs already enabled.")
            return

        # 3. Set Policy
        print("Updating IAM Policy to enable Audit Logs...")
        url = f"https://cloudresourcemanager.googleapis.com/v1/projects/{project_id}:setIamPolicy"
        resp = requests.post(url, headers={"Authorization": f"Bearer {token}"}, json={"policy": policy})
        
        if resp.status_code == 200:
            print("Successfully enabled Audit Logs.")
        else:
            print(f"Failed to set policy: {resp.status_code} {resp.text}")

    finally:
        db.close()

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python scripts/enable_gcp_audit_logs.py <canary_name>")
        sys.exit(1)
    enable_audit_logs(sys.argv[1])

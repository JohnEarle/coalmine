import sys
import os
import base64
import json
sys.path.append(os.getcwd())
from src.models import SessionLocal, CanaryResource
from google.oauth2 import service_account
from google.cloud import storage

def trigger(canary_name):
    db = SessionLocal()
    try:
        canary = db.query(CanaryResource).filter(CanaryResource.name == canary_name).first()
        if not canary:
            print(f"Canary {canary_name} not found")
            return
            
        if not canary.canary_credentials:
             print("No credentials found for canary.")
             return

        # Tofu output for google_service_account_key.private_key is Base64 encoded JSON
        raw_key = canary.canary_credentials.get("service_account_key")
        
        if not raw_key:
            print("No 'service_account_key' in credentials blob.")
            # Fallback if older version or different struct
            print(canary.canary_credentials.keys())
            return

        try:
            decoded = base64.b64decode(raw_key).decode('utf-8')
            info = json.loads(decoded)
        except Exception as e:
            print(f"Error decoding key (might be plain json?): {e}")
            info = raw_key if isinstance(raw_key, dict) else json.loads(raw_key)
            
        creds = service_account.Credentials.from_service_account_info(info)
        
        # Use a specific project if provided, else from key
        project = info.get('project_id')
        
        print(f"Authenticated as {info.get('client_email')}")
        
        # Action: List Buckets
        # This will trigger 'storage.buckets.list' or generic usage
        # Since the filter checks for 'principalEmail' in authenticationInfo, ANY authenticated call works.
        client = storage.Client(credentials=creds, project=project)
        
        print("Attempting to list buckets to generate traffic...")
        try:
            buckets = list(client.list_buckets())
            print(f"Buckets found: {len(buckets)}")
        except Exception as e:
            print(f"API Call Result: {e}")
            
    except Exception as e:
        print(f"Trigger failed: {e}")
        
    try:
        print("Attempting to create a bucket (Write op)...")
        bucket_name = f"canary-test-{canary_name}-{base64.b64encode(os.urandom(4)).decode('utf-8').lower().replace('=', '')}"
        bucket = client.bucket(bucket_name)
        bucket.create(location="US")
        print(f"Bucket {bucket_name} created (Unexpected!)")
    except Exception as e:
        print(f"Create Bucket Result: {e}")

    try:
        print("Attempting to create a service account key (Admin Activity)...")
        import requests
        from google.auth.transport.requests import Request
        
        # Scopes might need to be wider for IAM, default from_service_account_info might be scoped to cloud-platform if we didn't specify? 
        # Actually from_service_account_info usually has no scopes. We need to add them.
        scoped_creds = creds.with_scopes(['https://www.googleapis.com/auth/cloud-platform'])
        scoped_creds.refresh(Request())
        token = scoped_creds.token
        
        email = info.get('client_email')
        project_id = info.get('project_id')
        url = f"https://iam.googleapis.com/v1/projects/{project_id}/serviceAccounts/{email}/keys"
        
        resp = requests.post(url, headers={"Authorization": f"Bearer {token}"}, json={})
        print(f"Create Key Result: {resp.status_code} {resp.text}")
        
    except Exception as e:
        print(f"Create Key Failed: {e}")

    finally:
        db.close()

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python scripts/trigger_gcp_canary.py <canary_name>")
        sys.exit(1)
    trigger(sys.argv[1])

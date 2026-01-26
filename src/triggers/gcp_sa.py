import base64
import json
from google.oauth2 import service_account
from google.cloud import storage
from .base import CanaryTrigger, logger
from ..models import CanaryResource

class GcpSaTrigger(CanaryTrigger):
    def execute(self, canary: CanaryResource) -> bool:
        creds_data = canary.canary_credentials
        if not creds_data:
             logger.error(f"No credentials found for canary {canary.name}")
             return False
             
        raw_key = creds_data.get("service_account_key")
        if not raw_key:
             logger.error("No 'service_account_key' in credentials.")
             return False

        try:
             # Decode key
             try:
                 decoded = base64.b64decode(raw_key).decode('utf-8')
                 info = json.loads(decoded)
             except:
                 info = raw_key if isinstance(raw_key, dict) else json.loads(raw_key)

             credentials = service_account.Credentials.from_service_account_info(info)
             project = info.get('project_id')
             
             logger.info(f"Triggering {canary.name} via storage.buckets.list()...")
             client = storage.Client(credentials=credentials, project=project)
             
             # This might fail with 403, but that IS the trigger event usually
             try:
                 buckets = list(client.list_buckets())
                 logger.info(f"Listed {len(buckets)} buckets.")
             except Exception as api_err:
                 logger.info(f"API call made (expected error or success): {api_err}")
                 
             return True

        except Exception as e:
            logger.error(f"Failed to trigger GCP SA canary: {e}")
            return False

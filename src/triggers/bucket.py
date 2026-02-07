import requests
import boto3
from .base import CanaryTrigger, logger
from ..models import CanaryResource, ResourceType

class BucketTrigger(CanaryTrigger):
    def execute(self, canary: CanaryResource) -> bool:
        bucket_name = canary.current_resource_id
        if not bucket_name:
             logger.error("No bucket name found in current_resource_id")
             return False

        url = ""
        if canary.resource_type == ResourceType.AWS_BUCKET:
             # Use boto3 to generate an Authenticated CloudTrail event (ListObjects)
             try:
                 # Get credentials from the linked account
                 if not canary.account or not canary.account.credential:
                     logger.error("No account/credential linked to canary")
                     return False
                 creds = canary.account.credential.secrets or {}
                 # Construct session
                 session = boto3.Session(
                     aws_access_key_id=creds.get("aws_access_key_id") or creds.get("AWS_ACCESS_KEY_ID") or creds.get("access_key_id"),
                     aws_secret_access_key=creds.get("aws_secret_access_key") or creds.get("AWS_SECRET_ACCESS_KEY") or creds.get("secret_access_key"),
                     region_name=creds.get("region") or creds.get("AWS_REGION") or "us-east-1"
                 )
                 s3 = session.client("s3")
                 
                 logger.info(f"Triggering {canary.name} via boto3 ListObjectsV2...")
                 # This will likely work (App has admin) or Fail (if bucket policy denies)
                 # Either way, generates 'ListObjectsV2' event in CloudTrail
                 s3.list_objects_v2(Bucket=bucket_name)
                 try:
                    s3.get_bucket_location(Bucket=bucket_name)
                 except:
                    pass
                 logger.info("Trigger executed (ListObjectsV2 & GetBucketLocation called).")
                 return True
             except Exception as e:
                 logger.info(f"Trigger executed with error (expected): {e}")
                 return True
                 
        elif canary.resource_type == ResourceType.GCP_BUCKET:

             url = f"https://storage.googleapis.com/{bucket_name}"
        else:
             logger.error(f"Unknown bucket type: {canary.resource_type}")
             return False

        logger.info(f"Triggering {canary.name} via HTTP GET {url}...")
        try:
             # Expect 403 or 404, but the Access Log is generated
             resp = requests.get(url, timeout=5)
             logger.info(f"Response: {resp.status_code}")
             return True
        except Exception as e:
             logger.error(f"Failed to access bucket URL: {e}")
             return False

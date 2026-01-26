import boto3
from .base import CanaryTrigger, logger
from ..models import CanaryResource

class AwsIamTrigger(CanaryTrigger):
    def execute(self, canary: CanaryResource) -> bool:
        creds = canary.canary_credentials
        if not creds:
             logger.error(f"No credentials found for canary {canary.name}")
             return False

        try:
             # Use the canary credentials to make a call
             session = boto3.Session(
                 aws_access_key_id=creds.get("access_key_id"),
                 aws_secret_access_key=creds.get("secret_access_key")
             )
             sts = session.client("sts")
             
             logger.info(f"Triggering {canary.name} via sts.get_caller_identity()...")
             id_info = sts.get_caller_identity()
             logger.info(f"Identity confirmed: {id_info.get('Arn')}")
             return True
             
        except Exception as e:
            logger.error(f"Failed to trigger AWS IAM canary: {e}")
            return False


import sys
import os
import uuid
import time
import json
import base64
import boto3
from sqlalchemy.orm import Session

# Add src to path
sys.path.append(os.getcwd())

from src.models import (
    SessionLocal, CloudEnvironment, ResourceType, ResourceStatus, 
    LoggingResource, LoggingProviderType, init_db
)
from src.tasks.canary import create_canary
from google.oauth2 import service_account
from google.cloud import storage

# ANSI Colors
GREEN = '\033[92m'
RED = '\033[91m'
RESET = '\033[0m'

def log(msg, color=RESET):
    print(f"{color}{msg}{RESET}")

def setup_environments(db: Session):
    log("Setting up Cloud Environments...")
    
    # AWS Environment
    aws_env = db.query(CloudEnvironment).filter_by(name="test-aws-env").first()
    if not aws_env:
        log("Creating test-aws-env...", GREEN)
        aws_env = CloudEnvironment(
            name="test-aws-env",
            provider_type="AWS",
            credentials={
                "AWS_ACCESS_KEY_ID": os.getenv("AWS_ACCESS_KEY_ID"),
                "AWS_SECRET_ACCESS_KEY": os.getenv("AWS_SECRET_ACCESS_KEY"),
                "AWS_REGION": os.getenv("AWS_DEFAULT_REGION", "us-east-1")
            },
            config={"region": "us-east-1"}
        )
        db.add(aws_env)
    
    # GCP Environment
    gcp_env = db.query(CloudEnvironment).filter_by(name="test-gcp-env").first()
    if not gcp_env:
        log("Creating test-gcp-env...", GREEN)
        creds = {}
        # Try JSON content first
        if os.getenv("GCP_SERVICE_ACCOUNT_JSON"):
             creds["service_account_json"] = os.getenv("GCP_SERVICE_ACCOUNT_JSON")
        elif os.getenv("GOOGLE_APPLICATION_CREDENTIALS"):
             creds["google_application_credentials"] = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
             
        gcp_env = CloudEnvironment(
            name="test-gcp-env",
            provider_type="GCP",
            credentials=creds,
            config={"project_id": os.getenv("GOOGLE_CLOUD_PROJECT", "test-project")}
        )
        db.add(gcp_env)

    # Dummy Logging Resource (for dependencies)
    log_res = db.query(LoggingResource).filter_by(name="test-audit-sink").first()
    if not log_res:
         log("Creating test-audit-sink...", GREEN)
         log_res = LoggingResource(
             name="test-audit-sink",
             provider_type=LoggingProviderType.GCP_AUDIT_SINK,
             environment_id=gcp_env.id,  # Associate with GCP
             status=ResourceStatus.ACTIVE
         )
         db.add(log_res)
    
    db.commit()
    return aws_env, gcp_env, log_res

def test_aws_canary(db: Session, env_id, log_res_id):
    log("\n--- Testing AWS Canary ---")
    canary_name = f"aws-canary-{uuid.uuid4().hex[:6]}"
    
    try:
        # Create Canary
        log(f"Creating AWS Canary: {canary_name}")
        create_canary(
            name=canary_name,
            resource_type_str="AWS_SECRET", # Assuming this type exists or mapping to generic
            environment_id_str=str(env_id),
            logging_resource_id_str=str(log_res_id)
        )
        
        # Verify DB State
        canary = db.query(CanaryResource).filter_by(name=canary_name).first() # Query new instance
        if not canary:
            log("FAILED: Canary not found in DB", RED)
            return
        
        if canary.status != ResourceStatus.ACTIVE:
            log(f"FAILED: Canary status is {canary.status}", RED)
            # Check history
            return

        log("Canary created successfully.", GREEN)
        
        # Validate Credentials
        creds = canary.canary_credentials
        log(f"Testing Credentials: Access Key={creds.get('access_key_id')}...")
        
        client = boto3.client(
            'sts',
            aws_access_key_id=creds.get('access_key_id'),
            aws_secret_access_key=creds.get('secret_access_key'),
            region_name="us-east-1"
        )
        
        try:
            identity = client.get_caller_identity()
            log(f"SUCCESS: Identity confirmed: {identity['Arn']}", GREEN)
        except Exception as e:
            log(f"FAILED: Credential validation failed: {e}", RED)

    except Exception as e:
        log(f"AWS Test Exception: {e}", RED)

def test_gcp_canary(db: Session, env_id, log_res_id):
    log("\n--- Testing GCP Canary ---")
    canary_name = f"gcp-canary-{uuid.uuid4().hex[:6]}"
    
    try:
        # Create Canary
        log(f"Creating GCP Canary: {canary_name}")
        create_canary(
            name=canary_name,
            resource_type_str="GCP_SERVICE_ACCOUNT", 
            environment_id_str=str(env_id),
            logging_resource_id_str=str(log_res_id)
        )
        
        canary = db.query(CanaryResource).filter_by(name=canary_name).first()
        if not canary or canary.status != ResourceStatus.ACTIVE:
             log(f"FAILED: Canary creation failed. Status: {canary.status if canary else 'None'}", RED)
             return

        log("Canary created successfully.", GREEN)
        
        # Validate Credentials
        raw_key = canary.canary_credentials.get("service_account_key")
        
        try:
            # Handle potential double-encoding or raw dict
            info = raw_key
            if isinstance(raw_key, str):
                 try:
                    decoded = base64.b64decode(raw_key).decode('utf-8')
                    info = json.loads(decoded)
                 except:
                    info = json.loads(raw_key)
            
            creds = service_account.Credentials.from_service_account_info(info)
            log(f"Authenticated as {info.get('client_email')}", GREEN)
            
            # Simple API call
            storage_client = storage.Client(credentials=creds, project=info.get('project_id'))
            buckets = list(storage_client.list_buckets())
            log(f"SUCCESS: Listed {len(buckets)} buckets", GREEN)
            
        except Exception as e:
            log(f"FAILED: GCP Validation failed: {e}", RED)

    except Exception as e:
        log(f"GCP Test Exception: {e}", RED)

def main():
    init_db()
    db = SessionLocal()
    try:
        aws_env, gcp_env, log_res = setup_environments(db)
        
        # Run Tests
        if os.getenv("AWS_ACCESS_KEY_ID"):
            test_aws_canary(db, aws_env.id, log_res.id)
        else:
            log("Skipping AWS test (no creds in env)", RED)
            
        if os.getenv("GCP_SERVICE_ACCOUNT_JSON") or os.getenv("GOOGLE_APPLICATION_CREDENTIALS"):
             test_gcp_canary(db, gcp_env.id, log_res.id)
        else:
             log("Skipping GCP test (no creds in env)", RED)
             
    finally:
        db.close()

if __name__ == "__main__":
    main()

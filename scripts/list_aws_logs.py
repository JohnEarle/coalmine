import boto3
from src.models import SessionLocal, CloudEnvironment

db = SessionLocal()
try:
    env = db.query(CloudEnvironment).filter(CloudEnvironment.name == "dev-env").first()
    if not env:
        print("Env not found")
        exit(1)
    
    creds = env.credentials
    session = boto3.Session(
         aws_access_key_id=creds.get("aws_access_key_id") or creds.get("AWS_ACCESS_KEY_ID"),
         aws_secret_access_key=creds.get("aws_secret_access_key") or creds.get("AWS_SECRET_ACCESS_KEY"),
         region_name=creds.get("region", "us-east-1")
    )
    logs = session.client("logs")
    
    paginator = logs.get_paginator('describe_log_groups')
    for page in paginator.paginate():
        for group in page['logGroups']:
            print(f"LogGroup: {group['logGroupName']}")
            
finally:
    db.close()

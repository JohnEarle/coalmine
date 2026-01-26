import boto3
import time
from datetime import datetime, timedelta
from src.models import SessionLocal, CloudEnvironment

db = SessionLocal()
try:
    env = db.query(CloudEnvironment).filter(CloudEnvironment.name == "dev-env").first()
    creds = env.credentials
    session = boto3.Session(
         aws_access_key_id=creds.get("aws_access_key_id") or creds.get("AWS_ACCESS_KEY_ID"),
         aws_secret_access_key=creds.get("aws_secret_access_key") or creds.get("AWS_SECRET_ACCESS_KEY"),
         region_name=creds.get("region", "us-east-1")
    )
    logs = session.client("logs")
    
    log_group = "/aws/cloudtrail/pg-test-final"
    start_time = int((datetime.utcnow() - timedelta(minutes=15)).timestamp() * 1000)
    end_time = int(datetime.utcnow().timestamp() * 1000)
    
    print(f"Querying {log_group} from {start_time} to {end_time}...")
    
    # Try getting ANY event to verify flow
    resp = logs.filter_log_events(
        logGroupName=log_group,
        startTime=start_time,
        endTime=end_time,
        limit=5
    )
    
    events = resp.get('events', [])
    print(f"Found {len(events)} raw events.")
    for e in events:
        print(f" - {e['timestamp']} : {e['message'][:100]}...")

    # Try specific Canary pattern
    pattern = '{ ($.eventName = "ListObjectsV2") }'
    print(f"Querying with pattern: {pattern}")
    resp = logs.filter_log_events(
        logGroupName=log_group,
        startTime=start_time,
        endTime=end_time,
        filterPattern=pattern
    )
    matches = resp.get('events', [])
    print(f"Found {len(matches)} matching events.")
    for e in matches:
        print(f"MATCH: {e['message']}")

finally:
    db.close()

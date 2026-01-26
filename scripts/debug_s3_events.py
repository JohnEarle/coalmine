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
    start_time = int((datetime.utcnow() - timedelta(minutes=60)).timestamp() * 1000)
    end_time = int(datetime.utcnow().timestamp() * 1000)
    
    bucket_name = "s3-canary-01-202601251938"
    
    # Query for ANY event with this bucket name in parameters
    pattern = '{ ($.eventSource = "s3.amazonaws.com") && ($.requestParameters.bucketName = "' + bucket_name + '") }'
    
    print(f"Querying {log_group} for bucket {bucket_name}...")
    print(f"Pattern: {pattern}")
    
    resp = logs.filter_log_events(
        logGroupName=log_group,
        startTime=start_time,
        endTime=end_time,
        filterPattern=pattern
    )
    
    events = resp.get('events', [])
    print(f"Found {len(events)} events.")
    seen_events = set()
    for e in events:
        import json
        msg = json.loads(e['message'])
        evt = msg.get('eventName')
        seen_events.add(evt)
        print(f"[{e['timestamp']}] {evt} - {msg.get('sourceIPAddress')}")

    print(f"\nUnique Event Names Seen: {seen_events}")

finally:
    db.close()

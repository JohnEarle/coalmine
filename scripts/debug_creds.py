from src.models import SessionLocal, CanaryResource, ResourceType
db = SessionLocal()
try:
    canary = db.query(CanaryResource).filter(CanaryResource.name == "s3-canary-01").first()
    if canary and canary.environment:
        creds = canary.environment.credentials
        print(f"Credential Keys: {list(creds.keys())}")
        if 'aws_access_key_id' in creds:
             print("Has aws_access_key_id")
        else:
             print("MISSING aws_access_key_id")
finally:
    db.close()

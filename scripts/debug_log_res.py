from src.models import SessionLocal, CanaryResource
db = SessionLocal()
try:
    canary = db.query(CanaryResource).filter(CanaryResource.name == "s3-canary-01").first()
    if canary:
        print(f"Canary: {canary.name}")
        print(f"Environment: {canary.environment.name}")
        if canary.logging_resource:
            print(f"Logging Resource: {canary.logging_resource.name}")
            print(f"Config: {canary.logging_resource.configuration}")
        else:
            print("No Logging Resource associated!")
finally:
    db.close()

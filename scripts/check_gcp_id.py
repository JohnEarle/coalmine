from src.models import SessionLocal, CanaryResource, ResourceType
db = SessionLocal()
try:
    canary = db.query(CanaryResource).filter(CanaryResource.name == "argus-canary-01").first()
    if canary:
        print(f"Canary: {canary.name}")
        print(f"Resource ID: {canary.current_resource_id}")
finally:
    db.close()

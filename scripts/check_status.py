from src.models import SessionLocal, CanaryResource, ResourceStatus
db = SessionLocal()
try:
    canaries = db.query(CanaryResource).filter(CanaryResource.name == "argus-canary-01").all()
    for c in canaries:
        print(f"ID: {c.id}, Name: {c.name}, Status: {c.status.value}, Phys: {c.current_resource_id}")
finally:
    db.close()

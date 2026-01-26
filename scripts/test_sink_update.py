import sys
import os
import logging
from src.models import SessionLocal, CloudEnvironment, CanaryResource, ResourceType
from src.tasks import _update_gcp_sink_filter

# Setup logging
logging.basicConfig(level=logging.INFO)

def run():
    db = SessionLocal()
    try:
        # Get Environment
        # 84c91a54-0de2-4235-b6c9-87e94f4fd769 (argus-gcp)
        env = db.query(CloudEnvironment).filter(CloudEnvironment.name == 'argus-gcp').first()
        if not env:
            print("Env not found")
            return

        # Get Canary
        canary = db.query(CanaryResource).filter(CanaryResource.name == 'service-canary-05').first()
        if not canary:
            # Fallback if creation didn't write canary record? (It did, found it earlier)
            print("Canary not found")
            resource_val = "service-canary-05-manual"
        else:
            resource_val = canary.current_resource_id
            print(f"Updating for canary: {resource_val} (Type: {canary.resource_type})")

        sink_name = "canary-audit-sink" # Hardcoded for test
        
        print(f"Adding filter for {resource_val} to {sink_name}...")
        _update_gcp_sink_filter(env, sink_name, resource_val, ResourceType.GCP_SERVICE_ACCOUNT, add=True)
        print("Done.")

        # Verify?
        # We can implement a check here or trust the print inside _update_gcp_sink_filter
        
    except Exception as e:
        print(f"Failed: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    run()

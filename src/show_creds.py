import sys
import os
import uuid
import json
from src.models import SessionLocal, CanaryResource, ResourceType, ResourceStatus
from src.tasks import TofuManager, TOFU_BASE_DIR, STATE_BASE_DIR, _get_template_name

def main():
    if len(sys.argv) < 2:
        print("Usage: python src/show_creds.py <canary_name>")
        sys.exit(1)
        
    canary_name = sys.argv[1]
    
    db = SessionLocal()
    try:
        # Find the active canary
        canary = db.query(CanaryResource).filter(
            CanaryResource.name == canary_name,
            CanaryResource.status == ResourceStatus.ACTIVE
        ).first()
        
        if not canary:
            print(f"Canary '{canary_name}' not found or not active.")
            sys.exit(1)
            
        print(f"Checking credentials for {canary.name} (ID: {canary.id})...")
        print(f"Resource Type: {canary.resource_type.value}")
        print(f"Physical ID: {canary.current_resource_id}")
        
        # Init Tofu Manager
        template_name = _get_template_name(canary.resource_type)
        template_path = os.path.join(TOFU_BASE_DIR, template_name)
        work_dir = canary.tf_state_path
        
        if not work_dir or not os.path.exists(work_dir):
             print(f"State directory not found at {work_dir}")
             sys.exit(1)

        manager = TofuManager(template_path, work_dir)
        
        # Get Outputs
        try:
            outputs = manager.output()
            print("\n----- CREDENTIALS -----")
            print(json.dumps(outputs, indent=2))
            
            # Helper for copy-paste
            if "access_key_id" in outputs and "secret_access_key" in outputs:
                 print("\nCommand to configure AWS CLI:")
                 ak = outputs["access_key_id"]["value"]
                 sk = outputs["secret_access_key"]["value"]
                 print(f"aws configure set aws_access_key_id {ak} --profile canary-test")
                 print(f"aws configure set aws_secret_access_key {sk} --profile canary-test")
                 print("aws configure set region us-east-1 --profile canary-test")
                 
                 print("\nTest Command:")
                 print("aws sts get-caller-identity --profile canary-test")
                 
        except Exception as e:
            print(f"Error reading outputs: {e}")

    finally:
        db.close()

if __name__ == "__main__":
    main()

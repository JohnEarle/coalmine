import sys
import os
sys.path.append(os.getcwd())
from src.models import SessionLocal, CanaryResource, ResourceStatus
from src.tofu_manager import TofuManager
from src.tasks import _get_template_name, _build_env_vars, TOFU_BASE_DIR

def delete_resource(name_or_id):
    db = SessionLocal()
    try:
        # Check if UUID
        try:
             import uuid
             uuid_obj = uuid.UUID(name_or_id)
             canary = db.query(CanaryResource).filter(CanaryResource.id == uuid_obj).first()
        except ValueError:
             canary = db.query(CanaryResource).filter(CanaryResource.name == name_or_id).first()
             
        if not canary:
            print(f"Resource {name_or_id} not found.")
            return

        if canary.status == ResourceStatus.DELETED:
            print(f"Resource {canary.name} is already DELETED.")
            return

        print(f"Deleting {canary.name} ({canary.id})...")
        
        # Init Tofu
        manager = TofuManager(
            os.path.join(TOFU_BASE_DIR, _get_template_name(canary.resource_type)), 
            canary.tf_state_path
        )
        
        env_obj = canary.environment
        exec_env = _build_env_vars(env_obj)
        manager.init(env=exec_env)
        
        # Destroy
        print("Running Tofu Destroy...")
        
        # Check if we need to pass vars. Tofu destroy typically uses state, but if vars are required validation might fail if not passed.
        # Let's pass the same vars we stored? 
        vars_dict = {}
        if canary.resource_type.value == "AWS_IAM_USER":
             vars_dict["user_name"] = canary.current_resource_id
        elif canary.resource_type.value == "AWS_CENTRAL_TRAIL":
             vars_dict["name"] = canary.current_resource_id
        else:
             vars_dict["bucket_name"] = canary.current_resource_id
        
        if canary.module_params:
             vars_dict.update(canary.module_params)
        
        # Cleanup legacy/logic-only vars that are not in the template anymore
        if "ct_id" in vars_dict:
             del vars_dict["ct_id"]
        if "create_trail" in vars_dict:
             del vars_dict["create_trail"]
             
        print(f"DEBUG: resource_type={canary.resource_type}, current_resource_id={canary.current_resource_id}")
        print(f"DEBUG: Calling destroy with vars_dict: {vars_dict}")

        manager.destroy(vars_dict, env=exec_env)

        canary.status = ResourceStatus.DELETED
        db.commit()
        print(f"Successfully deleted {canary.name}.")
        
    except Exception as e:
        print(f"Error deleting {name_or_id}: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python scripts/delete_resource.py <logic_name>")
    else:
        delete_resource(sys.argv[1])

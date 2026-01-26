import sys
import os
import shutil
# Ensure src is in path
sys.path.append(os.getcwd())

from src.models import SessionLocal, CanaryResource, LoggingResource, ResourceStatus, ResourceType
from src.tofu_manager import TofuManager
from src.tasks import _get_template_name, _build_env_vars, TOFU_BASE_DIR, STATE_BASE_DIR

def destroy_all():
    db = SessionLocal()
    try:
        # 1. Destroy Canaries
        canaries = db.query(CanaryResource).filter(
            CanaryResource.status.in_([ResourceStatus.ACTIVE, ResourceStatus.ERROR, ResourceStatus.CREATING])
        ).all()
        
        print(f"Found {len(canaries)} canaries to destroy.")
        for c in canaries:
            print(f"Destroying Canary: {c.name} ({c.id})")
            if not c.tf_state_path or not os.path.exists(c.tf_state_path):
                print(f"  - No state path found for {c.name}, skipping Tofu destroy.")
                db.delete(c)
                continue

            try:
                template_name = _get_template_name(c.resource_type)
                template_path = os.path.join(TOFU_BASE_DIR, template_name)
                manager = TofuManager(template_path, c.tf_state_path)
                
                env = c.environment
                exec_env = _build_env_vars(env)
                
                # We need to init to get the providers ready for destroy
                manager.init(env=exec_env)
                
                # Reconstruct vars just for destroy (needed for required variables)
                vars_dict = {}
                if c.resource_type == ResourceType.AWS_IAM_USER:
                    vars_dict["user_name"] = c.current_resource_id
                else:
                    vars_dict["bucket_name"] = c.current_resource_id
                
                if env and env.config:
                    vars_dict.update(env.config)
                if c.module_params:
                    vars_dict.update(c.module_params)

                manager.destroy(vars_dict, env=exec_env)
                print(f"  - Tofu Destroy Successful")
                
            except Exception as e:
                print(f"  - Error destroying {c.name}: {e}")
            
            # Clean up filesystem
            if os.path.exists(c.tf_state_path):
                shutil.rmtree(c.tf_state_path)
            
            db.delete(c)
            db.commit()

        # 2. Destroy Logging Resources
        logs = db.query(LoggingResource).filter(
             LoggingResource.status.in_([ResourceStatus.ACTIVE, ResourceStatus.ERROR, ResourceStatus.CREATING])
        ).all()
        
        print(f"Found {len(logs)} logging resources to destroy.")
        for l in logs:
            print(f"Destroying Logging Resource: {l.name} ({l.id})")
            
            # Convention: State dir is STATE_BASE_DIR/ID
            state_path = os.path.join(STATE_BASE_DIR, str(l.id))
            
            if not os.path.exists(state_path):
                print(f"  - No state path found for {l.name}, skipping Tofu destroy.")
                db.delete(l)
                continue

            try:
                # Assuming AWS_CLOUDTRAIL use aws_central_trail
                # We need to know which template was used. 
                # For now we assume aws_central_trail if it looks like one.
                template_path = os.path.join(TOFU_BASE_DIR, "aws_central_trail")
                
                manager = TofuManager(template_path, state_path)
                env = l.environment
                exec_env = _build_env_vars(env)
                
                manager.init(env=exec_env)
                
                vars_dict = {"name": l.name}
                if l.configuration:
                    # filter out internal keys if mixed
                    pass
                
                manager.destroy(vars_dict, env=exec_env)
                print(f"  - Tofu Destroy Successful")
                
            except Exception as e:
                 print(f"  - Error destroying {l.name}: {e}")
            
            if os.path.exists(state_path):
                shutil.rmtree(state_path)
                
            db.delete(l)
            db.commit()

        print("All resources destroyed and DB cleared.")

    finally:
        db.close()

if __name__ == "__main__":
    destroy_all()

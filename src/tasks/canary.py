"""
Canary lifecycle management tasks - create, rotate, and auto-rotation checks.
"""
from ..celery_app import celery_app
from ..models import (
    SessionLocal, CanaryResource, ResourceHistory, ResourceType, 
    ResourceStatus, ActionType, CloudEnvironment, LoggingResource, LoggingProviderType
)
from ..tofu_manager import TofuManager
from ..logging_config import get_logger
from .helpers import (
    TOFU_BASE_DIR, STATE_BASE_DIR,
    _build_env_vars, _get_template_name, _get_backend_config
)
from ..resources.registry import ResourceRegistry
import uuid
import datetime
import os

logger = get_logger(__name__)


@celery_app.task(
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=300,
    max_retries=3
)
def create_canary(name: str, resource_type_str: str, interval_seconds: int = 86400, 
                  environment_id_str: str = None, module_params: dict = None, 
                  logging_resource_id_str: str = None):
    """
    Create a new canary resource with ACID-compliant transaction handling.
    
    Guarantees:
    - Single atomic commit on success
    - Cloud resource cleanup on failure (compensating transaction)
    - No orphaned resources
    """
    db = SessionLocal()
    manager = None
    vars_dict = {}
    exec_env = {}
    cloud_resource_created = False
    
    try:
        resource_type = ResourceType(resource_type_str)
        env_obj = None
        if environment_id_str:
            env_obj = db.query(CloudEnvironment).filter(CloudEnvironment.id == uuid.UUID(environment_id_str)).first()
            if not env_obj:
                raise ValueError(f"Environment {environment_id_str} not found")
            if "AWS" in resource_type.value and env_obj.provider_type != "AWS":
                raise ValueError("Env provider mismatch")
            if "GCP" in resource_type.value and env_obj.provider_type != "GCP":
                raise ValueError("Env provider mismatch")
        
        # Logging Resource Lookup
        log_res = None
        if logging_resource_id_str:
            log_res = db.query(LoggingResource).filter(LoggingResource.id == uuid.UUID(logging_resource_id_str)).first()
            if not log_res:
                raise ValueError(f"Logging Resource {logging_resource_id_str} not found")

        # For AWS Buckets, enforce Logging Resource
        if resource_type == ResourceType.AWS_BUCKET and not log_res:
            raise ValueError("AWS_BUCKET requires a valid logging_resource_id.")

        if interval_seconds > 0:
            timestamp_suffix = datetime.datetime.utcnow().strftime("%Y%m%d%H%M")
            physical_name = f"{name}-{timestamp_suffix}"
            expires_at = datetime.datetime.utcnow() + datetime.timedelta(seconds=interval_seconds)
        else:
            physical_name = name
            expires_at = None

        # Create record in CREATING status (not committed yet)
        canary = CanaryResource(
            name=name,
            resource_type=resource_type,
            environment_id=env_obj.id if env_obj else None,
            logging_resource_id=log_res.id if log_res else None,
            current_resource_id=physical_name,
            module_params=module_params,
            interval_seconds=interval_seconds,
            status=ResourceStatus.CREATING,
            created_at=datetime.datetime.utcnow(),
            expires_at=expires_at
        )
        db.add(canary)
        db.flush()  # Get ID without committing

        # Setup Tofu
        template_name = _get_template_name(resource_type)
        template_path = os.path.join(TOFU_BASE_DIR, template_name)
        work_dir = os.path.join(STATE_BASE_DIR, str(canary.id))
        canary.tf_state_path = work_dir

        manager = TofuManager(template_path, work_dir)
        exec_env = _build_env_vars(env_obj)
        
        # Debug: Log credential presence (not values!)
        if env_obj:
            logger.info(f"Environment '{env_obj.name}' (provider: {env_obj.provider_type}) loaded")
            cred_keys = list((env_obj.credentials or {}).keys())
            logger.info(f"Credential keys available: {cred_keys}")
            env_keys_set = [k for k in exec_env.keys() if k.startswith("AWS_") or k.startswith("GOOGLE_")]
            logger.info(f"Env vars set for Tofu: {env_keys_set}")
        else:
            logger.warning("No environment object provided - using ambient credentials")
        
        backend_config = _get_backend_config(str(canary.id))
        manager.init(env=exec_env, backend_config=backend_config)
        
        # Build variables
        # Build variables using EventHandler
        handler = ResourceRegistry.get_handler(resource_type)
        
        # Prepare merged config for handler (variable resolution)
        env_conf = env_obj.config.copy() if (env_obj and env_obj.config) else {}
        if env_obj and env_obj.credentials and "project_id" in env_obj.credentials and "project_id" not in env_conf:
             env_conf["project_id"] = env_obj.credentials["project_id"]

        vars_dict = handler.get_tform_vars(physical_name, env_conf, module_params)
        
        # Only merge allowed global vars from env config (region, tags)
        # to avoid passing undeclared variables to Tofu
        if env_obj and env_obj.config:
            allowed_global_vars = ['region', 'tags']
            for key in allowed_global_vars:
                if key in env_obj.config and key not in vars_dict:
                    vars_dict[key] = env_obj.config[key]

        # 1. Apply - Create cloud resource
        output = manager.apply(vars_dict, env=exec_env)
        cloud_resource_created = True  # Mark for cleanup on subsequent failures
        
        # 2. Get Outputs (Credentials)
        try:
            outputs_json = manager.output()
            creds = {}
            for k, v in outputs_json.items():
                creds[k] = v.get("value")
            canary.canary_credentials = creds
        except Exception as e:
            logger.warning(f"Failed to retrieve outputs for {name}: {e}")
        
        # 3. Verify with Plan (no drift)
        plan_code, plan_out = manager.plan(vars_dict, env=exec_env, detailed_exitcode=True)
        if plan_code != 0:
            raise Exception(f"Verification Failed. State does not match config. Tofu Plan ExitCode: {plan_code}")

        # 4. Register with logging infrastructure
        if log_res:
            handler.enable_logging(physical_name, log_res, env_obj)

        # 5. Record history
        history = ResourceHistory(
            resource_id=canary.id,
            action=ActionType.CREATE,
            details={"stdout": output, "physical_name": physical_name}
        )
        db.add(history)
        
        # 6. SUCCESS - Single atomic commit
        canary.status = ResourceStatus.ACTIVE
        db.commit()
        logger.info(f"Canary {name} created successfully and verified.")
        
    except Exception as e:
        logger.error(f"Error creating canary {name}: {e}")
        db.rollback()
        
        # Compensating Transaction: Cleanup cloud resource if created
        if cloud_resource_created and manager:
            try:
                logger.info(f"Attempting cleanup of cloud resource for {name}...")
                manager.destroy(vars_dict, env=exec_env)
                logger.info(f"Cleanup successful for {name}")
            except Exception as cleanup_err:
                logger.error(f"Cleanup FAILED for {name}: {cleanup_err}")
        
        # Record error in new transaction
        try:
            db_err = SessionLocal()
            err_canary = CanaryResource(
                name=name,
                resource_type=ResourceType(resource_type_str),
                status=ResourceStatus.ERROR,
                created_at=datetime.datetime.utcnow()
            )
            db_err.add(err_canary)
            db_err.flush()
            
            err_history = ResourceHistory(
                resource_id=err_canary.id, 
                action=ActionType.CREATE, 
                details={"error": str(e), "cleanup_attempted": cloud_resource_created}
            )
            db_err.add(err_history)
            db_err.commit()
            db_err.close()
        except Exception as record_err:
            logger.error(f"Failed to record error state: {record_err}")
        
        raise e

    finally:
        db.close()


@celery_app.task(
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=300,
    max_retries=3
)
def rotate_canary(resource_id_str: str, new_name: str = None):
    """
    Rotate an existing canary resource with ACID-compliant transaction handling.
    
    Guarantees:
    - Uses ROTATING intermediate status
    - Preserves old credentials until new rotation succeeds
    - Rolls back status on failure
    """
    db = SessionLocal()
    old_status = None
    old_resource_id = None
    old_credentials = None
    
    try:
        resource_id = uuid.UUID(resource_id_str)
        canary = db.query(CanaryResource).filter(CanaryResource.id == resource_id).first()
        
        if not canary:
            logger.warning(f"Canary {resource_id} not found.")
            return
        
        if canary.status != ResourceStatus.ACTIVE:
            logger.warning(f"Canary {resource_id} is not ACTIVE (status: {canary.status}). Skipping rotation.")
            return

        # Save old state for potential rollback
        old_status = canary.status
        old_resource_id = canary.current_resource_id
        old_credentials = canary.canary_credentials
        
        # Transition to ROTATING
        canary.status = ResourceStatus.ROTATING
        db.commit()
        
        logger.info(f"Rotating canary {canary.name}...")
        
        if new_name:
            new_physical_name = new_name
            canary.name = new_name
        else:
            timestamp_suffix = datetime.datetime.utcnow().strftime("%Y%m%d%H%M")
            base_name = canary.name 
            new_physical_name = f"{base_name}-{timestamp_suffix}"
        
        manager = TofuManager(
            os.path.join(TOFU_BASE_DIR, _get_template_name(canary.resource_type)), 
            canary.tf_state_path
        )
        
        env_obj = canary.environment
        exec_env = _build_env_vars(env_obj)
        
        backend_config = _get_backend_config(str(canary.id))
        manager.init(env=exec_env, backend_config=backend_config)

        handler = ResourceRegistry.get_handler(canary.resource_type)
        env_conf = env_obj.config.copy() if (env_obj and env_obj.config) else {}
        if env_obj and env_obj.credentials and "project_id" in env_obj.credentials and "project_id" not in env_conf:
             env_conf["project_id"] = env_obj.credentials["project_id"]

        vars_dict = handler.get_tform_vars(new_physical_name, env_conf, canary.module_params)
        
        # Only merge allowed global vars from env config (region, tags)
        if env_obj and env_obj.config:
            allowed_global_vars = ['region', 'tags']
            for key in allowed_global_vars:
                if key in env_obj.config and key not in vars_dict:
                    vars_dict[key] = env_obj.config[key]
        
        output = manager.apply(vars_dict, env=exec_env)
        
        # Get Outputs (for Creds)
        try:
            outputs_json = manager.output()
            creds = {}
            for k, v in outputs_json.items():
                creds[k] = v.get("value")
            canary.canary_credentials = creds
        except Exception as e:
            logger.warning(f"Failed to retrieve outputs for {canary.name}: {e}")

        canary.current_resource_id = new_physical_name
        canary.expires_at = datetime.datetime.utcnow() + datetime.timedelta(seconds=canary.interval_seconds)
        
        history = ResourceHistory(
            resource_id=canary.id,
            action=ActionType.ROTATE,
            details={"stdout": output, "old_physical_name": old_resource_id, "new_physical_name": new_physical_name}
        )
        db.add(history)
        
        # Dynamic Trail Registration (Rotation)
        if canary.logging_resource:
            log_res = canary.logging_resource
            handler.disable_logging(old_resource_id, log_res, env_obj)
            handler.enable_logging(new_physical_name, log_res, env_obj)

        # SUCCESS - Transition back to ACTIVE
        canary.status = ResourceStatus.ACTIVE
        db.commit()
        logger.info(f"Canary {canary.name} rotated to {new_physical_name}")

    except Exception as e:
        logger.error(f"Error rotating canary: {e}")
        
        # Rollback to previous state
        try:
            db.rollback()
            canary = db.query(CanaryResource).filter(CanaryResource.id == uuid.UUID(resource_id_str)).first()
            if canary and old_status:
                canary.status = old_status
                # Preserve old credentials and resource_id since rotation failed
                if old_credentials:
                    canary.canary_credentials = old_credentials
                if old_resource_id:
                    canary.current_resource_id = old_resource_id
                    
                err_history = ResourceHistory(
                    resource_id=canary.id,
                    action=ActionType.ROTATE,
                    details={"error": str(e), "rollback": True}
                )
                db.add(err_history)
                db.commit()
        except Exception as rollback_err:
            logger.error(f"Rollback failed: {rollback_err}")
        
        raise e
    finally:
        db.close()


@celery_app.task
def check_rotations():
    """Check for expired canaries and trigger rotation."""
    db = SessionLocal()
    try:
        now = datetime.datetime.utcnow()
        expired_canaries = db.query(CanaryResource).filter(
            CanaryResource.status == ResourceStatus.ACTIVE,
            CanaryResource.expires_at <= now
        ).all()
        
        for canary in expired_canaries:
            logger.info(f"Triggering rotation for {canary.id} (expired {canary.expires_at})")
            rotate_canary.delay(str(canary.id))
            
    finally:
        db.close()


@celery_app.task(
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=300,
    max_retries=3
)
def delete_canary(resource_id_str: str):
    """
    Delete a canary resource with ACID-compliant transaction handling.
    """
    import uuid
    db = SessionLocal()
    resource_id = None
    try:
        resource_id = uuid.UUID(resource_id_str)
        canary = db.query(CanaryResource).filter(CanaryResource.id == resource_id).first()
        
        if not canary:
            logger.warning(f"Canary {resource_id} not found.")
            return

        if canary.status == ResourceStatus.DELETED:
            logger.info(f"Canary {canary.id} already DELETED.")
            return

        # Transition to DELETING
        canary.status = ResourceStatus.DELETING
        db.commit()
        
        logger.info(f"Deleting canary {canary.id} ({canary.name})...")
        
        # Setup Tofu
        template_name = _get_template_name(canary.resource_type)
        template_path = os.path.join(TOFU_BASE_DIR, template_name)
        env_obj = canary.environment
        work_dir = canary.tf_state_path
        
        manager = None
        if work_dir and os.path.exists(work_dir):
            manager = TofuManager(template_path, work_dir)
            exec_env = _build_env_vars(env_obj)
            
            backend_config = _get_backend_config(str(canary.id))
            manager.init(env=exec_env, backend_config=backend_config)
        else:
            logger.warning(f"No state path found for {canary.id}. Skipping Tofu destroy.")
        
        # Build variables using Handler
        handler = ResourceRegistry.get_handler(canary.resource_type)
        env_conf = env_obj.config.copy() if (env_obj and env_obj.config) else {}
        if env_obj and env_obj.credentials and "project_id" in env_obj.credentials and "project_id" not in env_conf:
             env_conf["project_id"] = env_obj.credentials["project_id"]

        vars_dict = handler.get_tform_vars(canary.current_resource_id, env_conf, canary.module_params)
        
        # Only merge allowed global vars from env config (region, tags)
        if env_obj and env_obj.config:
            allowed_global_vars = ['region', 'tags']
            for key in allowed_global_vars:
                if key in env_obj.config and key not in vars_dict:
                    vars_dict[key] = env_obj.config[key]

        # 1. Unregister from logging if necessary
        from .logging import _update_trail_selectors, _update_gcp_sink_filter
        from ..models import LoggingProviderType
        
        if canary.logging_resource:
            handler.disable_logging(canary.current_resource_id, canary.logging_resource, env_obj)

        # 2. Run Tofu Destroy
        if manager:
            manager.destroy(vars_dict, env=exec_env)
        
        # 3. Success - Set status to DELETED
        canary.status = ResourceStatus.DELETED
        
        from ..models import ActionType, ResourceHistory
        history = ResourceHistory(
            resource_id=canary.id,
            action=ActionType.DELETE,
            details={"status": "success"}
        )
        db.add(history)
        db.commit()
        logger.info(f"Canary {canary.id} deleted successfully.")
        
    except Exception as e:
        logger.error(f"Error deleting canary {resource_id_str}: {e}")
        db.rollback()
        
        # Move to ERROR status
        try:
            canary = db.query(CanaryResource).filter(CanaryResource.id == resource_id).first()
            if canary:
                canary.status = ResourceStatus.ERROR
                from ..models import ActionType, ResourceHistory
                history = ResourceHistory(
                    resource_id=canary.id,
                    action=ActionType.DELETE,
                    details={"error": str(e)}
                )
                db.add(history)
                db.commit()
        except:
            pass
        raise e
    finally:
        db.close()


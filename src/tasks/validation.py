"""
Resource validation task - checks for drift and errors.
"""
from ..celery_app import celery_app
from ..models import (
    SessionLocal, CanaryResource, LoggingResource, ResourceHistory,
    ResourceStatus, ActionType, ResourceType, LoggingProviderType
)
from ..tofu_manager import TofuManager
from ..logging_config import get_logger
from .helpers import (
    TOFU_BASE_DIR, STATE_BASE_DIR,
    _build_env_vars, _get_template_name, _get_backend_config
)
import os

logger = get_logger(__name__)


@celery_app.task
def validate_resources():
    """
    Periodically checks ACTIVE resources for drift or errors.
    Runs `tofu plan` without changes.
    """
    db = SessionLocal()
    try:
        # Check Canaries
        canaries = db.query(CanaryResource).filter(
            CanaryResource.status == ResourceStatus.ACTIVE
        ).all()
        
        for canary in canaries:
            try:
                template_name = _get_template_name(canary.resource_type)
                template_path = os.path.join(TOFU_BASE_DIR, template_name)
                manager = TofuManager(template_path, canary.tf_state_path)
                
                env = canary.environment
                exec_env = _build_env_vars(env)
                
                backend_config = _get_backend_config(str(canary.id))
                manager.init(env=exec_env, backend_config=backend_config)
                
                vars_dict = {}
                if canary.resource_type == ResourceType.AWS_IAM_USER:
                    vars_dict["user_name"] = canary.current_resource_id
                else:
                    vars_dict["bucket_name"] = canary.current_resource_id
                
                if env and env.config:
                    vars_dict.update(env.config)
                if canary.module_params:
                    vars_dict.update(canary.module_params)
                    
                logger.info(f"Validating Canary {canary.name} ({canary.id})...")
                code, out = manager.plan(vars_dict, env=exec_env, detailed_exitcode=True)
                
                if code != 0:
                     logger.warning(f"Drift detected for {canary.name}. Exit Code: {code}")
                     canary.status = ResourceStatus.DRIFT
                     history = ResourceHistory(
                        resource_id=canary.id,
                        action=ActionType.ALERT,
                        details={"warning": f"Drift detected. Tofu ExitCode: {code}", "stdout": out}
                     )
                     db.add(history)
                     db.commit()
                else:
                    logger.info(f"Canary {canary.name} is healthy.")

            except Exception as e:
                logger.error(f"Error validating canary {canary.name}: {e}")
                
        # Check Logging Resources
        logs = db.query(LoggingResource).filter(
            LoggingResource.status == ResourceStatus.ACTIVE
        ).all()
        
        for log in logs:
            try:
                if log.provider_type != LoggingProviderType.AWS_CLOUDTRAIL:
                    continue
                    
                template_path = os.path.join(TOFU_BASE_DIR, "aws_central_trail")
                work_dir = os.path.join(STATE_BASE_DIR, str(log.id))
                
                manager = TofuManager(template_path, work_dir)
                env = log.environment
                exec_env = _build_env_vars(env)
                
                backend_config = _get_backend_config(str(log.id))
                manager.init(env=exec_env, backend_config=backend_config)
                
                vars_dict = {"name": log.name}
                if log.configuration:
                     for k,v in log.configuration.items():
                         if k not in ["trail_name", "tofu_output"]:
                             vars_dict[k] = v
                
                logger.info(f"Validating Log {log.name} ({log.id})...")
                code, out = manager.plan(vars_dict, env=exec_env, detailed_exitcode=True)
                
                if code != 0:
                     logger.warning(f"Drift/Error detected for {log.name}. Exit Code: {code}")
                     log.status = ResourceStatus.ERROR
                     db.commit()
                else:
                    logger.info(f"Log {log.name} is healthy.")
                    
            except Exception as e:
                logger.error(f"Error validating log {log.name}: {e}")

    finally:
        db.close()

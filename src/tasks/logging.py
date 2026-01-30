"""
Logging resource management tasks - CloudTrail and GCP Audit Sink.
"""
from ..celery_app import celery_app
from ..models import (
    SessionLocal, LoggingResource, LoggingProviderType, 
    ResourceStatus, CloudEnvironment, ResourceType, ActionType
)
from ..tofu_manager import TofuManager
from ..logging_config import get_logger
from .helpers import (
    TOFU_BASE_DIR, STATE_BASE_DIR, 
    _get_execution_env, _get_backend_config
)
from .lifecycle import ResourceLifecycleManager
from ..logging_utils import _update_trail_selectors, _update_gcp_sink_filter
import os
import json

logger = get_logger(__name__)






@celery_app.task
def create_logging_resource(name: str, provider_type_str: str, environment_id_str: str, config: dict = None):
    """
    Create a logging resource (CloudTrail or GCP Audit Sink).
    
    Guarantees:
    - Single atomic commit on success
    - Cloud resource cleanup on failure (compensating transaction)
    """
    import uuid
    with ResourceLifecycleManager(action_type=ActionType.CREATE) as ctx:
        provider_type = LoggingProviderType(provider_type_str)
        env_obj = ctx.db.query(CloudEnvironment).filter(CloudEnvironment.id == uuid.UUID(environment_id_str)).first()
        if not env_obj:
            raise ValueError(f"Environment {environment_id_str} not found")

        # Create Record in CREATING state
        log_res = LoggingResource(
            name=name,
            provider_type=provider_type,
            environment_id=env_obj.id,
            configuration=config or {},
            status=ResourceStatus.CREATING
        )
        ctx.db.add(log_res)
        ctx.db.flush()
        log_res_id = log_res.id
        ctx.resource = log_res

        # Unified Logic using ResourceRegistry
        from ..resources.registry import ResourceRegistry
        handler = ResourceRegistry.get_handler(provider_type)
        
        template_name = _get_template_name(provider_type)
        exec_env = _get_execution_env(env_obj)
        
        ctx.init_tofu(template_name, exec_env)
        
        # Prepare Environment Config (Project ID, etc)
        env_conf = env_obj.config.copy() if (env_obj and env_obj.config) else {}
        if env_obj and env_obj.credentials and "project_id" in env_obj.credentials and "project_id" not in env_conf:
                env_conf["project_id"] = env_obj.credentials["project_id"]

        # Ensure project_id is passed if available in environment (Env Var fallback)
        if "project_id" not in env_conf and "GOOGLE_CLOUD_PROJECT" in exec_env:
                env_conf["project_id"] = exec_env["GOOGLE_CLOUD_PROJECT"]

        vars_dict = handler.get_tform_vars(name, env_conf, config or {})
        
        output = ctx.apply(vars_dict)
        
        # Capture Outputs and update configuration
        try:
            outputs_json = ctx.manager.output()
            current_conf = dict(log_res.configuration) if log_res.configuration else {}
            
            # Merge outputs into config
            for k, v in outputs_json.items():
                current_conf[k] = v.get("value")
            
            # Store Tofu stdout
            current_conf["tofu_output"] = output
            
            # Additional CloudTrail specific field (legacy support)
            if provider_type == LoggingProviderType.AWS_CLOUDTRAIL:
                current_conf["trail_name"] = name
                
            log_res.configuration = current_conf
        except Exception as e:
            logger.warning(f"Failed to retrieve outputs for {name}: {e}")

        ctx.verify_plan()
                
        log_res.status = ResourceStatus.ACTIVE
        logger.info(f"Logging Resource {name} created and verified.")
        
        # ctx exit will commit

"""
Logging resource management tasks - CloudTrail and GCP Audit Sink.
"""
from ..celery_app import celery_app
from ..models import (
    SessionLocal, LoggingResource, LoggingProviderType, 
    ResourceStatus, Account, ResourceType, ActionType
)
from ..tofu_manager import TofuManager
from ..logging_config import get_logger
from .helpers import (
    TOFU_BASE_DIR, STATE_BASE_DIR, 
    _get_execution_env, _get_backend_config,
    _get_template_name
)
from .lifecycle import ResourceLifecycleManager
from ..logging_utils import _update_trail_selectors, _update_gcp_sink_filter
import os
import json

logger = get_logger(__name__)




@celery_app.task
def create_logging_resource(name: str, provider_type_str: str, account_id_str: str, config: dict = None):
    """
    Create a logging resource (CloudTrail or GCP Audit Sink).
    
    Guarantees:
    - Single atomic commit on success
    - Cloud resource cleanup on failure (compensating transaction)
    """
    import uuid
    with ResourceLifecycleManager(action_type=ActionType.CREATE) as ctx:
        provider_type = LoggingProviderType(provider_type_str)
        account_obj = ctx.db.query(Account).filter(Account.id == uuid.UUID(account_id_str)).first()
        if not account_obj:
            raise ValueError(f"Account {account_id_str} not found")

        # Create Record in CREATING state
        log_res = LoggingResource(
            name=name,
            provider_type=provider_type,
            account_id=account_obj.id,
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
        exec_env = _get_execution_env(account_obj)
        
        ctx.init_tofu(template_name, exec_env)
        
        # Prepare Account Config (Project ID, etc)
        cred = account_obj.credential
        env_conf = {}
        if cred and cred.secrets:
            if "project_id" in cred.secrets:
                env_conf["project_id"] = cred.secrets["project_id"]

        # Use account_id as project_id for GCP if not set
        if "project_id" not in env_conf and account_obj.account_id:
            env_conf["project_id"] = account_obj.account_id

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


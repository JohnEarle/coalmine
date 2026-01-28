"""
Logging resource management tasks - CloudTrail and GCP Audit Sink.
"""
from ..celery_app import celery_app
from ..models import (
    SessionLocal, LoggingResource, LoggingProviderType, 
    ResourceStatus, CloudEnvironment, ResourceType
)
from ..tofu_manager import TofuManager
from ..logging_config import get_logger
from .helpers import (
    TOFU_BASE_DIR, STATE_BASE_DIR, 
    _build_env_vars, _get_backend_config
)
from ..logging_utils import _update_trail_selectors, _update_gcp_sink_filter
import os
import json

logger = get_logger(__name__)






@celery_app.task
def create_logging_resource(name: str, provider_type_str: str, environment_id_str: str, config: dict = None):
    """Create a logging resource (CloudTrail or GCP Audit Sink)."""
    import uuid
    db = SessionLocal()
    try:
        provider_type = LoggingProviderType(provider_type_str)
        env_obj = db.query(CloudEnvironment).filter(CloudEnvironment.id == uuid.UUID(environment_id_str)).first()
        if not env_obj:
            raise ValueError(f"Environment {environment_id_str} not found")

        # Create Record
        log_res = LoggingResource(
            name=name,
            provider_type=provider_type,
            environment_id=env_obj.id,
            configuration=config or {},
            status=ResourceStatus.CREATING
        )
        db.add(log_res)
        db.commit()
        db.refresh(log_res)

        if provider_type == LoggingProviderType.AWS_CLOUDTRAIL:
            template_path = os.path.join(TOFU_BASE_DIR, "aws_central_trail")
            work_dir = os.path.join(STATE_BASE_DIR, str(log_res.id))
            
            manager = TofuManager(template_path, work_dir)
            exec_env = _build_env_vars(env_obj)
            
            backend_config = _get_backend_config(str(log_res.id))
            manager.init(env=exec_env, backend_config=backend_config)
            
            vars_dict = {"name": name}
            # Only merge allowed Tofu variables from config
            # Other config values are stored as metadata but not passed to Tofu
            if config:
                allowed_vars = ['region', 'tags', 'resource_prefix']
                for key in allowed_vars:
                    if key in config:
                        vars_dict[key] = config[key]
            
            output = manager.apply(vars_dict, env=exec_env)
            
            # Explicitly create a copy to ensure SQLAlchemy detects change
            conf = dict(log_res.configuration)
            conf["trail_name"] = name
            conf["tofu_output"] = output
            log_res.configuration = conf
            
            plan_code, plan_out = manager.plan(vars_dict, env=exec_env, detailed_exitcode=True)
            if plan_code != 0:
                 raise Exception(f"Verification Failed for Logging Resource. Tofu Plan ExitCode: {plan_code}")
                 
            log_res.status = ResourceStatus.ACTIVE
            db.commit()
            logger.info(f"Logging Resource {name} created and verified.")

        elif provider_type == LoggingProviderType.GCP_AUDIT_SINK:
            template_path = os.path.join(TOFU_BASE_DIR, "gcp_audit_sink")
            work_dir = os.path.join(STATE_BASE_DIR, str(log_res.id))
            
            manager = TofuManager(template_path, work_dir)
            exec_env = _build_env_vars(env_obj)
            
            backend_config = _get_backend_config(str(log_res.id))
            manager.init(env=exec_env, backend_config=backend_config)
            
            vars_dict = {"name": name}
            if env_obj.config and "project_id" in env_obj.config:
                 vars_dict["project_id"] = env_obj.config["project_id"]
            if env_obj.credentials and "project_id" in env_obj.credentials:
                 vars_dict["project_id"] = env_obj.credentials["project_id"]
            
            if config:
                # GCP sink only accepts project_id (name is already set)
                if 'project_id' in config:
                    vars_dict['project_id'] = config['project_id']

            if "project_id" not in vars_dict:
                 raise ValueError("project_id must be provided in env config or credentials for GCP_AUDIT_SINK")

            output = manager.apply(vars_dict, env=exec_env)
            
            # Explicitly create a copy to ensure SQLAlchemy detects change
            conf = dict(log_res.configuration)
            outputs_json = manager.output()
            for k, v in outputs_json.items():
                 conf[k] = v.get("value")
            
            conf["tofu_output"] = output
            log_res.configuration = conf
            
            plan_code, plan_out = manager.plan(vars_dict, env=exec_env, detailed_exitcode=True)
            if plan_code != 0:
                 raise Exception(f"Verification Failed for GCP Sink. Tofu Plan ExitCode: {plan_code}")
                 
            log_res.status = ResourceStatus.ACTIVE
            db.commit()
            logger.info(f"Logging Resource {name} (GCP Sink) created and verified.")

        else:
            log_res.status = ResourceStatus.ACTIVE
            db.commit()

    except Exception as e:
        logger.error(f"Error creating logging resource: {e}")
        db.rollback()
        log_res.status = ResourceStatus.ERROR
        db.commit()
        raise e
    finally:
        db.close()

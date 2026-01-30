from typing import Tuple
from .base import HealthCheck
from ..models import CanaryResource, ResourceType
from ..tasks.helpers import (
    TOFU_BASE_DIR, 
    _build_env_vars, _get_template_name, _get_backend_config
)
from ..tofu_manager import TofuManager
import os

class CanaryHealthCheck(HealthCheck):
    """Checks health (drift status) of canary resources using Tofu."""

    def check(self, resource: CanaryResource) -> Tuple[bool, str]:
        try:
            template_name = _get_template_name(resource.resource_type)
            template_path = os.path.join(TOFU_BASE_DIR, template_name)
            manager = TofuManager(template_path, resource.tf_state_path)
            
            env = resource.environment
            exec_env = _build_env_vars(env)
            
            backend_config = _get_backend_config(str(resource.id))
            manager.init(env=exec_env, backend_config=backend_config)
            
            # Use the Registry/Handlers to generate authoritative variables
            from ..resources.registry import ResourceRegistry
            handler = ResourceRegistry.get_handler(resource.resource_type)
            
            # Prepare merged config (Project ID Logic)
            env_conf = env.config.copy() if (env and env.config) else {}
            if env and env.credentials and "project_id" in env.credentials and "project_id" not in env_conf:
                 env_conf["project_id"] = env.credentials["project_id"]

            # Ensure project_id is passed if available in environment
            if "project_id" not in env_conf and "GOOGLE_CLOUD_PROJECT" in exec_env:
                 env_conf["project_id"] = exec_env["GOOGLE_CLOUD_PROJECT"]

            # Generate variables
            vars_dict = handler.get_tform_vars(resource.current_resource_id, env_conf, resource.module_params)
            
            # Only merge allowed global vars from env config (region, tags)
            if env and env.config:
                allowed_global_vars = ['region', 'tags']
                for key in allowed_global_vars:
                    if key in env.config and key not in vars_dict:
                        vars_dict[key] = env.config[key]
                
            code, out = manager.plan(vars_dict, env=exec_env, detailed_exitcode=True)
            
            if code == 0:
                return True, "Resource is in sync."
            elif code == 2:
                return False, f"Drift detected (Tofu Exit Code 2). Stdout: {out}"
            else:
                return False, f"Tofu Plan Error (Exit Code {code}): {out}"

        except Exception as e:
            return False, f"Validation Exception: {e}"

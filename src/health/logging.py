from typing import Tuple
from .base import HealthCheck
from ..models import LoggingResource, LoggingProviderType
from ..tasks.helpers import (
    TOFU_BASE_DIR, STATE_BASE_DIR,
    _build_env_vars, _get_backend_config
)
from ..tofu_manager import TofuManager
import os

class LoggingHealthCheck(HealthCheck):
    """Checks health (drift status) of logging resources using Tofu."""

    def check(self, resource: LoggingResource) -> Tuple[bool, str]:
        try:
            # Unified Logic using ResourceRegistry
            from ..resources.registry import ResourceRegistry
            from ..tasks.helpers import _get_template_name
            
            handler = ResourceRegistry.get_handler(resource.provider_type)
            template_dir = _get_template_name(resource.provider_type)
            
            template_path = os.path.join(TOFU_BASE_DIR, template_dir)
            work_dir = os.path.join(STATE_BASE_DIR, str(resource.id))
            
            manager = TofuManager(template_path, work_dir)
            env = resource.environment
            exec_env = _build_env_vars(env)
            
            backend_config = _get_backend_config(str(resource.id))
            manager.init(env=exec_env, backend_config=backend_config)
            
            # Prepare Environment Config (Project ID, etc)
            env_conf = env.config.copy() if (env and env.config) else {}
            if env and env.credentials and "project_id" in env.credentials and "project_id" not in env_conf:
                    env_conf["project_id"] = env.credentials["project_id"]

            # Ensure project_id is passed if available in environment (Env Var fallback)
            if "project_id" not in env_conf and "GOOGLE_CLOUD_PROJECT" in exec_env:
                    env_conf["project_id"] = exec_env["GOOGLE_CLOUD_PROJECT"]

            vars_dict = handler.get_tform_vars(resource.name, env_conf, resource.configuration or {})

            code, out = manager.plan(vars_dict, env=exec_env, detailed_exitcode=True)
            
            if code == 0:
                return True, "Resource is in sync."
            elif code == 2:
                return False, "Drift detected (Tofu Exit Code 2)"
            else:
                return False, f"Tofu Plan Error (Exit Code {code}): {out}"

        except Exception as e:
            return False, f"Validation Exception: {e}"

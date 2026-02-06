from typing import Tuple
from .base import HealthCheck
from ..models import CanaryResource, ResourceType
from ..tasks.helpers import (
    TOFU_BASE_DIR, 
    _get_execution_env, _get_template_name, _get_backend_config
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
            
            account = resource.account
            exec_env = _get_execution_env(account)
            
            backend_config = _get_backend_config(str(resource.id))
            manager.init(env=exec_env, backend_config=backend_config)
            
            # Use the Registry/Handlers to generate authoritative variables
            from ..resources.registry import ResourceRegistry
            handler = ResourceRegistry.get_handler(resource.resource_type)
            
            # Prepare Account Config (Project ID, etc)
            env_conf = {}
            if account:
                cred = account.credential
                if cred and cred.secrets and "project_id" in cred.secrets:
                    env_conf["project_id"] = cred.secrets["project_id"]
                # Use account_id as project_id for GCP if not set
                if "project_id" not in env_conf and account.account_id:
                    env_conf["project_id"] = account.account_id

            # Ensure project_id is passed if available in environment
            if "project_id" not in env_conf and "GOOGLE_CLOUD_PROJECT" in exec_env:
                 env_conf["project_id"] = exec_env["GOOGLE_CLOUD_PROJECT"]

            # Generate variables
            vars_dict = handler.get_tform_vars(resource.current_resource_id, env_conf, resource.module_params)
            
            code, out = manager.plan(vars_dict, env=exec_env, detailed_exitcode=True)
            
            if code == 0:
                return True, "Resource is in sync."
            elif code == 2:
                return False, f"Drift detected (Tofu Exit Code 2). Stdout: {out}"
            else:
                return False, f"Tofu Plan Error (Exit Code {code}): {out}"

        except Exception as e:
            return False, f"Validation Exception: {e}"


from typing import Tuple
from .base import HealthCheck
from ..models import LoggingResource, LoggingProviderType
from ..tofu_manager import TofuManager
import os


def _get_helpers():
    """Lazy import of task helpers to avoid circular dependency."""
    from ..tasks import helpers
    return helpers


class LoggingHealthCheck(HealthCheck):
    """Checks health (drift status) of logging resources using Tofu."""

    def check(self, resource: LoggingResource) -> Tuple[bool, str]:
        try:
            # Lazy imports to avoid circular dependency
            from ..resources.registry import ResourceRegistry
            from ..logging_utils import _get_canary_filters_for_logging
            helpers = _get_helpers()
            
            handler = ResourceRegistry.get_handler(resource.provider_type)
            template_dir = helpers._get_template_name(resource.provider_type)
            
            template_path = os.path.join(helpers.TOFU_BASE_DIR, template_dir)
            work_dir = os.path.join(helpers.STATE_BASE_DIR, str(resource.id))
            
            manager = TofuManager(template_path, work_dir)
            account = resource.account
            exec_env = helpers._get_execution_env(account)
            
            backend_config = helpers._get_backend_config(str(resource.id))
            manager.init(env=exec_env, backend_config=backend_config)
            
            # Prepare Account Config (Project ID, etc)
            env_conf = {}
            if account:
                cred = account.credential
                if cred and cred.secrets and "project_id" in cred.secrets:
                    env_conf["project_id"] = cred.secrets["project_id"]
                # Use account_id as project_id for GCP if not set
                if "project_id" not in env_conf and account.account_id:
                    env_conf["project_id"] = account.account_id

            # Ensure project_id is passed if available in environment (Env Var fallback)
            if "project_id" not in env_conf and "GOOGLE_CLOUD_PROJECT" in exec_env:
                    env_conf["project_id"] = exec_env["GOOGLE_CLOUD_PROJECT"]

            vars_dict = handler.get_tform_vars(resource.name, env_conf, resource.configuration or {})
            
            # Add canary filters for drift check - this ensures healthcheck includes
            # the same canary filters that would be applied, preventing false drift
            canary_filters = _get_canary_filters_for_logging(resource)
            if resource.provider_type == LoggingProviderType.GCP_AUDIT_SINK:
                vars_dict["canary_filters"] = canary_filters
            elif resource.provider_type == LoggingProviderType.AWS_CLOUDTRAIL:
                vars_dict["canary_arns"] = canary_filters

            code, out = manager.plan(vars_dict, env=exec_env, detailed_exitcode=True)
            
            if code == 0:
                return True, "Resource is in sync."
            elif code == 2:
                return False, "Drift detected (Tofu Exit Code 2)"
            else:
                return False, f"Tofu Plan Error (Exit Code {code}): {out}"

        except Exception as e:
            return False, f"Validation Exception: {e}"

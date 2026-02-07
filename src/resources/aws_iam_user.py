from typing import Dict, Any, Optional
from .base import ResourceManager

class AwsIamUserHandler(ResourceManager):
    def get_tform_vars(self, physical_id: str, env_config: Dict[str, Any], module_params: Dict[str, Any]) -> Dict[str, Any]:
        vars_dict = {"user_name": physical_id}
        if module_params:
            vars_dict.update(module_params)
        return vars_dict

    def validate(self, account: Any, module_params: Optional[Dict[str, Any]] = None, logging_resource: Optional[Any] = None) -> None:
        if not account or not account.credential or account.credential.provider != "AWS":
            raise ValueError("Account provider mismatch: Expected AWS")

from typing import Dict, Any
from .base import ResourceManager

class AwsIamUserHandler(ResourceManager):
    def get_tform_vars(self, physical_id: str, env_config: Dict[str, Any], module_params: Dict[str, Any]) -> Dict[str, Any]:
        vars_dict = {"user_name": physical_id}
        if module_params:
            vars_dict.update(module_params)
        return vars_dict

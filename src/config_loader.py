"""
Configuration loader for YAML-based resource and detection configs.

This module loads configuration from the config/ directory and provides
type-safe access to resource types, detection strategies, and cloud environments.

Environment variables can be used in YAML files with the following syntax:
  - ${VAR_NAME}           - Required, fails if not set
  - ${VAR_NAME:-default}  - Optional with default value
  - ${VAR_NAME:?error}    - Required with custom error message
"""
import os
import re
import yaml
from pathlib import Path
from typing import Dict, Any, Optional, Union
from .config_schemas import (
    ResourceTypesFile, ResourceTypeConfig, 
    DetectionsFile, DetectionConfig, 
    EnvironmentsFile, CloudEnvironmentConfig
)

# Config directory path
CONFIG_DIR = Path(os.getenv("CONFIG_DIR", "/app/config"))


def _load_yaml(filename: str) -> Dict[str, Any]:
    """Load a YAML file from the config directory."""
    filepath = CONFIG_DIR / filename
    if not filepath.exists():
        # Fallback to local config for development
        local_path = Path(__file__).parent.parent.parent / "config" / filename
        if local_path.exists():
            filepath = local_path
        else:
            return {}
    
    with open(filepath, 'r') as f:
        return yaml.safe_load(f) or {}


# Cached configs
_resource_types_cache: Optional[Dict[str, ResourceTypeConfig]] = None
_detections_cache: Optional[Dict[str, DetectionConfig]] = None
_alert_outputs_cache: Optional[Dict] = None

def get_alert_outputs() -> Dict[str, Dict]:
    """
    Get alert output configurations.
    Returns:
        Dict mapping output names to their config.
    """
    global _alert_outputs_cache
    if _alert_outputs_cache is None:
        config = _load_yaml("alert_outputs.yaml")
        _alert_outputs_cache = config.get("outputs") or {}
    return _alert_outputs_cache


def get_resource_types() -> Dict[str, ResourceTypeConfig]:
    """
    Get all resource type configurations.
    
    Returns:
        Dict mapping resource type names to their config.
    """
    global _resource_types_cache
    if _resource_types_cache is None:
        raw_config = _load_yaml("resource_types.yaml")
        # Validate with Pydantic
        # Note: ResourceTypesFile expects "resource_types" key
        if "resource_types" not in raw_config:
            raw_config = {"resource_types": {}}
            
        validated = ResourceTypesFile(**raw_config)
        _resource_types_cache = validated.resource_types
    return _resource_types_cache


def get_resource_type_config(resource_type: str) -> Optional[ResourceTypeConfig]:
    """Get configuration for a specific resource type."""
    return get_resource_types().get(resource_type)


def get_template_name(resource_type: str) -> str:
    """
    Get the Tofu template directory name for a resource type.
    
    Falls back to convention: AWS_BUCKET -> aws_bucket
    """
    config = get_resource_type_config(resource_type)
    if config and config.template:
        return config.template
    # Convention-based fallback
    return resource_type.lower()


def get_detections() -> Dict[str, DetectionConfig]:
    """
    Get all detection configurations.
    
    Returns:
        Dict mapping resource type names to their detection config.
    """
    global _detections_cache
    if _detections_cache is None:
        raw_config = _load_yaml("detections.yaml")
        if "detections" not in raw_config:
            raw_config = {"detections": {}}
        
        validated = DetectionsFile(**raw_config)
        _detections_cache = validated.detections
    return _detections_cache


def get_detection_config(resource_type: str) -> Optional[DetectionConfig]:
    """Get detection configuration for a specific resource type."""
    return get_detections().get(resource_type)


def requires_logging(resource_type: str) -> bool:
    """Check if a resource type requires a logging resource."""
    config = get_resource_type_config(resource_type)
    if config:
        return config.requires_logging
    return False


def get_resource_types_config() -> Dict[str, Any]:
    """
    Get raw resource types configuration dict from YAML.
    
    Used by the metadata API to expose type information to the WebUI.
    Returns the raw dict rather than Pydantic models for flexibility.
    """
    raw_config = _load_yaml("resource_types.yaml")
    return raw_config.get("resource_types", {})


def get_logging_types_config() -> Dict[str, Any]:
    """
    Get raw logging types configuration dict from YAML.
    
    Used by the metadata API to expose logging provider information to the WebUI.
    """
    raw_config = _load_yaml("resource_types.yaml")
    return raw_config.get("logging_types", {})


def reload_configs():
    """Force reload of all configuration files."""
    global _resource_types_cache, _detections_cache, _alert_outputs_cache, _environments_cache
    _resource_types_cache = None
    _detections_cache = None
    _alert_outputs_cache = None
    _environments_cache = None


# =============================================================================
# Environment Variable Expansion
# =============================================================================

def _expand_env_var(value: str) -> str:
    """
    Expand environment variables in a string value.
    
    Supports:
      - ${VAR_NAME}           - Required, fails if not set
      - ${VAR_NAME:-default}  - Optional with default value  
      - ${VAR_NAME:?error}    - Required with custom error message
    
    Args:
        value: String potentially containing ${...} expressions
        
    Returns:
        String with all environment variables expanded
        
    Raises:
        ValueError: If a required variable is not set
    """
    if not isinstance(value, str):
        return value
    
    # Pattern matches ${VAR}, ${VAR:-default}, ${VAR:?error}
    pattern = r'\$\{([^}:]+)(?::-([^}]*)|:\?([^}]*))?\}'
    
    def replacer(match):
        var_name = match.group(1)
        default_value = match.group(2)
        error_msg = match.group(3)
        
        env_value = os.environ.get(var_name)
        
        if env_value is not None:
            return env_value
        if default_value is not None:
            return default_value
        if error_msg is not None:
            raise ValueError(f"Required environment variable {var_name}: {error_msg}")
        raise ValueError(f"Environment variable {var_name} is not set")
    
    return re.sub(pattern, replacer, value)


def _expand_env_vars_recursive(obj: Any) -> Any:
    """
    Recursively expand environment variables in dicts, lists, and strings.
    
    Args:
        obj: Any Python object (dict, list, str, or other)
        
    Returns:
        Same structure with all string values having env vars expanded
    """
    if isinstance(obj, dict):
        return {k: _expand_env_vars_recursive(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_expand_env_vars_recursive(item) for item in obj]
    elif isinstance(obj, str):
        return _expand_env_var(obj)
    return obj


# =============================================================================
# Cloud Environments Configuration
# =============================================================================

_environments_cache: Optional[Dict[str, CloudEnvironmentConfig]] = None


def get_environments(expand_env_vars: bool = True) -> Dict[str, Union[Dict, CloudEnvironmentConfig]]:
    """
    Get cloud environment configurations from environments.yaml.
    
    Environment variables in the YAML are expanded by default.
    
    Args:
        expand_env_vars: If True, expand ${...} expressions. Set to False
                        to get raw config (useful for debugging).
    
    Returns:
        Dict mapping environment names to their config object (or dict if validation disabled via internal flag, but currently always validated if expanding).
    """
    global _environments_cache
    
    # Don't cache when not expanding (for validation use cases)
    if not expand_env_vars:
        config = _load_yaml("environments.yaml")
        return config.get("environments", {})
    
    if _environments_cache is None:
        config = _load_yaml("environments.yaml")
        raw_envs = config.get("environments", {})
        
        # Expand vars first
        expanded_envs = _expand_env_vars_recursive(raw_envs)
        
        # Wrap in Pydantic model for validation
        # EnvironmentsFile expects 'environments' dict
        env_file = EnvironmentsFile(environments=expanded_envs)
        _environments_cache = env_file.environments
    
    return _environments_cache


def get_environment_config(env_name: str) -> Optional[CloudEnvironmentConfig]:
    """
    Get configuration for a specific environment.
    
    Args:
        env_name: Name of the environment (e.g., "aws-production")
        
    Returns:
        Environment config object or None if not found
    """
    return get_environments().get(env_name)

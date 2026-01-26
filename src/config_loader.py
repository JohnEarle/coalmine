"""
Configuration loader for YAML-based resource and detection configs.

This module loads configuration from the config/ directory and provides
type-safe access to resource types and detection strategies.
"""
import os
import yaml
from pathlib import Path
from typing import Dict, Any, Optional

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
_resource_types_cache: Optional[Dict] = None
_detections_cache: Optional[Dict] = None
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


def get_resource_types() -> Dict[str, Dict]:
    """
    Get all resource type configurations.
    
    Returns:
        Dict mapping resource type names to their config:
        {
            "AWS_BUCKET": {
                "description": "...",
                "provider": "AWS",
                "template": "aws_bucket",
                "requires_logging": true
            },
            ...
        }
    """
    global _resource_types_cache
    if _resource_types_cache is None:
        config = _load_yaml("resource_types.yaml")
        _resource_types_cache = config.get("resource_types", {})
    return _resource_types_cache


def get_resource_type_config(resource_type: str) -> Optional[Dict]:
    """Get configuration for a specific resource type."""
    return get_resource_types().get(resource_type)


def get_template_name(resource_type: str) -> str:
    """
    Get the Tofu template directory name for a resource type.
    
    Falls back to convention: AWS_BUCKET -> aws_bucket
    """
    config = get_resource_type_config(resource_type)
    if config and "template" in config:
        return config["template"]
    # Convention-based fallback
    return resource_type.lower()


def get_detections() -> Dict[str, Dict]:
    """
    Get all detection configurations.
    
    Returns:
        Dict mapping resource type names to their detection config:
        {
            "AWS_BUCKET": {
                "strategy": "CloudWatchLogsQuery",
                "filter_pattern": "..."
            },
            ...
        }
    """
    global _detections_cache
    if _detections_cache is None:
        config = _load_yaml("detections.yaml")
        _detections_cache = config.get("detections", {})
    return _detections_cache


def get_detection_config(resource_type: str) -> Optional[Dict]:
    """Get detection configuration for a specific resource type."""
    return get_detections().get(resource_type)


def requires_logging(resource_type: str) -> bool:
    """Check if a resource type requires a logging resource."""
    config = get_resource_type_config(resource_type)
    if config:
        return config.get("requires_logging", False)
    return False


def reload_configs():
    """Force reload of all configuration files."""
    global _resource_types_cache, _detections_cache, _alert_outputs_cache
    _resource_types_cache = None
    _detections_cache = None
    _alert_outputs_cache = None

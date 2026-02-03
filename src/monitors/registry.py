"""
Detection Strategy Registry

Loads detection configurations from config/detections.yaml.
Raises an error if configuration is missing to catch deployment issues early.

To add a new detection type:
1. Edit config/detections.yaml
2. Restart the worker
"""
from ..models import ResourceType
from ..config_loader import get_detection_config, get_detections
from .strategies import CloudWatchLogsQuery, CloudTrailLookup, GcpAuditLogQuery
from ..logging_config import get_logger

logger = get_logger(__name__)

# Strategy class mapping
STRATEGY_CLASSES = {
    "CloudWatchLogsQuery": CloudWatchLogsQuery,
    "CloudTrailLookup": CloudTrailLookup,
    "GcpAuditLogQuery": GcpAuditLogQuery,
}

# Runtime cache for YAML-loaded strategies
_yaml_registry_cache = {}


def _build_strategy_from_config(config_obj):
    """Build a strategy instance from configuration."""
    # Handle Pydantic model
    if hasattr(config_obj, "model_dump"):
        config = config_obj.model_dump()
    elif hasattr(config_obj, "dict"):
        config = config_obj.dict()
    else:
        config = config_obj

    strategy_name = config.get("strategy")
    if not strategy_name or strategy_name not in STRATEGY_CLASSES:
        return None
    
    strategy_class = STRATEGY_CLASSES[strategy_name]
    
    if strategy_name == "CloudWatchLogsQuery":
        return strategy_class(filter_pattern=config.get("filter_pattern", ""))
    
    elif strategy_name == "CloudTrailLookup":
        return strategy_class(
            lookup_attr_keys=config.get("lookup_attributes", []),
            event_names=config.get("event_names")
        )
    
    elif strategy_name == "GcpAuditLogQuery":
        return strategy_class(filter_template=config.get("filter_template", ""))
    
    return None


def get_strategy(resource_type: ResourceType):
    """
    Get the detection strategy for a resource type.
    
    Loads from YAML config only. Raises ValueError if config is missing
    to catch deployment/configuration issues early.
    """
    # Check cache first
    if resource_type in _yaml_registry_cache:
        return _yaml_registry_cache[resource_type]
    
    # Try to load from YAML
    config = get_detection_config(resource_type.value)
    if config:
        strategy = _build_strategy_from_config(config)
        if strategy:
            _yaml_registry_cache[resource_type] = strategy
            return strategy
    
    # No fallback - fail fast to catch configuration errors
    logger.error(f"No detection strategy configured for {resource_type.value}. "
                 f"Please add configuration to config/detections.yaml")
    raise ValueError(f"No detection strategy configured for resource type: {resource_type.value}. "
                     f"Add configuration to config/detections.yaml")


def reload_registry():
    """Force reload of detection strategies from YAML."""
    global _yaml_registry_cache
    _yaml_registry_cache = {}


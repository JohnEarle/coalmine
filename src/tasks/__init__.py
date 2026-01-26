"""
Coalmine Tasks Package.

Re-exports all Celery tasks for backwards compatibility.
"""
from .canary import create_canary, rotate_canary, delete_canary, check_rotations
from .logging import create_logging_resource
from .monitoring import monitor_active_canaries
from .validation import validate_resources

# Also expose ActionType for test compatibility
from ..models import ActionType

# Re-export helpers that may be used by external code
from .helpers import (
    TOFU_BASE_DIR, STATE_BASE_DIR,
    _build_env_vars, _get_template_name, _get_backend_config
)

__all__ = [
    # Celery Tasks
    "create_canary",
    "rotate_canary", 
    "delete_canary",
    "check_rotations",
    "create_logging_resource",
    "monitor_active_canaries",
    "validate_resources",
    # Constants
    "TOFU_BASE_DIR",
    "STATE_BASE_DIR",
    # ActionType for tests
    "ActionType",
]

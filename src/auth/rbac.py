"""
Casbin RBAC Integration for FastAPI

Provides a Casbin enforcer and FastAPI dependencies for role-based
permission checks. Uses the existing permission/scope interface.
"""
import os
from pathlib import Path
from functools import lru_cache
from typing import Optional

import casbin
from fastapi import Request

from . import get_auth_config
from ..logging_config import get_logger

logger = get_logger(__name__)


def _get_config_path(relative_path: str) -> str:
    """Resolve config path, checking multiple locations."""
    # Try absolute path first
    if os.path.isabs(relative_path) and os.path.exists(relative_path):
        return relative_path
    
    # Try relative to /app (Docker)
    docker_path = Path("/app") / relative_path
    if docker_path.exists():
        return str(docker_path)
    
    # Try relative to project root (development)
    project_root = Path(__file__).parent.parent.parent
    local_path = project_root / relative_path
    if local_path.exists():
        return str(local_path)
    
    raise FileNotFoundError(f"Config file not found: {relative_path}")


@lru_cache(maxsize=1)
def get_enforcer() -> casbin.Enforcer:
    """
    Get or create the Casbin enforcer instance.
    
    Uses LRU cache for singleton pattern.
    """
    config = get_auth_config()
    
    model_path = _get_config_path(config.rbac.model_path)
    policy_path = _get_config_path(config.rbac.policy_path)
    
    logger.info(f"Loading Casbin model: {model_path}")
    logger.info(f"Loading Casbin policy: {policy_path}")
    
    enforcer = casbin.Enforcer(model_path, policy_path)
    return enforcer


def check_permission(role: str, resource: str, action: str) -> bool:
    """
    Check if a role has permission for an action on a resource.
    
    Args:
        role: User's role (admin, operator, viewer)
        resource: Resource type (canaries, alerts, logging, etc.)
        action: Action being performed (read, write, delete)
    
    Returns:
        True if allowed, False otherwise.
    """
    enforcer = get_enforcer()
    return enforcer.enforce(role, resource, action)


def reload_enforcer():
    """Force reload of Casbin policies."""
    get_enforcer.cache_clear()
    logger.info("Casbin enforcer cache cleared")


def get_roles() -> list[str]:
    """
    Get the ordered role hierarchy from Casbin grouping policies.
    
    Reads the 'g' (role inheritance) rules and returns roles
    ordered from most privileged to least privileged.
    """
    enforcer = get_enforcer()
    grouping_rules = enforcer.get_grouping_policy()
    
    # Build parent mapping: child -> parent
    parent_of: dict[str, str] = {}
    all_roles: set[str] = set()
    for rule in grouping_rules:
        child, parent = rule[0], rule[1]
        parent_of[child] = parent
        all_roles.add(child)
        all_roles.add(parent)
    
    # Find the root (a role that is never a child but appears as parent)
    # Actually: find roles that have no parent in the mapping
    roots = all_roles - set(parent_of.keys())
    
    # Walk from root down following the chain
    ordered: list[str] = []
    # Build child mapping: parent -> child
    child_of: dict[str, str] = {v: k for k, v in parent_of.items()}
    
    # Start from the least privileged (no children) and work up,
    # or start from root and work down
    current = roots.pop() if roots else None
    while current:
        ordered.append(current)
        current = child_of.get(current)
    
    return ordered

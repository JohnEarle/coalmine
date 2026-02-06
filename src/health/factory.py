from typing import Any
from .base import HealthCheck
from ..models import LoggingResource, CanaryResource, Credential, Account


class HealthCheckFactory:
    """Factory for creating health checkers."""
    
    _checkers = {}

    @classmethod
    def register(cls, model_class, checker_cls):
        cls._checkers[model_class] = checker_cls

    @classmethod
    def get_checker(cls, resource: Any) -> HealthCheck:
        """Get the appropriate health checker for a resource instance."""
        # Simple exact type match for now
        checker_cls = cls._checkers.get(type(resource))
        if not checker_cls:
            raise ValueError(f"No health checker registered for type {type(resource)}")
        return checker_cls()

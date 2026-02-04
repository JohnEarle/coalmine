from abc import ABC, abstractmethod
from typing import Tuple, Dict, Any

class HealthCheck(ABC):
    """Abstract base class for resource health checks."""

    @abstractmethod
    def check(self, resource: Any) -> Tuple[bool, str]:
        """
        Perform health check on the resource.
        
        Args:
            resource: The database model instance to check.
            
        Returns:
            Tuple[bool, str]: (is_healthy, message)
        """
        pass

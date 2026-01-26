from abc import ABC, abstractmethod
from ..models import CanaryResource
from ..logging_config import get_logger

logger = get_logger(__name__)

class CanaryTrigger(ABC):
    @abstractmethod
    def execute(self, canary: CanaryResource) -> bool:
        """
        Execute an action to trigger a security alert for this canary.
        Returns True if successful, False otherwise.
        """
        pass

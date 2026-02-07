import os
from abc import ABC, abstractmethod
from ..models import CanaryResource
from ..logging_config import get_logger

logger = get_logger(__name__)


def _get_test_ua_suffix() -> str:
    """Return the user-agent suffix containing the test token, or empty string."""
    token = os.getenv("COALMINE_TEST_UA_TOKEN")
    return f"coalmine-test/{token}" if token else ""


class CanaryTrigger(ABC):
    @abstractmethod
    def execute(self, canary: CanaryResource) -> bool:
        """
        Execute an action to trigger a security alert for this canary.
        Returns True if successful, False otherwise.
        """
        pass

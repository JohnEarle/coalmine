# Helper to mock modules during tests if they are missing
import sys
from unittest.mock import MagicMock

def mock_modules(modules):
    for mod in modules:
        sys.modules[mod] = MagicMock()

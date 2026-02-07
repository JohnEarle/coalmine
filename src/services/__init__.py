"""
Service Layer for Coalmine

Provides centralized business logic for all resource types.
Both CLI and API should use these services instead of direct database access.
"""
from .base import ServiceResult, ListResult, BaseService
from .accounts import AccountService
from .credentials import CredentialService
from .canaries import CanaryService
from .alerts import AlertService
from .logging_resources import LoggingResourceService
from .auth import AuthService
from .user_service import UserService
from .tasks import TaskService

__all__ = [
    "ServiceResult",
    "ListResult",
    "BaseService",
    "AccountService",
    "CredentialService",
    "CanaryService",
    "AlertService",
    "LoggingResourceService",
    "AuthService",
    "UserService",
    "TaskService",
]


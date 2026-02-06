"""
Organization Discovery - Base Class and Registry

Economy of Mechanism: Single interface for discovering accounts across all cloud providers.
Modularity: Each provider implements the same abstract interface.

Pattern: Strategy pattern with registry for extensibility.
"""
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, Type
from dataclasses import dataclass

from ..models import Credential, Account, AccountSource, CredentialAuthType
from ..logging_config import get_logger

logger = get_logger(__name__)


@dataclass
class DiscoveredAccount:
    """
    Represents an account discovered from a cloud organization.
    
    This is a clean data transfer object - no database dependencies.
    """
    account_id: str           # AWS account ID or GCP project ID
    name: str                 # Human-readable name
    metadata: Dict[str, Any]  # Provider-specific metadata (tags, labels, OU path)
    role_override: Optional[str] = None  # Custom role if different from default


class OrganizationDiscovery(ABC):
    """
    Abstract base class for organization discovery.
    
    Each cloud provider implements this interface to discover accounts.
    Economy of mechanism: One interface for all providers.
    """
    
    # Class-level provider identifier
    provider: str = "UNKNOWN"
    
    def __init__(self, credential: Credential):
        """Initialize with a credential that has ORGANIZATION scope."""
        self.credential = credential
        self.discovery_config = credential.discovery_config or {}
    
    @abstractmethod
    def discover(self) -> List[DiscoveredAccount]:
        """
        Discover all accounts accessible by this credential.
        
        Returns:
            List of DiscoveredAccount objects
        """
        pass
    
    @abstractmethod
    def validate_access(self) -> tuple[bool, str]:
        """
        Validate that the credential has organization access.
        
        Returns:
            (success: bool, message: str)
        """
        pass
    
    def get_role_for_account(self, account_id: str) -> str:
        """
        Get the role/SA to use for a specific account.
        
        Can be overridden for account-specific roles.
        """
        return self.discovery_config.get("member_role_name", self._default_role())
    
    @abstractmethod
    def _default_role(self) -> str:
        """Return the default role name for this provider."""
        pass


# =============================================================================
# Registry - Economy of Mechanism
# =============================================================================

_discovery_registry: Dict[str, Type[OrganizationDiscovery]] = {}


def register_discovery(provider: str):
    """
    Decorator to register a discovery implementation.
    
    Usage:
        @register_discovery("AWS")
        class AWSOrganizationDiscovery(OrganizationDiscovery):
            ...
    """
    def decorator(cls: Type[OrganizationDiscovery]):
        _discovery_registry[provider.upper()] = cls
        cls.provider = provider.upper()
        return cls
    return decorator


def get_discovery_for_credential(credential: Credential) -> OrganizationDiscovery:
    """
    Factory function to get the appropriate discovery handler.
    
    Economy of mechanism: Single entry point for all discovery.
    """
    provider = credential.provider.upper()
    
    if provider not in _discovery_registry:
        raise ValueError(f"No discovery implementation for provider: {provider}")
    
    discovery_class = _discovery_registry[provider]
    return discovery_class(credential)


def discover_accounts(credential: Credential) -> List[DiscoveredAccount]:
    """
    Discover accounts for a credential.
    
    Auto-detects credential capabilities by attempting organization API calls.
    If the credential doesn't have org access, discovery will fail gracefully.
    
    Economy of mechanism: One function handles all providers.
    """
    discovery = get_discovery_for_credential(credential)
    return discovery.discover()


def try_discover_accounts(credential: Credential) -> tuple[List[DiscoveredAccount], str | None]:
    """
    Attempt to discover accounts, returning error message if it fails.
    
    This is the safe version for auto-detection - it catches errors
    and returns them instead of raising.
    
    Returns:
        (accounts, error_message) - error_message is None on success
    """
    try:
        discovery = get_discovery_for_credential(credential)
        
        # First validate access
        has_access, message = discovery.validate_access()
        if not has_access:
            return [], message
        
        # Then discover
        accounts = discovery.discover()
        return accounts, None
        
    except Exception as e:
        logger.warning(f"Discovery failed for credential {credential.name}: {e}")
        return [], str(e)


# Import implementations to register them
# This happens at module load time
from . import aws_discovery, gcp_discovery

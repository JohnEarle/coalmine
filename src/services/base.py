"""
Base Service Classes and Types

Provides common infrastructure for all service classes.
"""
from dataclasses import dataclass, field
from typing import TypeVar, Generic, Optional, List, Any
import uuid

from src.models import SessionLocal

T = TypeVar('T')


@dataclass
class ServiceResult(Generic[T]):
    """
    Standard result type for service operations.
    
    Provides a consistent way to return success/failure status
    along with data or error messages.
    """
    success: bool
    data: Optional[T] = None
    error: Optional[str] = None
    
    @classmethod
    def ok(cls, data: T) -> "ServiceResult[T]":
        """Create a successful result with data."""
        return cls(success=True, data=data)
    
    @classmethod
    def fail(cls, error: str) -> "ServiceResult[T]":
        """Create a failed result with error message."""
        return cls(success=False, error=error)


@dataclass
class ListResult(Generic[T]):
    """
    Result type for list operations.
    
    Contains items and total count for pagination support.
    """
    items: List[T] = field(default_factory=list)
    total: int = 0


class BaseService:
    """
    Base class for all services.
    
    Provides:
    - Database session management with context manager support
    - Common utility methods for entity resolution
    
    Usage:
        with AccountService() as svc:
            result = svc.list()
    
    Or with an external session (for transactions):
        db = SessionLocal()
        try:
            svc1 = AccountService(db)
            svc2 = CredentialService(db)
            # ... operations share the same transaction
            db.commit()
        finally:
            db.close()
    """
    
    def __init__(self, db=None):
        """
        Initialize service.
        
        Args:
            db: Optional database session. If None, service creates its own.
        """
        self._db = db
        self._owns_session = db is None
    
    @property
    def db(self):
        """Get the database session, creating one if needed."""
        if self._db is None:
            self._db = SessionLocal()
        return self._db
    
    def close(self):
        """Close the database session if we own it."""
        if self._owns_session and self._db:
            self._db.close()
            self._db = None
    
    def __enter__(self):
        """Support context manager usage."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Close session on context exit."""
        self.close()
        return False  # Don't suppress exceptions
    
    def _resolve_by_id_or_name(self, model_class, identifier: str, name_field: str = "name"):
        """
        Find an entity by UUID or name.
        
        Args:
            model_class: SQLAlchemy model class
            identifier: UUID string or name
            name_field: Name of the name field (default: "name")
            
        Returns:
            Model instance or None
        """
        # Try UUID first
        try:
            entity = self.db.query(model_class).filter(
                model_class.id == uuid.UUID(identifier)
            ).first()
            if entity:
                return entity
        except ValueError:
            pass
        
        # Fall back to name
        name_attr = getattr(model_class, name_field)
        return self.db.query(model_class).filter(
            name_attr == identifier
        ).first()
    
    def _commit_and_refresh(self, entity):
        """Commit and refresh an entity."""
        self.db.commit()
        self.db.refresh(entity)
        return entity

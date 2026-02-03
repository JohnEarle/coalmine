from pydantic import BaseModel, Field, field_validator
from typing import Dict, Any, Optional, Literal

class CloudEnvironmentConfig(BaseModel):
    provider: Literal["AWS", "GCP"]
    credentials: Dict[str, str] = Field(default_factory=dict)
    config: Dict[str, Any] = Field(default_factory=dict)
    
    @field_validator('credentials')
    @classmethod
    def validate_credentials(cls, v):
        if not v:
            # It's possible credentials are empty if utilizing ambient auth, but usually we want at least something. 
            # Keeping permissive for now to match current behavior.
            pass
        return v

class EnvironmentsFile(BaseModel):
    environments: Dict[str, CloudEnvironmentConfig] = Field(default_factory=dict)

class ResourceTypeConfig(BaseModel):
    description: Optional[str] = None
    provider: Literal["AWS", "GCP"]
    template: Optional[str] = None
    requires_logging: bool = False

class ResourceTypesFile(BaseModel):
    resource_types: Dict[str, ResourceTypeConfig] = Field(default_factory=dict)

class DetectionConfig(BaseModel):
    strategy: str
    filter_pattern: Optional[str] = None
    query: Optional[str] = None
    # Strategy-specific fields
    filter_template: Optional[str] = None
    lookup_attributes: Optional[list[str]] = None
    event_names: Optional[list[str]] = None

class DetectionsFile(BaseModel):
    detections: Dict[str, DetectionConfig] = Field(default_factory=dict)

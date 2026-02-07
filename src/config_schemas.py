from pydantic import BaseModel, Field
from typing import Dict, Any, Optional, Literal


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

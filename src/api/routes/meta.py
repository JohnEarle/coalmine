"""
Metadata API Routes

Exposes configuration and type information for dynamic UI generation.
These endpoints are used by the WebUI to discover available resource types,
form schemas, and validation rules without hardcoding.

When new canary types are added to config/resource_types.yaml and models.py,
the WebUI automatically discovers them through these endpoints.
"""
from fastapi import APIRouter
from typing import Any, Dict, List

from ...models import ResourceType, LoggingProviderType, ResourceStatus
from ...config_loader import get_resource_types_config, get_logging_types_config

router = APIRouter(prefix="/meta", tags=["metadata"])


@router.get("/roles")
async def get_roles() -> Dict[str, Any]:
    """
    Returns available user roles from the RBAC policy.
    
    WebUI uses this to populate role dropdowns dynamically.
    When new roles are added to rbac_policy.csv, they
    automatically appear here.
    """
    from ...services import UserService
    
    with UserService() as svc:
        result = svc.list_roles()
    
    return {
        "roles": [
            {"value": r, "name": r.replace("_", " ").title()}
            for r in result.items
        ]
    }

@router.get("/resource-types")
async def get_resource_types() -> Dict[str, Any]:
    """
    Returns all available canary resource types with metadata.
    
    WebUI uses this to:
    - Populate resource type dropdowns dynamically
    - Show descriptions and provider info
    - Determine which fields are required (e.g., requires_logging)
    - Display provider-specific icons/styling
    
    When new resource types are added to ResourceType enum and
    config/resource_types.yaml, they automatically appear here.
    """
    config = get_resource_types_config()
    types_list = []
    
    for type_enum in ResourceType:
        type_config = config.get(type_enum.value, {})
        types_list.append({
            "value": type_enum.value,
            "name": type_enum.name.replace("_", " ").title(),
            "description": type_config.get("description", f"{type_enum.value} canary resource"),
            "provider": type_config.get("provider", _infer_provider(type_enum.value)),
            "requires_logging": type_config.get("requires_logging", False),
            "template": type_config.get("template", type_enum.value.lower()),
        })
    
    return {"types": types_list, "count": len(types_list)}


@router.get("/logging-types")
async def get_logging_types() -> Dict[str, Any]:
    """
    Returns all available logging provider types.
    
    WebUI uses this to populate logging resource type dropdowns
    and show provider-specific configuration options.
    """
    config = get_logging_types_config()
    types_list = []
    
    for type_enum in LoggingProviderType:
        type_config = config.get(type_enum.value, {})
        types_list.append({
            "value": type_enum.value,
            "name": type_enum.name.replace("_", " ").title(),
            "description": type_config.get("description", f"{type_enum.value} logging provider"),
            "provider": type_config.get("provider", _infer_provider(type_enum.value)),
            "template": type_config.get("template", type_enum.value.lower()),
        })
    
    return {"types": types_list, "count": len(types_list)}


@router.get("/statuses")
async def get_statuses() -> Dict[str, Any]:
    """
    Returns all possible resource status values with display metadata.
    
    Includes colors and labels for consistent UI rendering.
    """
    status_info = {
        "CREATING": {"color": "blue", "label": "Creating", "icon": "loader"},
        "ACTIVE": {"color": "green", "label": "Active", "icon": "check-circle"},
        "ROTATING": {"color": "yellow", "label": "Rotating", "icon": "refresh-cw"},
        "DELETING": {"color": "orange", "label": "Deleting", "icon": "trash"},
        "DELETED": {"color": "gray", "label": "Deleted", "icon": "x-circle"},
        "ERROR": {"color": "red", "label": "Error", "icon": "alert-circle"},
        "DRIFT": {"color": "purple", "label": "Drift Detected", "icon": "alert-triangle"},
    }
    
    return {
        "statuses": [
            {
                "value": s.value,
                "name": s.name,
                **status_info.get(s.value, {"color": "gray", "label": s.value, "icon": "help-circle"})
            }
            for s in ResourceStatus
        ]
    }


@router.get("/providers")
async def get_providers() -> Dict[str, Any]:
    """
    Returns supported cloud providers with display metadata.
    
    Useful for filtering resources by provider in the UI.
    """
    return {
        "providers": [
            {
                "value": "AWS",
                "name": "Amazon Web Services",
                "icon": "aws",
                "color": "#FF9900"
            },
            {
                "value": "GCP",
                "name": "Google Cloud Platform",
                "icon": "gcp",
                "color": "#4285F4"
            },
        ]
    }


@router.get("/form-schema/{resource_type}")
async def get_form_schema(resource_type: str) -> Dict[str, Any]:
    """
    Returns form field schema for a specific resource type.
    
    This enables fully dynamic form generation in the WebUI.
    When a new resource type needs custom parameters, add them here.
    """
    # Base fields common to all canaries
    base_fields = [
        {
            "name": "name",
            "type": "text",
            "label": "Name",
            "required": True,
            "placeholder": "my-canary",
            "description": "Unique name for this canary resource"
        },
        {
            "name": "environment_id",
            "type": "select",
            "label": "Environment",
            "required": True,
            "source": "/api/v1/environments",
            "valueKey": "id",
            "labelKey": "name",
            "description": "Cloud environment to deploy in"
        },
        {
            "name": "interval",
            "type": "number",
            "label": "Rotation Interval (seconds)",
            "required": False,
            "default": 0,
            "description": "0 for static credentials, or rotation interval in seconds"
        },
    ]
    
    # Type-specific additional fields
    type_specific = _get_type_specific_fields(resource_type)
    
    # Check if logging is required
    config = get_resource_types_config()
    type_config = config.get(resource_type, {})
    
    if type_config.get("requires_logging", False):
        base_fields.append({
            "name": "logging_id",
            "type": "select",
            "label": "Logging Resource",
            "required": True,
            "source": "/api/v1/logging",
            "valueKey": "id",
            "labelKey": "name",
            "description": "Logging resource for detection"
        })
    
    return {
        "resource_type": resource_type,
        "fields": base_fields + type_specific
    }


def _infer_provider(type_value: str) -> str:
    """Infer provider from type name prefix."""
    if type_value.startswith("AWS"):
        return "AWS"
    elif type_value.startswith("GCP"):
        return "GCP"
    return "UNKNOWN"


def _get_type_specific_fields(resource_type: str) -> List[Dict[str, Any]]:
    """
    Returns type-specific form fields.
    
    Add new resource types here as they're created.
    """
    type_fields = {
        "GCP_SERVICE_ACCOUNT": [
            {
                "name": "params.display_name",
                "type": "text",
                "label": "Display Name",
                "required": False,
                "placeholder": "Canary Service Account",
                "description": "Optional display name for the service account"
            }
        ],
        "GCP_BUCKET": [
            {
                "name": "params.location",
                "type": "select",
                "label": "Region",
                "required": False,
                "options": [
                    {"value": "US", "label": "US (Multi-region)"},
                    {"value": "EU", "label": "EU (Multi-region)"},
                    {"value": "us-central1", "label": "US Central"},
                    {"value": "us-east1", "label": "US East"},
                    {"value": "europe-west1", "label": "Europe West"},
                ],
                "description": "GCS bucket location"
            }
        ],
        "AWS_BUCKET": [
            {
                "name": "params.region",
                "type": "text",
                "label": "Region",
                "required": False,
                "placeholder": "us-east-1",
                "description": "AWS region for the S3 bucket"
            }
        ],
        "AWS_IAM_USER": [
            {
                "name": "params.path",
                "type": "text",
                "label": "IAM Path",
                "required": False,
                "placeholder": "/canaries/",
                "description": "Optional IAM path for the user"
            }
        ],
    }
    
    return type_fields.get(resource_type, [])

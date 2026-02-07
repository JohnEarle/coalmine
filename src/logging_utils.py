"""
Logging utility functions for Coalmine.

Filter updates are managed via Terraform to maintain single source of truth.
"""
from .models import ResourceType, LoggingResource, CanaryResource, LoggingProviderType
from .logging_config import get_logger
from .tofu_manager import TofuManager
import os

logger = get_logger(__name__)

# Import helpers lazily to avoid circular imports through tasks/__init__.py
def _get_helpers():
    """Lazy import of task helpers to avoid circular dependency."""
    from .tasks import helpers
    return helpers


def _apply_logging_with_canaries(logging_resource: LoggingResource):
    """
    Apply Terraform with current canary list for a logging resource.
    
    This is called when canaries are added/removed to update the filter.
    Queries all canaries linked to this logging resource and applies Terraform
    with the full list, ensuring single source of truth.
    
    Args:
        logging_resource: The LoggingResource to update
    """
    if not logging_resource or not logging_resource.account:
        logger.warning("Cannot apply logging: No logging resource or account")
        return False
    
    try:
        # Lazy imports to avoid circular dependency
        from .resources.registry import ResourceRegistry
        helpers = _get_helpers()
        
        handler = ResourceRegistry.get_handler(logging_resource.provider_type)
        template_dir = helpers._get_template_name(logging_resource.provider_type)
        
        template_path = os.path.join(helpers.TOFU_BASE_DIR, template_dir)
        work_dir = os.path.join(helpers.STATE_BASE_DIR, str(logging_resource.id))
        
        manager = TofuManager(template_path, work_dir)
        account = logging_resource.account
        exec_env = helpers._get_execution_env(account)
        
        backend_config = helpers._get_backend_config(str(logging_resource.id))
        manager.init(env=exec_env, backend_config=backend_config)
        
        # Build env_conf with project_id
        env_conf = {}
        if account:
            cred = account.credential
            if cred and cred.secrets and "project_id" in cred.secrets:
                env_conf["project_id"] = cred.secrets["project_id"]
            if "project_id" not in env_conf and account.account_id:
                env_conf["project_id"] = account.account_id
        
        if "project_id" not in env_conf and "GOOGLE_CLOUD_PROJECT" in exec_env:
            env_conf["project_id"] = exec_env["GOOGLE_CLOUD_PROJECT"]
        
        # Get canary filter clauses for all linked canaries
        canary_filters = _get_canary_filters_for_logging(logging_resource)
        
        # Get base vars and add canary filters
        vars_dict = handler.get_tform_vars(
            logging_resource.name, 
            env_conf, 
            logging_resource.configuration or {}
        )
        
        # Add provider-specific canary filters
        if logging_resource.provider_type == LoggingProviderType.GCP_AUDIT_SINK:
            vars_dict["canary_filters"] = canary_filters
        elif logging_resource.provider_type == LoggingProviderType.AWS_CLOUDTRAIL:
            vars_dict["canary_arns"] = canary_filters
        
        # Apply Terraform - apply() returns stdout, raises on failure
        output = manager.apply(vars_dict, env=exec_env)
        
        logger.info(f"Applied Terraform for {logging_resource.name} with {len(canary_filters)} canary filters")
        return True
        
    except Exception as e:
        logger.error(f"Error applying logging update: {e}")
        return False


def _get_canary_filters_for_logging(logging_resource: LoggingResource) -> list:
    """
    Get all canary filter clauses for a logging resource.
    
    Queries canaries linked to this logging resource and generates
    appropriate filter clauses based on provider type.
    
    Returns:
        List of filter clauses (strings for GCP, ARNs for AWS)
    """
    filters = []
    
    if not logging_resource.canaries:
        return filters
    
    project_id = None
    if logging_resource.account:
        project_id = logging_resource.account.account_id
        if not project_id and logging_resource.account.credential:
            secrets = logging_resource.account.credential.secrets or {}
            project_id = secrets.get("project_id")
    
    for canary in logging_resource.canaries:
        if logging_resource.provider_type == LoggingProviderType.GCP_AUDIT_SINK:
            # Generate GCP filter clause
            clause = _get_gcp_filter_clause(canary, project_id)
            if clause:
                filters.append(clause)
                
        elif logging_resource.provider_type == LoggingProviderType.AWS_CLOUDTRAIL:
            # Generate AWS ARNs (returns a list for bucket + object coverage)
            arns = _get_aws_canary_arn(canary)
            filters.extend(arns)
    
    return filters


def _get_gcp_filter_clause(canary: CanaryResource, project_id: str = None) -> str:
    """
    Generate GCP filter clause for a canary.
    
    For service accounts: matches principalEmail AND resourceName
    For buckets: matches resourceName
    """
    if canary.resource_type == ResourceType.GCP_SERVICE_ACCOUNT:
        email = canary.name
        if "@" not in email and project_id:
            email = f"{canary.name}@{project_id}.iam.gserviceaccount.com"
        return f'(protoPayload.authenticationInfo.principalEmail="{email}" OR protoPayload.resourceName:"{canary.name}")'
    
    elif canary.resource_type == ResourceType.GCP_BUCKET:
        return f'protoPayload.resourceName:"{canary.name}"'
    
    return ""


def _get_aws_canary_arn(canary: CanaryResource) -> list:
    """
    Generate AWS S3 ARN for a canary bucket.
    
    Returns bucket ARN for CloudTrail starts_with matching.
    The base ARN matches all objects in the bucket.
    """
    if canary.resource_type == ResourceType.AWS_BUCKET:
        # Get bucket name from canary configuration or name
        bucket_name = canary.name
        if canary.canary_credentials and "bucket_name" in canary.canary_credentials:
            bucket_name = canary.canary_credentials["bucket_name"]
        # Single ARN - starts_with will match bucket and all objects
        return [f"arn:aws:s3:::{bucket_name}"]
    
    return []


# Legacy functions - kept for backwards compatibility but now call Terraform
def _update_gcp_sink_filter(account, sink_name, resource_val, resource_type: ResourceType, add: bool = True):
    """
    DEPRECATED: Use _apply_logging_with_canaries() instead.
    
    This function now triggers a full Terraform apply with all canaries.
    The sink_name is used to find the associated LoggingResource.
    """
    from .models import SessionLocal
    
    logger.warning(
        f"_update_gcp_sink_filter is deprecated. "
        f"Use _apply_logging_with_canaries() for Terraform-managed filter updates."
    )
    
    try:
        db = SessionLocal()
        # Find logging resource by sink name (stored in configuration)
        log_resource = db.query(LoggingResource).filter(
            LoggingResource.account_id == account.id
        ).first()
        
        if log_resource:
            _apply_logging_with_canaries(log_resource)
        else:
            logger.warning(f"No logging resource found for account {account.id}")
            
    except Exception as e:
        logger.error(f"Error in deprecated _update_gcp_sink_filter: {e}")
    finally:
        db.close()


def _update_trail_selectors(account, trail_name, resource_arn, add: bool = True):
    """
    DEPRECATED: Use _apply_logging_with_canaries() instead.
    
    This function now triggers a full Terraform apply with all canaries.
    """
    from .models import SessionLocal
    
    logger.warning(
        f"_update_trail_selectors is deprecated. "
        f"Use _apply_logging_with_canaries() for Terraform-managed filter updates."
    )
    
    try:
        db = SessionLocal()
        log_resource = db.query(LoggingResource).filter(
            LoggingResource.account_id == account.id
        ).first()
        
        if log_resource:
            _apply_logging_with_canaries(log_resource)
        else:
            logger.warning(f"No logging resource found for account {account.id}")
            
    except Exception as e:
        logger.error(f"Error in deprecated _update_trail_selectors: {e}")
    finally:
        db.close()

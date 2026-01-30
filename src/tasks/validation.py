"""
Resource health check task - uses unified HealthCheckFactory.
"""
from ..celery_app import celery_app
from ..models import (
    SessionLocal, CanaryResource, LoggingResource, CloudEnvironment,
    ResourceHistory, ResourceStatus, ActionType
)
from ..logging_config import get_logger
from ..health.factory import HealthCheckFactory
from ..health.environment import EnvironmentHealthCheck
from ..health.logging import LoggingHealthCheck
from ..health.canary import CanaryHealthCheck

logger = get_logger(__name__)

# Register Validators
HealthCheckFactory.register(CloudEnvironment, EnvironmentHealthCheck)
HealthCheckFactory.register(LoggingResource, LoggingHealthCheck)
HealthCheckFactory.register(CanaryResource, CanaryHealthCheck)

@celery_app.task
def run_health_checks():
    """
    Periodically checks status of all resources (Environments, Logging, Canaries).
    """
    db = SessionLocal()
    try:
        # 1. Check Cloud Environments
        envs = db.query(CloudEnvironment).all()
        for env in envs:
            _check_and_update(db, env, "Environment")

        # 2. Check Logging Resources
        logs = db.query(LoggingResource).filter(
            LoggingResource.status != ResourceStatus.DELETED
        ).all()
        for log in logs:
            _check_and_update(db, log, "Logging")

        # 3. Check Canaries
        canaries = db.query(CanaryResource).filter(
            CanaryResource.status != ResourceStatus.DELETED
        ).all()
        for canary in canaries:
            _check_and_update(db, canary, "Canary")
            
    finally:
        db.close()

def _check_and_update(db, resource, label):
    """Helper to run check and update status/history."""
    try:
        checker = HealthCheckFactory.get_checker(resource)
        is_healthy, message = checker.check(resource)
        
        if not is_healthy:
            logger.warning(f"{label} {resource.name} Unhealthy: {message}")
            if resource.status != ResourceStatus.ERROR:
                resource.status = ResourceStatus.ERROR
                
                # History is only on Canaries currently, but we can check attribute
                if hasattr(resource, 'history'):
                    history = ResourceHistory(
                        resource_id=resource.id,
                        action=ActionType.ALERT,
                        details={"warning": f"Health Check Failed: {message}"}
                    )
                    db.add(history)
                db.commit()
        else:
            # Auto-recovery could be nice, but for now just log
            logger.info(f"{label} {resource.name} is healthy.")
            if resource.status == ResourceStatus.ERROR:
                resource.status = ResourceStatus.ACTIVE
                db.commit()
                
    except Exception as e:
        logger.error(f"Error checking {label} {resource.name}: {e}")

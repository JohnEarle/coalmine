"""
Canary access monitoring task - polls for alert events.
"""
from ..celery_app import celery_app
from ..models import (
    SessionLocal, CanaryResource, ResourceHistory, 
    ResourceStatus, ActionType, Alert, AlertStatus
)
from ..monitors import factory as monitor_factory
from ..notifications.registry import NotificationRegistry
from ..logging_config import get_logger
import datetime

logger = get_logger(__name__)


@celery_app.task
def monitor_active_canaries():
    """Poller for checking access logs."""
    db = SessionLocal()
    try:
        active_canaries = db.query(CanaryResource).filter(
            CanaryResource.status.in_([ResourceStatus.ACTIVE, ResourceStatus.DRIFT]),
        ).all()
        
        for canary in active_canaries:
            try:
                env = canary.environment
                if not env: 
                    continue
                
                monitor = monitor_factory.get_monitor(env)
                
                end_time = datetime.datetime.utcnow()
                start_time = end_time - datetime.timedelta(minutes=60)
                
                alerts = monitor.check(canary, start_time, end_time)
                
                if alerts:
                    logger.warning(f"Access detected on {canary.name} (Found {len(alerts)} events)")
                    for alert_dto in alerts:
                        # Deduplication via unique external_id
                        existing = db.query(Alert).filter(Alert.external_id == alert_dto.external_id).first()
                        if existing:
                            continue

                        logger.warning(f"  - New Alert: {alert_dto.event_name} from {alert_dto.source_ip} (ID: {alert_dto.external_id})")
                        
                        # Create Alert Object
                        new_alert = Alert(
                            canary_id=canary.id,
                            external_id=alert_dto.external_id,
                            timestamp=alert_dto.event_time,
                            source_ip=alert_dto.source_ip,
                            user_agent=alert_dto.user_agent,
                            event_name=alert_dto.event_name,
                            raw_data=alert_dto.raw_data,
                            status=AlertStatus.NEW
                        )
                        db.add(new_alert)
                        db.flush() # Generate ID

                        # Keep History as audit log
                        history = ResourceHistory(
                            resource_id=canary.id,
                            action=ActionType.ALERT,
                            timestamp=alert_dto.event_time, 
                            details={
                                "alert_id": str(new_alert.id),
                                "event_name": alert_dto.event_name,
                                "source_ip": alert_dto.source_ip
                            }
                        )
                        db.add(history)
                        
                    db.commit()
                    
                    # Dispatch Notifications Asynchronously (after commit so alerts exist)
                    from .notifications import send_all_notifications
                    for alert_dto in alerts:
                        # Find the alert we just created by external_id
                        created_alert = db.query(Alert).filter(Alert.external_id == alert_dto.external_id).first()
                        if created_alert:
                            send_all_notifications.delay(str(created_alert.id))
                    
            except Exception as e:
                logger.error(f"Error monitoring canary {canary.name}: {e}")
                
    finally:
        db.close()

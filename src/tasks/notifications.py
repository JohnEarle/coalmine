"""
Notification tasks - asynchronous alert dispatch.
"""
from ..celery_app import celery_app
from ..models import SessionLocal, Alert
from ..notifications.registry import NotificationRegistry
from ..logging_config import get_logger

logger = get_logger(__name__)


@celery_app.task(
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=60,
    max_retries=5
)
def send_notification(alert_id: str, notifier_type: str):
    """
    Send a notification for an alert using the specified notifier type.
    
    Decoupled from the monitoring loop to prevent slow notifiers from
    blocking alert processing.
    """
    db = SessionLocal()
    try:
        import uuid
        alert = db.query(Alert).filter(Alert.id == uuid.UUID(alert_id)).first()
        if not alert:
            logger.warning(f"Alert {alert_id} not found for notification.")
            return
        
        # Get all notifiers and find the one matching the type
        notifiers = NotificationRegistry.get_notifiers()
        for notifier in notifiers:
            if type(notifier).__name__.lower().replace("notifier", "") == notifier_type:
                try:
                    notifier.send_alert(alert)
                    logger.info(f"Sent {notifier_type} notification for alert {alert_id}")
                except Exception as e:
                    logger.error(f"Failed to send {notifier_type} notification: {e}")
                    raise  # Let Celery retry
                break
    finally:
        db.close()


@celery_app.task(
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=60,
    max_retries=5
)
def send_all_notifications(alert_id: str):
    """
    Send notifications for an alert to all enabled notifiers.
    """
    db = SessionLocal()
    try:
        import uuid
        alert = db.query(Alert).filter(Alert.id == uuid.UUID(alert_id)).first()
        if not alert:
            logger.warning(f"Alert {alert_id} not found for notification.")
            return
        
        notifiers = NotificationRegistry.get_notifiers()
        for notifier in notifiers:
            try:
                notifier.send_alert(alert)
                logger.info(f"Sent {type(notifier).__name__} notification for alert {alert_id}")
            except Exception as e:
                logger.error(f"Failed to send notification via {type(notifier).__name__}: {e}")
                # Continue to other notifiers, don't fail completely
    finally:
        db.close()

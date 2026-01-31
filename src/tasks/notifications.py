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
    Send a notification for an alert using all notifiers of the specified type.
    
    This task handles ALL notifiers of a given type (e.g. all webhooks).
    It attempts to send to all of them, identifying them by name.
    Failures are logged individually. If ANY fail, the task raises an exception
    to trigger a retry (but only for the failed ones, ideally, though here
    we retry the whole type block - simplified for stability).
    """
    db = SessionLocal()
    try:
        import uuid
        alert = db.query(Alert).filter(Alert.id == uuid.UUID(alert_id)).first()
        if not alert:
            logger.warning(f"Alert {alert_id} not found for notification.")
            return
        
        # Get all notifiers and find those matching the type
        notifiers = NotificationRegistry.get_notifiers()
        target_notifiers = [
            n for n in notifiers 
            if type(n).__name__.lower().replace("notifier", "") == notifier_type
        ]

        if not target_notifiers:
            logger.info(f"No notifiers found for type {notifier_type}")
            return

        failures = []
        for notifier in target_notifiers:
            try:
                notifier.send_alert(alert)
                logger.info(f"Sent {notifier_type} notification via '{notifier.name}' for alert {alert_id}")
            except Exception as e:
                logger.error(f"Failed to send {notifier_type} notification via '{notifier.name}': {e}")
                failures.append(notifier.name)
        
        if failures:
            raise Exception(f"Failed to send to the following {notifier_type} notifiers: {', '.join(failures)}")

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
    
    Dispatches a separate task for each notifier type (webhook, email, etc)
    to allow for parallel processing and isolated failures.
    """
    db = SessionLocal()
    try:
        import uuid
        alert = db.query(Alert).filter(Alert.id == uuid.UUID(alert_id)).first()
        if not alert:
            logger.warning(f"Alert {alert_id} not found for notification.")
            return
        
        notifiers = NotificationRegistry.get_notifiers()
        # Find unique types to dispatch
        # We normalize type names same as send_notification logic
        notifier_types = set()
        for n in notifiers:
            t = type(n).__name__.lower().replace("notifier", "")
            notifier_types.add(t)
        
        for n_type in notifier_types:
            logger.info(f"Dispatching notification task for type: {n_type}")
            send_notification.delay(alert_id, n_type)

    finally:
        db.close()

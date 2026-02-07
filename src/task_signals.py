"""
Celery Signal Handlers for TaskLog

Automatically tracks task lifecycle (STARTED → SUCCESS/FAILURE)
without modifying any existing task functions.

Only updates TaskLog rows that already exist (i.e., dispatched from
a known call site). System tasks without a TaskLog row are ignored.
"""
import datetime
from celery.signals import task_prerun, task_postrun, task_failure
from .models import SessionLocal, TaskLog, TaskStatus
from .logging_config import get_logger

logger = get_logger(__name__)


@task_prerun.connect
def _on_task_start(sender=None, task_id=None, **kwargs):
    """Mark task as STARTED when Celery begins executing it."""
    db = SessionLocal()
    try:
        row = db.query(TaskLog).filter(TaskLog.celery_task_id == task_id).first()
        if row:
            row.status = TaskStatus.STARTED
            row.started_at = datetime.datetime.utcnow()
            db.commit()
    except Exception as e:
        logger.warning(f"task_prerun signal error: {e}")
        db.rollback()
    finally:
        db.close()


@task_postrun.connect
def _on_task_success(sender=None, task_id=None, retval=None, state=None, **kwargs):
    """Mark task as SUCCESS when Celery finishes successfully."""
    if state != "SUCCESS":
        return
    db = SessionLocal()
    try:
        row = db.query(TaskLog).filter(TaskLog.celery_task_id == task_id).first()
        if row:
            row.status = TaskStatus.SUCCESS
            row.finished_at = datetime.datetime.utcnow()
            # Store a summary, not the full return value
            if isinstance(retval, dict):
                row.result_data = retval
            elif retval is not None:
                row.result_data = {"result": str(retval)}
            db.commit()
    except Exception as e:
        logger.warning(f"task_postrun signal error: {e}")
        db.rollback()
    finally:
        db.close()


@task_failure.connect
def _on_task_failure(sender=None, task_id=None, exception=None, traceback=None, **kwargs):
    """Mark task as FAILURE and record the error."""
    db = SessionLocal()
    try:
        row = db.query(TaskLog).filter(TaskLog.celery_task_id == task_id).first()
        if row:
            row.status = TaskStatus.FAILURE
            row.finished_at = datetime.datetime.utcnow()
            row.error = str(exception) if exception else "Unknown error"
            db.commit()
    except Exception as e:
        logger.warning(f"task_failure signal error: {e}")
        db.rollback()
    finally:
        db.close()

"""
Task Service

Provides visibility into async Celery task status and history.
"""
from .base import BaseService, ServiceResult, ListResult
from src.models import TaskLog


class TaskService(BaseService):
    """Service for querying task logs."""

    def list(self, include_system: bool = False) -> ListResult[TaskLog]:
        """
        List task logs.

        Args:
            include_system: If True, include system-triggered tasks.
                            Defaults to user-triggered only.
        """
        query = self.db.query(TaskLog)
        if not include_system:
            query = query.filter(TaskLog.source == "user")
        tasks = query.order_by(TaskLog.created_at.desc()).all()
        return ListResult(items=tasks, total=len(tasks))

    def get(self, identifier: str) -> ServiceResult[TaskLog]:
        """
        Get a task log by UUID or celery_task_id.

        Args:
            identifier: TaskLog UUID or Celery task ID string
        """
        # Try by celery_task_id first (most common lookup)
        row = self.db.query(TaskLog).filter(
            TaskLog.celery_task_id == identifier
        ).first()
        if row:
            return ServiceResult.ok(row)

        # Fall back to UUID
        row = self._resolve_by_id_or_name(TaskLog, identifier, name_field="celery_task_id")
        if row:
            return ServiceResult.ok(row)

        return ServiceResult.fail(f"Task '{identifier}' not found")

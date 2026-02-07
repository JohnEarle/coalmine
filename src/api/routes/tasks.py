"""
Task Log API Routes

Provides visibility into async Celery task status and history.
"""
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

from ..auth import require_scope
from src.services import TaskService

router = APIRouter(prefix="/tasks")


# =============================================================================
# Schemas
# =============================================================================

class TaskResponse(BaseModel):
    """Response schema for a single task log entry."""
    id: str
    celery_task_id: str
    task_name: str
    source: str
    status: str
    canary_id: Optional[str] = None
    canary_name: Optional[str] = None
    created_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    error: Optional[str] = None
    result_data: Optional[dict] = None

    @classmethod
    def from_model(cls, task):
        """Create response from TaskLog model."""
        return cls(
            id=str(task.id),
            celery_task_id=task.celery_task_id,
            task_name=task.task_name,
            source=task.source,
            status=task.status.value,
            canary_id=str(task.canary_id) if task.canary_id else None,
            canary_name=task.canary.name if task.canary else None,
            created_at=task.created_at,
            started_at=task.started_at,
            finished_at=task.finished_at,
            error=task.error,
            result_data=task.result_data,
        )


class TaskListResponse(BaseModel):
    """Response schema for list of task logs."""
    tasks: List[TaskResponse]
    total: int


# =============================================================================
# Endpoints
# =============================================================================

@router.get(
    "/",
    response_model=TaskListResponse,
    dependencies=[Depends(require_scope("canaries"))],
    summary="List task logs"
)
async def list_tasks(include_system: bool = False):
    """
    List async task logs.

    By default shows only user-triggered tasks.
    Pass ?include_system=true to include background system tasks.
    """
    with TaskService() as svc:
        result = svc.list(include_system=include_system)
        return TaskListResponse(
            tasks=[TaskResponse.from_model(t) for t in result.items],
            total=result.total,
        )


@router.get(
    "/{task_id}",
    response_model=TaskResponse,
    dependencies=[Depends(require_scope("canaries"))],
    summary="Get a specific task log"
)
async def get_task(task_id: str):
    """Get details for a specific task by UUID or Celery task ID."""
    from fastapi import HTTPException

    with TaskService() as svc:
        result = svc.get(task_id)
        if not result.success:
            raise HTTPException(status_code=404, detail=result.error)
        return TaskResponse.from_model(result.data)

from __future__ import annotations

from fastapi import APIRouter, Request

from src.schemas.task_pool import TaskPoolPage


router = APIRouter(prefix="/task-pool", tags=["task-pool"])


@router.get("", response_model=TaskPoolPage)
async def list_task_pool(request: Request, limit: int = 24, offset: int = 0):
    return await request.app.state.task_pool_service.list_tasks_page(
        limit=limit,
        offset=offset,
    )

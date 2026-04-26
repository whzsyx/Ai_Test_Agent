from __future__ import annotations
from fastapi import APIRouter, Request

from src.infrastructure.postgres_runtime import postgres_database_url


router = APIRouter(tags=["health"])


@router.get("/health")
async def health(request: Request):
    settings = request.app.state.settings
    memory_runtime_service = getattr(request.app.state, "memory_runtime_service", None)
    memory_backend = getattr(request.app.state, "memory_backend", "uninitialized")
    session_backend = getattr(request.app.state, "session_backend", "uninitialized")
    tool_job_backend = getattr(request.app.state, "tool_job_backend", "uninitialized")
    ui_graph_backend = getattr(request.app.state, "ui_graph_backend", "uninitialized")
    if memory_runtime_service is not None:
        memory_backend = await memory_runtime_service.refresh_backend_status()

    return {
        "status": "ok",
        "name": settings.app_name,
        "environment": settings.app_env,
        "memory_backend": memory_backend,
        "session_backend": session_backend,
        "tool_job_backend": tool_job_backend,
        "ui_graph_backend": ui_graph_backend,
        "knowledge_enabled": True,
        "memory_target": postgres_database_url(settings),
        "knowledge_target": f"bolt://{settings.memgraph_host}:{settings.memgraph_port}",
    }

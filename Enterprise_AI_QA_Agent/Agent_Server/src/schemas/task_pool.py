from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from src.schemas.session import SessionSummary


class TaskPoolSessionSummary(SessionSummary):
    selected_agent: str | None = None
    worker_dispatches: list[dict[str, Any]] = Field(default_factory=list)
    parent_session_id: str = ""


class TaskPoolPage(BaseModel):
    items: list[TaskPoolSessionSummary] = Field(default_factory=list)
    limit: int
    offset: int
    has_more: bool = False

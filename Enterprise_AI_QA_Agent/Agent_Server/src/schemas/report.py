from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from src.schemas.session import SessionSummary
from src.schemas.tool_job import ToolArtifactRecord


class ReportListEntry(BaseModel):
    session: SessionSummary
    artifacts: list[ToolArtifactRecord] = Field(default_factory=list)
    verifications: list[dict[str, Any]] = Field(default_factory=list)
    worker_dispatches: list[dict[str, Any]] = Field(default_factory=list)
    report_meta: dict[str, Any] = Field(default_factory=dict)
    report_session_id: str | None = None
    report_artifacts: list[ToolArtifactRecord] = Field(default_factory=list)


class ReportListPage(BaseModel):
    items: list[ReportListEntry] = Field(default_factory=list)
    limit: int
    offset: int
    has_more: bool = False

from __future__ import annotations

import asyncio
from datetime import datetime

from src.application.report_service import ReportService
from src.domain.models import SessionRecord
from src.schemas.session import RuntimeMode, SessionMode, SessionStatus
from src.schemas.tool_job import ToolArtifactRecord


class _Store:
    def __init__(self, sessions: list[SessionRecord]) -> None:
        self.sessions = sessions
        self.calls: list[dict] = []

    async def list_sessions(self, **kwargs):
        self.calls.append(kwargs)
        return self.sessions


class _ToolJobs:
    def __init__(self, artifacts: list[ToolArtifactRecord]) -> None:
        self.artifacts = artifacts
        self.requested_session_ids: list[str] = []

    async def list_artifacts_for_sessions(self, session_ids: list[str]):
        self.requested_session_ids = session_ids
        requested = set(session_ids)
        return [item for item in self.artifacts if item.session_id in requested]


def _session(session_id: str, metadata: dict) -> SessionRecord:
    now = datetime.utcnow()
    return SessionRecord(
        id=session_id,
        title=f"Report {session_id}",
        status=SessionStatus.completed,
        session_mode=SessionMode.normal,
        runtime_mode=RuntimeMode.interactive,
        mode_key="code_review",
        created_at=now,
        updated_at=now,
        metadata=metadata,
    )


def _artifact(artifact_id: str, session_id: str) -> ToolArtifactRecord:
    return ToolArtifactRecord(
        id=artifact_id,
        tool_job_id="job",
        session_id=session_id,
        turn_id="turn",
        trace_id="trace",
        tool_key="report-writer",
        artifact_type="report_markdown",
        path=f"{artifact_id}.md",
        created_at=datetime.utcnow(),
    )


def test_report_page_uses_lightweight_session_data_and_batches_artifacts():
    primary = _session(
        "primary",
        {
            "code_review_report": {
                "summary": "Ready",
                "report_session_id": "report-child",
            },
            "worker_dispatches": [{"task_id": "review", "status": "completed"}],
            "verification_results": [{"status": "passed", "summary": "ok"}],
        },
    )
    extra = _session("extra", {})
    store = _Store([primary, extra])
    tool_jobs = _ToolJobs(
        [
            _artifact("primary-artifact", "primary"),
            _artifact("report-artifact", "report-child"),
        ]
    )
    service = ReportService(  # type: ignore[arg-type]
        store=store,
        tool_job_service=tool_jobs,
    )

    page = asyncio.run(service.list_reports_page(limit=1, offset=0))

    assert page.has_more is True
    assert store.calls == [{"limit": 2, "offset": 0, "mode_key": "code_review"}]
    assert tool_jobs.requested_session_ids == ["primary", "report-child"]
    assert page.items[0].session.id == "primary"
    assert page.items[0].report_session_id == "report-child"
    assert [item.id for item in page.items[0].artifacts] == ["primary-artifact"]
    assert [item.id for item in page.items[0].report_artifacts] == ["report-artifact"]

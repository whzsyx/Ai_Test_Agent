"""Execution record and evidence helpers for Security Testing Mode."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.modes.security_testing_mode.campaign_state import (
    EvidenceArtifact,
    SecurityCampaign,
    SecurityTask,
    ToolExecutionRecord,
)
from src.modes.security_testing_mode.contracts import TASK_COMPLETED


class SecurityEvidenceService:
    """Convert runner output into auditable campaign records."""

    def record_runner_result(
        self,
        campaign: SecurityCampaign,
        task: SecurityTask,
        result: dict[str, Any],
        *,
        started_at: str = "",
    ) -> None:
        record = self.execution_record_from_runner(task, result, started_at=started_at)
        campaign.execution_records.append(record)
        campaign.evidence.extend(self.evidence_from_runner(task, result))

    def execution_record_from_runner(
        self,
        task: SecurityTask,
        result: dict[str, Any],
        *,
        started_at: str = "",
    ) -> ToolExecutionRecord:
        metrics = result.get("metrics") if isinstance(result.get("metrics"), dict) else {}
        artifacts = [
            str(item.get("path") or item.get("uri") or item.get("label") or item.get("filename") or "")
            for item in result.get("artifacts", [])
            if isinstance(item, dict)
        ]
        completed_at = task.completed_at or _utc_now()
        return ToolExecutionRecord(
            record_id=f"exec_{task.task_id}_{max(task.attempts, 1)}",
            task_id=task.task_id,
            tool_name=str(result.get("tool_name") or task.command_profile),
            command=str(result.get("command") or task.command_profile),
            started_at=started_at or task.started_at,
            completed_at=completed_at,
            duration_seconds=float(metrics.get("duration_seconds") or _duration_seconds(started_at or task.started_at, completed_at)),
            exit_code=result.get("exit_code") if isinstance(result.get("exit_code"), int) else None,
            stdout_summary=_truncate(str(result.get("raw_output") or task.raw_output or result.get("summary") or ""), 2000),
            stderr_summary=_truncate(str(result.get("stderr") or result.get("error") or ""), 1200),
            success=bool(result.get("success") or result.get("ok")),
            error="" if result.get("success") or result.get("ok") else str(result.get("error") or task.last_error or ""),
            artifacts=[item for item in artifacts if item],
        )

    def evidence_from_runner(
        self,
        task: SecurityTask,
        result: dict[str, Any],
    ) -> list[EvidenceArtifact]:
        evidence: list[EvidenceArtifact] = []
        for index, item in enumerate(result.get("artifacts", []), start=1):
            if not isinstance(item, dict):
                continue
            raw_path = str(item.get("path") or item.get("uri") or "").strip()
            label = str(item.get("label") or item.get("filename") or "").strip()
            filename = label or (Path(raw_path).name if raw_path else f"artifact_{index}.txt")
            evidence.append(
                EvidenceArtifact(
                    artifact_id=f"ev_{task.task_id}_{index}",
                    artifact_type=str(item.get("type") or "output"),
                    filename=filename,
                    content_type=str(item.get("content_type") or "application/octet-stream"),
                    size_bytes=int(item.get("size_bytes") or 0),
                    source_task_id=task.task_id,
                    created_at=_utc_now(),
                    content=raw_path,
                )
            )

        raw_output = str(result.get("raw_output") or task.raw_output or "").strip()
        if raw_output:
            evidence.append(
                EvidenceArtifact(
                    artifact_id=f"ev_{task.task_id}_raw_output",
                    artifact_type="tool_output",
                    filename=f"{task.task_id}_raw_output.txt",
                    content_type="text/plain",
                    content=_truncate(raw_output, 6000),
                    size_bytes=len(raw_output.encode("utf-8", errors="ignore")),
                    source_task_id=task.task_id,
                    created_at=_utc_now(),
                )
            )
        return evidence

    def hydrate_missing_records(self, campaign: SecurityCampaign) -> None:
        recorded_task_ids = {record.task_id for record in campaign.execution_records}
        for task in campaign.tasks:
            if task.task_id in recorded_task_ids:
                continue
            if not task.started_at and not task.completed_at and not task.result_summary:
                continue
            campaign.execution_records.append(
                ToolExecutionRecord(
                    record_id=f"exec_{task.task_id}_{max(task.attempts, 1)}",
                    task_id=task.task_id,
                    tool_name=task.command_profile,
                    command=task.command_profile,
                    started_at=task.started_at,
                    completed_at=task.completed_at,
                    success=task.status == TASK_COMPLETED,
                    stdout_summary=_truncate(task.raw_output or task.result_summary, 2000),
                    error=task.last_error,
                    artifacts=list(task.artifacts),
                )
            )


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _duration_seconds(started_at: str, completed_at: str) -> float:
    try:
        start = datetime.fromisoformat(started_at)
        end = datetime.fromisoformat(completed_at)
    except (TypeError, ValueError):
        return 0.0
    return max(0.0, (end - start).total_seconds())


def _truncate(value: str, limit: int) -> str:
    if len(value) <= limit:
        return value
    return f"{value[:limit]}...[truncated]"


__all__ = ["SecurityEvidenceService"]

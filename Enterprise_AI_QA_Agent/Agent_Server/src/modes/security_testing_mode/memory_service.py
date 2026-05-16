"""Memory and observation persistence for Security Testing Mode."""
from __future__ import annotations

import json
from typing import Any
from uuid import uuid4

from src.modes.security_testing_mode.campaign_state import (
    FindingRecord,
    SecurityCampaign,
    SecurityTask,
)
from src.modes.security_testing_mode.contracts import TASK_FAILED
from src.runtime.execution_logging import truncate_text
from src.schemas.observation import ObservationRecord


class SecurityMemoryService:
    """Build and persist compact observations from a security campaign."""

    async def persist_campaign_observations(
        self,
        *,
        campaign: SecurityCampaign,
        context: Any,
        memory_runtime_service: Any,
    ) -> list[str]:
        if memory_runtime_service is None:
            return []
        observations = self.build_campaign_observations(campaign, context)
        if not observations:
            return []
        return await memory_runtime_service.write_observations(observations)

    def build_campaign_observations(
        self,
        campaign: SecurityCampaign,
        context: Any,
    ) -> list[ObservationRecord]:
        session_id = str(getattr(context, "session_id", "") or "")
        turn_id = str(getattr(context, "turn_id", "") or "")
        trace_id = str(getattr(context, "trace_id", "") or "")
        observations = [
            self._campaign_observation(campaign, session_id, turn_id, trace_id),
        ]
        observations.extend(
            self._finding_observation(campaign, finding, session_id, turn_id, trace_id)
            for finding in campaign.findings[:20]
        )
        observations.extend(
            self._failed_task_observation(campaign, task, session_id, turn_id, trace_id)
            for task in campaign.tasks
            if task.status == TASK_FAILED
        )
        observations.extend(
            self._execution_observation(campaign, record, session_id, turn_id, trace_id)
            for record in campaign.execution_records[:20]
        )
        return observations

    def _campaign_observation(
        self,
        campaign: SecurityCampaign,
        session_id: str,
        turn_id: str,
        trace_id: str,
    ) -> ObservationRecord:
        completed = sum(1 for task in campaign.tasks if task.status == "completed")
        failed = sum(1 for task in campaign.tasks if task.status == "failed")
        title = f"Security campaign {campaign.campaign_id[:8] or 'summary'}"
        summary = (
            f"{len(campaign.tasks)} task(s), {completed} completed, {failed} failed, "
            f"{len(campaign.findings)} finding(s)."
        )
        content = {
            "campaign_id": campaign.campaign_id,
            "target_fingerprint": campaign.target_fingerprint,
            "objective": campaign.objective,
            "targets": [target.value for target in campaign.targets],
            "assets": len(campaign.assets),
            "services": len(campaign.fingerprints),
            "findings": len(campaign.findings),
            "evidence": len(campaign.evidence),
            "execution_records": len(campaign.execution_records),
            "risk_tolerance": campaign.risk_tolerance,
        }
        return self._observation(
            session_id=session_id,
            turn_id=turn_id,
            trace_id=trace_id,
            title=title,
            summary=summary,
            content=content,
            source=campaign.campaign_id,
            tags=["security", "security_testing", "campaign", "summary"],
        )

    def _finding_observation(
        self,
        campaign: SecurityCampaign,
        finding: FindingRecord,
        session_id: str,
        turn_id: str,
        trace_id: str,
    ) -> ObservationRecord:
        title = f"Security finding: {finding.title or finding.finding_id or 'untitled'}"
        content = {
            "campaign_id": campaign.campaign_id,
            "target_fingerprint": campaign.target_fingerprint,
            "finding_id": finding.finding_id,
            "title": finding.title,
            "severity": finding.severity,
            "category": finding.category,
            "affected_target": finding.affected_target,
            "affected_port": finding.affected_port,
            "affected_service": finding.affected_service,
            "description": finding.description,
            "evidence_summary": finding.evidence_summary,
            "recommendation": finding.recommendation,
            "source_task_ids": finding.source_task_ids,
        }
        return self._observation(
            session_id=session_id,
            turn_id=turn_id,
            trace_id=trace_id,
            title=title,
            summary=f"{finding.severity.upper()} {finding.category}: {finding.affected_target}",
            content=content,
            source=finding.affected_target or campaign.campaign_id,
            tags=[
                "security",
                "security_testing",
                "finding",
                f"severity:{finding.severity}",
                finding.category or "uncategorized",
            ],
        )

    def _failed_task_observation(
        self,
        campaign: SecurityCampaign,
        task: SecurityTask,
        session_id: str,
        turn_id: str,
        trace_id: str,
    ) -> ObservationRecord:
        content = {
            "campaign_id": campaign.campaign_id,
            "target_fingerprint": campaign.target_fingerprint,
            "task_id": task.task_id,
            "command_profile": task.command_profile,
            "target": task.target,
            "attempts": task.attempts,
            "last_error": task.last_error,
            "summary": task.result_summary,
        }
        return self._observation(
            session_id=session_id,
            turn_id=turn_id,
            trace_id=trace_id,
            title=f"Security task failed: {task.command_profile or task.task_id}",
            summary=truncate_text(task.last_error or task.result_summary or "Security task failed.", 180),
            content=content,
            source=task.target or campaign.campaign_id,
            tags=["security", "security_testing", "task_failure", task.command_profile or "unknown_profile"],
        )

    def _execution_observation(
        self,
        campaign: SecurityCampaign,
        record: Any,
        session_id: str,
        turn_id: str,
        trace_id: str,
    ) -> ObservationRecord:
        content = {
            "campaign_id": campaign.campaign_id,
            "target_fingerprint": campaign.target_fingerprint,
            "record_id": record.record_id,
            "task_id": record.task_id,
            "tool_name": record.tool_name,
            "command": record.command,
            "exit_code": record.exit_code,
            "success": record.success,
            "error": record.error,
            "artifact_count": len(record.artifacts),
            "stdout_summary": record.stdout_summary,
            "stderr_summary": record.stderr_summary,
        }
        status_tag = "success" if record.success else "failed"
        return self._observation(
            session_id=session_id,
            turn_id=turn_id,
            trace_id=trace_id,
            title=f"Security tool execution: {record.tool_name or record.task_id}",
            summary=truncate_text(record.stdout_summary or record.error or record.command, 180),
            content=content,
            source=record.artifacts[0] if record.artifacts else campaign.campaign_id,
            tags=["security", "security_testing", "tool_execution", status_tag, record.tool_name or "unknown_tool"],
        )

    def _observation(
        self,
        *,
        session_id: str,
        turn_id: str,
        trace_id: str,
        title: str,
        summary: str,
        content: dict[str, Any],
        source: str,
        tags: list[str],
    ) -> ObservationRecord:
        return ObservationRecord(
            id=str(uuid4()),
            session_id=session_id,
            turn_id=turn_id,
            trace_id=trace_id,
            tool_key="security-scan-runner",
            status="completed",
            scope="artifact",
            category="tool_execution",
            title=truncate_text(title, 140),
            summary=truncate_text(summary, 180),
            content=truncate_text(json.dumps(content, ensure_ascii=False), 1800),
            source=source or None,
            tags=list(dict.fromkeys([item for item in tags if item])),
            metadata={
                "mode": "security_testing",
                "campaign_id": content.get("campaign_id"),
                "target_fingerprint": content.get("target_fingerprint"),
                "observation_kind": tags[2] if len(tags) > 2 else "security",
            },
        )


__all__ = ["SecurityMemoryService"]

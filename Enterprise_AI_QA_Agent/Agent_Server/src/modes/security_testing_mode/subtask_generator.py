"""PentAGI-style subtask generation for Security Testing Mode."""
from __future__ import annotations

from src.modes.security_testing_mode.campaign_state import (
    SecurityCampaign,
    SecuritySubtask,
    SecurityTestingRequestState,
)


class SecuritySubtaskGenerator:
    """Derive auditable subtasks from the planned executable task list."""

    DEFAULT_SUCCESS_CRITERIA = [
        "Runner returns a completed status.",
        "Parser returns structured output or a clear empty result.",
        "Evidence artifact is captured or an explicit limitation is recorded.",
    ]
    DEFAULT_STOP_CONDITIONS = [
        "Stop after the configured timeout.",
        "Stop if the profile exceeds the requested risk tolerance.",
        "Do not escalate to unplanned profiles without a refined subtask.",
    ]

    def generate(
        self,
        campaign: SecurityCampaign,
        request: SecurityTestingRequestState,
    ) -> list[SecuritySubtask]:
        """Create one structured subtask for each planned runner task."""
        subtasks: list[SecuritySubtask] = []
        risk_tolerance = request.risk_tolerance or campaign.risk_tolerance or "medium"
        for index, task in enumerate(campaign.tasks, start=1):
            title = task.name or task.command_profile or f"Security subtask {index}"
            subtasks.append(
                SecuritySubtask(
                    subtask_id=f"sub_{task.task_id}",
                    task_id=task.task_id,
                    title=title,
                    description=task.description or title,
                    allowed_profiles=[task.command_profile] if task.command_profile else [],
                    risk_level=task.risk_level or risk_tolerance,
                    success_criteria=list(self.DEFAULT_SUCCESS_CRITERIA),
                    stop_conditions=list(self.DEFAULT_STOP_CONDITIONS),
                    status="planned",
                    worker_agent_key=task.worker_agent_key,
                    tool_family=task.tool_family,
                    target=task.target,
                    notes=[
                        f"Generated from runner task {task.task_id}.",
                        f"Requested risk tolerance: {risk_tolerance}.",
                    ],
                )
            )
        return subtasks


__all__ = ["SecuritySubtaskGenerator"]

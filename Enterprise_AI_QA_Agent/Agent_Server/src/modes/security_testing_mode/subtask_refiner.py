"""PentAGI-style subtask refinement for Security Testing Mode."""
from __future__ import annotations

from src.modes.security_testing_mode.campaign_state import (
    SecurityCampaign,
    SecuritySubtask,
    SecurityTestingRequestState,
)
from src.modes.security_testing_mode.contracts import TASK_FAILED
from src.modes.security_testing_mode.subtask_generator import SecuritySubtaskGenerator


class SecuritySubtaskRefiner:
    """Update subtasks with execution outcomes and safe stop decisions."""

    def __init__(self) -> None:
        self._generator = SecuritySubtaskGenerator()

    def refine_after_execution(self, campaign: SecurityCampaign) -> tuple[list[SecuritySubtask], list[str]]:
        """Return updated subtasks plus human-readable refinement notes."""
        subtasks = list(campaign.subtasks)
        if not subtasks and campaign.tasks:
            subtasks = self._generator.generate(
                campaign,
                request=SecurityTestingRequestState(risk_tolerance=campaign.risk_tolerance),
            )

        task_by_id = {task.task_id: task for task in campaign.tasks}
        notes: list[str] = []
        refined: list[SecuritySubtask] = []
        for subtask in subtasks:
            task = task_by_id.get(subtask.task_id)
            if task is None:
                refined.append(subtask)
                continue

            subtask.status = task.status
            subtask.result_summary = task.result_summary
            if task.worker_agent_key and not subtask.worker_agent_key:
                subtask.worker_agent_key = task.worker_agent_key
            if task.tool_family and not subtask.tool_family:
                subtask.tool_family = task.tool_family
            if task.target and not subtask.target:
                subtask.target = task.target

            if task.status == TASK_FAILED:
                category = self._classify_failure(task.last_error or task.result_summary)
                subtask.failure_category = category
                self._append_unique(
                    subtask.notes,
                    f"Execution failed and was classified as {category}.",
                )
                self._append_unique(
                    subtask.stop_conditions,
                    self._stop_condition_for_category(category),
                )
                notes.append(
                    f"Subtask {subtask.subtask_id} failed as {category}; record it as a limitation instead of escalating tools."
                )
            elif task.result_summary:
                self._append_unique(subtask.notes, task.result_summary)

            refined.append(subtask)
        return refined, notes

    def _classify_failure(self, message: str) -> str:
        normalized = message.lower()
        if "timeout" in normalized or "timed out" in normalized:
            return "timeout"
        if "exit_code=2" in normalized or "exit code 2" in normalized:
            return "profile_compatibility"
        if "exit_code=1" in normalized or "exit code 1" in normalized:
            return "tool_execution"
        if "approval" in normalized or "denied" in normalized:
            return "approval_or_policy"
        if "not configured" in normalized or "not installed" in normalized or "not found" in normalized:
            return "environment"
        return "execution"

    def _stop_condition_for_category(self, category: str) -> str:
        if category == "timeout":
            return "Execution timed out; record as limitation instead of escalating tools."
        if category == "profile_compatibility":
            return "Tool/profile compatibility failure; route to failure analysis before retrying."
        if category == "approval_or_policy":
            return "Approval or policy blocked execution; do not bypass with alternate tools."
        if category == "environment":
            return "Environment dependency is missing; report setup gap instead of free-form shell fallback."
        return "Execution failed; preserve evidence and let reporter judge impact."

    def _append_unique(self, values: list[str], value: str) -> None:
        if value and value not in values:
            values.append(value)

__all__ = ["SecuritySubtaskRefiner"]

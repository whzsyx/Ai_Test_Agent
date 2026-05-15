"""Post-run reflection for Security Testing Mode."""
from __future__ import annotations

from src.modes.security_testing_mode.campaign_state import SecurityCampaign
from src.modes.security_testing_mode.contracts import TASK_COMPLETED, TASK_FAILED, TASK_SKIPPED


class SecurityReflectionService:
    """Summarize execution health and suggest safe follow-up actions."""

    def analyze_campaign(self, campaign: SecurityCampaign) -> dict[str, object]:
        failed = [task for task in campaign.tasks if task.status == TASK_FAILED]
        skipped = [task for task in campaign.tasks if task.status == TASK_SKIPPED]
        completed = [task for task in campaign.tasks if task.status == TASK_COMPLETED]
        retryable = [
            task.task_id
            for task in failed
            if task.attempts <= task.max_retries and not task.requires_approval
        ]
        notes: list[str] = []
        if failed:
            notes.append(f"{len(failed)} security task(s) failed; review stderr and artifact transcripts before retry.")
        if skipped:
            notes.append(f"{len(skipped)} security task(s) were skipped due to dependency or policy constraints.")
        if not campaign.findings and completed:
            notes.append("No findings were normalized from completed tasks; this may mean the target is quiet or parser coverage needs expansion.")
        if retryable:
            notes.append(f"Retryable task ids: {', '.join(retryable)}.")

        return {
            "completed_count": len(completed),
            "failed_count": len(failed),
            "skipped_count": len(skipped),
            "retryable_task_ids": retryable,
            "notes": notes,
        }


__all__ = ["SecurityReflectionService"]

"""Execution guardrails for controlled security testing workflows."""
from __future__ import annotations

from collections import Counter
from typing import Any, Callable


LOW_RISK_BLOCKED_PROFILES: frozenset[str] = frozenset(
    {
        "ffuf_common_dirs",
        "gobuster_dirs",
        "nikto_web_scan",
        "nuclei_baseline",
        "nuclei_cve_scan",
        "sqlmap_readonly_probe",
        "hydra_basic_login",
    }
)


class SecurityExecutionMonitor:
    """Apply PentAGI-style execution limits before and after runner dispatch."""

    def __init__(
        self,
        *,
        max_profile_repeats: int = 2,
        max_smoke_test_tool_calls: int = 8,
        max_consecutive_runner_failures: int = 2,
    ) -> None:
        self.max_profile_repeats = max(1, max_profile_repeats)
        self.max_smoke_test_tool_calls = max(1, max_smoke_test_tool_calls)
        self.max_consecutive_runner_failures = max(1, max_consecutive_runner_failures)

    def profile_allowed_for_risk(self, profile_key: str, risk_tolerance: str) -> tuple[bool, str]:
        risk = str(risk_tolerance or "medium").strip().lower()
        profile = str(profile_key or "").strip()
        if risk == "low" and profile in LOW_RISK_BLOCKED_PROFILES:
            return (
                False,
                f"Profile {profile} is blocked for low-risk security testing. Use explicit medium/high risk authorization to enable it.",
            )
        return True, ""

    def filter_planned_tasks(self, tasks: list[Any], risk_tolerance: str) -> tuple[list[Any], list[str]]:
        notes: list[str] = []
        filtered: list[Any] = []
        profile_counts: Counter[str] = Counter()
        for task in tasks:
            profile_key = str(getattr(task, "command_profile", "") or "")
            allowed, reason = self.profile_allowed_for_risk(profile_key, risk_tolerance)
            if not allowed:
                notes.append(reason)
                continue

            profile_counts[profile_key] += 1
            if profile_counts[profile_key] > self.max_profile_repeats:
                notes.append(
                    f"Profile {profile_key} exceeded repeat limit ({self.max_profile_repeats}); extra task skipped."
                )
                continue

            if str(risk_tolerance or "").lower() == "low" and len(filtered) >= self.max_smoke_test_tool_calls:
                notes.append(
                    f"Low-risk smoke test reached tool-call budget ({self.max_smoke_test_tool_calls}); remaining tasks skipped."
                )
                break
            filtered.append(task)
        return filtered, notes

    def analyze_settled_tasks(
        self,
        tasks: list[Any],
        runner_lookup: Callable[[str], str],
    ) -> list[str]:
        notes: list[str] = []
        failed_by_runner: Counter[str] = Counter()
        for task in tasks:
            if str(getattr(task, "status", "") or "") != "failed":
                continue
            runner_key = runner_lookup(str(getattr(task, "tool_family", "") or ""))
            failed_by_runner[runner_key] += 1
        for runner_key, count in failed_by_runner.items():
            if count >= self.max_consecutive_runner_failures:
                notes.append(
                    f"Runner {runner_key} failed {count} time(s); route follow-up work to failure analysis before retrying."
                )
        return notes


__all__ = ["LOW_RISK_BLOCKED_PROFILES", "SecurityExecutionMonitor"]

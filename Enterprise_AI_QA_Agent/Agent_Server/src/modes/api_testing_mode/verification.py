"""API Testing Mode verification policy.

Implements the Verification Harness for API testing campaigns:
- Assertion pass rate threshold
- Critical endpoint enforcement (auth/core must all pass)
- Response time SLA checks
- Structured verdict output
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from src.modes.api_testing_mode.campaign_state import ApiTestCampaign, ApiTestTask, CampaignReport
from src.modes.api_testing_mode.capability_mapper import CAP_LOGIN, CORE_CAPABILITIES
from src.modes.api_testing_mode.contracts import TASK_COMPLETED, TASK_FAILED, TASK_SKIPPED


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

DEFAULT_PASS_RATE_THRESHOLD = 0.8  # 80% of tasks must pass
DEFAULT_CRITICAL_MUST_PASS = True  # auth + core endpoints must all pass
DEFAULT_RESPONSE_TIME_SLA_MS = 5000.0  # 5 seconds max per endpoint
DEFAULT_ALLOW_SKIPPED = True  # skipped tasks don't count as failures


@dataclass
class VerificationRule:
    """One verification rule with its evaluation result."""

    rule_id: str
    name: str
    passed: bool
    severity: str = "error"  # error / warning / info
    expected: Any = None
    actual: Any = None
    description: str = ""
    affected_tasks: list[str] = field(default_factory=list)


@dataclass
class VerificationVerdict:
    """Final verification verdict for a campaign."""

    passed: bool
    verdict: str  # "approved" / "rejected" / "warning"
    summary: str
    rules: list[VerificationRule] = field(default_factory=list)
    pass_rate: float = 0.0
    critical_passed: bool = True
    sla_passed: bool = True
    total_rules: int = 0
    failed_rules: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "passed": self.passed,
            "verdict": self.verdict,
            "summary": self.summary,
            "pass_rate": round(self.pass_rate, 4),
            "critical_passed": self.critical_passed,
            "sla_passed": self.sla_passed,
            "total_rules": self.total_rules,
            "failed_rules": self.failed_rules,
            "rules": [
                {
                    "rule_id": r.rule_id,
                    "name": r.name,
                    "passed": r.passed,
                    "severity": r.severity,
                    "expected": r.expected,
                    "actual": r.actual,
                    "description": r.description,
                    "affected_tasks": r.affected_tasks,
                }
                for r in self.rules
            ],
        }


class ApiTestingVerificationPolicy:
    """Evaluate whether a campaign meets quality gates."""

    def __init__(
        self,
        *,
        pass_rate_threshold: float = DEFAULT_PASS_RATE_THRESHOLD,
        critical_must_pass: bool = DEFAULT_CRITICAL_MUST_PASS,
        response_time_sla_ms: float = DEFAULT_RESPONSE_TIME_SLA_MS,
        allow_skipped: bool = DEFAULT_ALLOW_SKIPPED,
    ) -> None:
        self._pass_rate_threshold = pass_rate_threshold
        self._critical_must_pass = critical_must_pass
        self._response_time_sla_ms = response_time_sla_ms
        self._allow_skipped = allow_skipped

    def verify(self, *, campaign: ApiTestCampaign, report: CampaignReport | None = None) -> VerificationVerdict:
        """Run all verification rules against the campaign."""
        rules: list[VerificationRule] = []
        tasks = campaign.tasks

        # Rule 1: Overall pass rate.
        rule_pass_rate = self._check_pass_rate(tasks)
        rules.append(rule_pass_rate)

        # Rule 2: Critical endpoints must pass.
        rule_critical = self._check_critical_endpoints(tasks)
        rules.append(rule_critical)

        # Rule 3: Response time SLA.
        rule_sla = self._check_response_time_sla(tasks)
        rules.append(rule_sla)

        # Rule 4: No auth failures (indicates misconfiguration).
        rule_auth = self._check_no_auth_failures(tasks)
        rules.append(rule_auth)

        # Rule 5: No connection/timeout errors (indicates environment issues).
        rule_env = self._check_no_environment_errors(tasks)
        rules.append(rule_env)

        # Aggregate verdict.
        error_rules = [r for r in rules if not r.passed and r.severity == "error"]
        warning_rules = [r for r in rules if not r.passed and r.severity == "warning"]
        failed_rules = len(error_rules)

        if error_rules:
            verdict = "rejected"
            passed = False
        elif warning_rules:
            verdict = "warning"
            passed = True
        else:
            verdict = "approved"
            passed = True

        summary = self._build_summary(rules, verdict, campaign)

        return VerificationVerdict(
            passed=passed,
            verdict=verdict,
            summary=summary,
            rules=rules,
            pass_rate=rule_pass_rate.actual if isinstance(rule_pass_rate.actual, (int, float)) else 0.0,
            critical_passed=rule_critical.passed,
            sla_passed=rule_sla.passed,
            total_rules=len(rules),
            failed_rules=failed_rules,
        )

    # ------------------------------------------------------------------
    # Individual rules
    # ------------------------------------------------------------------

    def _check_pass_rate(self, tasks: list[ApiTestTask]) -> VerificationRule:
        if not tasks:
            return VerificationRule(
                rule_id="pass_rate",
                name="Task Pass Rate",
                passed=False,
                severity="error",
                expected=self._pass_rate_threshold,
                actual=0.0,
                description="No tasks were executed.",
            )

        total = len(tasks)
        if self._allow_skipped:
            evaluated = [t for t in tasks if t.status != TASK_SKIPPED]
        else:
            evaluated = list(tasks)

        if not evaluated:
            return VerificationRule(
                rule_id="pass_rate",
                name="Task Pass Rate",
                passed=False,
                severity="error",
                expected=self._pass_rate_threshold,
                actual=0.0,
                description="All tasks were skipped.",
            )

        passed_count = sum(1 for t in evaluated if t.status == TASK_COMPLETED)
        rate = passed_count / len(evaluated)
        threshold_met = rate >= self._pass_rate_threshold
        failed_ids = [t.task_id for t in evaluated if t.status == TASK_FAILED]

        return VerificationRule(
            rule_id="pass_rate",
            name="Task Pass Rate",
            passed=threshold_met,
            severity="error",
            expected=self._pass_rate_threshold,
            actual=round(rate, 4),
            description=(
                f"{passed_count}/{len(evaluated)} tasks passed ({rate:.0%}). "
                f"Threshold: {self._pass_rate_threshold:.0%}."
            ),
            affected_tasks=failed_ids,
        )

    def _check_critical_endpoints(self, tasks: list[ApiTestTask]) -> VerificationRule:
        if not self._critical_must_pass:
            return VerificationRule(
                rule_id="critical_endpoints",
                name="Critical Endpoints",
                passed=True,
                severity="error",
                description="Critical endpoint check is disabled.",
            )

        critical_tasks = [
            t for t in tasks
            if t.capability in CORE_CAPABILITIES or t.capability == CAP_LOGIN
        ]
        if not critical_tasks:
            return VerificationRule(
                rule_id="critical_endpoints",
                name="Critical Endpoints",
                passed=True,
                severity="info",
                description="No critical endpoints identified in this campaign.",
            )

        failed_critical = [t for t in critical_tasks if t.status == TASK_FAILED]
        all_passed = len(failed_critical) == 0

        return VerificationRule(
            rule_id="critical_endpoints",
            name="Critical Endpoints",
            passed=all_passed,
            severity="error",
            expected="all critical endpoints pass",
            actual=f"{len(critical_tasks) - len(failed_critical)}/{len(critical_tasks)} passed",
            description=(
                f"Critical endpoints: {len(critical_tasks)} total, {len(failed_critical)} failed."
                if not all_passed
                else f"All {len(critical_tasks)} critical endpoints passed."
            ),
            affected_tasks=[t.task_id for t in failed_critical],
        )

    def _check_response_time_sla(self, tasks: list[ApiTestTask]) -> VerificationRule:
        completed_tasks = [t for t in tasks if t.status == TASK_COMPLETED and t.duration_ms > 0]
        if not completed_tasks:
            return VerificationRule(
                rule_id="response_time_sla",
                name="Response Time SLA",
                passed=True,
                severity="warning",
                description="No completed tasks with timing data.",
            )

        slow_tasks = [t for t in completed_tasks if t.duration_ms > self._response_time_sla_ms]
        all_within_sla = len(slow_tasks) == 0
        max_time = max(t.duration_ms for t in completed_tasks)
        avg_time = sum(t.duration_ms for t in completed_tasks) / len(completed_tasks)

        return VerificationRule(
            rule_id="response_time_sla",
            name="Response Time SLA",
            passed=all_within_sla,
            severity="warning",
            expected=f"<= {self._response_time_sla_ms}ms",
            actual=f"max={max_time:.0f}ms, avg={avg_time:.0f}ms",
            description=(
                f"{len(slow_tasks)} endpoint(s) exceeded {self._response_time_sla_ms}ms SLA."
                if not all_within_sla
                else f"All endpoints within {self._response_time_sla_ms}ms SLA (max={max_time:.0f}ms)."
            ),
            affected_tasks=[t.task_id for t in slow_tasks],
        )

    def _check_no_auth_failures(self, tasks: list[ApiTestTask]) -> VerificationRule:
        auth_failed = [
            t for t in tasks
            if t.status == TASK_FAILED and t.response_status in {401, 403}
        ]
        passed = len(auth_failed) == 0

        return VerificationRule(
            rule_id="no_auth_failures",
            name="No Auth Failures",
            passed=passed,
            severity="error" if not passed else "info",
            expected="no 401/403 responses",
            actual=f"{len(auth_failed)} auth failures",
            description=(
                f"{len(auth_failed)} endpoint(s) returned 401/403, indicating credential or permission issues."
                if not passed
                else "No authentication failures detected."
            ),
            affected_tasks=[t.task_id for t in auth_failed],
        )

    def _check_no_environment_errors(self, tasks: list[ApiTestTask]) -> VerificationRule:
        env_errors = []
        for task in tasks:
            if task.status != TASK_FAILED:
                continue
            error = (task.last_error or "").lower()
            if any(kw in error for kw in ("timeout", "timed out", "connection", "dns", "refused")):
                env_errors.append(task)
            elif task.response_status and task.response_status >= 500:
                env_errors.append(task)

        passed = len(env_errors) == 0

        return VerificationRule(
            rule_id="no_environment_errors",
            name="No Environment Errors",
            passed=passed,
            severity="warning",
            expected="no timeout/connection/5xx errors",
            actual=f"{len(env_errors)} environment errors",
            description=(
                f"{len(env_errors)} task(s) failed due to environment issues (timeout/connection/5xx)."
                if not passed
                else "No environment-related failures detected."
            ),
            affected_tasks=[t.task_id for t in env_errors],
        )

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------

    def _build_summary(
        self,
        rules: list[VerificationRule],
        verdict: str,
        campaign: ApiTestCampaign,
    ) -> str:
        task_count = len(campaign.tasks)
        passed_rules = sum(1 for r in rules if r.passed)
        total_rules = len(rules)

        if verdict == "approved":
            return (
                f"✅ Campaign APPROVED: {passed_rules}/{total_rules} verification rules passed "
                f"across {task_count} tasks."
            )
        if verdict == "warning":
            warnings = [r.name for r in rules if not r.passed and r.severity == "warning"]
            return (
                f"⚠️ Campaign PASSED with warnings: {', '.join(warnings)}. "
                f"{passed_rules}/{total_rules} rules passed across {task_count} tasks."
            )
        errors = [r.name for r in rules if not r.passed and r.severity == "error"]
        return (
            f"❌ Campaign REJECTED: {', '.join(errors)} failed. "
            f"{passed_rules}/{total_rules} rules passed across {task_count} tasks."
        )


# Legacy constant for backward compatibility.
API_TESTING_VERIFICATION = {"policy": "api_contract_plus_status"}


__all__ = [
    "ApiTestingVerificationPolicy",
    "VerificationVerdict",
    "VerificationRule",
    "API_TESTING_VERIFICATION",
]

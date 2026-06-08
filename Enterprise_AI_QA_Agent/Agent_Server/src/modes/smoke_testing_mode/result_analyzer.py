from __future__ import annotations

from src.modes.smoke_testing_mode.contracts import (
    RegressionCandidateCase,
    SmokeExecutionPlan,
    SmokeRunResult,
    utc_now,
)


class SmokeResultAnalyzer:
    def finalize(self, *, plan: SmokeExecutionPlan, result: SmokeRunResult) -> tuple[SmokeRunResult, list[RegressionCandidateCase], str]:
        result.total_cases = len(plan.cases)
        result.selected_case_count = len(result.case_results)
        result.passed_cases = sum(1 for item in result.case_results if item.status == "passed")
        result.failed_cases = sum(1 for item in result.case_results if item.status == "failed")
        result.blocked_cases = sum(1 for item in result.case_results if item.status == "blocked")

        if result.selected_case_count == 0:
            result.status = "blocked"
            result.verdict = "blocked"
            result.summary = "没有选中可执行的冒烟用例。"
        elif result.failed_cases == 0 and result.blocked_cases == 0:
            result.status = "passed"
            result.verdict = "ready"
            result.summary = "冒烟测试准入通过，可以进入后续测试。"
        elif result.passed_cases > 0:
            result.status = "partial"
            result.verdict = "partial"
            result.summary = "冒烟测试部分通过，请优先处理失败或阻塞项。"
        else:
            result.status = "failed"
            result.verdict = "blocked"
            result.summary = "冒烟测试未通过，不建议进入后续测试。"

        result.completed_at = utc_now()
        candidates = self._build_regression_candidates(plan=plan, result=result)
        report = self._build_report(plan=plan, result=result, regression_candidates=candidates)
        return result, candidates, report

    def _build_regression_candidates(
        self,
        *,
        plan: SmokeExecutionPlan,
        result: SmokeRunResult,
    ) -> list[RegressionCandidateCase]:
        passed_ids = {item.case_id for item in result.case_results if item.status == "passed"}
        candidates: list[RegressionCandidateCase] = []
        for case in plan.cases:
            if case.case_id not in passed_ids:
                continue
            candidates.append(
                RegressionCandidateCase(
                    case_id=case.case_id,
                    source_plan_id=plan.plan_id,
                    source_run_id=result.run_id,
                    project_scope=plan.project_scope,
                    case_type=case.case_type,
                    title=case.title,
                    stability_score=100.0,
                    status="stable",
                    run_count=1,
                    pass_count=1,
                    fail_count=0,
                    blocked_count=0,
                    last_status="passed",
                    last_passed_at=result.completed_at,
                )
            )
        return candidates

    def _build_report(
        self,
        *,
        plan: SmokeExecutionPlan,
        result: SmokeRunResult,
        regression_candidates: list[RegressionCandidateCase],
    ) -> str:
        lines = [
            f"# 冒烟测试报告：{plan.title}",
            "",
            f"- Plan ID: {plan.plan_id}",
            f"- Run ID: {result.run_id}",
            f"- Project: {plan.project_scope}",
            f"- Target: {plan.target_url}",
            f"- Verdict: {result.verdict}",
            f"- Summary: {result.summary}",
            "",
            "## 统计",
            "",
            f"- 总用例数: {result.total_cases}",
            f"- 执行用例数: {result.selected_case_count}",
            f"- 通过: {result.passed_cases}",
            f"- 失败: {result.failed_cases}",
            f"- 阻塞: {result.blocked_cases}",
            f"- 回归候选: {len(regression_candidates)}",
            "",
            "## 用例结果",
        ]
        for item in result.case_results:
            lines.extend(
                [
                    "",
                    f"### {item.title}",
                    f"- Case ID: {item.case_id}",
                    f"- Type: {item.case_type}",
                    f"- Status: {item.status}",
                    f"- Summary: {item.summary}",
                    f"- Assertions: {item.passed_count}/{item.assertion_count}",
                ]
            )
            if item.failure_category:
                lines.append(f"- Failure Category: {item.failure_category}")
            for evidence in item.evidence:
                label = evidence.get("label") or evidence.get("type") or "evidence"
                detail = evidence.get("detail") or evidence.get("uri") or evidence.get("path") or ""
                lines.append(f"- Evidence: {label} {detail}".strip())
        return "\n".join(lines).strip()


def stability_score(*, run_count: int, pass_count: int, flaky_count: int = 0, recent_fail_count: int = 0, blocked_count: int = 0) -> float:
    if run_count <= 0:
        return 0.0
    score = 100.0 * pass_count / run_count
    score -= 15.0 * flaky_count
    score -= 25.0 * recent_fail_count
    score -= 10.0 * blocked_count
    return max(0.0, min(100.0, score))


from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import uuid4

from src.schemas.session import VerificationEvidence, VerificationResult, VerificationStatus


class VerificationService:
    def build_results(
        self,
        session_id: str,
        turn_id: str,
        trace_id: str,
        tool_results: list[dict[str, Any]],
        context_bundle: dict[str, Any] | None = None,
    ) -> list[VerificationResult]:
        results: list[VerificationResult] = []
        context_bundle = context_bundle or {}
        for item in tool_results:
            tool_key = str(item.get("tool_key") or "")
            output = item.get("output") if isinstance(item.get("output"), dict) else {}
            if tool_key == "api-tester":
                results.append(self._from_api_tester(session_id, turn_id, trace_id, item, output, context_bundle))
                continue
            if tool_key == "test-case-generator":
                results.append(self._from_test_case_generator(session_id, turn_id, trace_id, item, output))
                continue
            if tool_key == "browser-automation":
                results.append(self._from_browser_automation(session_id, turn_id, trace_id, item, output))
                continue
            if tool_key == "smoke-suite-runner":
                results.append(self._from_smoke_suite_runner(session_id, turn_id, trace_id, item, output))
                continue
        return results

    def _from_api_tester(
        self,
        session_id: str,
        turn_id: str,
        trace_id: str,
        tool_result: dict[str, Any],
        output: dict[str, Any],
        context_bundle: dict[str, Any],
    ) -> VerificationResult:
        checks = output.get("checks") if isinstance(output.get("checks"), list) else []
        passed_count = sum(1 for item in checks if isinstance(item, dict) and item.get("passed") is True)
        failed_count = sum(1 for item in checks if isinstance(item, dict) and item.get("passed") is False)
        status = VerificationStatus.passed if failed_count == 0 and checks else VerificationStatus.failed if failed_count > 0 else VerificationStatus.not_run
        if checks and failed_count == 0 and passed_count < len(checks):
            status = VerificationStatus.partial
        evidence = [
            VerificationEvidence(
                source_type="tool_result",
                source_id=str(tool_result.get("call_id") or tool_result.get("job_id") or uuid4()),
                label="api_checks",
                detail=str(output.get("summary") or tool_result.get("summary") or ""),
                metadata={
                    "endpoint": output.get("request", {}).get("endpoint") if isinstance(output.get("request"), dict) else "",
                    "method": output.get("request", {}).get("method") if isinstance(output.get("request"), dict) else "",
                    "verification_mode": bool(context_bundle.get("verification_mode")),
                },
            )
        ]
        return VerificationResult(
            id=str(uuid4()),
            session_id=session_id,
            turn_id=turn_id,
            trace_id=trace_id,
            verifier="api-tester",
            status=status,
            summary=str(output.get("summary") or tool_result.get("summary") or "API verification result captured."),
            assertion_count=len(checks),
            passed_count=passed_count,
            failed_count=failed_count,
            evidence=evidence,
            metadata={"tool_key": "api-tester", "tool_status": tool_result.get("status")},
            created_at=datetime.utcnow(),
        )

    def _from_test_case_generator(
        self,
        session_id: str,
        turn_id: str,
        trace_id: str,
        tool_result: dict[str, Any],
        output: dict[str, Any],
    ) -> VerificationResult:
        cases = output.get("cases") if isinstance(output.get("cases"), list) else []
        return VerificationResult(
            id=str(uuid4()),
            session_id=session_id,
            turn_id=turn_id,
            trace_id=trace_id,
            verifier="test-case-generator",
            status=VerificationStatus.not_run,
            summary=f"Generated {len(cases)} planned verification cases for downstream execution.",
            assertion_count=len(cases),
            passed_count=0,
            failed_count=0,
            evidence=[
                VerificationEvidence(
                    source_type="tool_result",
                    source_id=str(tool_result.get("call_id") or uuid4()),
                    label="planned_cases",
                    detail=str(tool_result.get("summary") or ""),
                    metadata={"case_count": len(cases)},
                )
            ],
            metadata={"tool_key": "test-case-generator", "coverage": output.get("coverage", {})},
            created_at=datetime.utcnow(),
        )

    def _from_browser_automation(
        self,
        session_id: str,
        turn_id: str,
        trace_id: str,
        tool_result: dict[str, Any],
        output: dict[str, Any],
    ) -> VerificationResult:
        steps = output.get("steps") if isinstance(output.get("steps"), list) else []
        artifacts = output.get("artifacts") if isinstance(output.get("artifacts"), list) else []
        status = VerificationStatus.passed if str(tool_result.get("status")) == "completed" else VerificationStatus.partial
        evidence = [
            VerificationEvidence(
                source_type="artifact",
                source_id=str(item.get("path") or item.get("label") or uuid4()),
                label=str(item.get("label") or item.get("type") or "artifact"),
                detail=str(item.get("path") or ""),
                metadata={k: v for k, v in item.items() if k not in {"label", "path"}},
            )
            for item in artifacts
            if isinstance(item, dict)
        ]
        return VerificationResult(
            id=str(uuid4()),
            session_id=session_id,
            turn_id=turn_id,
            trace_id=trace_id,
            verifier="browser-automation",
            status=status,
            summary=str(output.get("summary") or tool_result.get("summary") or "Browser verification evidence captured."),
            assertion_count=len(steps),
            passed_count=len(steps) if status == VerificationStatus.passed else 0,
            failed_count=0 if status == VerificationStatus.passed else max(0, len(steps) - 1),
            evidence=evidence,
            metadata={"tool_key": "browser-automation", "artifact_count": len(artifacts)},
            created_at=datetime.utcnow(),
        )

    def _from_smoke_suite_runner(
        self,
        session_id: str,
        turn_id: str,
        trace_id: str,
        tool_result: dict[str, Any],
        output: dict[str, Any],
    ) -> VerificationResult:
        run_result = output.get("run_result") if isinstance(output.get("run_result"), dict) else {}
        plan = output.get("plan") if isinstance(output.get("plan"), dict) else {}
        case_results = run_result.get("case_results") if isinstance(run_result.get("case_results"), list) else []
        assertion_count = sum(int(item.get("assertion_count") or 0) for item in case_results if isinstance(item, dict))
        passed_count = int(run_result.get("passed_cases") or 0)
        failed_count = int(run_result.get("failed_cases") or 0)
        blocked_count = int(run_result.get("blocked_cases") or 0)
        verdict = str(run_result.get("verdict") or output.get("phase") or "").strip()
        if verdict == "ready":
            status = VerificationStatus.passed
        elif verdict == "blocked" or failed_count > 0:
            status = VerificationStatus.failed
        elif verdict == "partial":
            status = VerificationStatus.partial
        else:
            status = VerificationStatus.not_run

        evidence: list[VerificationEvidence] = []
        for label, uri in [
            ("smoke_plan", output.get("plan_uri")),
            ("approved_plan", output.get("approved_plan_uri")),
            ("run_result", output.get("run_result_uri")),
            ("run_report", output.get("report_uri")),
        ]:
            if uri:
                evidence.append(
                    VerificationEvidence(
                        source_type="artifact",
                        source_id=str(uri),
                        label=label,
                        detail=str(uri),
                        metadata={"tool_key": "smoke-suite-runner"},
                    )
                )
        for case in case_results[:8]:
            if not isinstance(case, dict):
                continue
            evidence.append(
                VerificationEvidence(
                    source_type="tool_result",
                    source_id=str(case.get("case_id") or uuid4()),
                    label=str(case.get("status") or "smoke_case"),
                    detail=str(case.get("summary") or case.get("title") or ""),
                    metadata={
                        "case_type": case.get("case_type"),
                        "failure_category": case.get("failure_category"),
                    },
                )
            )

        return VerificationResult(
            id=str(uuid4()),
            session_id=session_id,
            turn_id=turn_id,
            trace_id=trace_id,
            verifier="冒烟测试结果",
            status=status,
            summary=str(run_result.get("summary") or output.get("summary") or tool_result.get("summary") or "冒烟测试方案已生成，等待确认。"),
            assertion_count=assertion_count,
            passed_count=passed_count,
            failed_count=failed_count,
            evidence=evidence,
            metadata={
                "tool_key": "smoke-suite-runner",
                "plan_id": output.get("plan_id") or plan.get("plan_id"),
                "plan_version": output.get("plan_version") or plan.get("version"),
                "verdict": verdict,
                "blocked_count": blocked_count,
                "selected_case_count": run_result.get("selected_case_count") or len(output.get("selected_case_ids") or []),
                "total_cases": run_result.get("total_cases") or len(plan.get("cases") or []),
                "report_uri": output.get("report_uri"),
                "approved_plan_uri": output.get("approved_plan_uri"),
            },
            created_at=datetime.utcnow(),
        )

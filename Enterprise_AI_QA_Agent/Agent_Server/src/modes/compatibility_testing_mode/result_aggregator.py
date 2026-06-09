from __future__ import annotations

from typing import Any

from src.modes.compatibility_testing_mode.contracts import (
    CaseRunResult,
    CompatibilityDispatchPlan,
    CompatibilityPlan,
    CompatibilityRun,
    EnvironmentRunResult,
)


class CompatibilityResultAggregator:
    def build_dispatch_run(
        self,
        *,
        plan: CompatibilityPlan,
        dispatch_plan: CompatibilityDispatchPlan,
        context: Any,
    ) -> CompatibilityRun:
        selected_case_ids_by_env = {
            task.environment_id: task.case_ids
            for task in dispatch_plan.tasks
        }
        results: list[EnvironmentRunResult] = []
        for environment in plan.environments:
            if environment.environment_id in selected_case_ids_by_env:
                case_ids = selected_case_ids_by_env[environment.environment_id]
                results.append(
                    EnvironmentRunResult(
                        environment_id=environment.environment_id,
                        status="ready_for_runner",
                        case_results=[
                            CaseRunResult(
                                case_id=case_id,
                                environment_id=environment.environment_id,
                                status="pending",
                                summary="等待 Runner 执行并回传结果。",
                            )
                            for case_id in case_ids
                        ],
                    )
                )
                continue
            if environment in dispatch_plan.skipped_environments:
                results.append(
                    EnvironmentRunResult(
                        environment_id=environment.environment_id,
                        status="skipped",
                        skipped=len(plan.cases),
                        case_results=[
                            CaseRunResult(
                                case_id=case.case_id,
                                environment_id=environment.environment_id,
                                status="skipped",
                                failure_type="environment_unavailable",
                                summary=environment.unavailable_reason or "环境 Provider/Runner 尚未接入。",
                            )
                            for case in plan.cases
                        ],
                    )
                )

        return CompatibilityRun(
            session_id=str(getattr(context, "session_id", "") or ""),
            phase="dispatching",
            plan_id=plan.plan_id,
            status="ready_for_runner",
            summary=(
                f"已生成 Runner 调度计划：{len(dispatch_plan.tasks)} 个可执行环境任务，"
                f"{len(dispatch_plan.skipped_environments)} 个环境待接入 Runner/Provider。"
            ),
            environment_results=results,
        )

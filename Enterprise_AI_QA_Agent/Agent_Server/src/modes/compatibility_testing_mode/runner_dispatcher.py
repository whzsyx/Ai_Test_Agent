from __future__ import annotations

from src.modes.compatibility_testing_mode.contracts import (
    CompatibilityCase,
    CompatibilityDispatchPlan,
    CompatibilityPlan,
    CompatibilityRunnerTask,
    EnvironmentSpec,
    RunnerSelector,
)
from src.modes.compatibility_testing_mode.mode_invoker import CompatibilityModeInvocationPlanner


class CompatibilityRunnerDispatcher:
    def __init__(self, mode_planner: CompatibilityModeInvocationPlanner | None = None) -> None:
        self._mode_planner = mode_planner or CompatibilityModeInvocationPlanner()

    def build_dispatch_plan(
        self,
        *,
        plan: CompatibilityPlan,
        selected_case_ids: list[str] | None = None,
        selected_environment_ids: list[str] | None = None,
    ) -> CompatibilityDispatchPlan:
        selected_cases = self._select_cases(plan.cases, selected_case_ids)
        selected_envs = self._select_environments(plan.environments, selected_environment_ids)
        tasks: list[CompatibilityRunnerTask] = []
        skipped: list[EnvironmentSpec] = []

        for environment in selected_envs:
            if environment.availability != "available":
                skipped.append(environment)
                continue
            tasks.append(
                CompatibilityRunnerTask(
                    environment_id=environment.environment_id,
                    case_ids=[case.case_id for case in selected_cases],
                    runner_selector=self.selector_for_environment(environment),
                    mode_calls=self._mode_planner.plan_calls(
                        product=plan.product,
                        environment=environment,
                        cases=selected_cases,
                    ),
                    metadata={
                        "product": plan.product.model_dump(),
                        "product_access_manifest": plan.product.access_manifest.model_dump() if plan.product.access_manifest else None,
                        "environment": environment.model_dump(),
                        "cases": [case.model_dump() for case in selected_cases],
                    },
                )
            )

        return CompatibilityDispatchPlan(
            plan_id=plan.plan_id,
            plan_version=plan.version,
            tasks=tasks,
            skipped_environments=skipped,
            total_case_runs=sum(len(task.case_ids) for task in tasks),
            notes=[
                "调度计划只包含 availability=available 的环境。",
                "missing_runner/missing_provider 环境会出现在 skipped_environments 中，待 Runner/Provider 接入后执行。",
            ],
        )

    def _select_cases(self, cases: list[CompatibilityCase], selected_ids: list[str] | None) -> list[CompatibilityCase]:
        if not selected_ids:
            return cases
        wanted = set(selected_ids)
        return [case for case in cases if case.case_id in wanted]

    def _select_environments(
        self,
        environments: list[EnvironmentSpec],
        selected_ids: list[str] | None,
    ) -> list[EnvironmentSpec]:
        if not selected_ids:
            return environments
        wanted = set(selected_ids)
        return [environment for environment in environments if environment.environment_id in wanted]

    def selector_for_environment(self, environment: EnvironmentSpec) -> RunnerSelector:
        capabilities = [environment.provider]
        if environment.automation_driver:
            capabilities.append(environment.automation_driver)
        if environment.browser:
            capabilities.append(environment.browser.lower())
        return RunnerSelector(
            provider=environment.provider,
            capabilities=sorted(set(capabilities)),
            os=environment.os,
            os_version=environment.os_version,
            browser=environment.browser,
            browser_version=environment.browser_version,
            device=environment.device,
        )

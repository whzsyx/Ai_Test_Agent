from __future__ import annotations

from typing import Any

from src.modes.compatibility_testing_mode.approval_policy import CompatibilityApprovalPolicy
from src.modes.compatibility_testing_mode.case_generator import CompatibilityCaseGenerator
from src.modes.compatibility_testing_mode.contracts import CompatibilityPlan, CompatibilityRun
from src.modes.compatibility_testing_mode.environment_matrix import CompatibilityEnvironmentMatrixBuilder
from src.modes.compatibility_testing_mode.product_intake import CompatibilityProductIntake
from src.modes.compatibility_testing_mode.product_probe import CompatibilityProductProbe
from src.modes.compatibility_testing_mode.result_aggregator import CompatibilityResultAggregator
from src.modes.compatibility_testing_mode.report_builder import CompatibilityReportBuilder
from src.modes.compatibility_testing_mode.runner_dispatcher import CompatibilityRunnerDispatcher


class CompatibilityTestingModeRuntime:
    def __init__(
        self,
        *,
        settings=None,
        coordinator_runtime_service=None,
        session_store=None,
        memory_runtime_service=None,
        runner_service=None,
        mode_call_bridge_enabled: bool = False,
    ) -> None:
        self._settings = settings
        self._coordinator_runtime_service = coordinator_runtime_service
        self._session_store = session_store
        self._memory_runtime_service = memory_runtime_service
        self._runner_service = runner_service
        self._mode_call_bridge_enabled = mode_call_bridge_enabled
        self._intake = CompatibilityProductIntake()
        self._probe = CompatibilityProductProbe()
        self._matrix_builder = CompatibilityEnvironmentMatrixBuilder()
        self._case_generator = CompatibilityCaseGenerator()
        self._approval_policy = CompatibilityApprovalPolicy()
        self._runner_dispatcher = CompatibilityRunnerDispatcher()
        self._result_aggregator = CompatibilityResultAggregator()
        self._report_builder = CompatibilityReportBuilder()

    def set_coordinator_runtime_service(self, svc) -> None:
        self._coordinator_runtime_service = svc

    def set_session_store(self, store) -> None:
        self._session_store = store

    def set_memory_runtime_service(self, svc) -> None:
        self._memory_runtime_service = svc

    async def handle(self, arguments: dict[str, Any], context: Any) -> dict[str, Any]:
        arguments = self._merge_context_arguments(arguments, context)
        action = str(arguments.get("action") or "draft_plan").strip().lower()
        if action in {"draft", "plan", "generate_plan"}:
            action = "draft_plan"
        if action in {"execute", "run"}:
            action = "execute_approved_plan"

        if action == "draft_plan":
            return await self._draft_plan(arguments, context)
        if action == "get_capabilities":
            return self._capabilities()
        if action == "execute_approved_plan":
            return await self._execute_approved_plan(arguments, context)
        return {
            "status": "failed",
            "ok": False,
            "phase": "failed",
            "summary": f"Unsupported compatibility-test-runner action: {action}",
            "error": "unsupported_action",
        }

    async def _draft_plan(self, arguments: dict[str, Any], context: Any) -> dict[str, Any]:
        product = self._intake.build_profile(arguments, context)
        probe = self._probe.summarize(product)
        environments = self._matrix_builder.build(product=product, probe=probe, arguments=arguments)
        environments = await self._reconcile_environment_runner_availability(environments)
        cases = self._case_generator.generate(product)
        risks = self._approval_policy.build_risks(product, cases)
        executable_env_count = sum(1 for item in environments if item.availability == "available")
        estimated_task_count = executable_env_count * len(cases)
        plan = CompatibilityPlan(
            product=product,
            probe=probe,
            environments=environments,
            cases=cases,
            risks=risks,
            estimated_task_count=estimated_task_count,
            estimated_duration_minutes=max(5, estimated_task_count * 3) if estimated_task_count else 0,
            notes=[
                "执行前必须由用户确认该计划、风险动作和人工接管点。",
                "第一版仅将 availability=available 的环境纳入自动执行；其他环境作为待接入 Provider 诊断展示。",
            ],
        )
        run = CompatibilityRun(
            session_id=str(getattr(context, "session_id", "") or ""),
            phase="awaiting_approval",
            plan_id=plan.plan_id,
            status="awaiting_user_confirmation",
            summary=f"兼容性测试计划已生成：{len(plan.environments)} 个环境、{len(plan.cases)} 条用例、{len(plan.risks)} 个风险项。",
        )
        report_markdown = self._report_builder.build_plan_markdown(plan)
        return {
            "status": "partial",
            "ok": True,
            "phase": "awaiting_approval",
            "summary": run.summary,
            "action": "draft_plan",
            "compatibility_run": run.model_dump(),
            "plan": plan.model_dump(),
            "report_markdown": report_markdown,
            "next_steps": [
                "请用户确认环境矩阵、测试用例、风险动作和人工接管点。",
                "确认后调用 execute_approved_plan；Runner/Provider 未接入的环境会保持 unavailable。",
                "后续执行阶段将调度 smoke_testing、ui_automation、api_testing 等模式。",
            ],
        }

    async def _reconcile_environment_runner_availability(self, environments):
        if self._runner_service is None:
            return environments
        reconciled = []
        for environment in environments:
            selector = self._runner_dispatcher.selector_for_environment(environment).model_dump()
            matches = await self._runner_service.find_matching_runners(selector)
            metadata = {
                **environment.metadata,
                "runner_selector": selector,
                "matching_runner_ids": [runner.runner_id for runner in matches],
            }
            if matches:
                reconciled.append(
                    environment.model_copy(
                        update={
                            "availability": "available",
                            "unavailable_reason": None,
                            "metadata": metadata,
                        }
                    )
                )
                continue
            if environment.availability == "available":
                reconciled.append(
                    environment.model_copy(
                        update={
                            "availability": "missing_runner",
                            "unavailable_reason": "当前没有注册且在线的 Runner 满足该环境能力要求。",
                            "metadata": metadata,
                        }
                    )
                )
            else:
                reconciled.append(environment.model_copy(update={"metadata": metadata}))
        return reconciled

    def _capabilities(self) -> dict[str, Any]:
        return {
            "status": "completed",
            "ok": True,
            "phase": "completed",
            "summary": "兼容性测试模式当前支持 Web/H5 计划生成与本地浏览器矩阵规划，移动端/小程序/Linux App Provider 按扩展接口接入。",
            "product_types": [
                "web",
                "h5",
                "android_app",
                "ios_app",
                "wechat_mini_program",
                "alipay_mini_program",
                "linux_app",
            ],
            "providers": [
                "local_browser",
                "macos_browser",
                "android_browser",
                "ios_browser",
                "android_appium",
                "ios_appium",
                "wechat_miniprogram",
                "alipay_miniprogram",
                "linux_app",
            ],
        }

    async def _execute_approved_plan(self, arguments: dict[str, Any], context: Any) -> dict[str, Any]:
        plan_data = arguments.get("plan") or arguments.get("approved_plan")
        if not isinstance(plan_data, dict):
            return {
                "status": "failed",
                "ok": False,
                "phase": "failed",
                "summary": "执行兼容性测试需要提供已确认的 plan 对象。",
                "action": "execute_approved_plan",
                "error": "missing_plan",
            }
        try:
            plan = CompatibilityPlan.model_validate(plan_data)
        except Exception as exc:
            return {
                "status": "failed",
                "ok": False,
                "phase": "failed",
                "summary": f"兼容性测试计划格式无效：{exc}",
                "action": "execute_approved_plan",
                "error": "invalid_plan",
            }

        selected_case_ids = self._string_list(arguments.get("selected_case_ids"))
        selected_environment_ids = self._string_list(arguments.get("selected_environment_ids"))
        known_case_ids = {case.case_id for case in plan.cases}
        known_environment_ids = {environment.environment_id for environment in plan.environments}
        selected_cases_provided = "selected_case_ids" in arguments and arguments.get("selected_case_ids") is not None
        selected_environments_provided = (
            "selected_environment_ids" in arguments and arguments.get("selected_environment_ids") is not None
        )
        if selected_cases_provided and not selected_case_ids:
            return {
                "status": "failed",
                "ok": False,
                "phase": "failed",
                "summary": "执行兼容性测试至少需要选择一条用例。",
                "action": "execute_approved_plan",
                "plan": plan.model_dump(),
                "error": "no_selected_cases",
            }
        if selected_environments_provided and not selected_environment_ids:
            return {
                "status": "failed",
                "ok": False,
                "phase": "failed",
                "summary": "执行兼容性测试至少需要选择一个环境。",
                "action": "execute_approved_plan",
                "plan": plan.model_dump(),
                "error": "no_selected_environments",
            }
        unknown_case_ids = [case_id for case_id in selected_case_ids if case_id not in known_case_ids]
        if unknown_case_ids:
            return {
                "status": "failed",
                "ok": False,
                "phase": "failed",
                "summary": "执行兼容性测试包含未知用例 ID：" + "、".join(unknown_case_ids[:5]),
                "action": "execute_approved_plan",
                "plan": plan.model_dump(),
                "error": "unknown_selected_cases",
                "unknown_case_ids": unknown_case_ids,
            }
        unknown_environment_ids = [
            environment_id for environment_id in selected_environment_ids if environment_id not in known_environment_ids
        ]
        if unknown_environment_ids:
            return {
                "status": "failed",
                "ok": False,
                "phase": "failed",
                "summary": "执行兼容性测试包含未知环境 ID：" + "、".join(unknown_environment_ids[:5]),
                "action": "execute_approved_plan",
                "plan": plan.model_dump(),
                "error": "unknown_selected_environments",
                "unknown_environment_ids": unknown_environment_ids,
            }
        selected_risks = self._selected_risks(plan, selected_case_ids if selected_cases_provided else None)
        if selected_risks and not bool(arguments.get("confirm_risks")):
            return {
                "status": "partial",
                "ok": True,
                "phase": "awaiting_approval",
                "summary": f"所选兼容性测试范围包含 {len(selected_risks)} 个风险/人工接管项，执行前需要显式确认 confirm_risks=true。",
                "action": "execute_approved_plan",
                "plan": plan.model_dump(),
                "risks": [risk.model_dump() for risk in selected_risks],
                "next_steps": [
                    "确认风险动作是否允许执行。",
                    "如仅允许执行安全子集，请通过 selected_case_ids / selected_environment_ids 缩小范围。",
                    "确认后再次调用 execute_approved_plan，并设置 confirm_risks=true。",
                ],
            }
        dispatch_plan = self._runner_dispatcher.build_dispatch_plan(
            plan=plan,
            selected_case_ids=selected_case_ids or None,
            selected_environment_ids=selected_environment_ids or None,
        )
        if not dispatch_plan.tasks:
            return {
                "status": "failed",
                "ok": False,
                "phase": "failed",
                "summary": "所选兼容性测试范围没有可执行 Runner/Provider 环境，未生成队列任务。",
                "action": "execute_approved_plan",
                "plan": plan.model_dump(),
                "dispatch_plan": dispatch_plan.model_dump(),
                "missing_components": ["available runner/provider"],
                "error": "no_runnable_environments",
                "next_steps": [
                    "选择 availability=available 的环境后重新派发。",
                    "或先注册满足所选环境能力要求的 Runner/Provider。",
                ],
            }
        run = self._result_aggregator.build_dispatch_run(
            plan=plan,
            dispatch_plan=dispatch_plan,
            context=context,
        )
        queued_tasks = []
        runner_summary = None
        if self._runner_service is not None:
            queued_tasks = [
                task.model_dump()
                for task in await self._runner_service.enqueue_dispatch_plan(dispatch_plan)
            ]
            runner_summary = (
                await self._runner_service.summarize_tasks(dispatch_id=dispatch_plan.dispatch_id)
            ).model_dump()
        missing_components = []
        if self._runner_service is None:
            missing_components.append("runner queue service")
        if (
            not self._mode_call_bridge_enabled
            and dispatch_plan.tasks
            and any(task.mode_calls for task in dispatch_plan.tasks)
        ):
            missing_components.append("mode invoker execution bridge")
        return {
            "status": "partial",
            "ok": True,
            "phase": "dispatching",
            "summary": run.summary,
            "action": "execute_approved_plan",
            "compatibility_run": run.model_dump(),
            "plan": plan.model_dump(),
            "dispatch_plan": dispatch_plan.model_dump(),
            "runner_queue": {
                "queued_task_count": len(queued_tasks),
                "tasks": queued_tasks,
                "backend": "in_memory" if self._runner_service is not None else "not_configured",
            },
            "runner_summary": runner_summary,
            "missing_components": missing_components,
            "next_steps": [
                "Runner 调用 /api/v1/compatibility/runners/{runner_id}/tasks/poll 拉取任务。",
                "Runner 执行每个 task.mode_calls 中的模式工具，并上传 artifact。",
                "result_aggregator 根据 Runner 回传结果生成最终兼容性矩阵报告。",
            ],
        }

    def _string_list(self, value: Any) -> list[str]:
        if value is None:
            return []
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return [str(value).strip()] if str(value).strip() else []

    def _selected_risks(self, plan: CompatibilityPlan, selected_case_ids: list[str] | None) -> list[Any]:
        if not selected_case_ids:
            return list(plan.risks)
        selected = set(selected_case_ids)
        return [risk for risk in plan.risks if not risk.case_id or risk.case_id in selected]

    def _merge_context_arguments(self, arguments: dict[str, Any], context: Any) -> dict[str, Any]:
        bundle = getattr(context, "context_bundle", None)
        if not isinstance(bundle, dict):
            return dict(arguments)
        request = bundle.get("compatibility_testing_request")
        if not isinstance(request, dict):
            request = {}
        merged = dict(arguments)
        compatibility_action = str(bundle.get("compatibility_action") or request.get("action") or "").strip()
        if compatibility_action and not merged.get("action"):
            merged["action"] = compatibility_action
        for key in (
            "plan",
            "approved_plan",
            "confirm_risks",
            "selected_case_ids",
            "selected_environment_ids",
            "product",
            "product_type",
            "target_url",
            "entrypoint",
            "priority_flows",
            "test_scope",
            "forbidden_actions",
            "manual_steps",
            "product_access_manifest",
            "access_manifest",
            "product_name",
            "product_version",
            "artifact",
            "artifact_type",
            "package_name",
            "activity",
            "bundle_id",
            "mini_program_path",
            "command",
            "base_api",
            "proxy",
            "requires_vpn",
            "exclude",
        ):
            if (key not in merged or merged.get(key) is None) and key in bundle:
                merged[key] = bundle[key]
            if (key not in merged or merged.get(key) is None) and key in request:
                merged[key] = request[key]
        return merged

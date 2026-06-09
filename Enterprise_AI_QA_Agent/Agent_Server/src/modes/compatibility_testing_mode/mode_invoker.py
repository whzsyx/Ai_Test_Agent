from __future__ import annotations

from src.modes.compatibility_testing_mode.contracts import (
    CompatibilityCase,
    CompatibilityModeCall,
    EnvironmentSpec,
    ProductProfile,
)


class CompatibilityModeInvocationPlanner:
    def plan_calls(
        self,
        *,
        product: ProductProfile,
        environment: EnvironmentSpec,
        cases: list[CompatibilityCase],
    ) -> list[CompatibilityModeCall]:
        calls = [
            CompatibilityModeCall(
                tool_key="smoke-suite-runner",
                reason="每个兼容环境先执行启动/打开/登录基线检查。",
                arguments={
                    "action": "draft_plan",
                    "objective": f"{environment.name} 兼容性基线检查",
                    "target_url": product.entrypoint,
                    "include_ui": product.product_type in {"web", "h5"},
                    "include_api": False,
                    "max_cases": 3,
                    "product": product.model_dump(),
                    "compatibility_environment": environment.model_dump(),
                    "compatibility_case_ids": [case.case_id for case in cases],
                    "external_runner_note": (
                        "非 Web/H5 产品由兼容性 Runner 根据 task.metadata 中的产品、环境和用例信息接管真实执行。"
                        if product.product_type not in {"web", "h5"}
                        else ""
                    ),
                },
            )
        ]
        if product.product_type in {"web", "h5"}:
            calls.append(
                CompatibilityModeCall(
                    tool_key="ui-automation-runner",
                    reason="Web/H5 环境使用 UI 自动化模式执行页面探索、核心流程和证据采集。",
                    arguments={
                        "target_url": product.entrypoint,
                        "objective": self._case_objective(cases),
                        "action": "explore_and_verify",
                        "max_pages": 6,
                        "max_interactions": 20,
                        "same_origin_only": True,
                        "compatibility_environment": environment.model_dump(),
                    },
                )
            )
        if product.product_type in {"web", "h5"} and product.entrypoint:
            calls.append(
                CompatibilityModeCall(
                    tool_key="api-test-runner",
                    reason="如存在 API 文档或接口上下文，执行前置数据准备和后置断言。",
                    arguments={
                        "objective": f"{environment.name} 兼容性测试接口前置/后置校验",
                        "target_url": product.entrypoint,
                        "compatibility_environment": environment.model_dump(),
                        "compatibility_case_ids": [case.case_id for case in cases],
                    },
                )
            )
        return calls

    def _case_objective(self, cases: list[CompatibilityCase]) -> str:
        names = [case.name for case in cases[:6]]
        if not names:
            return "执行兼容性基础 UI 检查"
        return "执行兼容性核心流程：" + "、".join(names)

from __future__ import annotations

from src.modes.compatibility_testing_mode.contracts import (
    CompatibilityCase,
    CompatibilityStep,
    ProductProfile,
)


class CompatibilityCaseGenerator:
    def generate(self, product: ProductProfile) -> list[CompatibilityCase]:
        cases: list[CompatibilityCase] = []
        cases.append(self._launch_case(product))
        if str(product.auth.strategy or "").strip().lower() not in {"none", "no_auth", "anonymous"}:
            cases.append(self._login_case(product))
        cases.extend(self._priority_flow_cases(product))
        cases.append(self._layout_case(product))
        return cases

    def _launch_case(self, product: ProductProfile) -> CompatibilityCase:
        return CompatibilityCase(
            name="启动/打开产品入口",
            priority="P0",
            applicable_product_types=[product.product_type],
            steps=[
                CompatibilityStep(action="open_or_launch", target=product.entrypoint or "product_artifact"),
                CompatibilityStep(action="wait_until_ready", target="main_surface"),
                CompatibilityStep(action="capture_screenshot", target="main_surface"),
            ],
            assertions=["产品入口可打开或应用可启动", "主界面在目标环境中可见"],
            notes=["所有环境执行前的基础可用性检查。"],
        )

    def _login_case(self, product: ProductProfile) -> CompatibilityCase:
        manual = bool(product.auth.manual_steps)
        return CompatibilityCase(
            name="登录/认证流程",
            priority="P0",
            applicable_product_types=[product.product_type],
            steps=[
                CompatibilityStep(action="navigate_or_tap", target="login_entry"),
                CompatibilityStep(action="fill", target="username", value_ref=product.auth.username_ref or "auth.username"),
                CompatibilityStep(action="fill", target="password", value_ref=product.auth.password_ref or "auth.password"),
                CompatibilityStep(action="submit", target="login_button"),
                CompatibilityStep(action="assert_visible", target="authenticated_home", assertion="登录后首页可见"),
            ],
            assertions=["测试账号可完成登录", "登录后页面/应用状态正确"],
            risk_level="medium" if manual else "low",
            requires_manual_approval=manual,
            notes=["如存在验证码、2FA 或扫码登录，需要人工接管。"] if manual else [],
        )

    def _priority_flow_cases(self, product: ProductProfile) -> list[CompatibilityCase]:
        flows = product.priority_flows or ["核心业务链路"]
        cases: list[CompatibilityCase] = []
        for index, flow in enumerate(flows[:8], start=1):
            cases.append(
                CompatibilityCase(
                    name=f"核心流程：{flow}",
                    priority="P1" if index > 1 else "P0",
                    applicable_product_types=[product.product_type],
                    steps=[
                        CompatibilityStep(action="start_flow", target=flow),
                        CompatibilityStep(action="execute_flow_steps", target=flow),
                        CompatibilityStep(action="assert_flow_success", target=flow, assertion="流程关键结果可见"),
                        CompatibilityStep(action="capture_screenshot", target=flow),
                    ],
                    assertions=[f"{flow} 在目标环境中可完成", "关键结果无功能或布局异常"],
                    notes=["具体选择器和动作由执行模式/Runner 基于页面或控件树解析。"],
                )
            )
        return cases

    def _layout_case(self, product: ProductProfile) -> CompatibilityCase:
        return CompatibilityCase(
            name="基础布局与交互兼容检查",
            priority="P2",
            applicable_product_types=[product.product_type],
            steps=[
                CompatibilityStep(action="scan_visible_surface", target="current_screen"),
                CompatibilityStep(action="detect_overflow_or_overlap", target="current_screen"),
                CompatibilityStep(action="collect_console_or_device_logs", target="runtime_logs"),
            ],
            assertions=["无明显遮挡、溢出、错位", "无阻塞级 JS/App/系统日志错误"],
            notes=["Web/H5 可结合浏览器 console/network；App/小程序可结合设备日志。"],
        )

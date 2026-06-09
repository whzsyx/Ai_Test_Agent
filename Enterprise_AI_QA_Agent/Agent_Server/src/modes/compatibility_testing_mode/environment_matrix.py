from __future__ import annotations

from typing import Any

from src.modes.compatibility_testing_mode.contracts import EnvironmentSpec, ProductProbeSummary, ProductProfile


class CompatibilityEnvironmentMatrixBuilder:
    def build(
        self,
        *,
        product: ProductProfile,
        probe: ProductProbeSummary,
        arguments: dict[str, Any],
    ) -> list[EnvironmentSpec]:
        requested = self._requested_environments(arguments)
        if requested:
            return [self._from_requested(item, product) for item in requested]
        if product.product_type in {"web", "h5"}:
            return self._web_defaults(product)
        if product.product_type == "android_app":
            return self._android_defaults(product)
        if product.product_type == "ios_app":
            return self._ios_defaults(product)
        if product.product_type == "wechat_mini_program":
            return self._wechat_defaults(product)
        if product.product_type == "alipay_mini_program":
            return self._alipay_defaults(product)
        if product.product_type == "linux_app":
            return self._linux_defaults(product)
        return [
            EnvironmentSpec(
                name="待补充产品类型后生成环境矩阵",
                priority="P0",
                product_types=["unknown"],
                provider="unresolved",
                availability="planned_only",
                unavailable_reason="产品类型不明确，无法匹配环境 Provider。",
            )
        ]

    def _web_defaults(self, product: ProductProfile) -> list[EnvironmentSpec]:
        product_types = [product.product_type]
        return [
            EnvironmentSpec(
                name="Windows / Chrome latest",
                priority="P0",
                product_types=product_types,
                provider="local_browser",
                os="Windows",
                browser="Chrome",
                browser_version="latest",
                viewport="1366x768",
                automation_driver="playwright",
                availability="available",
            ),
            EnvironmentSpec(
                name="Windows / Edge latest",
                priority="P0",
                product_types=product_types,
                provider="local_browser",
                os="Windows",
                browser="Edge",
                browser_version="latest",
                viewport="1366x768",
                automation_driver="playwright",
                availability="available",
            ),
            EnvironmentSpec(
                name="Linux / Firefox latest",
                priority="P1",
                product_types=product_types,
                provider="local_browser",
                os="Linux",
                browser="Firefox",
                browser_version="latest",
                viewport="1366x768",
                automation_driver="playwright",
                availability="available",
            ),
            EnvironmentSpec(
                name="macOS / Safari latest",
                priority="P1",
                product_types=product_types,
                provider="macos_browser",
                os="macOS",
                browser="Safari",
                browser_version="latest",
                viewport="1440x900",
                automation_driver="playwright",
                availability="missing_runner",
                unavailable_reason="需要 macOS Runner 或远程浏览器云 Provider。",
            ),
            EnvironmentSpec(
                name="Android 14 / Chrome mobile",
                priority="P2",
                product_types=product_types,
                provider="android_browser",
                os="Android",
                os_version="14",
                browser="Chrome",
                device="Pixel 7",
                viewport="412x915",
                automation_driver="playwright_or_appium",
                availability="missing_runner",
                unavailable_reason="需要 Android Runner、模拟器或设备云 Provider。",
            ),
            EnvironmentSpec(
                name="iOS 18 / Safari mobile",
                priority="P2",
                product_types=product_types,
                provider="ios_browser",
                os="iOS",
                os_version="18",
                browser="Safari",
                device="iPhone 16",
                viewport="393x852",
                automation_driver="appium_or_webkit",
                availability="missing_runner",
                unavailable_reason="需要 macOS/iOS Runner 或设备云 Provider。",
            ),
        ]

    def _android_defaults(self, product: ProductProfile) -> list[EnvironmentSpec]:
        return [
            EnvironmentSpec(
                name="Android 13 / Pixel",
                priority="P0",
                product_types=[product.product_type],
                provider="android_appium",
                os="Android",
                os_version="13",
                device="Pixel",
                automation_driver="appium",
                availability="missing_runner",
                unavailable_reason="需要 Android Emulator/真机 Runner 或设备云 Provider。",
            ),
            EnvironmentSpec(
                name="Android 14 / Pixel",
                priority="P0",
                product_types=[product.product_type],
                provider="android_appium",
                os="Android",
                os_version="14",
                device="Pixel",
                automation_driver="appium",
                availability="missing_runner",
                unavailable_reason="需要 Android Emulator/真机 Runner 或设备云 Provider。",
            ),
        ]

    def _ios_defaults(self, product: ProductProfile) -> list[EnvironmentSpec]:
        return [
            EnvironmentSpec(
                name="iOS 17 / iPhone",
                priority="P0",
                product_types=[product.product_type],
                provider="ios_appium",
                os="iOS",
                os_version="17",
                device="iPhone",
                automation_driver="appium_xcuitest",
                availability="missing_runner",
                unavailable_reason="需要 macOS Runner、iOS Simulator/真机或设备云 Provider。",
            ),
            EnvironmentSpec(
                name="iOS 18 / iPhone",
                priority="P0",
                product_types=[product.product_type],
                provider="ios_appium",
                os="iOS",
                os_version="18",
                device="iPhone",
                automation_driver="appium_xcuitest",
                availability="missing_runner",
                unavailable_reason="需要 macOS Runner、iOS Simulator/真机或设备云 Provider。",
            ),
        ]

    def _wechat_defaults(self, product: ProductProfile) -> list[EnvironmentSpec]:
        return [
            EnvironmentSpec(
                name="微信小程序 / Android 14",
                priority="P0",
                product_types=[product.product_type],
                provider="wechat_miniprogram",
                os="Android",
                os_version="14",
                automation_driver="miniprogram_automator",
                availability="missing_runner",
                unavailable_reason="需要微信开发者工具/真机微信客户端 Runner。",
            )
        ]

    def _alipay_defaults(self, product: ProductProfile) -> list[EnvironmentSpec]:
        return [
            EnvironmentSpec(
                name="支付宝小程序 / Android 14",
                priority="P0",
                product_types=[product.product_type],
                provider="alipay_miniprogram",
                os="Android",
                os_version="14",
                automation_driver="alipay_miniprogram_cli",
                availability="missing_runner",
                unavailable_reason="需要支付宝小程序 IDE/CLI 或真机支付宝客户端 Runner。",
            )
        ]

    def _linux_defaults(self, product: ProductProfile) -> list[EnvironmentSpec]:
        return [
            EnvironmentSpec(
                name="Linux / Ubuntu LTS",
                priority="P0",
                product_types=[product.product_type],
                provider="linux_app",
                os="Linux",
                os_version="Ubuntu LTS",
                automation_driver="cli_or_gui",
                availability="missing_runner",
                unavailable_reason="需要 Docker/VM/Xvfb/VNC 或远程 Linux Runner。",
            )
        ]

    def _requested_environments(self, arguments: dict[str, Any]) -> list[dict[str, Any]]:
        value = arguments.get("environments")
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
        return []

    def _from_requested(self, item: dict[str, Any], product: ProductProfile) -> EnvironmentSpec:
        return EnvironmentSpec(
            name=str(item.get("name") or item.get("id") or "自定义环境"),
            priority=item.get("priority") if item.get("priority") in {"P0", "P1", "P2"} else "P1",
            product_types=[product.product_type],
            provider=str(item.get("provider") or "custom"),
            os=item.get("os"),
            os_version=item.get("os_version"),
            browser=item.get("browser"),
            browser_version=item.get("browser_version"),
            device=item.get("device"),
            viewport=item.get("viewport"),
            automation_driver=item.get("automation_driver"),
            availability=item.get("availability") if item.get("availability") in {"available", "missing_provider", "missing_runner", "planned_only"} else "planned_only",
            unavailable_reason=item.get("unavailable_reason"),
            metadata={key: value for key, value in item.items() if key not in {"name", "priority", "provider"}},
        )

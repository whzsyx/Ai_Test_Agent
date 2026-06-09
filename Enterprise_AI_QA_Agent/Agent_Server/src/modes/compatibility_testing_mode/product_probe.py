from __future__ import annotations

from src.modes.compatibility_testing_mode.contracts import ProductProbeSummary, ProductProfile


class CompatibilityProductProbe:
    def summarize(self, product: ProductProfile) -> ProductProbeSummary:
        if product.product_type in {"web", "h5"}:
            capabilities = ["browser_ui", "api_validation", "artifact_capture"]
            providers = ["local_browser"]
            notes = ["第一版可通过本地 Playwright Provider 执行 Chrome/Edge/Firefox。"]
        elif product.product_type == "android_app":
            capabilities = ["mobile_ui", "device_logs", "artifact_capture"]
            providers = ["android_appium"]
            notes = ["需要 Android Emulator、真机 Runner 或设备云 Provider。"]
        elif product.product_type == "ios_app":
            capabilities = ["mobile_ui", "device_logs", "artifact_capture"]
            providers = ["ios_appium"]
            notes = ["需要 macOS Runner、iOS Simulator/真机或设备云 Provider。"]
        elif product.product_type == "wechat_mini_program":
            capabilities = ["mini_program_ui", "client_logs", "artifact_capture"]
            providers = ["wechat_miniprogram"]
            notes = ["需要微信开发者工具、真机微信客户端或小程序设备 Provider。"]
        elif product.product_type == "alipay_mini_program":
            capabilities = ["mini_program_ui", "client_logs", "artifact_capture"]
            providers = ["alipay_miniprogram"]
            notes = ["需要支付宝小程序 IDE/CLI、真机支付宝客户端或设备 Provider。"]
        elif product.product_type == "linux_app":
            capabilities = ["desktop_or_cli", "system_logs", "artifact_capture"]
            providers = ["linux_app"]
            notes = ["需要 Docker、VM、Xvfb/VNC 或远程 Linux Runner。"]
        else:
            capabilities = []
            providers = []
            notes = ["产品类型不明确，需要补充入口、安装包或 AppID 信息。"]

        manual_points = list(product.auth.manual_steps)
        if product.auth.strategy in {"manual_login", "manual"}:
            manual_points.append("manual_login")

        blocking = []
        if product.product_type == "unknown":
            blocking.append("product_type")
        if product.product_type in {"web", "h5"} and not product.entrypoint:
            blocking.append("entrypoint")

        return ProductProbeSummary(
            product_type=product.product_type,
            automation_capabilities=capabilities,
            required_providers=providers,
            manual_intervention_points=sorted(set(manual_points)),
            blocking_requirements=blocking,
            confidence="high" if product.product_type != "unknown" else "low",
            notes=notes,
        )

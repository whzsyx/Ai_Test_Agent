from __future__ import annotations

from src.modes.compatibility_testing_mode.contracts import (
    CompatibilityCase,
    CompatibilityRiskItem,
    ProductProfile,
)


class CompatibilityApprovalPolicy:
    HIGH_RISK_KEYWORDS = {
        "支付": "real_payment",
        "付款": "real_payment",
        "删除": "delete_data",
        "提交订单": "submit_order",
        "下单": "submit_order",
        "发消息": "send_message",
        "发送": "send_message",
        "修改配置": "modify_configuration",
        "生产": "production_access",
    }

    def build_risks(self, product: ProductProfile, cases: list[CompatibilityCase]) -> list[CompatibilityRiskItem]:
        risks: list[CompatibilityRiskItem] = []
        for action in product.forbidden_actions:
            risks.append(
                CompatibilityRiskItem(
                    action=action,
                    level="high",
                    reason="产品接入策略声明该动作禁止或需审批。",
                    suggested_control="执行计划中跳过该动作，或改为沙箱数据并由用户显式确认。",
                )
            )

        for case in cases:
            haystack = f"{case.name} {' '.join(step.target or '' for step in case.steps)}"
            for keyword, action in self.HIGH_RISK_KEYWORDS.items():
                if keyword in haystack:
                    case.risk_level = "high"
                    case.requires_manual_approval = True
                    risks.append(
                        CompatibilityRiskItem(
                            case_id=case.case_id,
                            action=action,
                            level="high",
                            reason=f"用例包含潜在高风险动作：{keyword}。",
                            suggested_control="执行到确认页停止、使用沙箱账号/数据，或请求用户人工确认后继续。",
                        )
                    )

        if product.auth.manual_steps:
            risks.append(
                CompatibilityRiskItem(
                    action="manual_intervention",
                    level="medium",
                    reason="登录或业务流程包含验证码、扫码、2FA 等人工接管节点。",
                    suggested_control="Runner 执行到该节点暂停，等待用户接管或提供临时凭据。",
                )
            )
        return risks

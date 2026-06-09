from __future__ import annotations

from src.modes.compatibility_testing_mode.contracts import CompatibilityPlan


class CompatibilityReportBuilder:
    def build_plan_markdown(self, plan: CompatibilityPlan) -> str:
        available = sum(1 for item in plan.environments if item.availability == "available")
        unavailable = len(plan.environments) - available
        lines = [
            "# 兼容性测试计划",
            "",
            f"- 产品：{plan.product.name}",
            f"- 类型：{plan.product.product_type}",
            f"- 环境数：{len(plan.environments)}（可执行 {available}，待接入 {unavailable}）",
            f"- 用例数：{len(plan.cases)}",
            f"- 风险项：{len(plan.risks)}",
            f"- 预计任务数：{plan.estimated_task_count}",
            f"- 预计耗时：约 {plan.estimated_duration_minutes} 分钟",
            "",
            "## 环境矩阵",
        ]
        for env in plan.environments:
            suffix = "" if env.availability == "available" else f" - {env.unavailable_reason or env.availability}"
            lines.append(f"- [{env.priority}] {env.name} ({env.provider}, {env.availability}){suffix}")
        lines.extend(["", "## 测试用例"])
        for case in plan.cases:
            approval = "，需审批" if case.requires_manual_approval else ""
            lines.append(f"- [{case.priority}] {case.name}（风险：{case.risk_level}{approval}）")
        if plan.risks:
            lines.extend(["", "## 风险与人工接管"])
            for risk in plan.risks:
                lines.append(f"- {risk.action}：{risk.reason} 建议：{risk.suggested_control}")
        return "\n".join(lines)

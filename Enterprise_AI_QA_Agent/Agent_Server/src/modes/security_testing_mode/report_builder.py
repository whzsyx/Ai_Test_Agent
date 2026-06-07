"""Security Testing Mode report builder."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from src.modes.security_testing_mode.campaign_state import (
    FindingRecord,
    SecurityCampaign,
    SecurityReport,
)
from src.modes.security_testing_mode.contracts import (
    RISK_CRITICAL,
    RISK_HIGH,
    RISK_INFO,
    RISK_LOW,
    RISK_MEDIUM,
    SEVERITY_ORDER,
    TASK_COMPLETED,
    TASK_FAILED,
    TASK_SKIPPED,
)


class SecurityReportBuilder:
    """Build structured, Markdown, and artifact security reports."""

    def build_report(self, campaign: SecurityCampaign) -> SecurityReport:
        findings = list(campaign.findings or [])
        tasks = list(campaign.tasks or [])

        completed = sum(1 for task in tasks if task.status == TASK_COMPLETED)
        failed = sum(1 for task in tasks if task.status == TASK_FAILED)
        skipped = sum(1 for task in tasks if task.status == TASK_SKIPPED)

        severity_counts = {
            RISK_CRITICAL: sum(1 for item in findings if item.severity == RISK_CRITICAL),
            RISK_HIGH: sum(1 for item in findings if item.severity == RISK_HIGH),
            RISK_MEDIUM: sum(1 for item in findings if item.severity == RISK_MEDIUM),
            RISK_LOW: sum(1 for item in findings if item.severity == RISK_LOW),
            RISK_INFO: sum(1 for item in findings if item.severity == RISK_INFO),
        }

        duration = self._duration_seconds(campaign.created_at, campaign.updated_at)
        target_summary = self._target_summary(campaign)
        recommendations = self._build_recommendations(findings)
        limitations = self._build_limitations(
            failed=failed,
            skipped=skipped,
            operational_constraints=list(campaign.operational_constraints or []),
        )

        return SecurityReport(
            campaign_id=campaign.campaign_id,
            title=f"安全测试报告 - {target_summary[:80] or campaign.campaign_id[:8]}",
            target_summary=target_summary,
            scope_description=campaign.scope_notes or campaign.objective,
            executive_summary=self._build_executive_summary(
                findings=findings,
                completed=completed,
                failed=failed,
                critical=severity_counts[RISK_CRITICAL],
                high=severity_counts[RISK_HIGH],
                medium=severity_counts[RISK_MEDIUM],
            ),
            total_tasks=len(tasks),
            completed_tasks=completed,
            failed_tasks=failed,
            skipped_tasks=skipped,
            total_findings=len(findings),
            critical_count=severity_counts[RISK_CRITICAL],
            high_count=severity_counts[RISK_HIGH],
            medium_count=severity_counts[RISK_MEDIUM],
            low_count=severity_counts[RISK_LOW],
            info_count=severity_counts[RISK_INFO],
            findings=findings,
            activities=list(campaign.activities or []),
            assets_discovered=len(campaign.assets or []),
            services_discovered=len(campaign.fingerprints or []),
            evidence_count=len(campaign.evidence or []),
            execution_record_count=len(campaign.execution_records or []),
            duration_seconds=duration,
            tested_at=campaign.created_at,
            generated_at=datetime.now(timezone.utc).isoformat(),
            recommendations=recommendations,
            limitations=limitations,
        )

    def build_markdown(self, report: SecurityReport) -> str:
        lines: list[str] = [
            f"# {report.title}",
            "",
            f"**报告名称**：{report.title}",
            f"**生成日期**：{self._date_part(report.generated_at)}",
            f"**生成时间**：{self._time_part(report.generated_at)}",
            f"**测试目标**：{report.target_summary}",
            f"**执行耗时**：{report.duration_seconds:.0f} 秒",
            "",
            "## 执行摘要",
            "",
            report.executive_summary or "本次运行未生成摘要。",
            "",
            "## 测试结果",
            "",
            f"- 任务总数：{report.total_tasks}",
            f"- 已完成：{report.completed_tasks}",
            f"- 失败：{report.failed_tasks}",
            f"- 跳过：{report.skipped_tasks}",
            f"- 发现资产：{report.assets_discovered}",
            f"- 发现服务：{report.services_discovered}",
            f"- 执行记录：{report.execution_record_count}",
            f"- 证据产物：{report.evidence_count}",
            "",
            "## 风险等级概览",
            "",
            "| 风险等级 | 数量 |",
            "|---|---:|",
            f"| 严重 | {report.critical_count} |",
            f"| 高危 | {report.high_count} |",
            f"| 中危 | {report.medium_count} |",
            f"| 低危 | {report.low_count} |",
            f"| 信息 | {report.info_count} |",
            "",
            "## Agent 执行情况",
            "",
        ]

        if report.activities:
            lines.extend([
                f"执行策略：{self._execution_strategy(report.activities)}",
                "",
                "| Agent | 任务 | 动作 | 执行模式 | 执行内容 |",
                "|---|---|---|---|---|",
            ])
            for activity in report.activities:
                lines.append(
                    f"| {activity.agent_name or activity.agent_key} | "
                    f"{activity.task_id} | {activity.action} | "
                    f"{activity.execution_mode or 'unknown'} | "
                    f"{self._table_text(activity.summary or activity.notes)} |"
                )
        else:
            lines.append("未记录到 worker 执行活动。")

        lines.extend(["", "## 发现、风险与错误", ""])
        if report.findings:
            for index, finding in enumerate(self._sort_findings(report.findings), start=1):
                lines.extend(self._render_finding_markdown(index, finding))
                lines.append("")
        else:
            lines.append("本次运行未产生已验证的安全发现。")
            lines.append("")

        lines.extend(["## 修复建议", ""])
        if report.recommendations:
            for index, recommendation in enumerate(report.recommendations, start=1):
                lines.append(f"{index}. {recommendation}")
        else:
            lines.append("本次运行未生成额外修复建议。")

        if report.limitations:
            lines.extend(["", "## 测试限制", ""])
            for limitation in report.limitations:
                lines.append(f"- {limitation}")

        lines.extend(["", "---", "由安全测试模式生成。"])
        return "\n".join(lines)

    def build_json_payload(self, report: SecurityReport) -> dict[str, Any]:
        return report.model_dump(mode="json")

    def build_artifacts(
        self,
        report: SecurityReport,
        markdown_report: str,
        html_report: str = "",
    ) -> list[dict[str, Any]]:
        artifacts: list[dict[str, Any]] = [
            {
                "type": "report_markdown",
                "filename": f"security_report_{report.campaign_id[:8]}.md",
                "label": "安全测试报告（Markdown）",
                "content_type": "text/markdown",
                "content": markdown_report,
            },
            {
                "type": "report_json",
                "filename": f"security_report_{report.campaign_id[:8]}.json",
                "label": "安全测试报告（JSON）",
                "content_type": "application/json",
                "content": json.dumps(self.build_json_payload(report), ensure_ascii=False, indent=2),
            },
        ]
        if html_report:
            artifacts.append(
                {
                    "type": "report_html",
                    "filename": f"security_report_{report.campaign_id[:8]}.html",
                    "label": "安全测试报告（HTML）",
                    "content_type": "text/html",
                    "content": html_report,
                }
            )
        return artifacts

    def _build_executive_summary(
        self,
        *,
        findings: list[FindingRecord],
        completed: int,
        failed: int,
        critical: int,
        high: int,
        medium: int,
    ) -> str:
        if not findings:
            return (
                f"本次安全测试完成 {completed} 个任务，未产生已验证的安全发现。"
                "在将目标视为无风险前，请先查看测试限制部分。"
            )

        summary = [
            f"本次安全测试完成 {completed} 个任务，产生 {len(findings)} 个发现。",
        ]
        if critical:
            summary.append(f"其中 {critical} 个为严重风险，应立即处理。")
        elif high:
            summary.append(f"其中 {high} 个为高危风险，应优先处理。")
        elif medium:
            summary.append(f"其中 {medium} 个为中危风险，应纳入修复计划。")
        if failed:
            summary.append(f"有 {failed} 个任务执行失败，因此覆盖范围可能不完整。")
        return " ".join(summary)

    def _build_recommendations(self, findings: list[FindingRecord]) -> list[str]:
        recommendations: list[str] = []
        seen: set[str] = set()
        for finding in self._sort_findings(findings):
            recommendation = finding.recommendation.strip()
            if recommendation and recommendation not in seen:
                recommendations.append(recommendation)
                seen.add(recommendation)
        if findings and not recommendations:
            recommendations.append("逐项复核发现、验证暴露面，并修复受影响的服务或安全控制。")
        return recommendations[:10]

    def _build_limitations(
        self,
        *,
        failed: int,
        skipped: int,
        operational_constraints: list[str],
    ) -> list[str]:
        limitations: list[str] = []
        for constraint in operational_constraints:
            value = str(constraint or "").strip()
            if value and value not in limitations:
                limitations.append(value)
        if failed:
            limitations.append(f"{failed} 个任务执行失败，相关覆盖范围可能不完整。")
        if skipped:
            limitations.append(f"{skipped} 个任务因依赖条件未满足而被跳过。")
        return limitations

    def _render_finding_markdown(self, index: int, finding: FindingRecord) -> list[str]:
        lines = [
            f"### {index}. {finding.title or '未命名发现'}",
            "",
            f"- **风险等级**：{self._severity_label(finding.severity)}",
            f"- **类别**：{finding.category or '未知'}",
            f"- **受影响目标**：{finding.affected_target or '未知'}",
        ]
        if finding.affected_port:
            lines.append(f"- **受影响端口**：{finding.affected_port}")
        if finding.affected_service:
            lines.append(f"- **受影响服务**：{finding.affected_service}")
        if finding.cve_id:
            lines.append(f"- **CVE**: {finding.cve_id}")
        if finding.cvss_score:
            lines.append(f"- **CVSS**: {finding.cvss_score}")
        lines.extend([
            f"- **置信度**：{finding.confidence}",
            f"- **是否验证**：{'是' if finding.verified else '否'}",
            "",
        ])
        if finding.description:
            lines.extend(["**描述**", "", finding.description, ""])
        if finding.evidence_summary:
            lines.extend(["**证据**", "", f"```text\n{finding.evidence_summary[:1200]}\n```", ""])
        lines.extend(["**复现方式**", ""])
        if finding.reproduction_steps:
            for step_index, step in enumerate(finding.reproduction_steps, start=1):
                lines.append(f"{step_index}. {step}")
        else:
            lines.append("未记录复现步骤。")
        if finding.recommendation:
            lines.extend(["", "**修复建议**", "", finding.recommendation])
        return lines

    def _target_summary(self, campaign: SecurityCampaign) -> str:
        parts = [
            f"{target.value} ({target.target_type})"
            for target in campaign.targets
            if target.value
        ]
        return ", ".join(parts) if parts else campaign.objective

    def _duration_seconds(self, started_at: str, completed_at: str) -> float:
        if not started_at:
            return 0.0
        try:
            start = datetime.fromisoformat(started_at)
            end = datetime.fromisoformat(completed_at) if completed_at else datetime.now(timezone.utc)
            return max(0.0, (end - start).total_seconds())
        except (TypeError, ValueError):
            return 0.0

    def _sort_findings(self, findings: list[FindingRecord]) -> list[FindingRecord]:
        return sorted(
            findings,
            key=lambda item: SEVERITY_ORDER.get(item.severity, 0),
            reverse=True,
        )

    def _date_part(self, value: str) -> str:
        return value.split("T", 1)[0] if value else ""

    def _time_part(self, value: str) -> str:
        if not value or "T" not in value:
            return ""
        return value.split("T", 1)[1].split(".", 1)[0]

    def _table_text(self, value: str) -> str:
        return str(value or "").replace("|", "\\|").replace("\n", " ")[:180]

    def _execution_strategy(self, activities: list[Any]) -> str:
        modes = sorted({
            str(getattr(activity, "execution_mode", "") or "").strip()
            for activity in activities
            if str(getattr(activity, "execution_mode", "") or "").strip()
        })
        if not modes:
            return "unknown"
        if len(modes) == 1:
            return modes[0]
        return ", ".join(modes)

    def _severity_label(self, severity: str) -> str:
        return {
            RISK_CRITICAL: "严重",
            RISK_HIGH: "高危",
            RISK_MEDIUM: "中危",
            RISK_LOW: "低危",
            RISK_INFO: "信息",
        }.get(str(severity or "").lower(), str(severity or "未知").upper())


__all__ = ["SecurityReportBuilder"]

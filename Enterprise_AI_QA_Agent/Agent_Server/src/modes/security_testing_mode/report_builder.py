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
        limitations = self._build_limitations(failed=failed, skipped=skipped)

        return SecurityReport(
            campaign_id=campaign.campaign_id,
            title=f"Security Test Report - {target_summary[:80] or campaign.campaign_id[:8]}",
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
            f"**Name**: {report.title}",
            f"**Date**: {self._date_part(report.generated_at)}",
            f"**Time**: {self._time_part(report.generated_at)}",
            f"**Target**: {report.target_summary}",
            f"**Duration**: {report.duration_seconds:.0f}s",
            "",
            "## Executive Summary",
            "",
            report.executive_summary or "No summary was generated.",
            "",
            "## Test Result",
            "",
            f"- Total tasks: {report.total_tasks}",
            f"- Completed: {report.completed_tasks}",
            f"- Failed: {report.failed_tasks}",
            f"- Skipped: {report.skipped_tasks}",
            f"- Assets discovered: {report.assets_discovered}",
            f"- Services discovered: {report.services_discovered}",
            f"- Execution records: {report.execution_record_count}",
            f"- Evidence artifacts: {report.evidence_count}",
            "",
            "## Severity Overview",
            "",
            "| Severity | Count |",
            "|---|---:|",
            f"| Critical | {report.critical_count} |",
            f"| High | {report.high_count} |",
            f"| Medium | {report.medium_count} |",
            f"| Low | {report.low_count} |",
            f"| Info | {report.info_count} |",
            "",
            "## Agents Used",
            "",
        ]

        if report.activities:
            lines.extend([
                "| Agent | Task | Action | What it did |",
                "|---|---|---|---|",
            ])
            for activity in report.activities:
                lines.append(
                    f"| {activity.agent_name or activity.agent_key} | "
                    f"{activity.task_id} | {activity.action} | "
                    f"{self._table_text(activity.summary or activity.notes)} |"
                )
        else:
            lines.append("No worker activity was recorded.")

        lines.extend(["", "## Findings, Risks, And Errors", ""])
        if report.findings:
            for index, finding in enumerate(self._sort_findings(report.findings), start=1):
                lines.extend(self._render_finding_markdown(index, finding))
                lines.append("")
        else:
            lines.append("No verified security findings were produced by this run.")
            lines.append("")

        lines.extend(["## Recommendations", ""])
        if report.recommendations:
            for index, recommendation in enumerate(report.recommendations, start=1):
                lines.append(f"{index}. {recommendation}")
        else:
            lines.append("No additional remediation recommendations were generated.")

        if report.limitations:
            lines.extend(["", "## Limitations", ""])
            for limitation in report.limitations:
                lines.append(f"- {limitation}")

        lines.extend(["", "---", "Generated by Security Testing Mode."])
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
                "label": "Security report (Markdown)",
                "content_type": "text/markdown",
                "content": markdown_report,
            },
            {
                "type": "report_json",
                "filename": f"security_report_{report.campaign_id[:8]}.json",
                "label": "Security report (JSON)",
                "content_type": "application/json",
                "content": json.dumps(self.build_json_payload(report), ensure_ascii=False, indent=2),
            },
        ]
        if html_report:
            artifacts.append(
                {
                    "type": "report_html",
                    "filename": f"security_report_{report.campaign_id[:8]}.html",
                    "label": "Security report (HTML)",
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
                f"The campaign completed {completed} task(s) and did not produce verified findings. "
                "Review the limitations section before treating this as a clean bill of health."
            )

        summary = [
            f"The campaign completed {completed} task(s) and produced {len(findings)} finding(s).",
        ]
        if critical:
            summary.append(f"{critical} finding(s) are critical and should be handled immediately.")
        elif high:
            summary.append(f"{high} finding(s) are high severity and should be prioritized.")
        elif medium:
            summary.append(f"{medium} finding(s) are medium severity and should be scheduled for remediation.")
        if failed:
            summary.append(f"{failed} task(s) failed, so coverage may be incomplete.")
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
            recommendations.append("Review each finding, validate exposure, and remediate the affected service or control.")
        return recommendations[:10]

    def _build_limitations(self, *, failed: int, skipped: int) -> list[str]:
        limitations: list[str] = []
        if failed:
            limitations.append(f"{failed} task(s) failed; related coverage may be incomplete.")
        if skipped:
            limitations.append(f"{skipped} task(s) were skipped because dependencies did not complete.")
        return limitations

    def _render_finding_markdown(self, index: int, finding: FindingRecord) -> list[str]:
        lines = [
            f"### {index}. {finding.title or 'Untitled finding'}",
            "",
            f"- **Severity**: {finding.severity.upper()}",
            f"- **Category**: {finding.category or 'unknown'}",
            f"- **Affected target**: {finding.affected_target or 'unknown'}",
        ]
        if finding.affected_port:
            lines.append(f"- **Affected port**: {finding.affected_port}")
        if finding.affected_service:
            lines.append(f"- **Affected service**: {finding.affected_service}")
        if finding.cve_id:
            lines.append(f"- **CVE**: {finding.cve_id}")
        if finding.cvss_score:
            lines.append(f"- **CVSS**: {finding.cvss_score}")
        lines.extend([
            f"- **Confidence**: {finding.confidence}",
            f"- **Verified**: {'yes' if finding.verified else 'no'}",
            "",
        ])
        if finding.description:
            lines.extend(["**Description**", "", finding.description, ""])
        if finding.evidence_summary:
            lines.extend(["**Evidence**", "", f"```text\n{finding.evidence_summary[:1200]}\n```", ""])
        lines.extend(["**How To Reproduce**", ""])
        if finding.reproduction_steps:
            for step_index, step in enumerate(finding.reproduction_steps, start=1):
                lines.append(f"{step_index}. {step}")
        else:
            lines.append("No reproduction steps were captured.")
        if finding.recommendation:
            lines.extend(["", "**Recommendation**", "", finding.recommendation])
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


__all__ = ["SecurityReportBuilder"]

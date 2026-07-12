"""API Testing Mode HTML report template renderer.

Renders the api_testing_report.html template with campaign data,
producing a self-contained HTML file suitable for email or artifact storage.
"""
from __future__ import annotations

import html
from pathlib import Path
from typing import Any

from src.modes.api_testing_mode.campaign_state import ApiTestCampaign, CampaignReport
from src.modes.api_testing_mode.contracts import TASK_COMPLETED, TASK_FAILED, TASK_SKIPPED
from src.modes.api_testing_mode.evaluation import EvaluationResult
from src.modes.api_testing_mode.verification import VerificationVerdict


_TEMPLATE_PATH = Path(__file__).resolve().parents[2] / "templates" / "api_testing_report.html"


class ApiTestingReportTemplate:
    """Render the API testing HTML report from campaign results."""

    def render(
        self,
        *,
        campaign: ApiTestCampaign,
        report: CampaignReport,
        verification: VerificationVerdict | None = None,
        evaluation: EvaluationResult | None = None,
    ) -> str:
        template = self._load_template()

        # Verdict styling
        verdict = verification.verdict if verification else "unknown"
        verdict_icon, verdict_label, verdict_class, _, _ = self._verdict_style(verdict)
        verdict_summary = verification.summary if verification else report.summary

        # Quality score
        quality_score = str(int(evaluation.quality_score.overall)) if evaluation else "—"
        grade = evaluation.quality_score.grade if evaluation else "—"
        reliability = f"{evaluation.quality_score.reliability:.0f}" if evaluation else "—"
        performance = f"{evaluation.quality_score.performance:.0f}" if evaluation else "—"
        coverage = f"{evaluation.quality_score.coverage:.0f}" if evaluation else "—"
        penalty = f"{evaluation.quality_score.severity_penalty:.0f}" if evaluation else "0"

        # Duration
        duration_ms = report.duration_ms
        if duration_ms >= 60000:
            duration_label = f"{duration_ms / 60000:.1f}m"
        elif duration_ms >= 1000:
            duration_label = f"{duration_ms / 1000:.1f}s"
        else:
            duration_label = f"{duration_ms:.0f}ms"

        # Findings section
        findings_html = self._render_findings(report.findings)

        # Task rows
        task_rows_html = self._render_task_rows(report.tasks)

        # Recommendations
        recommendations_html = self._render_recommendations(evaluation)

        # Title
        title = f"{campaign.project_name or 'API'} - {campaign.objective or 'Interface Test Report'}"

        replacements = {
            "{{ title }}": html.escape(title),
            "{{ time_label }}": html.escape(report.generated_at or ""),
            "{{ verdict_icon }}": verdict_icon,
            "{{ verdict_label }}": html.escape(verdict_label),
            "{{ verdict_class }}": verdict_class,
            "{{ verdict_summary }}": html.escape(verdict_summary),
            "{{ total_tasks }}": str(report.total_tasks),
            "{{ passed_tasks }}": str(report.completed),
            "{{ failed_tasks }}": str(report.failed),
            "{{ duration_label }}": duration_label,
            "{{ quality_score }}": quality_score,
            "{{ grade }}": grade,
            "{{ reliability_score }}": reliability,
            "{{ performance_score }}": performance,
            "{{ coverage_score }}": coverage,
            "{{ severity_penalty }}": penalty,
            "{{ findings_section }}": findings_html,
            "{{ task_rows }}": task_rows_html,
            "{{ recommendations_section }}": recommendations_html,
            "{{ campaign_id }}": html.escape(campaign.campaign_id[:12]),
            "{{ generated_at }}": html.escape(report.generated_at or ""),
        }

        result = template
        for placeholder, value in replacements.items():
            result = result.replace(placeholder, value)
        return result

    # ------------------------------------------------------------------
    # Sections
    # ------------------------------------------------------------------

    def _render_findings(self, findings: list[str]) -> str:
        if not findings:
            return ""
        items = "".join(
            f'<li>{html.escape(f)}</li>'
            for f in findings[:10]
        )
        return (
            '<h3 class="section-title">Findings</h3>'
            f'<ul class="findings-list">{items}</ul>'
        )

    def _render_task_rows(self, tasks: list[dict[str, Any]]) -> str:
        rows: list[str] = []
        for task in tasks:
            status = task.get("status", "")
            method = html.escape(str(task.get("method", "")))
            path = html.escape(str(task.get("path", "")))
            response_status = task.get("response_status")
            duration = task.get("duration_ms", 0)
            checks_passed = task.get("checks_passed", 0)
            checks_failed = task.get("checks_failed", 0)
            error = task.get("error", "")

            # Status badge
            if status == TASK_COMPLETED:
                badge = '<span class="badge badge-pass">PASS</span>'
            elif status == TASK_FAILED:
                badge = '<span class="badge badge-fail">FAIL</span>'
            elif status == TASK_SKIPPED:
                badge = '<span class="badge badge-skip">SKIP</span>'
            else:
                badge = '<span class="badge">—</span>'

            # HTTP status
            http_label = str(response_status) if response_status else "—"
            http_class = "http-code http-ok" if response_status and 200 <= response_status < 300 else (
                "http-code http-err" if response_status and response_status >= 400 else "http-code"
            )

            # Duration
            dur_label = f"{duration:.0f}ms" if duration else "—"

            # Row class
            row_class = ' class="row-fail"' if status == TASK_FAILED else ""

            row = f'<tr{row_class}>'
            row += f'<td><span class="endpoint-method method-{method}">{method}</span>{path}'
            if error:
                row += f'<div class="task-error">{html.escape(str(error)[:100])}</div>'
            row += '</td>'
            row += f'<td class="center">{badge}</td>'
            row += f'<td class="center"><span class="{http_class}">{http_label}</span></td>'
            row += f'<td class="right">{dur_label}</td>'
            row += f'<td class="center"><span class="checks-label"><span class="checks-pass">{checks_passed}</span> / <span class="checks-fail">{checks_failed}</span></span></td>'
            row += '</tr>'
            rows.append(row)
        return "\n".join(rows)

    def _render_recommendations(self, evaluation: EvaluationResult | None) -> str:
        if not evaluation or not evaluation.recommendations:
            return ""
        items = "".join(
            f'<li>{html.escape(r)}</li>'
            for r in evaluation.recommendations[:8]
        )
        return (
            '<h3 class="section-title">Recommendations</h3>'
            f'<ul class="recommendations">{items}</ul>'
        )

    # ------------------------------------------------------------------
    # Styling helpers
    # ------------------------------------------------------------------

    def _verdict_style(self, verdict: str) -> tuple[str, str, str, str, str]:
        """Return (icon, label, bg_color, border_color, text_color)."""
        if verdict == "approved":
            return ("&#10004;", "APPROVED", "approved", "", "")
        if verdict == "warning":
            return ("&#9888;", "PASSED WITH WARNINGS", "warning", "", "")
        if verdict == "rejected":
            return ("&#10006;", "REJECTED", "rejected", "", "")
        return ("&#8212;", "PENDING", "unknown", "", "")

    def _grade_colors(self, grade: str) -> tuple[str, str]:
        """Return (bg_color, text_color) for the grade circle."""
        if grade == "A":
            return ("var(--success-bg)", "var(--success)")
        if grade == "B":
            return ("var(--info-bg)", "var(--info)")
        if grade == "C":
            return ("var(--warning-bg)", "var(--warning)")
        if grade in {"D", "F"}:
            return ("var(--danger-bg)", "var(--danger)")
        return ("var(--surface-alt)", "var(--text-muted)")

    def _load_template(self) -> str:
        return _TEMPLATE_PATH.read_text(encoding="utf-8")


__all__ = ["ApiTestingReportTemplate"]

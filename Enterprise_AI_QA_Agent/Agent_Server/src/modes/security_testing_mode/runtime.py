"""Security Testing Mode runtime.

This module drives the Phase 1 security testing state machine. The runtime is
intentionally conservative: it builds a small, auditable campaign from the
target supplied by the user, executes it through registered runner tools, and
packages the resulting findings into Markdown/JSON/HTML report artifacts.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Awaitable, Callable
from uuid import uuid4

from src.application.reporting.report_template_service import ReportTemplateService
from src.application.security.finding_normalizer import FindingNormalizer
from src.application.security.risk_policy import SecurityRiskPolicy
from src.application.security.tool_catalog import SecurityToolCatalog
from src.modes.security_testing_mode.agent import SURFACE_WORKER_MAP
from src.modes.security_testing_mode.asset_discovery_service import SecurityAssetDiscoveryService
from src.modes.security_testing_mode.auth_strategy_planner import SecurityAuthStrategyPlanner
from src.modes.security_testing_mode.campaign_state import (
    AgentActivityRecord,
    ReportDeliveryRecord,
    SecurityCampaign,
    SecurityReport,
    SecurityTask,
    SecurityTestingRequestState,
    SecurityTestingState,
    TargetCandidate,
)
from src.modes.security_testing_mode.contracts import (
    PHASE_ASSET_DISCOVERED,
    PHASE_EMAIL_DELIVERED,
    PHASE_ATTACK_PLAN_READY,
    PHASE_FAILED,
    PHASE_RECON_COMPLETE,
    PHASE_RECON_RUNNING,
    PHASE_REPORT_READY,
    PHASE_REQUEST_RESOLVED,
    PHASE_SCOPE_CONFIRMED,
    PHASE_TARGET_DISCOVERED,
    PHASE_TASK_DISPATCHING,
    PHASE_TASK_RUNNING,
    STATE_METADATA_KEY,
    TASK_COMPLETED,
    TASK_FAILED,
    TASK_SKIPPED,
    TERMINAL_PHASES,
)
from src.modes.security_testing_mode.evidence_service import SecurityEvidenceService
from src.modes.security_testing_mode.memory_service import SecurityMemoryService
from src.modes.security_testing_mode.recon_planner import SecurityReconPlanner
from src.modes.security_testing_mode.reflection_service import SecurityReflectionService
from src.modes.security_testing_mode.report_builder import SecurityReportBuilder
from src.modes.security_testing_mode.report_template import SecurityReportTemplate
from src.modes.security_testing_mode.request_interpreter import SecurityRequestInterpreter
from src.modes.security_testing_mode.severity_evaluator import SeverityEvaluator
from src.modes.security_testing_mode.subagent_coordinator import SecuritySubagentCoordinator
from src.modes.security_testing_mode.task_pool import SecurityTaskPool
from src.modes.security_testing_mode.vulnerability_planner import SecurityVulnerabilityPlanner

RunnerExecutor = Callable[[dict[str, Any], Any, str | None], Awaitable[dict[str, Any]]]
ReportDeliveryExecutor = Callable[[dict[str, Any], Any], Awaitable[dict[str, Any]]]


class SecurityTestingModeRuntime:
    """Drives the Security Testing Mode phase machine."""

    def __init__(
        self,
        *,
        settings: Any = None,
        coordinator_runtime_service: Any = None,
        session_store: Any = None,
        memory_runtime_service: Any = None,
        report_template_service: ReportTemplateService | None = None,
        runner_executor: RunnerExecutor | None = None,
        report_delivery_executor: ReportDeliveryExecutor | None = None,
    ) -> None:
        self._settings = settings
        self._coordinator_runtime_service = coordinator_runtime_service
        self._session_store = session_store
        self._memory_runtime_service = memory_runtime_service
        self._runner_executor = runner_executor
        self._report_delivery_executor = report_delivery_executor
        self._tool_catalog = SecurityToolCatalog()
        self._risk_policy = SecurityRiskPolicy()
        self._finding_normalizer = FindingNormalizer()
        self._severity_evaluator = SeverityEvaluator()
        self._request_interpreter = SecurityRequestInterpreter()
        self._asset_discovery = SecurityAssetDiscoveryService()
        self._auth_strategy_planner = SecurityAuthStrategyPlanner()
        self._evidence_service = SecurityEvidenceService()
        self._memory_service = SecurityMemoryService()
        self._recon_planner = SecurityReconPlanner(
            tool_catalog=self._tool_catalog,
            risk_policy=self._risk_policy,
        )
        self._vulnerability_planner = SecurityVulnerabilityPlanner(
            risk_policy=self._risk_policy,
        )
        self._reflection_service = SecurityReflectionService()
        self._report_builder = SecurityReportBuilder()
        self._report_template = SecurityReportTemplate(report_template_service)
        self._last_markdown_report = ""
        self._last_html_report = ""
        self._last_artifacts: list[dict[str, Any]] = []

    def set_coordinator_runtime_service(self, coordinator_runtime_service: Any) -> None:
        self._coordinator_runtime_service = coordinator_runtime_service

    def set_session_store(self, session_store: Any) -> None:
        self._session_store = session_store

    def set_memory_runtime_service(self, memory_runtime_service: Any) -> None:
        self._memory_runtime_service = memory_runtime_service

    def set_runner_executor(self, runner_executor: RunnerExecutor | None) -> None:
        self._runner_executor = runner_executor

    def set_report_delivery_executor(
        self,
        report_delivery_executor: ReportDeliveryExecutor | None,
    ) -> None:
        self._report_delivery_executor = report_delivery_executor

    async def handle(self, arguments: dict[str, Any], context: Any) -> dict[str, Any]:
        """Restore state, advance the phase machine, persist, and return output."""
        worker_action = str(arguments.get("worker_action") or "").strip().lower()
        if worker_action == "execute_security_task" or isinstance(arguments.get("task"), dict):
            return await self._execute_dispatched_task(arguments, context)

        state = self._restore_state(context)
        request = self._build_request(arguments, context)

        if state.phase in TERMINAL_PHASES and request.raw_message.strip():
            state = SecurityTestingState()

        state.request = request
        state = await self._advance(state, context)
        self._persist_state(state, context)
        return self._build_output(state)

    async def _advance(self, state: SecurityTestingState, context: Any) -> SecurityTestingState:
        """Advance until a terminal phase or an external wait point."""
        if state.phase in TERMINAL_PHASES:
            return state

        if state.phase == PHASE_REQUEST_RESOLVED:
            state = self._resolve_targets(state)

        if state.phase == PHASE_TARGET_DISCOVERED:
            state = self._confirm_scope(state)

        if state.phase == PHASE_SCOPE_CONFIRMED:
            state = self._discover_seed_assets(state)

        if state.phase == PHASE_ASSET_DISCOVERED:
            state = self._build_campaign(state)

        if state.phase == PHASE_ATTACK_PLAN_READY:
            state = await self._execute_campaign(state, context)

        return state

    def _resolve_targets(self, state: SecurityTestingState) -> SecurityTestingState:
        target = self._request_interpreter.resolve_primary_target(state.request)
        if target is None:
            state.notes.append("Security testing requires a target URL, host, IP, domain, or CIDR range.")
            state.record_phase_transition(PHASE_FAILED, "No target was provided.")
            return state

        state.targets = [target]
        state.record_phase_transition(PHASE_TARGET_DISCOVERED, f"Resolved target: {target.value}")
        return state

    def _confirm_scope(self, state: SecurityTestingState) -> SecurityTestingState:
        if not state.targets:
            state.record_phase_transition(PHASE_FAILED, "No target to scope.")
            return state

        target_values = ", ".join(target.value for target in state.targets if target.value)
        state.notes.append(
            f"Scope auto-confirmed for Phase 1 safe baseline testing: {target_values}."
        )
        state.record_phase_transition(PHASE_SCOPE_CONFIRMED, "Scope auto-confirmed.")
        return state

    def _discover_seed_assets(self, state: SecurityTestingState) -> SecurityTestingState:
        assets = self._asset_discovery.seed_assets(state.targets, state.request)
        credential_session = self._auth_strategy_planner.prepare_credential_session(state.request)
        state.record_phase_transition(PHASE_ASSET_DISCOVERED, f"Seeded {len(assets)} asset(s).")
        if state.campaign is None:
            state.campaign = SecurityCampaign(
                campaign_id=str(uuid4()),
                objective=state.request.objective,
                targets=list(state.targets),
                assets=assets,
                scope_notes=", ".join(target.value for target in state.targets),
                risk_tolerance=state.request.risk_tolerance or "medium",
                credential_session=credential_session,
                created_at=datetime.now(timezone.utc).isoformat(),
            )
        else:
            state.campaign.assets = assets
            state.campaign.credential_session = credential_session
        return state

    def _build_campaign(self, state: SecurityTestingState) -> SecurityTestingState:
        if state.campaign is None:
            state.record_phase_transition(PHASE_FAILED, "No campaign state available.")
            return state

        tasks = self._recon_planner.build_campaign_tasks(state.targets, state.request)
        tasks = self._vulnerability_planner.refine_tasks(tasks, state.request)

        if not tasks:
            state.notes.append("No executable security tasks could be planned for the supplied target.")
            state.record_phase_transition(PHASE_FAILED, "No planned tasks.")
            return state

        state.campaign.tasks = tasks
        state.campaign.updated_at = datetime.now(timezone.utc).isoformat()
        state.record_phase_transition(PHASE_ATTACK_PLAN_READY, f"Built campaign with {len(tasks)} task(s).")
        return state

    async def _execute_campaign(self, state: SecurityTestingState, context: Any) -> SecurityTestingState:
        if state.campaign is None:
            state.record_phase_transition(PHASE_FAILED, "No campaign to execute.")
            return state

        state.record_phase_transition(PHASE_TASK_DISPATCHING, "Dispatching security tasks.")
        pool = SecurityTaskPool(tasks=state.campaign.tasks)
        state.record_phase_transition(PHASE_TASK_RUNNING, "Executing security tasks.")
        state.record_phase_transition(PHASE_RECON_RUNNING, "Reconnaissance tasks are running.")

        if self._can_use_subagent_execution(context):
            coordinator = SecuritySubagentCoordinator(
                pool=pool,
                coordinator_runtime_service=self._coordinator_runtime_service,
                session_store=self._session_store,
                parent_context=self._build_dispatch_context(context),
                max_workers=state.campaign.max_workers,
                worker_model_key=str(getattr(context, "selected_model_key", "") or "") or None,
            )
            completed_tasks = await coordinator.run_all()
            state.campaign.activities.extend(coordinator.activities)
        else:
            completed_tasks = await self._run_tasks_locally(pool, context, state.campaign)

        state.campaign.tasks = completed_tasks
        self._evidence_service.hydrate_missing_records(state.campaign)
        self._hydrate_campaign_from_task_results(state.campaign)
        reflection = self._reflection_service.analyze_campaign(state.campaign)
        for note in reflection.get("notes", []):
            if isinstance(note, str) and note not in state.notes:
                state.notes.append(note)
        state.campaign.updated_at = datetime.now(timezone.utc).isoformat()
        state.record_phase_transition(PHASE_RECON_COMPLETE, "Task execution complete.")

        report = self._report_builder.build_report(state.campaign)
        state.report = report
        markdown_report = self._report_builder.build_markdown(report)
        html_report = self._report_template.render(
            report=report,
            markdown_content=markdown_report,
            sender=str(getattr(context, "selected_agent_key", "") or "security-testing-agent"),
        )
        self._last_markdown_report = markdown_report
        self._last_html_report = html_report
        self._last_artifacts = self._report_builder.build_artifacts(
            report=report,
            markdown_report=markdown_report,
            html_report=html_report,
        )
        memory_ids = await self._memory_service.persist_campaign_observations(
            campaign=state.campaign,
            context=context,
            memory_runtime_service=self._memory_runtime_service,
        )
        if memory_ids:
            state.notes.append(f"Persisted {len(memory_ids)} security observation(s) to memory.")
        state.record_phase_transition(PHASE_REPORT_READY, "Security report generated.")
        state = await self._deliver_report_if_requested(
            state=state,
            context=context,
            markdown_report=markdown_report,
            html_report=html_report,
        )
        return state

    async def _deliver_report_if_requested(
        self,
        *,
        state: SecurityTestingState,
        context: Any,
        markdown_report: str,
        html_report: str,
    ) -> SecurityTestingState:
        recipients = self._to_string_list(state.request.report_recipients)
        if not recipients or state.report is None:
            return state

        payload = self._build_report_delivery_payload(
            report=state.report,
            recipients=recipients,
            markdown_report=markdown_report,
            html_report=html_report,
            context=context,
        )
        if self._report_delivery_executor is None:
            state.delivery = ReportDeliveryRecord(
                status="skipped",
                recipients=recipients,
                subject=str(payload.get("subject") or ""),
                summary="Report recipients were provided, but no report delivery executor is configured.",
                error="report_delivery_executor_not_configured",
            )
            state.notes.append(state.delivery.summary)
            return state

        try:
            result = await self._report_delivery_executor(payload, context)
        except Exception as exc:
            state.delivery = ReportDeliveryRecord(
                status="failed",
                recipients=recipients,
                subject=str(payload.get("subject") or ""),
                summary=f"Security report email delivery failed: {exc}",
                error=str(exc),
            )
            state.notes.append(state.delivery.summary)
            return state

        delivery = result.get("delivery") if isinstance(result.get("delivery"), dict) else {}
        artifacts = result.get("artifacts") if isinstance(result.get("artifacts"), list) else []
        artifact_paths = [
            str(item.get("path") or item.get("filename") or "")
            for item in artifacts
            if isinstance(item, dict) and str(item.get("path") or item.get("filename") or "").strip()
        ]
        explicit_status = str(result.get("status") or "").strip().lower()
        ok = result.get("ok")
        failed = explicit_status in {"failed", "denied"} or ok is False or bool(result.get("error"))
        sent = bool(delivery.get("sent")) and not failed
        recipient_count = int(delivery.get("recipient_count") or len(recipients)) if sent else 0
        delivery_error = "" if sent else str(result.get("error") or result.get("summary") or "email_delivery_failed")

        state.delivery = ReportDeliveryRecord(
            status="sent" if sent else "failed",
            recipients=recipients,
            subject=str(payload.get("subject") or ""),
            summary=str(result.get("summary") or ""),
            sent=sent,
            provider=str(delivery.get("provider") or ""),
            from_email=str(delivery.get("from_email") or ""),
            recipient_count=recipient_count,
            artifact_paths=artifact_paths,
            error=delivery_error,
            delivered_at=datetime.now(timezone.utc).isoformat() if sent else "",
        )
        if sent:
            state.notes.append(f"Delivered security report email to {len(recipients)} recipient(s).")
            state.record_phase_transition(PHASE_EMAIL_DELIVERED, "Security report delivered by email.")
        else:
            state.notes.append(
                state.delivery.summary
                or f"Security report email delivery failed for {len(recipients)} recipient(s)."
            )
        return state

    def _build_report_delivery_payload(
        self,
        *,
        report: SecurityReport,
        recipients: list[str],
        markdown_report: str,
        html_report: str,
        context: Any,
    ) -> dict[str, Any]:
        generated_at = datetime.now(timezone.utc)
        target_label = " ".join((report.target_summary or report.campaign_id[:8]).split())
        if len(target_label) > 80:
            target_label = f"{target_label[:77]}..."
        date_label = generated_at.strftime("%Y-%m-%d %H:%M:%S UTC")
        subject = f"Security Test Report - {target_label} - {date_label}"
        return {
            "to": recipients,
            "subject": subject,
            "content": markdown_report,
            "content_markdown": markdown_report,
            "content_html": html_report,
            "sender": str(getattr(context, "selected_agent_key", "") or "security-testing-agent"),
            "time_label": date_label,
            "template_key": "security_testing_full",
            "template_context": {
                "campaign_id": report.campaign_id,
                "target_summary": report.target_summary,
                "total_findings": str(report.total_findings),
                "completed_tasks": str(report.completed_tasks),
                "total_tasks": str(report.total_tasks),
            },
            "file_name": f"security_report_email_{report.campaign_id[:8]}",
        }

    async def _run_tasks_locally(
        self,
        pool: SecurityTaskPool,
        context: Any,
        campaign: SecurityCampaign,
    ) -> list[SecurityTask]:
        while not pool.is_complete:
            pool.resolve_blocked()
            ready = pool.ready_tasks()
            if not ready:
                break
            for task in ready:
                pool.mark_running(task.task_id)
                started_at = task.started_at
                runner_key = self._tool_catalog.resolve_runner_for_family(task.tool_family)
                result = await self._execute_task_with_runner(task, context, runner_key)
                task.raw_output = str(result.get("raw_output") or "")[:10000]
                task.parsed_result = result.get("parsed_result") if isinstance(result.get("parsed_result"), dict) else {}
                task.result_summary = str(result.get("summary") or "")
                task.artifacts = [
                    str(item.get("path") or item.get("label") or item.get("filename") or "")
                    for item in result.get("artifacts", [])
                    if isinstance(item, dict)
                ]
                if result.get("success") or result.get("ok"):
                    pool.mark_completed(task.task_id, task.result_summary)
                else:
                    pool.mark_failed(task.task_id, str(result.get("error") or task.result_summary or "execution_failed"))
                self._evidence_service.record_runner_result(campaign, task, result, started_at=started_at)
                self._record_local_activity(task, started_at)
        return pool.all_tasks

    async def _execute_task_with_runner(
        self,
        task: SecurityTask,
        context: Any,
        runner_key: str,
    ) -> dict[str, Any]:
        if self._runner_executor is None:
            return {
                "status": "failed",
                "ok": False,
                "success": False,
                "summary": "Security runner executor is not configured.",
                "error": "runner_executor_not_configured",
            }
        return await self._runner_executor(
            {
                "worker_action": "execute_security_task",
                "task": task.model_dump(mode="json"),
            },
            context,
            runner_key,
        )

    async def _execute_dispatched_task(self, arguments: dict[str, Any], context: Any) -> dict[str, Any]:
        raw_task = arguments.get("task")
        if not isinstance(raw_task, dict):
            return {
                "status": "failed",
                "ok": False,
                "success": False,
                "summary": "Security task execution requires a serialized `task` payload.",
                "error": "missing_task_payload",
            }
        task = SecurityTask.model_validate(raw_task)
        runner_key = self._tool_catalog.resolve_runner_for_family(task.tool_family)
        return await self._execute_task_with_runner(task, context, runner_key)

    def _build_tasks_for_target(
        self,
        target: TargetCandidate,
        request: SecurityTestingRequestState,
    ) -> list[SecurityTask]:
        return self._recon_planner.build_tasks_for_target(target, request)

    def _suggest_profile_keys(
        self,
        surface_type: str,
        target: TargetCandidate,
        request: SecurityTestingRequestState,
    ) -> list[str]:
        return self._recon_planner.suggest_profile_keys(surface_type, target, request)

    def _hydrate_campaign_from_task_results(self, campaign: SecurityCampaign) -> None:
        self._asset_discovery.hydrate_campaign_from_task_results(
            campaign,
            profile_lookup=self._tool_catalog.get_profile,
            finding_normalizer=self._finding_normalizer,
            severity_evaluator=self._severity_evaluator,
        )

    def _record_local_activity(self, task: SecurityTask, started_at: str = "") -> None:
        if task.completed_at and started_at:
            try:
                start = datetime.fromisoformat(started_at)
                end = datetime.fromisoformat(task.completed_at)
                duration = max(0.0, (end - start).total_seconds())
            except (TypeError, ValueError):
                duration = 0.0
        else:
            duration = 0.0
        if not task.worker_agent_key:
            task.worker_agent_key = SURFACE_WORKER_MAP.get(task.surface_type, "security-recon-worker")
        activity = AgentActivityRecord(
            activity_id=f"act_{task.task_id}",
            agent_key=task.worker_agent_key,
            agent_name=task.worker_agent_key,
            task_id=task.task_id,
            action="completed" if task.status == TASK_COMPLETED else "failed",
            summary=task.result_summary or task.last_error,
            started_at=started_at or task.started_at,
            completed_at=task.completed_at,
            duration_seconds=duration,
            tool_calls=[task.command_profile],
        )
        # The current direct execution path owns the campaign in the caller.
        # Activity records are regenerated from tasks in _build_output metrics.
        task.observations.append(activity.summary)

    def _build_request(self, arguments: dict[str, Any], context: Any) -> SecurityTestingRequestState:
        return self._request_interpreter.interpret(arguments, context)

    def _restore_state(self, context: Any) -> SecurityTestingState:
        bundle = getattr(context, "context_bundle", None) or {}
        raw = bundle.get(STATE_METADATA_KEY)
        if isinstance(raw, dict):
            try:
                return SecurityTestingState.model_validate(raw)
            except Exception:
                pass
        return SecurityTestingState()

    def _persist_state(self, state: SecurityTestingState, context: Any) -> None:
        state.last_updated_at = datetime.now(timezone.utc).isoformat()
        bundle = getattr(context, "context_bundle", None)
        if isinstance(bundle, dict):
            bundle[STATE_METADATA_KEY] = state.model_dump(mode="json")

    def _build_output(self, state: SecurityTestingState) -> dict[str, Any]:
        delivery_failed = state.delivery is not None and state.delivery.status == "failed"
        completed = state.phase in {PHASE_REPORT_READY, PHASE_EMAIL_DELIVERED}
        output: dict[str, Any] = {
            "status": "partial" if delivery_failed else "completed" if completed else "failed" if state.phase == PHASE_FAILED else "partial",
            "phase": state.phase,
            "summary": self._build_summary(state),
        }
        if state.targets:
            output["targets"] = [target.model_dump(mode="json") for target in state.targets]
        if state.campaign:
            output["campaign_id"] = state.campaign.campaign_id
            output["task_count"] = len(state.campaign.tasks)
            output["task_summary"] = self._task_summary(state.campaign.tasks)
        if state.report:
            output["report"] = state.report.model_dump(mode="json")
            output["report_markdown"] = self._last_markdown_report
            output["report_html"] = self._last_html_report
            output["artifacts"] = [
                {
                    "type": item.get("type"),
                    "filename": item.get("filename"),
                    "content_type": item.get("content_type"),
                    "label": item.get("label"),
                }
                for item in self._last_artifacts
            ]
        if state.delivery:
            output["delivery"] = state.delivery.model_dump(mode="json")
        if state.notes:
            output["notes"] = list(state.notes)
        if state.error:
            output["error"] = state.error
        output[STATE_METADATA_KEY] = state.model_dump(mode="json")
        return output

    def _build_summary(self, state: SecurityTestingState) -> str:
        if state.phase == PHASE_FAILED:
            return state.notes[-1] if state.notes else "Security testing mode encountered an error."
        if state.phase == PHASE_EMAIL_DELIVERED and state.report:
            recipient_count = state.delivery.recipient_count if state.delivery else 0
            return (
                f"Security testing completed for {state.report.target_summary}; "
                f"{state.report.total_findings} finding(s), "
                f"{state.report.completed_tasks}/{state.report.total_tasks} task(s) completed; "
                f"report emailed to {recipient_count} recipient(s)."
            )
        if state.phase == PHASE_REPORT_READY and state.report:
            return (
                f"Security testing completed for {state.report.target_summary}; "
                f"{state.report.total_findings} finding(s), "
                f"{state.report.completed_tasks}/{state.report.total_tasks} task(s) completed."
            )
        if state.phase == PHASE_ATTACK_PLAN_READY and state.campaign:
            return f"Security campaign is ready with {len(state.campaign.tasks)} task(s)."
        return f"Security testing mode is in phase: {state.phase}."

    def _can_use_subagent_execution(self, context: Any) -> bool:
        if self._coordinator_runtime_service is None or self._session_store is None:
            return False
        return bool(getattr(context, "session_id", "") and getattr(context, "turn_id", ""))

    def _build_dispatch_context(self, context: Any) -> dict[str, Any]:
        return {
            "session_id": str(getattr(context, "session_id", "") or ""),
            "turn_id": str(getattr(context, "turn_id", "") or ""),
            "trace_id": str(getattr(context, "trace_id", "") or ""),
            "selected_agent_key": str(getattr(context, "selected_agent_key", "") or ""),
            "selected_model_key": str(getattr(context, "selected_model_key", "") or ""),
            "context_bundle": dict(getattr(context, "context_bundle", {}) or {}),
        }

    def _task_summary(self, tasks: list[SecurityTask]) -> dict[str, int]:
        return {
            "total": len(tasks),
            "completed": sum(1 for task in tasks if task.status == TASK_COMPLETED),
            "failed": sum(1 for task in tasks if task.status == TASK_FAILED),
            "skipped": sum(1 for task in tasks if task.status == TASK_SKIPPED),
        }

    def _to_string_list(self, value: Any) -> list[str]:
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
        if isinstance(value, str) and value.strip():
            return [item.strip() for item in value.split(",") if item.strip()]
        return []


__all__ = ["SecurityTestingModeRuntime"]

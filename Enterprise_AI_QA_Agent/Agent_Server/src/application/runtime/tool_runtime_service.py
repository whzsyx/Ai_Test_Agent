from __future__ import annotations

import asyncio
import json
import os
import re
import shlex
import shutil
import smtplib
import subprocess
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from email.message import EmailMessage
from pathlib import Path, PurePosixPath
from typing import Any

from src.application.context.memory_runtime_service import MemoryRuntimeService
from src.application.context.mcp_runtime_service import MCPRuntimeService
from src.application.artifacts.artifact_storage_service import ArtifactStorageService
from src.application.exploration.ui_graph_store import UIGraphStore
from src.modes.code_review_mode import build_code_review_campaign
from src.modes.code_review_mode.project_source import (
    DEFAULT_IGNORED_NAMES,
    normalize_project_source,
    project_source_root,
    resolve_local_project_file,
    resolve_local_project_root,
)
from src.application.reporting.report_template_service import ReportTemplateService
from src.application.runtime.tool_job_service import ToolJobService
from src.application.context.transcript_hygiene_service import TranscriptHygieneService
from src.application.testing.ui_exploration_service import UIExplorationService
from src.core.config import Settings
from src.infrastructure.email_config_store import MySQLEmailConfigStore
from src.modes.ui_automation_mode.runtime import UIAutomationModeRuntime
from src.runtime.store import SessionStore
from src.schemas.agent import ToolDescriptor
from src.schemas.model_config import ModelConfigRecord
from src.schemas.tool_runtime import ModelToolCall, ToolExecutionRecord

CODE_REVIEW_RESULT_CATEGORY_LABELS = {
    "serious_issue": "严重问题",
    "critical": "严重问题",
    "严重问题": "严重问题",
    "defect": "缺陷",
    "缺陷": "缺陷",
    "risk": "隐患",
    "隐患": "隐患",
    "feasible": "可行",
    "可行": "可行",
    "excellent": "优秀",
    "优秀": "优秀",
}


@dataclass
class ToolExecutionContext:
    session_id: str
    turn_id: str
    trace_id: str
    user_message: str
    normalized_input: str
    context_bundle: dict[str, Any]
    selected_agent_key: str = ""
    selected_model_key: str = ""
    tool_job_id: str = ""


class ToolRuntimeService:
    def __init__(
        self,
        request_timeout_seconds: int = 20,
        settings: Settings | None = None,
        mcp_runtime_service: MCPRuntimeService | None = None,
        memory_runtime_service: MemoryRuntimeService | None = None,
        tool_job_service: ToolJobService | None = None,
        session_store: SessionStore | None = None,
        transcript_hygiene_service: TranscriptHygieneService | None = None,
        artifact_storage_service: ArtifactStorageService | None = None,
        coordinator_runtime_service=None,
    ) -> None:
        self._request_timeout_seconds = request_timeout_seconds
        self._settings = settings
        self._docs_dir = Path(__file__).resolve().parents[3] / "docs"
        self._workspace_root = Path.cwd()
        self._mcp_runtime_service = mcp_runtime_service
        self._memory_runtime_service = memory_runtime_service
        self._tool_job_service = tool_job_service
        self._artifact_storage_service = artifact_storage_service
        self._session_store = session_store
        self._transcript_hygiene_service = transcript_hygiene_service or TranscriptHygieneService()
        self._coordinator_runtime_service = coordinator_runtime_service
        self._model_registry = None
        self._email_config_store = MySQLEmailConfigStore(settings) if settings is not None else None
        self._report_template_service = ReportTemplateService()
        self._ui_graph_store = UIGraphStore(settings) if settings is not None else None
        self._ui_exploration_service = (
            UIExplorationService(
                settings=settings,
                mcp_runtime_service=mcp_runtime_service,
                memory_runtime_service=memory_runtime_service,
                ui_graph_store=self._ui_graph_store,
            )
            if settings is not None
            else None
        )
        self._ui_automation_mode_runtime = UIAutomationModeRuntime(
            memory_runtime_service=memory_runtime_service,
            ui_exploration_service=self._ui_exploration_service,
        )
        self._handlers = {
            "workflow-router": self._run_workflow_router,
            "subagent-dispatch": self._run_subagent_dispatch,
            "knowledge-rag": self._run_knowledge_rag,
            "attachment-reader": self._run_attachment_reader,
            "session-history": self._run_session_history,
            "session-timeline": self._run_session_timeline,
            "observation-search": self._run_observation_search,
            "test-case-generator": self._run_test_case_generator,
            "ui-page-explorer": self._run_ui_page_explorer,
            "dom-inspector": self._run_dom_inspector,
            "browser-automation": self._run_browser_automation,
            "browser-control": self._run_browser_control,
            "api-tester": self._run_api_tester,
            "cli-executor": self._run_cli_executor,
            "file-artifact-manager": self._run_file_artifact_manager,
            "message-dispatch": self._run_message_dispatch,
            "send-email": self._run_send_email,
            "report-writer": self._run_report_writer,
            "project-source-loader": self._run_project_source_loader,
            "project-tree-scanner": self._run_project_tree_scanner,
            "project-file-reader": self._run_project_file_reader,
            "project-diff-reader": self._run_project_diff_reader,
            "code-review-orchestrator": self._run_code_review_orchestrator,
            "ui-automation-runner": self._run_ui_automation_runner,
            "api-test-runner": self._run_api_test_runner,
            "security-scan-runner": self._run_security_scan_runner,
            "performance-test-runner": self._run_performance_test_runner,
            "smoke-suite-runner": self._run_smoke_suite_runner,
        }

    def set_coordinator_runtime_service(self, coordinator_runtime_service) -> None:
        self._coordinator_runtime_service = coordinator_runtime_service

    def set_model_registry(self, model_registry) -> None:
        self._model_registry = model_registry

    def set_memory_runtime_service(self, memory_runtime_service: MemoryRuntimeService) -> None:
        self._memory_runtime_service = memory_runtime_service
        self._ui_automation_mode_runtime.set_memory_runtime_service(memory_runtime_service)
        if self._ui_exploration_service is not None:
            self._ui_exploration_service._memory_runtime_service = memory_runtime_service

    def set_tool_job_service(self, tool_job_service: ToolJobService) -> None:
        self._tool_job_service = tool_job_service

    def set_session_store(self, session_store: SessionStore) -> None:
        self._session_store = session_store

    def has_handler(self, tool_key: str) -> bool:
        return tool_key in self._handlers

    async def execute(
        self,
        tool: ToolDescriptor,
        call: ModelToolCall,
        context: ToolExecutionContext,
    ) -> ToolExecutionRecord:
        started_at = datetime.utcnow()
        job = None
        handler = self._handlers.get(tool.key)
        if handler is None:
            return ToolExecutionRecord(
                call_id=call.id,
                tool_key=tool.key,
                tool_name=tool.name,
                status="failed",
                summary=f"No runtime handler is registered for tool '{tool.key}'.",
                trace_id=context.trace_id,
                input=call.arguments,
                output={},
                started_at=started_at,
                completed_at=datetime.utcnow(),
            )

        try:
            job_context = context
            if self._tool_job_service is not None:
                job = await self._tool_job_service.create_job(
                    tool=tool,
                    call_id=call.id,
                    session_id=context.session_id,
                    turn_id=context.turn_id,
                    trace_id=context.trace_id,
                    input_payload=call.arguments,
                    metadata={
                        "selected_agent_key": context.selected_agent_key,
                        "selected_model_key": context.selected_model_key,
                    },
                )
                await self._tool_job_service.mark_running(job)
                job_context = ToolExecutionContext(
                    session_id=context.session_id,
                    turn_id=context.turn_id,
                    trace_id=context.trace_id,
                    user_message=context.user_message,
                    normalized_input=context.normalized_input,
                    context_bundle=context.context_bundle,
                    selected_agent_key=context.selected_agent_key,
                    selected_model_key=context.selected_model_key,
                    tool_job_id=job.id,
                )

            raw_result = await handler(call.arguments, job_context)
            result = self._normalize_result(tool, raw_result, context=job_context)
            if self._artifact_storage_service is not None:
                result = await self._artifact_storage_service.store_output_artifacts(
                    result,
                    session_id=job_context.session_id,
                    turn_id=job_context.turn_id,
                    tool_key=tool.key,
                )
            resolved_status = self._resolve_result_status(result)
            summary = str(result.get("summary", f"Tool '{tool.key}' completed."))
            if job is not None and self._tool_job_service is not None:
                if resolved_status == "failed":
                    await self._tool_job_service.mark_failed(
                        job.id,
                        summary=summary,
                        error_message=str(result.get("error") or summary),
                        output_payload=result,
                    )
                elif resolved_status == "partial":
                    await self._tool_job_service.mark_partial(
                        job.id,
                        summary=summary,
                        output_payload=result,
                        artifacts=result.get("artifacts", []) if isinstance(result, dict) else [],
                    )
                elif resolved_status == "waiting_approval":
                    await self._tool_job_service.mark_waiting_approval(
                        job.id,
                        summary=summary,
                        metadata={"output_payload": result},
                    )
                elif resolved_status == "denied":
                    await self._tool_job_service.mark_denied(
                        job.id,
                        summary=summary,
                        output_payload=result,
                    )
                else:
                    await self._tool_job_service.mark_completed(
                        job.id,
                        summary=summary,
                        output_payload=result,
                        artifacts=result.get("artifacts", []) if isinstance(result, dict) else [],
                    )
            return ToolExecutionRecord(
                call_id=call.id,
                tool_key=tool.key,
                tool_name=tool.name,
                status=resolved_status,
                summary=summary,
                trace_id=str(result.get("trace_id") or context.trace_id or ""),
                job_id=job.id if job is not None else None,
                input=call.arguments,
                output=result,
                started_at=started_at,
                completed_at=datetime.utcnow(),
            )
        except Exception as exc:
            if job is not None and self._tool_job_service is not None:
                await self._tool_job_service.mark_failed(
                    job.id,
                    summary=f"Tool '{tool.key}' failed.",
                    error_message=str(exc),
                    output_payload={"error": str(exc)},
                )
            return ToolExecutionRecord(
                call_id=call.id,
                tool_key=tool.key,
                tool_name=tool.name,
                status="failed",
                summary=f"Tool '{tool.key}' failed: {exc}",
                trace_id=context.trace_id,
                job_id=job.id if job is not None else None,
                input=call.arguments,
                output={"error": str(exc)},
                started_at=started_at,
                completed_at=datetime.utcnow(),
            )

    def _resolve_result_status(self, result: dict[str, Any]) -> str:
        explicit_status = str(result.get("status") or "").strip().lower()
        if explicit_status in {"completed", "partial", "failed", "waiting_approval", "denied"}:
            return explicit_status
        if result.get("ok") is False:
            workers = result.get("workers")
            if isinstance(workers, list):
                running_count = sum(1 for item in workers if isinstance(item, dict) and item.get("status") == "running")
                failed_count = sum(1 for item in workers if isinstance(item, dict) and item.get("status") == "failed")
                if running_count > 0 and failed_count > 0:
                    return "partial"
            return "failed"
        return "completed"

    async def _run_knowledge_rag(
        self,
        arguments: dict[str, Any],
        context: ToolExecutionContext,
    ) -> dict[str, Any]:
        query = str(arguments.get("query") or context.normalized_input).strip()
        top_k = int(arguments.get("top_k") or 3)
        if not query:
            return {
                "summary": "No query was provided for knowledge retrieval.",
                "chunks": [],
            }

        memory_matches: list[dict[str, Any]] = []
        if self._memory_runtime_service is not None:
            memory_result = await self._memory_runtime_service.retrieve_for_turn(
                session_id=context.session_id,
                trace_id=context.trace_id,
                query=query,
                context=context.context_bundle,
            )
            memory_matches = [
                {
                    "source": item.source or (self._memory_runtime_service.backend if self._memory_runtime_service is not None else "memory"),
                    "score": item.score or 0.0,
                    "excerpt": item.summary or item.content,
                    "kind": item.kind,
                }
                for item in memory_result.hits
            ]

        tokens = [token.lower() for token in re.split(r"\W+", query) if token.strip()]
        matches: list[dict[str, Any]] = []

        if self._docs_dir.exists():
            for file_path in sorted(self._docs_dir.glob("*.md")):
                text = file_path.read_text(encoding="utf-8", errors="ignore")
                lowered = text.lower()
                filename_score = sum(file_path.name.lower().count(token) for token in tokens)
                score = (sum(lowered.count(token) for token in tokens) + filename_score) or 0
                if score <= 0:
                    continue
                excerpt = _build_excerpt(text, tokens)
                matches.append(
                    {
                        "source": file_path.name,
                        "score": score,
                        "excerpt": excerpt,
                    }
                )

        matches.sort(key=lambda item: item["score"], reverse=True)
        selected = [*memory_matches, *matches][:top_k]
        return {
            "summary": f"Retrieved {len(selected)} knowledge chunks for query '{query}'.",
            "chunks": selected,
            "query": query,
        }

    async def _run_subagent_dispatch(
        self,
        arguments: dict[str, Any],
        context: ToolExecutionContext,
    ) -> dict[str, Any]:
        coordinator_runtime = self._require_coordinator_runtime()
        return await coordinator_runtime.dispatch(
            payload=arguments,
            context=asdict(context),
        )

    async def _run_test_case_generator(
        self,
        arguments: dict[str, Any],
        context: ToolExecutionContext,
    ) -> dict[str, Any]:
        feature = str(arguments.get("feature") or arguments.get("goal") or context.user_message).strip()
        requirements = _to_string_list(arguments.get("requirements"))
        acceptance_criteria = _to_string_list(arguments.get("acceptance_criteria"))
        platforms = _to_string_list(arguments.get("platforms")) or ["web"]
        risk_focus = _to_string_list(arguments.get("risk_focus"))

        if not feature:
            return {
                "status": "failed",
                "ok": False,
                "summary": "No feature or QA goal was provided for test case generation.",
                "cases": [],
                "metrics": {"case_count": 0},
                "error": "missing_feature",
            }

        scenario_inputs = acceptance_criteria or requirements or [feature]
        cases: list[dict[str, Any]] = []
        for index, item in enumerate(scenario_inputs, start=1):
            title = item if len(item) <= 72 else f"{item[:69]}..."
            case_id = f"TC-{index:03d}"
            steps = [
                {"step": 1, "action": f"Prepare the environment for {feature}.", "expected": "The target workflow is reachable."},
                {"step": 2, "action": f"Execute scenario: {item}.", "expected": "The workflow processes the action without validation errors."},
                {"step": 3, "action": "Verify outcome and evidence.", "expected": "Observed results match the expected behavior."},
            ]
            cases.append(
                {
                    "id": case_id,
                    "title": title,
                    "type": "functional",
                    "priority": "high" if index == 1 else "medium",
                    "platforms": platforms,
                    "preconditions": [
                        f"The {feature} workflow is available.",
                        "Required test data and environment access are prepared.",
                    ],
                    "steps": steps,
                    "assertions": [
                        item,
                        *[criterion for criterion in acceptance_criteria if criterion != item],
                    ],
                    "risk_focus": risk_focus,
                }
            )

        coverage = {
            "requirements": requirements,
            "acceptance_criteria": acceptance_criteria,
            "risk_focus": risk_focus,
            "platforms": platforms,
        }
        return {
            "summary": f"Generated {len(cases)} structured test cases for '{feature}'.",
            "cases": cases,
            "coverage": coverage,
            "artifacts": [
                {
                    "type": "generated_cases",
                    "label": "test_cases.json",
                    "content": json.dumps({"feature": feature, "cases": cases}, ensure_ascii=False, indent=2),
                }
            ],
            "metrics": {
                "case_count": len(cases),
                "requirement_count": len(requirements),
                "acceptance_criteria_count": len(acceptance_criteria),
            },
        }

    async def _run_attachment_reader(
        self,
        arguments: dict[str, Any],
        context: ToolExecutionContext,
    ) -> dict[str, Any]:
        store = self._require_session_store()
        session = await store.get_session(context.session_id)
        if session is None:
            return {
                "status": "failed",
                "ok": False,
                "summary": f"Session '{context.session_id}' was not found.",
                "error": "session_not_found",
            }

        attachments = self._collect_available_attachments(context, session)
        if not attachments:
            return {
                "status": "failed",
                "ok": False,
                "summary": "No uploaded attachments are available in the current turn or recent user message.",
                "error": "attachment_not_found",
            }

        target = self._select_attachment_for_read(arguments, attachments)
        if target is None:
            requested_name = str(arguments.get("name") or arguments.get("attachment_id") or arguments.get("uri") or "").strip()
            return {
                "status": "failed",
                "ok": False,
                "summary": f"No attachment matched '{requested_name or 'current attachment'}'.",
                "available_attachments": [self._attachment_summary(item) for item in attachments],
                "error": "attachment_not_found",
            }

        max_chars = _clamp_int(arguments.get("max_chars"), minimum=200, maximum=50000, default=12000)
        prefer_excerpt = bool(arguments.get("prefer_excerpt", False))
        excerpt = " ".join(str(target.get("text_excerpt") or "").split())
        excerpt_text, excerpt_truncated = _truncate_text(excerpt, max_chars) if excerpt else ("", False)
        attachment_allowed, security_report = self._attachment_read_allowed(target)
        if not attachment_allowed:
            security_decision = str(security_report.get("decision") or "blocked").strip() if security_report else "blocked"
            return {
                "status": "failed",
                "ok": False,
                "summary": f"Attachment '{target.get('name')}' is not readable because it is marked as {security_decision}.",
                "attachment": self._attachment_summary(target),
                "error": "attachment_security_blocked",
            }
        uri = str(target.get("uri") or "").strip()
        content_type = str(target.get("content_type") or target.get("metadata", {}).get("content_type") or "").strip()

        resolved_content = ""
        resolved_from = "excerpt"
        preview_truncated = excerpt_truncated or bool(target.get("metadata", {}).get("preview_truncated"))
        size_bytes = target.get("metadata", {}).get("size_bytes")

        if not prefer_excerpt and uri.startswith("minio://") and self._artifact_storage_service is not None:
            try:
                storage_result = await self._artifact_storage_service.read_object_uri(uri)
                decoded_content, decode_error = self._decode_attachment_bytes(
                    content=storage_result["content"],
                    content_type=str(storage_result.get("content_type") or content_type),
                    filename=str(target.get("name") or ""),
                    max_chars=max_chars,
                )
                size_bytes = storage_result.get("size_bytes", size_bytes)
                if decoded_content:
                    resolved_content = decoded_content
                    resolved_from = "minio"
                    preview_truncated = len(storage_result["content"]) > len(decoded_content.encode("utf-8", errors="ignore"))
                elif excerpt_text:
                    resolved_content = excerpt_text
                    resolved_from = "excerpt_fallback"
                else:
                    return {
                        "status": "failed",
                        "ok": False,
                        "summary": f"Attachment '{target.get('name')}' is stored but could not be decoded as readable text.",
                        "attachment": self._attachment_summary(target),
                        "error": decode_error or "attachment_not_readable",
                    }
            except Exception as exc:
                if excerpt_text:
                    resolved_content = excerpt_text
                    resolved_from = "excerpt_fallback"
                else:
                    return {
                        "status": "failed",
                        "ok": False,
                        "summary": f"Failed to read attachment '{target.get('name')}' from object storage: {exc}",
                        "attachment": self._attachment_summary(target),
                        "error": "attachment_storage_read_failed",
                    }
        else:
            resolved_content = excerpt_text

        if not resolved_content:
            return {
                "status": "failed",
                "ok": False,
                "summary": f"Attachment '{target.get('name')}' does not contain readable text content yet.",
                "attachment": self._attachment_summary(target),
                "error": "attachment_empty",
            }

        attachment_summary = self._attachment_summary(target)
        attachment_summary["size_bytes"] = size_bytes
        return {
            "summary": f"Read attachment '{target.get('name')}' from {resolved_from}.",
            "attachment": attachment_summary,
            "content": resolved_content,
            "content_format": self._attachment_content_format(str(target.get('name') or ""), content_type),
            "resolved_from": resolved_from,
            "preview_truncated": preview_truncated,
            "available_attachments": [self._attachment_summary(item) for item in attachments],
            "metrics": {
                "attachment_count": len(attachments),
                "content_chars": len(resolved_content),
            },
        }

    async def _run_session_history(
        self,
        arguments: dict[str, Any],
        context: ToolExecutionContext,
    ) -> dict[str, Any]:
        store = self._require_session_store()
        action = str(arguments.get("action") or "history_summary").strip().lower()
        scope = str(arguments.get("scope") or "current_session").strip().lower()
        include_assistant = bool(arguments.get("include_assistant"))
        limit = int(arguments.get("limit") or 10)
        limit = max(1, min(limit, 50))

        current_session = await store.get_session(context.session_id)
        if current_session is None:
            return {
                "status": "failed",
                "ok": False,
                "summary": f"Session '{context.session_id}' was not found.",
                "error": "session_not_found",
            }

        sessions = [current_session]
        full_sessions = [current_session]
        if scope == "all_sessions":
            sessions = await store.list_sessions()
            # Only load full transcripts for actions that actually need message bodies.
            if action == "list_questions":
                full_sessions = []
                for item in sessions[:limit]:
                    loaded = await store.get_session(item.id)
                    if loaded is not None:
                        full_sessions.append(loaded)
            else:
                full_sessions = sessions
        else:
            scope = "current_session"

        if action == "count_sessions":
            status_counts: dict[str, int] = {}
            for item in sessions:
                status_key = item.status.value
                status_counts[status_key] = status_counts.get(status_key, 0) + 1
            return {
                "summary": (
                    f"Counted {len(sessions)} stored session(s) for scope '{scope}'."
                    if scope == "all_sessions"
                    else "Counted the current session."
                ),
                "scope": scope,
                "session_count": len(sessions),
                "status_counts": status_counts,
                "sessions": [self._session_overview(item) for item in sessions[:limit]],
                "metrics": {
                    "session_count": len(sessions),
                    "status_kind_count": len(status_counts),
                },
            }

        if action == "list_questions":
            questions = self._extract_questions(
                sessions=full_sessions,
                include_assistant=include_assistant,
                limit=limit,
            )
            return {
                "summary": f"Collected {len(questions)} historical question item(s) from scope '{scope}'.",
                "scope": scope,
                "questions": questions,
                "metrics": {
                    "question_count": len(questions),
                    "session_count": len(full_sessions),
                },
            }

        if action == "session_report":
            report = await self._build_session_report(
                session=current_session,
                store=store,
                include_assistant=include_assistant,
                limit=limit,
            )
            markdown = self._format_session_report_markdown(report)
            report_html = self._report_template_service.render_report_html(
                title=f"Session Report: {report['title']}",
                time_label=datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
                sender=context.selected_agent_key or "Enterprise AI QA Agent",
                markdown_content=markdown,
            )
            return {
                "summary": f"Generated a structured report for session '{current_session.id}'.",
                "scope": "current_session",
                "report": report,
                "report_markdown": markdown,
                "report_html": report_html,
                "artifacts": [
                    {
                        "type": "session_report_markdown",
                        "label": "session_report.md",
                        "content": markdown,
                    },
                    {
                        "type": "session_report_html",
                        "label": "session_report.html",
                        "content": report_html,
                    }
                ],
                "metrics": {
                    "message_count": report["message_count"],
                    "event_count": report["event_count"],
                    "snapshot_count": report["snapshot_count"],
                },
            }

        sessions_overview = [self._session_overview(item) for item in sessions[:limit]]
        recent_questions = (
            self._extract_questions(
                sessions=full_sessions,
                include_assistant=False,
                limit=limit,
            )
            if scope != "all_sessions"
            else []
        )
        return {
            "summary": f"Built a history summary for scope '{scope}' across {len(sessions)} session(s).",
            "scope": scope,
            "sessions": sessions_overview,
            "questions": recent_questions,
            "metrics": {
                "session_count": len(sessions),
                "question_count": len(recent_questions),
            },
        }

    async def _run_session_timeline(
        self,
        arguments: dict[str, Any],
        context: ToolExecutionContext,
    ) -> dict[str, Any]:
        store = self._require_session_store()
        memory_runtime = self._require_memory_runtime()
        session = await store.get_session(context.session_id)
        if session is None:
            return {
                "status": "failed",
                "ok": False,
                "summary": f"Session '{context.session_id}' was not found.",
                "error": "session_not_found",
            }

        limit = int(arguments.get("limit") or 20)
        limit = max(1, min(limit, 100))
        include_messages = bool(arguments.get("include_messages", True))
        include_events = bool(arguments.get("include_events", True))
        include_observations = bool(arguments.get("include_observations", True))

        timeline: list[dict[str, Any]] = []
        if include_messages:
            for item in session.messages[-limit:]:
                message_view = self._transcript_hygiene_service.classify_message(item)
                role = message_view["role"]
                content = message_view["content"]
                if not content:
                    continue
                timeline.append(
                    {
                        "kind": "message",
                        "timestamp": item.created_at.isoformat(),
                        "label": f"{role} message",
                        "role": role,
                        "content": content,
                        "transcript_bucket": message_view["transcript_bucket"],
                        "context_eligible": message_view["context_eligible"],
                        "response_mode": message_view["response_mode"],
                    }
                )
        if include_events:
            events = await store.list_events(session.id)
            for event in events[-limit:]:
                timeline.append(
                    {
                        "kind": "event",
                        "timestamp": event.timestamp.isoformat(),
                        "label": event.type,
                        "payload": dict(event.payload or {}),
                    }
                )
        if include_observations:
            observations = await memory_runtime.list_session_observations(session.id, top_k=limit)
            for observation in observations[-limit:]:
                timeline.append(
                    {
                        "kind": "observation",
                        "timestamp": observation.created_at.isoformat(),
                        "label": observation.title,
                        "category": observation.category,
                        "tool_key": observation.tool_key,
                        "summary": observation.summary,
                        "source": observation.source,
                    }
                )

        timeline.sort(key=lambda item: item.get("timestamp", ""))
        trimmed_timeline = timeline[-limit:]
        report = {
            "session": self._session_overview(session),
            "timeline_count": len(trimmed_timeline),
            "transcript_summary": self._transcript_hygiene_service.summarize_messages(session.messages),
            "includes": {
                "messages": include_messages,
                "events": include_events,
                "observations": include_observations,
            },
        }
        return {
            "summary": f"Built a chronological timeline with {len(trimmed_timeline)} entries for session '{session.id}'.",
            "timeline": trimmed_timeline,
            "report": report,
            "metrics": {
                "timeline_count": len(trimmed_timeline),
                "include_messages": int(include_messages),
                "include_events": int(include_events),
                "include_observations": int(include_observations),
            },
        }

    async def _run_observation_search(
        self,
        arguments: dict[str, Any],
        context: ToolExecutionContext,
    ) -> dict[str, Any]:
        memory_runtime = self._require_memory_runtime()
        query = str(arguments.get("query") or context.normalized_input or context.user_message).strip()
        if not query:
            return {
                "status": "failed",
                "ok": False,
                "summary": "No observation query was provided.",
                "error": "missing_query",
            }

        scope = str(arguments.get("scope") or "current_session").strip().lower()
        limit = int(arguments.get("limit") or 8)
        limit = max(1, min(limit, 20))
        category_filter = str(arguments.get("category") or "").strip()
        tool_key_filter = str(arguments.get("tool_key") or "").strip()

        result = await memory_runtime.retrieve_observation_context(
            session_id=context.session_id if scope != "all_sessions" else None,
            trace_id=context.trace_id,
            query=query,
            context=context.context_bundle,
            top_k=limit,
        )
        observations = []
        for item in result.hits:
            metadata = item.metadata or {}
            category = str(metadata.get("observation_category") or "")
            tool_key = str(metadata.get("tool_key") or "")
            if category_filter and category != category_filter:
                continue
            if tool_key_filter and tool_key != tool_key_filter:
                continue
            observations.append(
                {
                    "id": str(metadata.get("observation_id") or item.id),
                    "title": str(metadata.get("observation_title") or item.summary or item.source or item.id),
                    "summary": item.summary,
                    "content": item.content,
                    "scope": item.scope,
                    "source": item.source,
                    "category": category or "tool_execution",
                    "tool_key": tool_key or "tool",
                    "score": item.score or 0.0,
                    "created_at": item.created_at.isoformat(),
                    "tags": list(item.tags or []),
                }
            )

        observations = observations[:limit]
        return {
            "summary": f"Retrieved {len(observations)} observation(s) for query '{query}'.",
            "scope": scope,
            "query": query,
            "observations": observations,
            "metrics": {
                "observation_count": len(observations),
                "category_filter": category_filter,
                "tool_key_filter": tool_key_filter,
            },
        }

    async def _run_workflow_router(
        self,
        arguments: dict[str, Any],
        context: ToolExecutionContext,
    ) -> dict[str, Any]:
        query = str(arguments.get("query") or context.user_message).lower()
        route = "coordinator"
        rationale = "Defaulted to coordinator for orchestration."
        if any(token in query for token in ["browser", "page", "ui", "selenium", "playwright", "页面", "浏览器", "探索", "图谱"]):
            route = "ui-executor"
            rationale = "Detected browser or UI execution intent."
        elif any(
            token in query
            for token in [
                "cli",
                "terminal",
                "shell",
                "powershell",
                "command",
                "cmd",
                "bash",
                "终端",
                "命令行",
                "控制台",
                "shell命令",
            ]
        ):
            route = "ops-executor"
            rationale = "Detected terminal or command execution intent."
        elif any(token in query for token in ["api", "payload", "response", "request"]):
            route = "api-verifier"
            rationale = "Detected API verification intent."
        elif any(token in query for token in ["history", "session report", "conversation report", "previous questions", "历史", "会话报告", "对话报告", "之前问", "以前问"]):
            route = "report-analyst"
            rationale = "Detected session history or conversation reporting intent."
        elif any(token in query for token in ["email", "message", "notify", "notification", "send"]):
            route = "communication-agent"
            rationale = "Detected messaging or notification intent."
        elif any(token in query for token in ["report", "summary", "结论", "报告"]):
            route = "report-analyst"
            rationale = "Detected reporting intent."
        elif any(token in query for token in ["plan", "case", "scenario", "用例", "测试点"]):
            route = "qa-planner"
            rationale = "Detected planning or case design intent."

        return {
            "summary": f"Recommended execution route: {route}.",
            "route": route,
            "rationale": rationale,
        }

    async def _run_dom_inspector(
        self,
        arguments: dict[str, Any],
        context: ToolExecutionContext,
    ) -> dict[str, Any]:
        runtime = self._require_mcp_runtime()
        return await runtime.call(
            "browser-mcp",
            "inspect-page",
            arguments,
            asdict(context),
        )

    async def _run_ui_page_explorer(
        self,
        arguments: dict[str, Any],
        context: ToolExecutionContext,
    ) -> dict[str, Any]:
        if self._ui_exploration_service is None:
            return {"status": "failed", "error": "UI exploration service is not configured."}
        return await self._ui_exploration_service.explore(arguments, context)

    async def _run_browser_automation(
        self,
        arguments: dict[str, Any],
        context: ToolExecutionContext,
    ) -> dict[str, Any]:
        runtime = self._require_mcp_runtime()
        return await runtime.call(
            "browser-mcp",
            "browser-automation",
            arguments,
            asdict(context),
        )

    async def _run_browser_control(
        self,
        arguments: dict[str, Any],
        context: ToolExecutionContext,
    ) -> dict[str, Any]:
        runtime = self._require_mcp_runtime()
        return await runtime.call(
            "browser-mcp",
            "browser-control",
            arguments,
            asdict(context),
        )

    async def _run_api_tester(
        self,
        arguments: dict[str, Any],
        context: ToolExecutionContext,
    ) -> dict[str, Any]:
        endpoint = str(arguments.get("endpoint") or arguments.get("url") or "").strip()
        method = str(arguments.get("method") or "GET").upper()
        request_body = arguments.get("request_body") if isinstance(arguments.get("request_body"), dict) else {}
        response_body = arguments.get("response_body") if isinstance(arguments.get("response_body"), dict) else {}
        response_status = arguments.get("response_status")
        expected_status = arguments.get("expected_status")
        expected_fields = _to_string_list(arguments.get("expected_fields"))
        assertions = _to_string_list(arguments.get("assertions"))

        checks: list[dict[str, Any]] = []
        passed = 0
        failed = 0

        if expected_status is not None:
            status_ok = response_status == expected_status
            checks.append(
                {
                    "name": "status_code",
                    "passed": status_ok,
                    "expected": expected_status,
                    "actual": response_status,
                    "reason": "Response status matched expectation." if status_ok else "Response status did not match expectation.",
                }
            )
            passed += 1 if status_ok else 0
            failed += 0 if status_ok else 1

        for field_path in expected_fields:
            value, exists = _lookup_path(response_body, field_path)
            checks.append(
                {
                    "name": f"field:{field_path}",
                    "passed": exists,
                    "expected": "present",
                    "actual": value if exists else None,
                    "reason": "Field is present in the response payload." if exists else "Field is missing from the response payload.",
                }
            )
            passed += 1 if exists else 0
            failed += 0 if exists else 1

        for assertion in assertions:
            checks.append(
                {
                    "name": f"assertion:{len(checks)+1}",
                    "passed": True,
                    "expected": assertion,
                    "actual": "captured",
                    "reason": "Assertion was captured for downstream verification.",
                }
            )
            passed += 1

        if not checks:
            return {
                "status": "partial",
                "ok": True,
                "summary": f"No executable API checks were supplied for {method} {endpoint or 'request'}; captured the request context only.",
                "checks": [],
                "request": {"endpoint": endpoint, "method": method, "body": request_body},
                "response": {"status": response_status, "body": response_body},
                "metrics": {"check_count": 0, "passed": 0, "failed": 0},
                "artifacts": [],
            }

        overall_ok = failed == 0
        status = "completed" if overall_ok else "partial"
        return {
            "status": status,
            "ok": overall_ok,
            "summary": (
                f"Validated {len(checks)} API checks for {method} {endpoint or 'request'}; "
                f"{passed} passed and {failed} failed."
            ),
            "checks": checks,
            "request": {"endpoint": endpoint, "method": method, "body": request_body},
            "response": {"status": response_status, "body": response_body},
            "metrics": {
                "check_count": len(checks),
                "passed": passed,
                "failed": failed,
            },
            "artifacts": [
                {
                    "type": "api-check-summary",
                    "label": "api_checks.json",
                    "content": json.dumps({"checks": checks, "endpoint": endpoint, "method": method}, ensure_ascii=False, indent=2),
                }
            ],
            "error": None if overall_ok else "api_assertions_failed",
        }

    async def _run_cli_executor(
        self,
        arguments: dict[str, Any],
        context: ToolExecutionContext,
    ) -> dict[str, Any]:
        command = str(arguments.get("command") or "").strip()
        if not command:
            return {
                "status": "failed",
                "ok": False,
                "summary": "CLI Executor requires a non-empty command.",
                "error": "missing_command",
            }

        shell_name = str(arguments.get("shell") or "powershell").strip().lower()
        timeout_seconds = float(arguments.get("timeout_seconds") or 20)
        timeout_seconds = max(1.0, min(timeout_seconds, 300.0))
        cwd = self._resolve_cli_cwd(arguments.get("cwd"))
        artifact_dir = self._prepare_local_artifact_dir(context, "cli-executor")

        executable, shell_args = self._build_cli_invocation(shell_name, command)
        started_at = datetime.utcnow()
        try:
            completed = await asyncio.to_thread(
                subprocess.run,
                [shutil.which(executable) or executable, *shell_args],
                cwd=str(cwd),
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout_seconds,
            )
            stdout_text = completed.stdout or ""
            stderr_text = completed.stderr or ""
            exit_code = completed.returncode
            timed_out = False
        except subprocess.TimeoutExpired as exc:
            stdout_text = exc.stdout or ""
            stderr_text = exc.stderr or ""
            exit_code = -1
            timed_out = True

        status = "completed" if exit_code == 0 and not timed_out else "partial" if timed_out else "failed"
        ok = exit_code == 0 and not timed_out

        transcript = {
            "command": command,
            "shell": shell_name,
            "cwd": str(cwd),
            "started_at": started_at.isoformat(),
            "completed_at": datetime.utcnow().isoformat(),
            "exit_code": exit_code,
            "timed_out": timed_out,
            "stdout": stdout_text,
            "stderr": stderr_text,
        }
        transcript_path = artifact_dir / "cli_transcript.json"
        transcript_path.write_text(json.dumps(transcript, ensure_ascii=False, indent=2), encoding="utf-8")

        summary = (
            f"Command finished with exit code {exit_code} in {shell_name}."
            if not timed_out
            else f"Command timed out after {timeout_seconds:.0f}s in {shell_name}."
        )
        return {
            "status": status,
            "ok": ok,
            "summary": summary,
            "command": command,
            "shell": shell_name,
            "cwd": str(cwd),
            "exit_code": exit_code,
            "stdout": stdout_text[-8000:],
            "stderr": stderr_text[-8000:],
            "metrics": {
                "stdout_chars": len(stdout_text),
                "stderr_chars": len(stderr_text),
                "timed_out": timed_out,
            },
            "artifacts": [{"type": "cli_transcript", "path": str(transcript_path)}],
            "error": None if ok else ("timeout" if timed_out else stderr_text[-500:] or f"exit_code={exit_code}"),
        }

    async def _run_file_artifact_manager(
        self,
        arguments: dict[str, Any],
        context: ToolExecutionContext,
    ) -> dict[str, Any]:
        runtime = self._require_mcp_runtime()
        return await runtime.call(
            "filesystem-mcp",
            "write-artifact",
            arguments,
            asdict(context),
        )

    async def _run_message_dispatch(
        self,
        arguments: dict[str, Any],
        context: ToolExecutionContext,
    ) -> dict[str, Any]:
        arguments = self._coerce_message_dispatch_arguments(arguments)
        channel = str(arguments.get("channel") or "artifact").strip().lower()
        subject = str(arguments.get("subject") or "Runtime Notification").strip()
        content = str(arguments.get("content") or "").strip()
        content_markdown = str(arguments.get("content_markdown") or "").strip()
        content_html = str(arguments.get("content_html") or "").strip()
        sender = str(arguments.get("sender") or context.selected_agent_key or "Enterprise AI QA Agent").strip() or "Enterprise AI QA Agent"
        template_key = str(arguments.get("template_key") or "default").strip() or "default"
        template_context = arguments.get("template_context") if isinstance(arguments.get("template_context"), dict) else {}
        artifact_dir = self._prepare_local_artifact_dir(context, "message-dispatch")

        if not content and not content_html and not content_markdown:
            raw_payload = str(arguments.get("raw") or "").strip()
            if raw_payload:
                # Keep artifact delivery moving even when the model emitted a
                # single raw payload blob instead of fully structured fields.
                content = raw_payload

        if not content and not content_html and not content_markdown:
            return {
                "status": "failed",
                "ok": False,
                "summary": "Message Dispatch requires content, content_markdown, or content_html.",
                "error": "missing_content",
            }

        if content_markdown and not content_html:
            content_html = self._report_template_service.render_report_html(
                title=subject,
                time_label=str(arguments.get("time_label") or datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")),
                sender=sender,
                markdown_content=content_markdown,
                template_key=template_key,
                template_context=template_context,
            )
            if not content:
                content = content_markdown

        recipients = [
            str(item).strip()
            for item in (arguments.get("to") if isinstance(arguments.get("to"), list) else [])
            if str(item).strip()
        ]

        delivery_record = {
            "channel": channel,
            "subject": subject,
            "recipients": recipients,
            "content": content,
            "content_markdown": content_markdown,
            "content_html": content_html,
            "sender": sender,
            "template_key": template_key,
            "template_context": template_context,
            "session_id": context.session_id,
            "turn_id": context.turn_id,
            "trace_id": context.trace_id,
            "created_at": datetime.utcnow().isoformat(),
        }
        artifact_name = _slug(str(arguments.get("file_name") or subject or "message")) or "message"
        artifact_path = artifact_dir / f"{artifact_name}.json"
        artifact_path.write_text(json.dumps(delivery_record, ensure_ascii=False, indent=2), encoding="utf-8")

        if channel == "artifact":
            return {
                "summary": f"Persisted local message artifact '{artifact_path.name}'.",
                "delivery": {"channel": "artifact", "artifact_path": str(artifact_path), "sent": False},
                "artifacts": [{"type": "message_artifact", "path": str(artifact_path)}],
            }

        if channel == "email":
            if not recipients:
                return {
                    "status": "failed",
                    "ok": False,
                    "summary": "Email delivery requires at least one recipient in 'to'.",
                    "artifacts": [{"type": "message_artifact", "path": str(artifact_path)}],
                    "error": "missing_recipients",
                }
            email_result = await asyncio.to_thread(
                self._send_email_message,
                recipients,
                subject,
                content,
                content_html,
            )
            return {
                "summary": f"Delivered email notification to {len(recipients)} recipient(s).",
                "delivery": {"channel": "email", **email_result},
                "artifacts": [{"type": "message_artifact", "path": str(artifact_path)}],
            }

        return {
            "status": "failed",
            "ok": False,
            "summary": f"Unsupported message channel '{channel}'.",
            "artifacts": [{"type": "message_artifact", "path": str(artifact_path)}],
            "error": "unsupported_channel",
        }

    def _coerce_message_dispatch_arguments(
        self,
        arguments: dict[str, Any],
    ) -> dict[str, Any]:
        normalized = dict(arguments)
        raw_payload = normalized.get("raw")
        if not isinstance(raw_payload, str) or not raw_payload.strip():
            return normalized
        if any(
            str(normalized.get(key) or "").strip()
            for key in ("content", "content_markdown", "content_html")
        ):
            return normalized
        try:
            parsed = json.loads(raw_payload)
        except Exception:
            return normalized
        if not isinstance(parsed, dict):
            return normalized
        for key, value in parsed.items():
            normalized.setdefault(key, value)
        return normalized

    async def _run_send_email(
        self,
        arguments: dict[str, Any],
        context: ToolExecutionContext,
    ) -> dict[str, Any]:
        email_arguments = dict(arguments)
        email_arguments["channel"] = "email"
        if not str(email_arguments.get("subject") or "").strip():
            email_arguments["subject"] = "Runtime Notification"
        return await self._run_message_dispatch(email_arguments, context)

    async def _run_report_writer(
        self,
        arguments: dict[str, Any],
        context: ToolExecutionContext,
    ) -> dict[str, Any]:
        campaign_kind = str(context.context_bundle.get("campaign_kind") or "").strip()
        campaign_project_name = str(context.context_bundle.get("campaign_project_name") or "").strip()
        requested_template_key = str(arguments.get("template_key") or "").strip()
        template_key = requested_template_key or "default"
        if (
            template_key == "default"
            and campaign_kind in {"code_review_debate", "code_review_debate_summary"}
        ):
            template_key = "code_review_debate"

        title = str(arguments.get("title") or "QA Execution Report").strip()
        if (
            template_key == "code_review_debate"
            and (not title or title == "QA Execution Report")
            and campaign_project_name
        ):
            title = f"《{campaign_project_name}》的辩论报告"
        objective = str(arguments.get("objective") or context.user_message).strip()
        summary = str(arguments.get("summary") or "").strip()
        status = str(arguments.get("status") or "completed").strip()
        sender = str(arguments.get("sender") or context.selected_agent_key or "Enterprise AI QA Agent").strip() or "Enterprise AI QA Agent"
        content_markdown = str(arguments.get("content_markdown") or "").strip()
        generated_at = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        findings = arguments.get("findings") if isinstance(arguments.get("findings"), list) else []
        evidence = arguments.get("evidence") if isinstance(arguments.get("evidence"), list) else []
        recommendations = _to_string_list(arguments.get("recommendations"))
        report_sections: list[dict[str, Any]]
        template_context: dict[str, Any] | None = None
        report_artifact_stem = "qa_report"

        if template_key == "code_review_debate":
            project_name = str(arguments.get("project_name") or campaign_project_name or title).strip() or title
            approval_time = str(arguments.get("approval_time") or generated_at).strip() or generated_at
            approval_result = str(arguments.get("approval_result") or status).strip() or status
            reviewer_dispatches = (
                context.context_bundle.get("reviewer_dispatches")
                if isinstance(context.context_bundle.get("reviewer_dispatches"), list)
                else []
            )
            inferred_agent_count = len(reviewer_dispatches)
            agent_count = _clamp_int(
                arguments.get("agent_count"),
                minimum=0,
                maximum=99,
                default=inferred_agent_count,
            )
            result_rows = arguments.get("result_rows") if isinstance(arguments.get("result_rows"), list) else []
            report_sections = [
                {"title": "审批概览", "content": summary or f"围绕《{project_name}》生成的代码审批辩论报告。"},
                {"title": "最终结论", "content": approval_result},
                {"title": "审批结果", "content": self._build_code_review_category_sections(result_rows)},
                {"title": "证据与发现", "content": _format_object_list(findings)},
                {"title": "辩论证据", "content": _format_object_list(evidence)},
                {"title": "建议措施", "content": "\n".join(f"- {item}" for item in recommendations) or "None provided."},
            ]
            markdown = content_markdown or self._build_code_review_debate_markdown(
                title=title,
                project_name=project_name,
                approval_time=approval_time,
                approval_result=approval_result,
                agent_count=agent_count,
                report_sections=report_sections,
                result_rows=result_rows,
            )
            template_context = {
                "project_name": project_name,
                "approval_result": approval_result,
                "agent_count": str(agent_count),
                "result_summary_markdown": self._build_code_review_result_summary_markdown(result_rows),
            }
            report_artifact_stem = "code_review_debate_report"
            generated_at = approval_time
        else:
            report_sections = [
                {"title": "Overview", "content": summary or f"Report generated for: {objective or title}."},
                {"title": "Status", "content": status},
                {"title": "Findings", "content": _format_object_list(findings)},
                {"title": "Evidence", "content": _format_object_list(evidence)},
                {"title": "Recommendations", "content": "\n".join(f"- {item}" for item in recommendations) or "None provided."},
            ]
            markdown_lines = [f"# {title}", "", f"Status: {status}"]
            if objective:
                markdown_lines.extend(["", f"Objective: {objective}"])
            for section in report_sections:
                markdown_lines.extend(["", f"## {section['title']}", "", str(section["content"])])
            markdown = content_markdown or "\n".join(markdown_lines).strip()

        report_html = self._report_template_service.render_report_html(
            title=title,
            time_label=generated_at,
            sender=sender,
            markdown_content=markdown,
            template_key=template_key,
            template_context=template_context,
        )

        return {
            "summary": f"Generated a structured QA report with {len(report_sections)} sections.",
            "report_title": title,
            "report_sections": report_sections,
            "report_markdown": markdown,
            "report_html": report_html,
            "sender": sender,
            "generated_at": generated_at,
            "template_key": template_key,
            "template_context": template_context,
            "artifacts": [
                {
                    "type": "report_markdown",
                    "label": f"{report_artifact_stem}.md",
                    "content": markdown,
                },
                {
                    "type": "report_html",
                    "label": f"{report_artifact_stem}.html",
                    "content": report_html,
                }
            ],
            "metrics": {
                "section_count": len(report_sections),
                "finding_count": len(findings),
                "evidence_count": len(evidence),
                "recommendation_count": len(recommendations),
            },
        }

    async def _run_project_source_loader(
        self,
        arguments: dict[str, Any],
        context: ToolExecutionContext,
    ) -> dict[str, Any]:
        project_source = normalize_project_source(arguments)
        timeout_seconds = _clamp_float(arguments.get("timeout_seconds"), minimum=5.0, maximum=60.0, default=20.0)
        try:
            source_info = (
                await self._collect_ssh_source_info(project_source, timeout_seconds)
                if project_source.source_type == "ssh"
                else await self._collect_local_source_info(project_source, timeout_seconds)
            )
        except Exception as exc:
            return {
                "status": "failed",
                "ok": False,
                "summary": f"Failed to load project source '{project_source.project_name}': {exc}",
                "project_source": project_source.model_dump(mode="python"),
                "error": str(exc),
            }
        return {
            "summary": (
                f"Loaded project source '{project_source.project_name}' via {project_source.source_type} "
                f"at {source_info['root_path']}."
            ),
            "project_source": project_source.model_dump(mode="python"),
            "source_info": source_info,
            "metrics": {
                "top_entry_count": len(source_info.get("top_entries", [])),
                "git_repo": 1 if source_info.get("is_git_repo") else 0,
            },
        }

    async def _run_project_tree_scanner(
        self,
        arguments: dict[str, Any],
        context: ToolExecutionContext,
    ) -> dict[str, Any]:
        project_source = normalize_project_source(arguments)
        max_depth = _clamp_int(arguments.get("max_depth"), minimum=1, maximum=8, default=3)
        max_files = _clamp_int(arguments.get("max_files"), minimum=20, maximum=2000, default=400)
        timeout_seconds = _clamp_float(arguments.get("timeout_seconds"), minimum=5.0, maximum=90.0, default=30.0)
        try:
            tree_summary = (
                await self._scan_ssh_project_tree(project_source, max_depth=max_depth, max_files=max_files, timeout_seconds=timeout_seconds)
                if project_source.source_type == "ssh"
                else await self._scan_local_project_tree(project_source, max_depth=max_depth, max_files=max_files)
            )
        except Exception as exc:
            return {
                "status": "failed",
                "ok": False,
                "summary": f"Failed to scan project tree for '{project_source.project_name}': {exc}",
                "project_source": project_source.model_dump(mode="python"),
                "error": str(exc),
            }
        return {
            "summary": (
                f"Scanned project tree for '{project_source.project_name}' and sampled "
                f"{len(tree_summary.get('sample_files', []))} file(s)."
            ),
            "project_source": project_source.model_dump(mode="python"),
            "tree_summary": tree_summary,
            "sample_files": tree_summary.get("sample_files", []),
            "metrics": {
                "sample_file_count": len(tree_summary.get("sample_files", [])),
                "top_module_count": len(tree_summary.get("top_modules", [])),
                "extension_count": len(tree_summary.get("extensions", {})),
            },
        }

    async def _run_project_file_reader(
        self,
        arguments: dict[str, Any],
        context: ToolExecutionContext,
    ) -> dict[str, Any]:
        project_source = normalize_project_source(arguments)
        file_path = str(arguments.get("path") or arguments.get("file_path") or "").strip()
        if not file_path:
            return {
                "status": "failed",
                "ok": False,
                "summary": "Project file reader requires a path or file_path.",
                "error": "missing_file_path",
            }
        start_line = _clamp_int(arguments.get("start_line"), minimum=1, maximum=500000, default=1)
        end_line = _clamp_int(arguments.get("end_line"), minimum=start_line, maximum=500000, default=start_line + 199)
        max_chars = _clamp_int(arguments.get("max_chars"), minimum=500, maximum=120000, default=16000)
        timeout_seconds = _clamp_float(arguments.get("timeout_seconds"), minimum=5.0, maximum=90.0, default=20.0)
        try:
            file_payload = (
                await self._read_ssh_project_file(
                    project_source,
                    file_path=file_path,
                    start_line=start_line,
                    end_line=end_line,
                    max_chars=max_chars,
                    timeout_seconds=timeout_seconds,
                )
                if project_source.source_type == "ssh"
                else self._read_local_project_file(
                    project_source,
                    file_path=file_path,
                    start_line=start_line,
                    end_line=end_line,
                    max_chars=max_chars,
                )
            )
        except Exception as exc:
            return {
                "status": "failed",
                "ok": False,
                "summary": f"Failed to read file '{file_path}': {exc}",
                "project_source": project_source.model_dump(mode="python"),
                "error": str(exc),
            }
        return {
            "summary": (
                f"Read file '{file_payload['file']['path']}' lines "
                f"{file_payload['file']['start_line']}-{file_payload['file']['end_line']}."
            ),
            "project_source": project_source.model_dump(mode="python"),
            **file_payload,
        }

    async def _run_project_diff_reader(
        self,
        arguments: dict[str, Any],
        context: ToolExecutionContext,
    ) -> dict[str, Any]:
        project_source = normalize_project_source(arguments)
        timeout_seconds = _clamp_float(arguments.get("timeout_seconds"), minimum=5.0, maximum=90.0, default=20.0)
        max_chars = _clamp_int(arguments.get("max_chars"), minimum=1000, maximum=200000, default=24000)
        try:
            diff_payload = (
                await self._read_ssh_project_diff(project_source, arguments, timeout_seconds=timeout_seconds, max_chars=max_chars)
                if project_source.source_type == "ssh"
                else await self._read_local_project_diff(project_source, arguments, timeout_seconds=timeout_seconds, max_chars=max_chars)
            )
        except Exception as exc:
            return {
                "status": "failed",
                "ok": False,
                "summary": f"Failed to read project diff for '{project_source.project_name}': {exc}",
                "project_source": project_source.model_dump(mode="python"),
                "error": str(exc),
            }
        return {
            "summary": (
                f"Collected git diff context for '{project_source.project_name}' with "
                f"{len(diff_payload.get('status_lines', []))} status line(s)."
            ),
            "project_source": project_source.model_dump(mode="python"),
            **diff_payload,
        }

    async def _run_code_review_orchestrator(
        self,
        arguments: dict[str, Any],
        context: ToolExecutionContext,
    ) -> dict[str, Any]:
        bootstrap = await self._build_code_review_bootstrap(arguments, context)
        debate_plan = self._resolve_code_review_debate_plan(arguments, bootstrap, context)
        effective_arguments = {
            **arguments,
            "cross_review_rounds": debate_plan["cross_review_round_count"],
            "debate_time_budget_minutes": debate_plan["debate_time_budget_minutes"],
        }
        campaign = build_code_review_campaign(effective_arguments, context)
        campaign["bootstrap"] = bootstrap
        campaign["debate_plan"] = debate_plan
        scanned_file_count = int(((bootstrap.get("tree_summary") or {}) if isinstance(bootstrap.get("tree_summary"), dict) else {}).get("scanned_file_count") or 0)
        requested_reviewer_limit = _clamp_int(arguments.get("reviewer_count"), minimum=0, maximum=5, default=0)
        reviewer_limit = requested_reviewer_limit
        if reviewer_limit <= 0:
            if scanned_file_count and scanned_file_count <= 80:
                reviewer_limit = 3
            elif scanned_file_count and scanned_file_count <= 200:
                reviewer_limit = 4
        workers_payload = campaign["dispatch_payload"].get("workers", [])
        followup_workers_payload = campaign["dispatch_payload"].get("followup_workers", [])
        if reviewer_limit > 0 and isinstance(workers_payload, list):
            campaign["dispatch_payload"]["workers"] = workers_payload[:reviewer_limit]
            if isinstance(followup_workers_payload, list):
                limited_followup_workers: list[dict[str, Any]] = []
                grouped_followup_workers: dict[int, list[dict[str, Any]]] = {}
                for item in followup_workers_payload:
                    if not isinstance(item, dict):
                        continue
                    context_payload = item.get("context")
                    debate_round_index = 0
                    if isinstance(context_payload, dict):
                        debate_round_index = int(context_payload.get("debate_round_index") or 0)
                    grouped_followup_workers.setdefault(debate_round_index, []).append(item)
                for round_index in sorted(grouped_followup_workers):
                    limited_followup_workers.extend(grouped_followup_workers[round_index][:reviewer_limit])
                campaign["dispatch_payload"]["followup_workers"] = limited_followup_workers
            campaign["review_team"] = campaign["review_team"][:reviewer_limit]
            campaign["metrics"]["reviewer_count"] = len(campaign["dispatch_payload"]["workers"])
        bootstrap_brief = self._build_code_review_bootstrap_brief(bootstrap)
        for worker in campaign["dispatch_payload"].get("workers", []):
            if isinstance(worker, dict):
                prompt = str(worker.get("prompt") or "").strip()
                if prompt and bootstrap_brief:
                    worker["prompt"] = (
                        f"{prompt}\n\n"
                        "Bootstrap digest:\n"
                        f"{bootstrap_brief}\n\n"
                        "Execution constraints:\n"
                        "- Start with findings from the bootstrap digest before exploring more files.\n"
                        "- Do not rerun project-source-loader or project-tree-scanner unless the bootstrap digest is missing critical evidence.\n"
                        "- During the first pass, read at most 3 targeted files with project-file-reader.\n"
                        "- Avoid shell-style exploration and focus on evidence-backed findings quickly.\n"
                        "- If you already have enough evidence for a finding, write it immediately instead of continuing broad exploration.\n"
                    )
                worker_context = worker.get("context")
                if isinstance(worker_context, dict):
                    worker_context["project_bootstrap"] = bootstrap
                    worker_context["debate_plan"] = debate_plan
        for worker in campaign["dispatch_payload"].get("followup_workers", []):
            if isinstance(worker, dict):
                prompt = str(worker.get("prompt") or "").strip()
                if prompt and bootstrap_brief:
                    worker["prompt"] = (
                        f"{prompt}\n\n"
                        "Bootstrap digest:\n"
                        f"{bootstrap_brief}\n\n"
                        "Execution constraints:\n"
                        "- This is the rebuttal round, so begin from peer findings instead of rediscovering the repository.\n"
                        "- Use the bootstrap digest only to validate or challenge claims precisely.\n"
                        "- Read at most 2 additional targeted files unless a claim is impossible to evaluate otherwise.\n"
                        f"- Stay within the moderator budget of approximately {debate_plan['debate_time_budget_minutes']} minutes for the whole debate.\n"
                    )
                worker_context = worker.get("context")
                if isinstance(worker_context, dict):
                    worker_context["project_bootstrap"] = bootstrap
                    worker_context["debate_plan"] = debate_plan
        summary_agent = campaign.get("summary_agent", {})
        if isinstance(summary_agent, dict):
            summary_prompt = str(summary_agent.get("prompt") or "").strip()
            if summary_prompt and bootstrap_brief:
                summary_agent["prompt"] = (
                    f"{summary_prompt}\n\n"
                    "Bootstrap digest:\n"
                    f"{bootstrap_brief}\n\n"
                    "Debate time budget:\n"
                    f"- moderator_budget_minutes: {debate_plan['debate_time_budget_minutes']}\n"
                    f"- context_window_tokens: {debate_plan['model_context_window_tokens']}\n"
                    f"- context_pressure: {debate_plan['context_pressure']}\n\n"
                    "Execution constraints:\n"
                    "- Synthesize reviewer outputs first; do not restart broad repository exploration unless reviewer evidence is clearly insufficient.\n"
                    "- Prefer report generation over additional discovery once proposer/support/challenge relationships are established.\n"
                )
        summary_context = summary_agent.get("context")
        if isinstance(summary_context, dict):
            summary_context["project_bootstrap"] = bootstrap
            summary_context["debate_plan"] = debate_plan
        campaign["metrics"]["debate_time_budget_minutes"] = debate_plan["debate_time_budget_minutes"]
        campaign["metrics"]["cross_review_round_count"] = debate_plan["cross_review_round_count"]
        launch_workers = bool(campaign.get("launch_workers", True))
        dispatch_result: dict[str, Any] | None = None
        if launch_workers:
            coordinator_runtime = self._require_coordinator_runtime()
            dispatch_result = await coordinator_runtime.dispatch(
                payload=campaign["dispatch_payload"],
                context=asdict(context),
            )

        workers = dispatch_result.get("workers", []) if isinstance(dispatch_result, dict) else []
        dispatch_status = str(dispatch_result.get("status") or "").strip() if isinstance(dispatch_result, dict) else ""
        return {
            "status": "partial" if launch_workers else "completed",
            "summary": (
                f"Initialized code review debate campaign for '{campaign['project_source']['project_name']}' "
                f"and launched {len(workers)} reviewer worker session(s)."
                if launch_workers
                else f"Prepared code review debate campaign for '{campaign['project_source']['project_name']}'."
            ),
            "approval_decision": "pending_debate",
            "findings": [],
            "campaign": campaign,
            "review_plan": [
                "Normalize project source and scope",
                "Create review points for project or target paths",
                "Launch parallel round-1 reviewer sessions",
                "Launch parallel round-2 cross-review rebuttals",
                "Collect debated findings for summary synthesis",
                "Produce approval-ready structured report",
            ],
            "targets": [point["target"] for point in campaign["review_points"]],
            "change_summary": str(arguments.get("change_summary") or context.user_message).strip(),
            "dispatch": dispatch_result or {
                "status": "not_started",
                "summary": "Reviewer dispatch was skipped for this invocation.",
                "workers": [],
            },
            "bootstrap": bootstrap,
            "next_steps": [
                "Connect repository-aware project readers for local and SSH sources",
                "Feed reviewer outputs into cross-review rounds and summary synthesis",
                "Persist debated findings into the evaluation harness and report center",
            ],
            "metrics": {
                **campaign.get("metrics", {}),
                "bootstrap_ok": 1 if bootstrap.get("ok", False) else 0,
                "launched_worker_count": len(workers),
                "dispatch_started": launch_workers,
                "dispatch_status": dispatch_status or "not_started",
            },
        }

    async def _run_ui_automation_runner(
        self,
        arguments: dict[str, Any],
        context: ToolExecutionContext,
    ) -> dict[str, Any]:
        return await self._ui_automation_mode_runtime.handle(arguments, context)

    async def _run_api_test_runner(
        self,
        arguments: dict[str, Any],
        context: ToolExecutionContext,
    ) -> dict[str, Any]:
        request_context = (
            context.context_bundle.get("api_testing_request")
            if isinstance(context.context_bundle.get("api_testing_request"), dict)
            else {}
        )
        endpoint = str(arguments.get("endpoint") or request_context.get("endpoint") or "").strip()
        method = str(arguments.get("method") or request_context.get("method") or "").strip().upper()
        objective = str(arguments.get("objective") or request_context.get("objective") or context.user_message).strip()
        verification_focus = str(arguments.get("verification_focus") or request_context.get("verification_focus") or "general").strip()
        return {
            "status": "partial",
            "summary": "API testing mode scaffold is registered. Dedicated contract and assertion flows can now be attached to this entry tool.",
            "endpoint": endpoint,
            "method": method,
            "objective": objective,
            "verification_focus": verification_focus,
            "checks": [],
            "next_steps": ["Bind this tool to API contract checks, payload assertions, and report generation."],
        }

    async def _run_security_scan_runner(
        self,
        arguments: dict[str, Any],
        context: ToolExecutionContext,
    ) -> dict[str, Any]:
        return self._build_placeholder_mode_result(
            mode_key="security_testing",
            summary="Security testing mode scaffold is ready; specialized scanners are not connected yet.",
            arguments=arguments,
            context=context,
        )

    async def _run_performance_test_runner(
        self,
        arguments: dict[str, Any],
        context: ToolExecutionContext,
    ) -> dict[str, Any]:
        return self._build_placeholder_mode_result(
            mode_key="performance_testing",
            summary="Performance testing mode scaffold is ready; benchmark runners are not connected yet.",
            arguments=arguments,
            context=context,
        )

    async def _run_smoke_suite_runner(
        self,
        arguments: dict[str, Any],
        context: ToolExecutionContext,
    ) -> dict[str, Any]:
        return self._build_placeholder_mode_result(
            mode_key="smoke_testing",
            summary="Smoke testing mode scaffold is ready; critical-path suites are not connected yet.",
            arguments=arguments,
            context=context,
        )

    def _build_placeholder_mode_result(
        self,
        mode_key: str,
        summary: str,
        arguments: dict[str, Any],
        context: ToolExecutionContext,
    ) -> dict[str, Any]:
        request_context_key = f"{mode_key}_request"
        request_context = (
            context.context_bundle.get(request_context_key)
            if isinstance(context.context_bundle.get(request_context_key), dict)
            else {}
        )
        return {
            "status": "partial",
            "summary": summary,
            "mode_key": mode_key,
            "objective": str(arguments.get("objective") or request_context.get("objective") or context.user_message).strip(),
            "recognized_intent": dict(context.context_bundle.get("mode_intent") or {}),
            "request": request_context,
            "next_steps": [
                "Replace placeholder runtime with dedicated mode executor",
                "Attach verification and evaluation policies",
            ],
        }

    async def _collect_local_source_info(
        self,
        project_source,
        timeout_seconds: float,
    ) -> dict[str, Any]:
        root = resolve_local_project_root(project_source)
        if not root.exists():
            raise FileNotFoundError(f"Project root was not found: {root}")
        if not root.is_dir():
            raise NotADirectoryError(f"Project root is not a directory: {root}")

        top_entries = [
            {
                "name": item.name,
                "kind": "directory" if item.is_dir() else "file",
            }
            for item in sorted(root.iterdir(), key=lambda value: (not value.is_dir(), value.name.lower()))[:25]
        ]
        git_root = ""
        branch = project_source.branch
        git_check = await self._run_subprocess("git", ["-C", str(root), "rev-parse", "--show-toplevel"], timeout_seconds=timeout_seconds)
        is_git_repo = git_check["ok"]
        if is_git_repo:
            git_root = git_check["stdout"].strip()
            if not branch:
                branch_result = await self._run_subprocess(
                    "git",
                    ["-C", git_root, "branch", "--show-current"],
                    timeout_seconds=timeout_seconds,
                )
                branch = branch_result["stdout"].strip() if branch_result["ok"] else ""

        return {
            "access_mode": "local",
            "root_path": str(root),
            "exists": True,
            "is_directory": True,
            "is_git_repo": is_git_repo,
            "git_root": git_root,
            "branch": branch,
            "top_entries": top_entries,
        }

    async def _build_code_review_bootstrap(
        self,
        arguments: dict[str, Any],
        context: ToolExecutionContext,
    ) -> dict[str, Any]:
        source_result = await self._run_project_source_loader(arguments, context)
        tree_result = await self._run_project_tree_scanner(arguments, context)
        diff_result = await self._run_project_diff_reader(
            {
                **arguments,
                "max_chars": arguments.get("max_chars") or 12000,
            },
            context,
        )
        source_ok = source_result.get("ok", True)
        tree_ok = tree_result.get("ok", True)
        diff_ok = diff_result.get("ok", True)
        project_source = source_result.get("project_source") or normalize_project_source(arguments).model_dump(mode="python")
        return {
            "ok": bool(source_ok and tree_ok),
            "project_source": project_source,
            "source_info": source_result.get("source_info"),
            "tree_summary": tree_result.get("tree_summary"),
            "sample_files": tree_result.get("sample_files", []),
            "diff_summary": {
                "ok": diff_ok,
                "diff_mode": diff_result.get("diff_mode"),
                "commit_range": diff_result.get("commit_range"),
                "status_lines": diff_result.get("status_lines", []),
                "diff_stat": diff_result.get("diff_stat"),
                "diff_text": diff_result.get("diff_text"),
                "truncated": diff_result.get("truncated", False),
                "error": diff_result.get("error"),
            },
            "errors": {
                "source": source_result.get("error"),
                "tree": tree_result.get("error"),
                "diff": diff_result.get("error"),
            },
        }

    def _build_code_review_bootstrap_brief(self, bootstrap: dict[str, Any]) -> str:
        if not isinstance(bootstrap, dict):
            return ""

        project_source = bootstrap.get("project_source") if isinstance(bootstrap.get("project_source"), dict) else {}
        source_info = bootstrap.get("source_info") if isinstance(bootstrap.get("source_info"), dict) else {}
        tree_summary = bootstrap.get("tree_summary") if isinstance(bootstrap.get("tree_summary"), dict) else {}
        diff_summary = bootstrap.get("diff_summary") if isinstance(bootstrap.get("diff_summary"), dict) else {}
        sample_files = bootstrap.get("sample_files") if isinstance(bootstrap.get("sample_files"), list) else []

        project_name = str(project_source.get("project_name") or source_info.get("root_path") or "Unnamed Project").strip()
        branch = str(source_info.get("branch") or project_source.get("branch") or "unknown").strip()
        scanned_file_count = int(tree_summary.get("scanned_file_count") or 0)
        directory_count = int(tree_summary.get("directory_count") or 0)
        top_modules = [
            str(item).strip()
            for item in (tree_summary.get("top_modules") if isinstance(tree_summary.get("top_modules"), list) else [])
            if str(item).strip()
        ][:6]
        sample_paths: list[str] = []
        for item in sample_files[:6]:
            if not isinstance(item, dict):
                continue
            path = str(item.get("path") or item.get("relative_path") or "").strip()
            if path:
                sample_paths.append(path)
        diff_stat = str(diff_summary.get("diff_stat") or "").strip()
        status_lines = [
            str(item).strip()
            for item in (diff_summary.get("status_lines") if isinstance(diff_summary.get("status_lines"), list) else [])
            if str(item).strip()
        ][:5]

        lines = [
            f"- project_name: {project_name}",
            f"- branch: {branch}",
            f"- scanned_files: {scanned_file_count}",
            f"- directories: {directory_count}",
            f"- top_modules: {', '.join(top_modules) if top_modules else 'unknown'}",
            f"- diff_stat: {diff_stat or 'no diff summary'}",
            f"- changed_paths: {', '.join(status_lines) if status_lines else 'none captured'}",
            f"- sampled_files: {', '.join(sample_paths) if sample_paths else 'none captured'}",
        ]
        return "\n".join(lines)

    def _resolve_code_review_debate_plan(
        self,
        arguments: dict[str, Any],
        bootstrap: dict[str, Any],
        context: ToolExecutionContext,
    ) -> dict[str, Any]:
        requested_budget = _clamp_int(
            arguments.get("debate_time_budget_minutes"),
            minimum=5,
            maximum=60,
            default=0,
        )
        legacy_round_request = _clamp_int(
            arguments.get("cross_review_rounds"),
            minimum=1,
            maximum=4,
            default=0,
        )
        if legacy_round_request <= 0:
            legacy_round_request = _clamp_int(
                arguments.get("debate_round_count"),
                minimum=1,
                maximum=4,
                default=0,
            )
        if requested_budget <= 0 and legacy_round_request > 0:
            # Backward compatibility for older callers that still drive the
            # debate by round count. We translate the legacy round request into
            # a moderator time budget, then continue through the same
            # time-budget path as newer callers.
            requested_budget = {
                1: 15,
                2: 28,
                3: 42,
                4: 55,
            }.get(legacy_round_request, 28)
        tree_summary = bootstrap.get("tree_summary") if isinstance(bootstrap.get("tree_summary"), dict) else {}
        diff_summary = bootstrap.get("diff_summary") if isinstance(bootstrap.get("diff_summary"), dict) else {}

        scanned_file_count = int(tree_summary.get("scanned_file_count") or 0)
        directory_count = int(tree_summary.get("directory_count") or 0)
        changed_path_count = len(diff_summary.get("status_lines", [])) if isinstance(diff_summary.get("status_lines"), list) else 0

        reviewer_count = _clamp_int(arguments.get("reviewer_count"), minimum=2, maximum=5, default=3)
        model_config = self._resolve_code_review_model_config(arguments, context)
        context_window_tokens = int(model_config.max_tokens) if model_config is not None else 8192
        supports_reasoning = bool(model_config.supports_reasoning) if model_config is not None else False

        if context_window_tokens <= 8192:
            context_pressure = "high"
            context_round_cap = 2
            context_budget_penalty = 8
        elif context_window_tokens <= 32768:
            context_pressure = "medium"
            context_round_cap = 3
            context_budget_penalty = 3
        else:
            context_pressure = "low"
            context_round_cap = 4
            context_budget_penalty = 0

        if scanned_file_count <= 80:
            project_size = "small"
            base_budget = 12
        elif scanned_file_count <= 200:
            project_size = "medium"
            base_budget = 22
        elif scanned_file_count <= 500:
            project_size = "large"
            base_budget = 34
        else:
            project_size = "xlarge"
            base_budget = 46

        complexity_bonus = min(8, directory_count // 12)
        diff_bonus = min(6, max(0, changed_path_count // 8))
        reviewer_bonus = max(0, reviewer_count - 3)
        reasoning_bonus = 4 if supports_reasoning else 0

        auto_budget = base_budget + complexity_bonus + diff_bonus + reviewer_bonus + reasoning_bonus - context_budget_penalty
        effective_budget = requested_budget if requested_budget > 0 else auto_budget
        debate_time_budget_minutes = max(8, min(60, effective_budget))

        if debate_time_budget_minutes <= 15:
            derived_rounds = 1
        elif debate_time_budget_minutes <= 28:
            derived_rounds = 2
        elif debate_time_budget_minutes <= 42:
            derived_rounds = 3
        else:
            derived_rounds = 4
        cross_review_round_count = min(context_round_cap, derived_rounds)

        return {
            "strategy": "time_budget",
            "requested_time_budget_minutes": requested_budget,
            "debate_time_budget_minutes": debate_time_budget_minutes,
            "cross_review_round_count": cross_review_round_count,
            "project_size": project_size,
            "scanned_file_count": scanned_file_count,
            "directory_count": directory_count,
            "changed_path_count": changed_path_count,
            "reviewer_count": reviewer_count,
            "model_context_window_tokens": context_window_tokens,
            "supports_reasoning": supports_reasoning,
            "context_pressure": context_pressure,
        }

    def _resolve_code_review_model_config(
        self,
        arguments: dict[str, Any],
        context: ToolExecutionContext,
    ) -> ModelConfigRecord | None:
        if self._model_registry is None:
            return None
        candidate_keys = [
            str(arguments.get("worker_model_key") or "").strip(),
            str(arguments.get("summary_model_key") or "").strip(),
            str(context.selected_model_key or "").strip(),
            str(context.context_bundle.get("preferred_model") or "").strip(),
        ]
        for model_key in candidate_keys:
            if not model_key:
                continue
            try:
                return self._model_registry.get_runtime_config(model_key)
            except Exception:
                continue
        try:
            return self._model_registry.get_default_runtime_config()
        except Exception:
            return None

    async def _collect_ssh_source_info(
        self,
        project_source,
        timeout_seconds: float,
    ) -> dict[str, Any]:
        root_value = project_source_root(project_source).replace("\\", "/")
        script = (
            f"ROOT={shlex.quote(root_value)}; "
            'if [ ! -d "$ROOT" ]; then echo "__ERROR__:missing_root"; exit 4; fi; '
            'echo "__TOP__"; '
            'find "$ROOT" -mindepth 1 -maxdepth 1 | head -n 25; '
            'echo "__TOP_END__"; '
            'if command -v git >/dev/null 2>&1 && git -C "$ROOT" rev-parse --is-inside-work-tree >/dev/null 2>&1; then '
            'echo "__GIT__"; '
            'git -C "$ROOT" rev-parse --show-toplevel; '
            'git -C "$ROOT" branch --show-current 2>/dev/null; '
            'else echo "__NO_GIT__"; fi'
        )
        result = await self._run_ssh_shell(project_source, script, timeout_seconds=timeout_seconds)
        if not result["ok"]:
            raise RuntimeError(result["stderr"].strip() or result["stdout"].strip() or "SSH source probe failed.")

        top_entries: list[dict[str, Any]] = []
        is_git_repo = False
        git_root = ""
        branch = project_source.branch
        section = ""
        git_lines: list[str] = []
        for raw_line in result["stdout"].splitlines():
            line = raw_line.strip()
            if not line:
                continue
            if line == "__TOP__":
                section = "top"
                continue
            if line == "__TOP_END__":
                section = ""
                continue
            if line == "__GIT__":
                section = "git"
                is_git_repo = True
                continue
            if line == "__NO_GIT__":
                section = ""
                continue
            if line.startswith("__ERROR__:"):
                raise RuntimeError(line.removeprefix("__ERROR__:"))
            if section == "top":
                top_entries.append(
                    {
                        "name": PurePosixPath(line).name,
                        "kind": "unknown",
                        "path": line,
                    }
                )
            elif section == "git":
                git_lines.append(line)

        if git_lines:
            git_root = git_lines[0]
        if len(git_lines) > 1 and not branch:
            branch = git_lines[1]

        return {
            "access_mode": "ssh",
            "root_path": root_value,
            "exists": True,
            "is_directory": True,
            "is_git_repo": is_git_repo,
            "git_root": git_root,
            "branch": branch,
            "top_entries": top_entries,
            "ssh_target": self._build_ssh_target(project_source),
        }

    async def _scan_local_project_tree(
        self,
        project_source,
        max_depth: int,
        max_files: int,
    ) -> dict[str, Any]:
        root = resolve_local_project_root(project_source)
        if not root.exists():
            raise FileNotFoundError(f"Project root was not found: {root}")

        sample_files: list[dict[str, Any]] = []
        extension_counter: Counter[str] = Counter()
        language_counter: Counter[str] = Counter()
        top_modules: set[str] = set()
        directories_seen: set[str] = set()
        scanned_files = 0
        scan_truncated = False

        for dirpath, dirnames, filenames in os.walk(root):
            current_path = Path(dirpath)
            relative_dir = current_path.relative_to(root).as_posix() if current_path != root else "."
            depth = 0 if relative_dir == "." else len(PurePosixPath(relative_dir).parts)
            dirnames[:] = [
                item
                for item in dirnames
                if item not in DEFAULT_IGNORED_NAMES and depth < max_depth
            ]
            directories_seen.add(relative_dir)
            if relative_dir != ".":
                top_modules.add(relative_dir.split("/")[0])
            if depth > max_depth:
                continue
            for filename in sorted(filenames):
                full_path = current_path / filename
                relative_path = full_path.relative_to(root).as_posix()
                extension = full_path.suffix.lower() or "<none>"
                extension_counter[extension] += 1
                language_counter[_language_from_extension(extension)] += 1
                scanned_files += 1
                if len(sample_files) < 50:
                    sample_files.append(
                        {
                            "path": relative_path,
                            "extension": extension,
                            "size_bytes": full_path.stat().st_size,
                        }
                    )
                if scanned_files >= max_files:
                    scan_truncated = True
                    break
            if scan_truncated:
                break

        top_entries = [
            {
                "name": item.name,
                "kind": "directory" if item.is_dir() else "file",
            }
            for item in sorted(root.iterdir(), key=lambda value: (not value.is_dir(), value.name.lower()))[:25]
        ]
        return {
            "access_mode": "local",
            "root_path": str(root),
            "max_depth": max_depth,
            "scan_truncated": scan_truncated,
            "scanned_file_count": scanned_files,
            "directory_count": len(directories_seen),
            "top_modules": sorted(top_modules)[:50],
            "top_entries": top_entries,
            "extensions": dict(extension_counter.most_common(20)),
            "languages": dict(language_counter.most_common(15)),
            "sample_files": sample_files,
        }

    async def _scan_ssh_project_tree(
        self,
        project_source,
        max_depth: int,
        max_files: int,
        timeout_seconds: float,
    ) -> dict[str, Any]:
        root_value = project_source_root(project_source).replace("\\", "/")
        prune_clause = " -o ".join(f"-name {shlex.quote(item)}" for item in sorted(DEFAULT_IGNORED_NAMES))
        script = (
            f"ROOT={shlex.quote(root_value)}; "
            'if [ ! -d "$ROOT" ]; then echo "__ERROR__:missing_root"; exit 4; fi; '
            'echo "__TOP__"; '
            'find "$ROOT" -mindepth 1 -maxdepth 1 | head -n 25; '
            'echo "__TOP_END__"; '
            'echo "__FILES__"; '
            f'find "$ROOT" -maxdepth {max_depth} \\( {prune_clause} \\) -prune -o -type f -print | head -n {max_files}; '
            'echo "__FILES_END__"'
        )
        result = await self._run_ssh_shell(project_source, script, timeout_seconds=timeout_seconds)
        if not result["ok"]:
            raise RuntimeError(result["stderr"].strip() or result["stdout"].strip() or "SSH tree scan failed.")

        top_entries: list[dict[str, Any]] = []
        sample_files: list[dict[str, Any]] = []
        extension_counter: Counter[str] = Counter()
        language_counter: Counter[str] = Counter()
        top_modules: set[str] = set()
        section = ""
        for raw_line in result["stdout"].splitlines():
            line = raw_line.strip()
            if not line:
                continue
            if line == "__TOP__":
                section = "top"
                continue
            if line == "__TOP_END__":
                section = ""
                continue
            if line == "__FILES__":
                section = "files"
                continue
            if line == "__FILES_END__":
                section = ""
                continue
            if line.startswith("__ERROR__:"):
                raise RuntimeError(line.removeprefix("__ERROR__:"))
            if section == "top":
                top_entries.append(
                    {
                        "name": PurePosixPath(line).name,
                        "kind": "unknown",
                        "path": line,
                    }
                )
            elif section == "files":
                relative_path = _relativize_remote_path(root_value, line)
                extension = PurePosixPath(relative_path).suffix.lower() or "<none>"
                extension_counter[extension] += 1
                language_counter[_language_from_extension(extension)] += 1
                sample_files.append({"path": relative_path, "extension": extension})
                if relative_path and "/" in relative_path:
                    top_modules.add(relative_path.split("/")[0])

        return {
            "access_mode": "ssh",
            "root_path": root_value,
            "max_depth": max_depth,
            "scan_truncated": len(sample_files) >= max_files,
            "scanned_file_count": len(sample_files),
            "directory_count": len(top_entries),
            "top_modules": sorted(top_modules)[:50],
            "top_entries": top_entries,
            "extensions": dict(extension_counter.most_common(20)),
            "languages": dict(language_counter.most_common(15)),
            "sample_files": sample_files[:50],
            "ssh_target": self._build_ssh_target(project_source),
        }

    def _read_local_project_file(
        self,
        project_source,
        file_path: str,
        start_line: int,
        end_line: int,
        max_chars: int,
    ) -> dict[str, Any]:
        resolved = resolve_local_project_file(project_source, file_path)
        if not resolved.exists():
            raise FileNotFoundError(f"File was not found: {resolved}")
        if not resolved.is_file():
            raise IsADirectoryError(f"Target path is not a file: {resolved}")

        text = resolved.read_text(encoding="utf-8", errors="replace")
        lines = text.splitlines()
        total_lines = len(lines)
        bounded_end = min(end_line, total_lines if total_lines > 0 else end_line)
        selected_lines = lines[start_line - 1:bounded_end]
        content = "\n".join(selected_lines)
        truncated = len(content) > max_chars
        if truncated:
            content = content[:max_chars]

        return {
            "content": content,
            "file": {
                "path": resolved.relative_to(resolve_local_project_root(project_source)).as_posix(),
                "absolute_path": str(resolved),
                "start_line": start_line,
                "end_line": bounded_end,
                "total_lines": total_lines,
                "truncated": truncated,
            },
        }

    async def _read_ssh_project_file(
        self,
        project_source,
        file_path: str,
        start_line: int,
        end_line: int,
        max_chars: int,
        timeout_seconds: float,
    ) -> dict[str, Any]:
        remote_path = _join_remote_path(project_source_root(project_source), file_path)
        script = (
            f"FILE={shlex.quote(remote_path)}; "
            'if [ ! -f "$FILE" ]; then echo "__ERROR__:missing_file"; exit 4; fi; '
            'printf "__LINES__=%s\n" "$(wc -l < "$FILE" 2>/dev/null || echo 0)"; '
            'echo "__CONTENT__"; '
            f"sed -n '{start_line},{end_line}p' \"$FILE\""
        )
        result = await self._run_ssh_shell(project_source, script, timeout_seconds=timeout_seconds)
        if not result["ok"]:
            raise RuntimeError(result["stderr"].strip() or result["stdout"].strip() or "SSH file read failed.")

        total_lines = 0
        content_lines: list[str] = []
        capture = False
        for raw_line in result["stdout"].splitlines():
            line = raw_line.rstrip("\n")
            if line.startswith("__ERROR__:"):
                raise RuntimeError(line.removeprefix("__ERROR__:"))
            if line.startswith("__LINES__="):
                total_lines = int(line.removeprefix("__LINES__=") or "0")
                continue
            if line == "__CONTENT__":
                capture = True
                continue
            if capture:
                content_lines.append(raw_line)

        content = "\n".join(content_lines)
        truncated = len(content) > max_chars
        if truncated:
            content = content[:max_chars]

        return {
            "content": content,
            "file": {
                "path": _relativize_remote_path(project_source_root(project_source), remote_path),
                "absolute_path": remote_path,
                "start_line": start_line,
                "end_line": min(end_line, total_lines if total_lines > 0 else end_line),
                "total_lines": total_lines,
                "truncated": truncated,
            },
        }

    async def _read_local_project_diff(
        self,
        project_source,
        arguments: dict[str, Any],
        timeout_seconds: float,
        max_chars: int,
    ) -> dict[str, Any]:
        root = resolve_local_project_root(project_source)
        git_root_result = await self._run_subprocess("git", ["-C", str(root), "rev-parse", "--show-toplevel"], timeout_seconds=timeout_seconds)
        if not git_root_result["ok"]:
            raise RuntimeError("Local project source is not a git repository.")
        git_root = git_root_result["stdout"].strip()

        diff_mode = str(arguments.get("diff_mode") or "").strip().lower()
        commit_range = str(arguments.get("commit_range") or project_source.commit_range or "").strip()
        paths = _to_string_list(arguments.get("paths") or arguments.get("targets"))

        status_result = await self._run_subprocess("git", ["-C", git_root, "status", "--short"], timeout_seconds=timeout_seconds)
        diff_stat_args = self._build_git_diff_args(git_root, commit_range, diff_mode, paths, stat_only=True)
        diff_args = self._build_git_diff_args(git_root, commit_range, diff_mode, paths, stat_only=False)
        diff_stat_result = await self._run_subprocess("git", diff_stat_args, timeout_seconds=timeout_seconds)
        diff_result = await self._run_subprocess("git", diff_args, timeout_seconds=timeout_seconds)
        diff_text, truncated = _truncate_text(diff_result["stdout"], max_chars)

        return {
            "git_root": git_root,
            "commit_range": commit_range,
            "diff_mode": diff_mode or ("range" if commit_range else "working_tree"),
            "status_lines": [line for line in status_result["stdout"].splitlines() if line.strip()],
            "diff_stat": diff_stat_result["stdout"].strip(),
            "diff_text": diff_text,
            "truncated": truncated,
            "paths": paths,
        }

    async def _read_ssh_project_diff(
        self,
        project_source,
        arguments: dict[str, Any],
        timeout_seconds: float,
        max_chars: int,
    ) -> dict[str, Any]:
        root_value = project_source_root(project_source).replace("\\", "/")
        diff_mode = str(arguments.get("diff_mode") or "").strip().lower()
        commit_range = str(arguments.get("commit_range") or project_source.commit_range or "").strip()
        paths = _to_string_list(arguments.get("paths") or arguments.get("targets"))
        path_clause = ""
        if paths:
            path_clause = " --" + "".join(f" {shlex.quote(item)}" for item in paths)
        range_clause = f" {shlex.quote(commit_range)}" if commit_range else ""
        cached_clause = " --cached" if diff_mode == "staged" else ""
        script = (
            f"ROOT={shlex.quote(root_value)}; "
            'if ! command -v git >/dev/null 2>&1; then echo "__ERROR__:git_missing"; exit 5; fi; '
            'if ! git -C "$ROOT" rev-parse --is-inside-work-tree >/dev/null 2>&1; then echo "__ERROR__:not_git_repo"; exit 6; fi; '
            'echo "__STATUS__"; '
            'git -C "$ROOT" status --short; '
            'echo "__STAT__"; '
            f'git -C "$ROOT" diff --stat{cached_clause}{range_clause}{path_clause}; '
            'echo "__DIFF__"; '
            f'git -C "$ROOT" diff --unified=3{cached_clause}{range_clause}{path_clause}'
        )
        result = await self._run_ssh_shell(project_source, script, timeout_seconds=timeout_seconds)
        if not result["ok"]:
            raise RuntimeError(result["stderr"].strip() or result["stdout"].strip() or "SSH diff read failed.")

        status_lines: list[str] = []
        diff_stat_lines: list[str] = []
        diff_lines: list[str] = []
        section = ""
        for raw_line in result["stdout"].splitlines():
            line = raw_line.rstrip("\n")
            if line.startswith("__ERROR__:"):
                raise RuntimeError(line.removeprefix("__ERROR__:"))
            if line == "__STATUS__":
                section = "status"
                continue
            if line == "__STAT__":
                section = "stat"
                continue
            if line == "__DIFF__":
                section = "diff"
                continue
            if section == "status":
                status_lines.append(line)
            elif section == "stat":
                diff_stat_lines.append(line)
            elif section == "diff":
                diff_lines.append(raw_line)

        diff_text, truncated = _truncate_text("\n".join(diff_lines), max_chars)
        return {
            "git_root": root_value,
            "commit_range": commit_range,
            "diff_mode": diff_mode or ("range" if commit_range else "working_tree"),
            "status_lines": [line for line in status_lines if line.strip()],
            "diff_stat": "\n".join(diff_stat_lines).strip(),
            "diff_text": diff_text,
            "truncated": truncated,
            "paths": paths,
            "ssh_target": self._build_ssh_target(project_source),
        }

    def _build_git_diff_args(
        self,
        git_root: str,
        commit_range: str,
        diff_mode: str,
        paths: list[str],
        *,
        stat_only: bool,
    ) -> list[str]:
        args = ["-C", git_root, "diff"]
        if stat_only:
            args.append("--stat")
        else:
            args.append("--unified=3")
        normalized_mode = diff_mode or ("range" if commit_range else "working_tree")
        if normalized_mode == "staged":
            args.append("--cached")
        elif commit_range:
            args.append(commit_range)
        if paths:
            args.append("--")
            args.extend(paths)
        return args

    async def _run_ssh_shell(
        self,
        project_source,
        remote_script: str,
        *,
        timeout_seconds: float,
    ) -> dict[str, Any]:
        target = self._build_ssh_target(project_source)
        if not target:
            raise ValueError("SSH project source requires at least a host.")
        args = ["-o", "BatchMode=yes", "-o", "ConnectTimeout=10", "-p", str(project_source.ssh.port or 22)]
        auth_ref = str(project_source.ssh.auth_ref or "").strip()
        if auth_ref:
            args.extend(["-i", auth_ref])
        args.extend([target, f"sh -lc {shlex.quote(remote_script)}"])
        return await self._run_subprocess("ssh", args, timeout_seconds=timeout_seconds)

    async def _run_subprocess(
        self,
        executable: str,
        args: list[str],
        *,
        cwd: str | None = None,
        timeout_seconds: float,
    ) -> dict[str, Any]:
        try:
            completed = await asyncio.to_thread(
                subprocess.run,
                [shutil.which(executable) or executable, *args],
                cwd=cwd,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout_seconds,
            )
            stdout_text = completed.stdout or ""
            stderr_text = completed.stderr or ""
            exit_code = completed.returncode
            timed_out = False
        except subprocess.TimeoutExpired as exc:
            stdout_text = exc.stdout or ""
            stderr_text = exc.stderr or ""
            exit_code = -1
            timed_out = True
        return {
            "ok": exit_code == 0 and not timed_out,
            "exit_code": exit_code,
            "timed_out": timed_out,
            "stdout": stdout_text,
            "stderr": stderr_text,
        }

    def _build_ssh_target(self, project_source) -> str:
        host = str(project_source.ssh.host or "").strip()
        username = str(project_source.ssh.username or "").strip()
        if not host:
            return ""
        return f"{username}@{host}" if username else host

    def _require_mcp_runtime(self) -> MCPRuntimeService:
        if self._mcp_runtime_service is None:
            raise RuntimeError("MCP runtime service is not configured.")
        return self._mcp_runtime_service

    def _require_session_store(self) -> SessionStore:
        if self._session_store is None:
            raise RuntimeError("Session store is not configured.")
        return self._session_store

    def _require_memory_runtime(self) -> MemoryRuntimeService:
        if self._memory_runtime_service is None:
            raise RuntimeError("Memory runtime service is not configured.")
        return self._memory_runtime_service

    def _require_coordinator_runtime(self):
        if self._coordinator_runtime_service is None:
            raise RuntimeError("Coordinator runtime service is not configured.")
        return self._coordinator_runtime_service

    def _resolve_cli_cwd(self, requested_cwd: Any) -> Path:
        if isinstance(requested_cwd, str) and requested_cwd.strip():
            candidate = Path(requested_cwd.strip())
            resolved = candidate.resolve() if candidate.is_absolute() else (self._workspace_root / candidate).resolve()
        else:
            resolved = self._workspace_root.resolve()
        workspace_root = self._workspace_root.resolve()
        if workspace_root != resolved and workspace_root not in resolved.parents:
            raise RuntimeError(f"CLI Executor cwd must stay within the workspace root: {workspace_root}")
        resolved.mkdir(parents=True, exist_ok=True)
        return resolved

    def _build_cli_invocation(self, shell_name: str, command: str) -> tuple[str, list[str]]:
        if shell_name in {"powershell", "pwsh"}:
            executable = "powershell" if shell_name == "powershell" else "pwsh"
            return executable, ["-Command", command]
        if shell_name in {"cmd", "command"}:
            return "cmd", ["/c", command]
        if shell_name in {"bash", "sh"}:
            executable = "bash" if shell_name == "bash" else "sh"
            return executable, ["-lc", command]
        return "powershell", ["-Command", command]

    def _prepare_local_artifact_dir(self, context: ToolExecutionContext, tool_key: str) -> Path:
        settings = self._settings or Settings()
        artifact_root = Path(__file__).resolve().parents[2] / settings.artifact_root_dir
        artifact_root.mkdir(parents=True, exist_ok=True)
        session_id = _slug(context.session_id or "session")
        turn_id = _slug(context.turn_id or datetime.utcnow().strftime("%Y%m%d%H%M%S"))
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        artifact_dir = artifact_root / session_id / turn_id / f"{tool_key}_{timestamp}"
        artifact_dir.mkdir(parents=True, exist_ok=True)
        return artifact_dir

    def _send_email_message(
        self,
        recipients: list[str],
        subject: str,
        content: str,
        content_html: str,
    ) -> dict[str, Any]:
        if self._email_config_store is None:
            raise RuntimeError("Email config store is not available.")
        records = self._email_config_store.list_all()
        enabled = [item for item in records if item.enabled]
        if not enabled:
            raise RuntimeError("No enabled email configuration is available.")
        record = next((item for item in enabled if item.is_default), enabled[0])
        if record.provider == "aliyun":
            self._send_via_aliyun_directmail(record, recipients, subject, content_html or content)
        else:
            self._send_via_smtp_provider(record, recipients, subject, content, content_html)

        return {
            "sent": True,
            "provider": record.provider,
            "from_email": record.sender_email or record.smtp_username or "",
            "recipient_count": len(recipients),
        }

    def _send_via_smtp_provider(
        self,
        record,
        recipients: list[str],
        subject: str,
        content: str,
        content_html: str,
    ) -> None:
        if not record.smtp_host or not record.smtp_port:
            raise RuntimeError("Selected email configuration is missing SMTP host or port.")
        if not record.api_key:
            raise RuntimeError("Selected email configuration is missing SMTP password.")

        message = EmailMessage()
        message["Subject"] = subject
        message["From"] = record.sender_email or record.smtp_username or ""
        message["To"] = ", ".join(recipients)
        if content:
            message.set_content(content)
        else:
            message.set_content(" ")
        if content_html:
            message.add_alternative(content_html, subtype="html")

        username = record.smtp_username or record.sender_email
        use_ssl = int(record.smtp_port) == 465
        if use_ssl:
            with smtplib.SMTP_SSL(record.smtp_host, int(record.smtp_port), timeout=15) as client:
                client.login(username, record.api_key or "")
                client.send_message(message)
        else:
            with smtplib.SMTP(record.smtp_host, int(record.smtp_port), timeout=15) as client:
                client.ehlo()
                try:
                    client.starttls()
                    client.ehlo()
                except smtplib.SMTPException:
                    pass
                client.login(username, record.api_key or "")
                client.send_message(message)

    def _send_via_aliyun_directmail(self, record, recipients: list[str], subject: str, html_body: str) -> None:
        import base64
        import hashlib
        import hmac
        import urllib.parse
        import uuid

        import httpx

        if not record.api_key or not record.secret_key or not record.sender_email:
            raise RuntimeError("Selected Aliyun email configuration is incomplete.")

        for recipient in recipients:
            params = {
                "Action": "SingleSendMail",
                "AccountName": record.sender_email,
                "ReplyToAddress": "false",
                "AddressType": "1",
                "ToAddress": recipient,
                "Subject": subject,
                "HtmlBody": html_body,
                "Format": "JSON",
                "Version": "2015-11-23",
                "AccessKeyId": record.api_key,
                "SignatureMethod": "HMAC-SHA1",
                "SignatureVersion": "1.0",
                "SignatureNonce": str(uuid.uuid4()),
                "Timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            }
            sorted_params = sorted(params.items())
            query_string = urllib.parse.urlencode(sorted_params, quote_via=urllib.parse.quote)
            string_to_sign = "POST&%2F&" + urllib.parse.quote(query_string, safe="")
            sign_key = (record.secret_key + "&").encode("utf-8")
            signature = base64.b64encode(
                hmac.new(sign_key, string_to_sign.encode("utf-8"), hashlib.sha1).digest()
            ).decode("utf-8")
            params["Signature"] = signature

            response = httpx.post("https://dm.aliyuncs.com/", data=params, timeout=15)
            response.raise_for_status()
            payload = response.json()
            if "Code" in payload:
                raise RuntimeError(f"Aliyun DirectMail failed: {payload.get('Message') or payload['Code']}")

    def _normalize_result(
        self,
        tool: ToolDescriptor,
        result: dict[str, Any],
        context: ToolExecutionContext,
    ) -> dict[str, Any]:
        normalized = dict(result)
        explicit_status = str(normalized.get("status") or "").strip().lower()
        if "artifacts" not in normalized or not isinstance(normalized.get("artifacts"), list):
            normalized["artifacts"] = []
        if "metrics" not in normalized or not isinstance(normalized.get("metrics"), dict):
            normalized["metrics"] = {}
        if "summary" not in normalized or not str(normalized.get("summary") or "").strip():
            normalized["summary"] = f"Tool '{tool.key}' completed."
        if explicit_status in {"failed", "denied"} and "ok" not in normalized:
            normalized["ok"] = False
        elif "ok" not in normalized:
            normalized["ok"] = True
        if not normalized["ok"] and "error" not in normalized:
            normalized["error"] = normalized.get("summary")
        normalized.setdefault("trace_id", context.trace_id)
        return normalized

    def _collect_available_attachments(self, context: ToolExecutionContext, session) -> list[dict[str, Any]]:
        attachments: list[dict[str, Any]] = []
        for item in context.context_bundle.get("attachments") or []:
            if isinstance(item, dict):
                attachments.append(dict(item))
        if attachments:
            return attachments

        for message in reversed(getattr(session, "messages", []) or []):
            role = getattr(message.role, "value", str(message.role))
            if role != "user":
                continue
            metadata = dict(getattr(message, "metadata", {}) or {})
            for item in metadata.get("attachments") or []:
                if isinstance(item, dict):
                    attachments.append(dict(item))
            if attachments:
                return attachments
        return attachments

    def _select_attachment_for_read(
        self,
        arguments: dict[str, Any],
        attachments: list[dict[str, Any]],
    ) -> dict[str, Any] | None:
        requested_id = str(arguments.get("attachment_id") or "").strip()
        requested_uri = str(arguments.get("uri") or "").strip()
        requested_name = str(arguments.get("name") or "").strip().lower()

        def matches(item: dict[str, Any]) -> bool:
            metadata = item.get("metadata", {}) if isinstance(item.get("metadata"), dict) else {}
            attachment_id = str(metadata.get("attachment_id") or item.get("id") or "").strip()
            item_uri = str(item.get("uri") or "").strip()
            item_name = str(item.get("name") or "").strip().lower()
            if requested_id and attachment_id == requested_id:
                return True
            if requested_uri and item_uri == requested_uri:
                return True
            if requested_name and item_name == requested_name:
                return True
            return False

        for item in attachments:
            if matches(item):
                return item
        return attachments[0] if attachments else None

    def _attachment_summary(self, item: dict[str, Any]) -> dict[str, Any]:
        metadata = item.get("metadata", {}) if isinstance(item.get("metadata"), dict) else {}
        security = self._attachment_security_report(item)
        return {
            "attachment_id": str(metadata.get("attachment_id") or item.get("id") or "").strip(),
            "name": str(item.get("name") or "").strip(),
            "uri": str(item.get("uri") or "").strip(),
            "content_type": str(item.get("content_type") or "").strip(),
            "source": str(metadata.get("source") or "").strip(),
            "uploaded_at": str(metadata.get("uploaded_at") or "").strip(),
            "size_bytes": metadata.get("size_bytes"),
            "security_decision": str(security.get("decision") or "").strip(),
            "security_risk_score": security.get("risk_score"),
        }

    def _attachment_security_report(self, item: dict[str, Any]) -> dict[str, Any]:
        metadata = item.get("metadata", {}) if isinstance(item.get("metadata"), dict) else {}
        security = metadata.get("security")
        return security if isinstance(security, dict) else {}

    def _attachment_read_allowed(self, item: dict[str, Any]) -> tuple[bool, dict[str, Any]]:
        security = self._attachment_security_report(item)
        decision = str(security.get("decision") or "").strip().lower()
        if decision and decision != "allow":
            return False, security

        uri = str(item.get("uri") or "").strip()
        if uri.startswith("minio://"):
            bucket = self._attachment_bucket_from_uri(uri)
            if self._settings is not None and bucket in {
                self._settings.minio_upload_temp_bucket,
                self._settings.minio_upload_quarantine_bucket,
            }:
                return False, security
        return True, security

    def _attachment_bucket_from_uri(self, uri: str) -> str:
        raw = uri.removeprefix("minio://")
        bucket, _, _ = raw.partition("/")
        return bucket

    def _decode_attachment_bytes(
        self,
        *,
        content: bytes,
        content_type: str,
        filename: str,
        max_chars: int,
    ) -> tuple[str, str]:
        if not content:
            return "", "empty_attachment"

        text_like = (
            content_type.startswith("text/")
            or content_type in {
                "application/json",
                "application/xml",
                "application/javascript",
                "application/x-yaml",
                "application/yaml",
            }
            or Path(filename).suffix.lower() in {".md", ".txt", ".json", ".yaml", ".yml", ".xml", ".csv", ".log", ".py", ".js", ".ts", ".tsx", ".jsx", ".java", ".go", ".rs", ".vue", ".html", ".css"}
        )
        if not text_like:
            return "", "binary_attachment"

        for encoding in ("utf-8", "utf-8-sig", "gb18030", "gbk", "latin-1"):
            try:
                decoded = content.decode(encoding)
                break
            except UnicodeDecodeError:
                decoded = ""
        if not decoded:
            return "", "attachment_decode_failed"
        normalized = decoded.replace("\r\n", "\n").strip()
        truncated, _ = _truncate_text(normalized, max_chars)
        return truncated, ""

    def _attachment_content_format(self, filename: str, content_type: str) -> str:
        suffix = Path(filename).suffix.lower()
        if suffix == ".md":
            return "markdown"
        if suffix in {".json"} or content_type == "application/json":
            return "json"
        if suffix in {".yaml", ".yml"}:
            return "yaml"
        if suffix in {".html", ".htm"}:
            return "html"
        if suffix in {".csv"}:
            return "csv"
        if suffix in {".xml"}:
            return "xml"
        return "text"

    def _session_overview(self, session) -> dict[str, Any]:
        return {
            "session_id": session.id,
            "title": session.title,
            "status": session.status.value,
            "created_at": session.created_at.isoformat(),
            "updated_at": session.updated_at.isoformat(),
            "message_count": len(session.messages),
            "event_count": session.event_count,
            "snapshot_count": session.snapshot_count,
            "selected_agent": session.selected_agent,
            "preferred_model": session.preferred_model,
        }

    def _extract_questions(
        self,
        sessions: list[Any],
        include_assistant: bool,
        limit: int,
    ) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        for session in sorted(sessions, key=lambda item: item.updated_at, reverse=True):
            for message in session.messages:
                role = getattr(message.role, "value", str(message.role))
                if role != "user" and not include_assistant:
                    continue
                if not str(message.content or "").strip():
                    continue
                if role == "assistant" and not include_assistant:
                    continue
                items.append(
                    {
                        "session_id": session.id,
                        "role": role,
                        "content": str(message.content).strip(),
                        "created_at": message.created_at.isoformat(),
                    }
                )
        items.sort(key=lambda item: item["created_at"])
        return items[:limit]

    async def _build_session_report(
        self,
        session,
        store: SessionStore,
        include_assistant: bool,
        limit: int,
    ) -> dict[str, Any]:
        events = await store.list_events(session.id)
        snapshots = await store.list_snapshots(session.id)
        approvals = await store.list_approvals(session.id)
        transcript_summary = self._transcript_hygiene_service.summarize_messages(session.messages)
        user_messages = [item for item in session.messages if getattr(item.role, "value", str(item.role)) == "user"]
        assistant_messages = [item for item in session.messages if getattr(item.role, "value", str(item.role)) == "assistant"]
        tool_messages = [item for item in session.messages if getattr(item.role, "value", str(item.role)) == "tool"]
        transcript_excerpt = self._transcript_hygiene_service.build_display_transcript(
            session.messages,
            limit=limit,
            include_assistant=include_assistant,
            include_tools=False,
            include_errors=False,
        )

        recent_event_types = [event.type for event in events[-limit:]]
        snapshot_stages = [snapshot.stage for snapshot in snapshots[-limit:]]
        return {
            "session_id": session.id,
            "title": session.title,
            "status": session.status.value,
            "created_at": session.created_at.isoformat(),
            "updated_at": session.updated_at.isoformat(),
            "message_count": len(session.messages),
            "event_count": len(events),
            "snapshot_count": len(snapshots),
            "approval_count": len(approvals),
            "user_message_count": len(user_messages),
            "assistant_message_count": len(assistant_messages),
            "tool_message_count": len(tool_messages),
            "transcript_summary": transcript_summary,
            "recent_user_questions": [
                {
                    "content": str(item.content or "").strip(),
                    "created_at": item.created_at.isoformat(),
                }
                for item in user_messages[-limit:]
            ],
            "recent_event_types": recent_event_types,
            "snapshot_stages": snapshot_stages,
            "transcript_excerpt": transcript_excerpt,
        }

    def _format_session_report_markdown(self, report: dict[str, Any]) -> str:
        lines = [
            f"# Session Report: {report['title']}",
            "",
            f"- Session ID: {report['session_id']}",
            f"- Status: {report['status']}",
            f"- Created At: {report['created_at']}",
            f"- Updated At: {report['updated_at']}",
            f"- Messages: {report['message_count']}",
            f"- Events: {report['event_count']}",
            f"- Snapshots: {report['snapshot_count']}",
            f"- Approvals: {report['approval_count']}",
            f"- Context Eligible Messages: {report.get('transcript_summary', {}).get('context_eligible_count', 0)}",
            f"- Tool Messages: {report.get('transcript_summary', {}).get('tool_count', 0)}",
            f"- Error Messages: {report.get('transcript_summary', {}).get('error_count', 0)}",
            "",
            "## Recent User Questions",
        ]
        questions = report.get("recent_user_questions") or []
        if questions:
            for item in questions:
                lines.append(f"- {item['created_at']}: {item['content']}")
        else:
            lines.append("- None")
        lines.extend(["", "## Recent Event Types"])
        event_types = report.get("recent_event_types") or []
        if event_types:
            for item in event_types:
                lines.append(f"- {item}")
        else:
            lines.append("- None")
        lines.extend(["", "## Snapshot Stages"])
        snapshot_stages = report.get("snapshot_stages") or []
        if snapshot_stages:
            for item in snapshot_stages:
                lines.append(f"- {item}")
        else:
            lines.append("- None")
        return "\n".join(lines).strip()

    def _build_code_review_debate_markdown(
        self,
        *,
        title: str,
        project_name: str,
        approval_time: str,
        approval_result: str,
        agent_count: int,
        report_sections: list[dict[str, Any]],
        result_rows: list[Any],
    ) -> str:
        markdown_lines = [
            f"# {title}",
            "",
            f"## 就《{project_name}》的辩论报告",
            "",
            f"- 审批时间: {approval_time}",
            f"- 审批结果: {approval_result}",
            f"- 参与agent数量: {agent_count}",
            "",
            "## 审批结果总览",
            "",
            self._build_code_review_result_summary_markdown(result_rows),
        ]
        for section in report_sections:
            markdown_lines.extend(["", f"## {section['title']}", "", str(section["content"])])
        return "\n".join(markdown_lines).strip()

    def _build_code_review_result_summary_markdown(self, result_rows: list[Any]) -> str:
        if not result_rows:
            return "暂无审批结果摘要。"
        lines = [
            "| 类别 | 结果 | 提出Agent | 摘要 | 建议措施 |",
            "| --- | --- | --- | --- | --- |",
        ]
        for item in result_rows:
            if not isinstance(item, dict):
                continue
            lines.append(
                "| "
                + " | ".join(
                    [
                        self._escape_markdown_table_cell(self._code_review_category_label(item.get("category"))),
                        self._escape_markdown_table_cell(str(item.get("title") or item.get("result") or "未命名结果")),
                        self._escape_markdown_table_cell(str(item.get("proposer_agent") or item.get("agent") or "未标注")),
                        self._escape_markdown_table_cell(str(item.get("summary") or item.get("detail") or "暂无摘要")),
                        self._escape_markdown_table_cell(str(item.get("recommended_action") or item.get("action") or "待补充")),
                    ]
                )
                + " |"
            )
        return "\n".join(lines)

    def _build_code_review_category_sections(self, result_rows: list[Any]) -> str:
        grouped: dict[str, list[dict[str, Any]]] = {
            "严重问题": [],
            "缺陷": [],
            "隐患": [],
            "可行": [],
            "优秀": [],
        }
        for item in result_rows:
            if not isinstance(item, dict):
                continue
            grouped[self._code_review_category_label(item.get("category"))].append(item)

        section_lines: list[str] = []
        for label, items in grouped.items():
            section_lines.append(f"### {label}")
            if not items:
                section_lines.extend(["", "- None provided.", ""])
                continue
            section_lines.append("")
            for item in items:
                title = str(item.get("title") or item.get("result") or "未命名结果")
                proposer = str(item.get("proposer_agent") or item.get("agent") or "未标注")
                summary = str(item.get("summary") or item.get("detail") or "暂无摘要")
                section_lines.append(f"- {title} | 提出Agent: {proposer} | {summary}")
            section_lines.append("")
        return "\n".join(section_lines).strip()

    def _code_review_category_label(self, value: Any) -> str:
        raw_value = str(value or "").strip()
        if raw_value in CODE_REVIEW_RESULT_CATEGORY_LABELS:
            return CODE_REVIEW_RESULT_CATEGORY_LABELS[raw_value]
        return CODE_REVIEW_RESULT_CATEGORY_LABELS.get(raw_value.lower(), "隐患")

    def _escape_markdown_table_cell(self, value: str) -> str:
        return value.replace("|", "\\|").replace("\n", "<br>")


def _build_excerpt(text: str, tokens: list[str], radius: int = 140) -> str:
    lowered = text.lower()
    pivot = min(
        (lowered.find(token) for token in tokens if lowered.find(token) >= 0),
        default=0,
    )
    start = max(0, pivot - radius)
    end = min(len(text), pivot + radius)
    return " ".join(text[start:end].split())


def _slug(value: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_-]+", "_", value).strip("_").lower()


def _to_string_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []


def _clamp_int(value: Any, *, minimum: int, maximum: int, default: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = default
    return max(minimum, min(maximum, parsed))


def _clamp_float(value: Any, *, minimum: float, maximum: float, default: float) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        parsed = default
    return max(minimum, min(maximum, parsed))


def _truncate_text(value: str, max_chars: int) -> tuple[str, bool]:
    if len(value) <= max_chars:
        return value, False
    return value[:max_chars], True


def _language_from_extension(extension: str) -> str:
    mapping = {
        ".py": "python",
        ".js": "javascript",
        ".ts": "typescript",
        ".tsx": "typescript",
        ".jsx": "javascript",
        ".vue": "vue",
        ".java": "java",
        ".go": "go",
        ".rs": "rust",
        ".cs": "csharp",
        ".cpp": "cpp",
        ".c": "c",
        ".h": "c",
        ".hpp": "cpp",
        ".json": "json",
        ".yaml": "yaml",
        ".yml": "yaml",
        ".md": "markdown",
        ".sql": "sql",
        ".sh": "shell",
        ".ps1": "powershell",
        ".html": "html",
        ".css": "css",
        ".scss": "scss",
    }
    return mapping.get(extension.lower(), "other")


def _join_remote_path(root_path: str, child_path: str) -> str:
    normalized_root = root_path.replace("\\", "/").strip()
    normalized_child = child_path.replace("\\", "/").strip()
    if not normalized_child:
        return normalized_root
    if normalized_child.startswith("/"):
        return normalized_child
    return str(PurePosixPath(normalized_root) / normalized_child)


def _relativize_remote_path(root_path: str, target_path: str) -> str:
    normalized_root = root_path.replace("\\", "/").rstrip("/")
    normalized_target = target_path.replace("\\", "/")
    if normalized_target.startswith(f"{normalized_root}/"):
        return normalized_target[len(normalized_root) + 1:]
    if normalized_target == normalized_root:
        return "."
    return normalized_target


def _lookup_path(payload: dict[str, Any], dotted_path: str) -> tuple[Any, bool]:
    current: Any = payload
    for segment in dotted_path.split("."):
        if not isinstance(current, dict) or segment not in current:
            return None, False
        current = current[segment]
    return current, True


def _format_object_list(items: list[Any]) -> str:
    if not items:
        return "None provided."
    lines: list[str] = []
    for item in items:
        if isinstance(item, dict):
            title = str(item.get("title") or item.get("name") or item.get("id") or "Item")
            body = str(item.get("summary") or item.get("detail") or item.get("content") or item)
            lines.append(f"- {title}: {body}")
            continue
        lines.append(f"- {item}")
    return "\n".join(lines)

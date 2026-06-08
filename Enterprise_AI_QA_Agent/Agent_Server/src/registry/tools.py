from __future__ import annotations

from dataclasses import dataclass

from src.schemas.agent import ToolDescriptor


@dataclass(frozen=True)
class ToolModule:
    descriptor: ToolDescriptor
    handler_key: str | None = None


SECURITY_RUNNER_OUTPUT_SCHEMA = {
    "status": "string",
    "ok": "boolean",
    "success": "boolean",
    "summary": "string",
    "runner_key": "string",
    "command_profile": "string",
    "tool_name": "string",
    "command": "string",
    "execution_backend": "string",
    "container_name": "string",
    "exit_code": "integer",
    "timed_out": "boolean",
    "metrics": "object",
    "findings": "array",
    "parsed_result": "object",
    "raw_output": "string",
    "artifacts": "array",
    "error": "string",
}


SECURITY_SCAN_RUNNER_OUTPUT_SCHEMA = {
    **SECURITY_RUNNER_OUTPUT_SCHEMA,
    "phase": "string",
    "trace_id": "string",
    "selected_agent": "string",
    "selected_tools": "array",
    "context_refs": "array",
    "targets": "array",
    "campaign_id": "string",
    "task_count": "integer",
    "task_summary": "object",
    "report": "object",
    "report_markdown": "string",
    "report_html": "string",
    "delivery": "object",
    "verification_result": "object",
    "evaluation_result": "object",
    "errors": "array",
    "execution_checkpoint": "object",
    "task_events": "array",
    "security_testing_state": "object",
}


PERFORMANCE_RUNNER_OUTPUT_SCHEMA = {
    "status": "string",
    "ok": "boolean",
    "phase": "string",
    "summary": "string",
    "run_id": "string",
    "run_intent": "string",
    "verdict": "string",
    "metrics": "object",
    "sla_result": "object",
    "error_breakdown": "object",
    "engine_threshold_crosscheck": "object",
    "baseline_comparison": "object",
    "load_side_observations": "array",
    "report_markdown": "string",
    "report_html": "string",
    "smoke_result": "object",
    "guard_result": "object",
    "plan": "object",
    "errors": "array",
    "performance_testing_state": "object",
}


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, ToolModule] = {
            "workflow-router": ToolModule(
                descriptor=ToolDescriptor(
                    key="workflow-router",
                    name="Workflow Router",
                    description="Route a request to the right agent role and graph path.",
                    category="system",
                    permission_level="safe",
                    input_schema={
                        "type": "object",
                        "properties": {
                            "query": {"type": "string", "description": "The user task to classify and route."},
                        },
                    },
                    output_schema={"route": "string"},
                    tags=["core", "orchestration"],
                ),
                handler_key="workflow-router",
            ),
            "subagent-dispatch": ToolModule(
                descriptor=ToolDescriptor(
                    key="subagent-dispatch",
                    name="Subagent Dispatch",
                    description="Launch one or more background worker sessions and send task-notification results back to the coordinator.",
                    category="orchestration",
                    permission_level="safe",
                    input_schema={
                        "type": "object",
                        "properties": {
                            "workers": {
                                "type": "array",
                                "description": "One or more worker dispatch specifications.",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "description": {"type": "string"},
                                        "prompt": {"type": "string"},
                                        "agent_key": {"type": "string"},
                                        "model_key": {"type": "string"},
                                        "skill_keys": {"type": "array", "items": {"type": "string"}},
                                        "context": {"type": "object"},
                                    },
                                    "required": ["description", "prompt", "agent_key"],
                                },
                            },
                            "description": {"type": "string", "description": "Dispatch description for a single worker."},
                            "prompt": {"type": "string", "description": "Task prompt for a single worker."},
                            "agent_key": {"type": "string", "description": "Worker agent key."},
                            "model_key": {"type": "string", "description": "Optional worker model key override."},
                            "skill_keys": {"type": "array", "items": {"type": "string"}},
                            "context": {"type": "object"},
                            "completion_worker": {
                                "type": "object",
                                "description": "Optional worker dispatched only after the primary workers for this turn have all settled.",
                                "properties": {
                                    "description": {"type": "string"},
                                    "prompt": {"type": "string"},
                                    "agent_key": {"type": "string"},
                                    "model_key": {"type": "string"},
                                    "skill_keys": {"type": "array", "items": {"type": "string"}},
                                    "context": {"type": "object"},
                                },
                            },
                        },
                    },
                    output_schema={"workers": "array"},
                    tags=["coordinator", "worker", "async"],
                ),
                handler_key="subagent-dispatch",
            ),
            "knowledge-rag": ToolModule(
                descriptor=ToolDescriptor(
                    key="knowledge-rag",
                    name="Knowledge RAG",
                    description="Retrieve test rules, page knowledge, and historical defects.",
                    category="knowledge",
                    permission_level="safe",
                    input_schema={
                        "type": "object",
                        "properties": {
                            "query": {"type": "string", "description": "The knowledge lookup query."},
                            "top_k": {"type": "integer", "description": "Maximum number of chunks to return.", "default": 3},
                        },
                        "required": ["query"],
                    },
                    supports_streaming=True,
                    output_schema={"chunks": "array"},
                    tags=["retrieval", "knowledge"],
                ),
                handler_key="knowledge-rag",
            ),
            "api-docs-library": ToolModule(
                descriptor=ToolDescriptor(
                    key="api-docs-library",
                    name="API Docs Library",
                    description=(
                        "List imported API documentation/test files, inspect one file's details, and precisely search "
                        "endpoint paths, methods, titles, projects, and generated Markdown content. Use this before "
                        "Knowledge RAG when the user asks questions like '我有哪些接口文档', '查看接口文档详情', or '查找登录接口'."
                    ),
                    category="knowledge",
                    permission_level="safe",
                    input_schema={
                        "type": "object",
                        "properties": {
                            "action": {
                                "type": "string",
                                "description": "One of list, detail, or search.",
                                "enum": ["list", "detail", "search"],
                            },
                            "doc_id": {
                                "type": "string",
                                "description": "Document id returned by action=list, required for action=detail unless query can identify one.",
                            },
                            "query": {
                                "type": "string",
                                "description": "Search text, document title, endpoint keyword, or combined text such as 'POST /login'.",
                            },
                            "project_name": {
                                "type": "string",
                                "description": "Optional project name filter.",
                            },
                            "project_url": {
                                "type": "string",
                                "description": "Optional project/base URL filter.",
                            },
                            "method": {
                                "type": "string",
                                "description": "Optional HTTP method filter, such as GET or POST.",
                            },
                            "path": {
                                "type": "string",
                                "description": "Optional endpoint path or path fragment filter, such as /api/users.",
                            },
                            "limit": {
                                "type": "integer",
                                "description": "Maximum number of documents or matches to return.",
                                "default": 10,
                            },
                            "include_preview": {
                                "type": "boolean",
                                "description": "Whether to include Markdown preview snippets in list/search results.",
                                "default": False,
                            },
                            "max_chars": {
                                "type": "integer",
                                "description": "Maximum preview or excerpt characters to return.",
                                "default": 4000,
                            },
                        },
                        "required": ["action"],
                    },
                    output_schema={"documents": "array", "document": "object", "matches": "array"},
                    tags=["api", "docs", "testing", "retrieval"],
                ),
                handler_key="api-docs-library",
            ),
            "attachment-reader": ToolModule(
                descriptor=ToolDescriptor(
                    key="attachment-reader",
                    name="Attachment Reader",
                    description="Read the current turn's uploaded attachment from object storage and return its text content, preview, and metadata.",
                    category="knowledge",
                    permission_level="safe",
                    input_schema={
                        "type": "object",
                        "properties": {
                            "attachment_id": {
                                "type": "string",
                                "description": "Optional attachment identifier from attachment metadata.",
                            },
                            "uri": {
                                "type": "string",
                                "description": "Optional object storage URI such as minio://bucket/object.",
                            },
                            "name": {
                                "type": "string",
                                "description": "Optional attachment filename to match against the current turn.",
                            },
                            "max_chars": {
                                "type": "integer",
                                "description": "Maximum number of decoded characters to return.",
                                "default": 12000,
                            },
                            "prefer_excerpt": {
                                "type": "boolean",
                                "description": "When true, return the stored excerpt without fetching full object bytes unless needed.",
                                "default": False,
                            },
                        },
                    },
                    output_schema={"attachment": "object", "content": "string"},
                    tags=["attachment", "file", "minio", "retrieval"],
                ),
                handler_key="attachment-reader",
            ),
            "session-history": ToolModule(
                descriptor=ToolDescriptor(
                    key="session-history",
                    name="Session History",
                    description="Inspect stored session history, count historical sessions, list prior user questions, and generate a structured session report without relying on model memory reconstruction.",
                    category="knowledge",
                    permission_level="safe",
                    input_schema={
                        "type": "object",
                        "properties": {
                            "action": {
                                "type": "string",
                                "description": "One of count_sessions, list_questions, session_report, or history_summary.",
                            },
                            "scope": {
                                "type": "string",
                                "description": "Use current_session or all_sessions.",
                                "default": "current_session",
                            },
                            "limit": {
                                "type": "integer",
                                "description": "Maximum number of messages, questions, or sessions to include.",
                                "default": 10,
                            },
                            "include_assistant": {
                                "type": "boolean",
                                "description": "Whether assistant messages should be included in the returned transcript excerpts.",
                                "default": False,
                            },
                        },
                        "required": ["action"],
                    },
                    output_schema={"report": "object", "questions": "array", "sessions": "array"},
                    tags=["history", "session", "reporting"],
                ),
                handler_key="session-history",
            ),
            "session-timeline": ToolModule(
                descriptor=ToolDescriptor(
                    key="session-timeline",
                    name="Session Timeline",
                    description="Build a chronological timeline of session messages, events, snapshots, and observations for the current session.",
                    category="knowledge",
                    permission_level="safe",
                    input_schema={
                        "type": "object",
                        "properties": {
                            "limit": {
                                "type": "integer",
                                "description": "Maximum number of timeline entries to include.",
                                "default": 20,
                            },
                            "include_messages": {
                                "type": "boolean",
                                "description": "Whether user and assistant messages should be included.",
                                "default": True,
                            },
                            "include_events": {
                                "type": "boolean",
                                "description": "Whether execution events should be included.",
                                "default": True,
                            },
                            "include_observations": {
                                "type": "boolean",
                                "description": "Whether persisted testing observations should be included.",
                                "default": True,
                            },
                        },
                    },
                    output_schema={"timeline": "array", "report": "object"},
                    tags=["history", "timeline", "session"],
                ),
                handler_key="session-timeline",
            ),
            "observation-search": ToolModule(
                descriptor=ToolDescriptor(
                    key="observation-search",
                    name="Observation Search",
                    description="Search persisted testing observations and return structured evidence about prior page states, API assertions, CLI runs, and report artifacts.",
                    category="knowledge",
                    permission_level="safe",
                    input_schema={
                        "type": "object",
                        "properties": {
                            "query": {"type": "string", "description": "Search query for historical testing observations."},
                            "scope": {
                                "type": "string",
                                "description": "Use current_session or all_sessions.",
                                "default": "current_session",
                            },
                            "limit": {
                                "type": "integer",
                                "description": "Maximum number of observations to return.",
                                "default": 8,
                            },
                            "category": {
                                "type": "string",
                                "description": "Optional observation category filter, such as page_state or api_assertion.",
                            },
                            "tool_key": {
                                "type": "string",
                                "description": "Optional tool key filter, such as browser-automation or api-tester.",
                            },
                        },
                        "required": ["query"],
                    },
                    output_schema={"observations": "array"},
                    tags=["history", "observation", "retrieval"],
                ),
                handler_key="observation-search",
            ),
            "test-case-generator": ToolModule(
                descriptor=ToolDescriptor(
                    key="test-case-generator",
                    name="Test Case Generator",
                    description="Generate structured test scenarios, assertions, and coverage suggestions.",
                    category="qa",
                    permission_level="safe",
                    input_schema={
                        "type": "object",
                        "properties": {
                            "feature": {"type": "string", "description": "Feature or workflow under test."},
                            "goal": {"type": "string", "description": "Primary QA objective."},
                            "requirements": {"type": "array", "items": {"type": "string"}},
                            "acceptance_criteria": {"type": "array", "items": {"type": "string"}},
                            "platforms": {"type": "array", "items": {"type": "string"}},
                            "risk_focus": {"type": "array", "items": {"type": "string"}},
                        },
                    },
                    output_schema={"cases": "array"},
                    tags=["planning", "qa"],
                ),
                handler_key="test-case-generator",
            ),
            "browser-automation": ToolModule(
                descriptor=ToolDescriptor(
                    key="browser-automation",
                    name="Browser Automation",
                    description="Drive browser execution for UI automation and replay.",
                    category="execution",
                    permission_level="ask",
                    input_schema={
                        "type": "object",
                        "properties": {
                            "target_url": {"type": "string", "description": "The web page URL to automate."},
                            "objective": {"type": "string", "description": "What the browser automation should validate."},
                            "actions": {
                                "type": "array",
                                "description": "Optional explicit Playwright CLI action list for the browser executor.",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "type": {"type": "string"},
                                        "selector": {"type": "string"},
                                        "value": {"type": "string"},
                                        "seconds": {"type": "number"},
                                        "label": {"type": "string"},
                                        "y": {"type": "number"},
                                    },
                                    "required": ["type"],
                                },
                            },
                        },
                        "required": ["target_url"],
                    },
                    supports_streaming=True,
                    output_schema={"steps": "array", "artifacts": "array"},
                    tags=["ui", "automation"],
                ),
                handler_key="browser-automation",
            ),
            "browser-control": ToolModule(
                descriptor=ToolDescriptor(
                    key="browser-control",
                    name="Browser Control",
                    description="Control browser actions explicitly for navigation, screenshot, DOM inspection, JavaScript evaluation, and scripted UI actions.",
                    category="execution",
                    permission_level="ask",
                    input_schema={
                        "type": "object",
                        "properties": {
                            "action": {
                                "type": "string",
                                "description": "One of navigate, inspect, screenshot, evaluate_js, run_actions, or command.",
                            },
                            "target_url": {"type": "string", "description": "The target page URL."},
                            "command": {"type": "string", "description": "A playwright-cli style command, used when action=command."},
                            "args": {
                                "type": "array",
                                "description": "A playwright-cli style argument list, used when action=command.",
                                "items": {"type": "string"},
                            },
                            "javascript": {"type": "string", "description": "JavaScript expression for evaluate_js."},
                            "label": {"type": "string", "description": "Optional screenshot or artifact label."},
                            "actions": {
                                "type": "array",
                                "description": "UI actions used when action=run_actions.",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "type": {"type": "string"},
                                        "selector": {"type": "string"},
                                        "value": {"type": "string"},
                                        "seconds": {"type": "number"},
                                        "label": {"type": "string"},
                                        "y": {"type": "number"},
                                    },
                                    "required": ["type"],
                                },
                            },
                        },
                        "required": ["action"],
                    },
                    supports_streaming=True,
                    output_schema={"artifacts": "array", "steps": "array"},
                    tags=["ui", "browser", "automation"],
                ),
                handler_key="browser-control",
            ),
            "ui-page-explorer": ToolModule(
                descriptor=ToolDescriptor(
                    key="ui-page-explorer",
                    name="UI Explorer Agent",
                    description="Explore UI structure with Playwright ARIA snapshots, build semantic context trees, and persist a project-scoped UI graph without creating tests or assertions.",
                    category="execution",
                    permission_level="ask",
                    input_schema={
                        "type": "object",
                        "properties": {
                            "target_url": {"type": "string", "description": "The UI entry page URL to explore."},
                            "max_pages": {"type": "integer", "description": "Maximum pages to inspect for the app map."},
                            "same_origin_only": {"type": "boolean", "description": "Only follow links on the same origin."},
                            "include_hidden": {"type": "boolean", "description": "Include ARIA nodes that Playwright reports as not visible."},
                            "max_interactions": {"type": "integer", "description": "Maximum non-navigation interactions to open per page, such as dialogs, drawers, tabs, and expandable regions."},
                            "login_credentials": {
                                "type": "object",
                                "description": "Optional credentials used only after a login form is detected.",
                                "properties": {
                                    "username": {"type": "string"},
                                    "password": {"type": "string"},
                                },
                            },
                            "project_scope": {"type": "string", "description": "Optional project scope key for knowledge graph storage."},
                        },
                        "required": ["target_url"],
                    },
                    supports_streaming=True,
                    output_schema={"semantic_graph": "object", "app_map": "object", "artifacts": "array"},
                    tags=["ui", "exploration", "playwright", "aria", "graph"],
                ),
                handler_key="ui-page-explorer",
            ),
            "dom-inspector": ToolModule(
                descriptor=ToolDescriptor(
                    key="dom-inspector",
                    name="DOM Inspector",
                    description="Inspect page structure, selectors, and interactive elements.",
                    category="execution",
                    permission_level="ask",
                    input_schema={
                        "type": "object",
                        "properties": {
                            "target_url": {"type": "string", "description": "The web page URL to inspect."},
                        },
                        "required": ["target_url"],
                    },
                    output_schema={"dom_summary": "string"},
                    tags=["ui", "inspection"],
                ),
                handler_key="dom-inspector",
            ),
            "api-tester": ToolModule(
                descriptor=ToolDescriptor(
                    key="api-tester",
                    name="API Tester",
                    description="Call APIs, validate payloads, and capture structured assertions.",
                    category="execution",
                    permission_level="ask",
                    input_schema={
                        "type": "object",
                        "properties": {
                            "endpoint": {"type": "string", "description": "API endpoint or route."},
                            "method": {"type": "string", "description": "HTTP method."},
                            "request_body": {"type": "object"},
                            "response_body": {"type": "object"},
                            "response_status": {"type": "integer"},
                            "expected_status": {"type": "integer"},
                            "expected_fields": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Dot-path fields expected in the response body.",
                            },
                            "assertions": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Free-form checks to include in the report.",
                            },
                        },
                    },
                    output_schema={"checks": "array"},
                    tags=["api", "verification"],
                ),
                handler_key="api-tester",
            ),
            "cli-executor": ToolModule(
                descriptor=ToolDescriptor(
                    key="cli-executor",
                    name="CLI Executor",
                    description="Run shell or PowerShell commands with captured stdout, stderr, exit code, and transcript artifacts.",
                    category="execution",
                    permission_level="ask",
                    input_schema={
                        "type": "object",
                        "properties": {
                            "command": {"type": "string", "description": "The command text to execute."},
                            "shell": {
                                "type": "string",
                                "description": "Shell runtime to use, such as powershell or cmd.",
                                "default": "powershell",
                            },
                            "cwd": {"type": "string", "description": "Optional working directory within the workspace."},
                            "timeout_seconds": {
                                "type": "number",
                                "description": "Execution timeout in seconds.",
                                "default": 20,
                            },
                        },
                        "required": ["command"],
                    },
                    output_schema={"exit_code": "integer", "stdout": "string", "stderr": "string"},
                    tags=["cli", "shell", "terminal"],
                ),
                handler_key="cli-executor",
            ),
            "file-artifact-manager": ToolModule(
                descriptor=ToolDescriptor(
                    key="file-artifact-manager",
                    name="File Artifact Manager",
                    description="Persist run artifacts, screenshots, traces, and output files.",
                    category="artifact",
                    permission_level="ask",
                    input_schema={
                        "type": "object",
                        "properties": {
                            "file_name": {"type": "string", "description": "Artifact file name without extension."},
                            "extension": {"type": "string", "description": "Artifact extension like json, txt, md."},
                            "content": {"type": "string", "description": "Plain text artifact content."},
                            "json_data": {"type": "object", "description": "Structured JSON artifact content."},
                        },
                    },
                    output_schema={"artifact_paths": "array"},
                    tags=["artifact", "storage"],
                ),
                handler_key="file-artifact-manager",
            ),
            "message-dispatch": ToolModule(
                descriptor=ToolDescriptor(
                    key="message-dispatch",
                    name="Message Dispatch",
                    description="Send execution notifications as email using the active email channel, or persist message payloads as local delivery artifacts.",
                    category="communication",
                    permission_level="ask",
                    input_schema={
                        "type": "object",
                        "properties": {
                            "channel": {
                                "type": "string",
                                "description": "Delivery channel, such as email or artifact.",
                                "default": "artifact",
                            },
                            "to": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "One or more recipients for external delivery.",
                            },
                            "subject": {"type": "string", "description": "Message subject or title."},
                            "content": {"type": "string", "description": "Plain text message content."},
                            "content_markdown": {"type": "string", "description": "Markdown content that should be rendered into the report HTML template."},
                            "content_html": {"type": "string", "description": "Optional HTML content for email delivery."},
                            "sender": {"type": "string", "description": "Display sender name used by the report template."},
                            "time_label": {"type": "string", "description": "Optional time label rendered in the report template."},
                            "template_key": {"type": "string", "description": "Optional report template key, such as default or code_review_debate."},
                            "template_context": {"type": "object", "description": "Optional template-specific context used during HTML rendering."},
                            "file_name": {"type": "string", "description": "Optional artifact file name for local delivery."},
                        },
                    },
                    output_schema={"delivery": "object", "artifacts": "array"},
                    tags=["message", "notification", "email"],
                ),
                handler_key="message-dispatch",
            ),
            "send-email": ToolModule(
                descriptor=ToolDescriptor(
                    key="send-email",
                    name="Send Email",
                    description="Send an email through the currently active email channel without specifying provider details.",
                    category="communication",
                    permission_level="ask",
                    input_schema={
                        "type": "object",
                        "properties": {
                            "to": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "One or more recipient email addresses.",
                            },
                            "subject": {"type": "string", "description": "Email subject line."},
                            "content": {"type": "string", "description": "Plain text email body."},
                            "content_markdown": {"type": "string", "description": "Markdown body rendered with the report HTML template when content_html is absent."},
                            "content_html": {"type": "string", "description": "Optional HTML email body."},
                            "sender": {"type": "string", "description": "Display sender name used by the report template."},
                            "time_label": {"type": "string", "description": "Optional time label rendered in the report template."},
                            "template_key": {"type": "string", "description": "Optional report template key, such as default or code_review_debate."},
                            "template_context": {"type": "object", "description": "Optional template-specific context used during HTML rendering."},
                        },
                        "required": ["to", "subject"],
                    },
                    output_schema={"delivery": "object", "artifacts": "array"},
                    tags=["email", "message", "notification"],
                ),
                handler_key="send-email",
            ),
            "report-writer": ToolModule(
                descriptor=ToolDescriptor(
                    key="report-writer",
                    name="Report Writer",
                    description="Summarize execution evidence into a structured QA report.",
                    category="reporting",
                    permission_level="safe",
                    input_schema={
                        "type": "object",
                        "properties": {
                            "title": {"type": "string"},
                            "objective": {"type": "string"},
                            "summary": {"type": "string"},
                            "findings": {"type": "array", "items": {"type": "object"}},
                            "evidence": {"type": "array", "items": {"type": "object"}},
                            "recommendations": {"type": "array", "items": {"type": "string"}},
                            "status": {"type": "string"},
                            "sender": {"type": "string", "description": "Display sender name rendered into the HTML report template."},
                            "content_markdown": {"type": "string", "description": "Optional prebuilt markdown body. When omitted, the runtime assembles markdown from structured fields."},
                            "template_key": {"type": "string", "description": "Optional report template key, such as default or code_review_debate."},
                            "project_name": {"type": "string", "description": "Project name used by the code review debate report template."},
                            "approval_time": {"type": "string", "description": "Approval time shown by the code review debate report template."},
                            "approval_result": {"type": "string", "description": "Final approval result shown by the code review debate report template."},
                            "agent_count": {"type": "integer", "description": "Participating agent count shown by the code review debate report template."},
                            "result_rows": {
                                "type": "array",
                                "description": "Structured result rows for the code review debate summary table.",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "category": {"type": "string"},
                                        "title": {"type": "string"},
                                        "result": {"type": "string"},
                                        "proposer_agent": {"type": "string"},
                                        "agent": {"type": "string"},
                                        "summary": {"type": "string"},
                                        "detail": {"type": "string"},
                                        "recommended_action": {"type": "string"},
                                        "action": {"type": "string"},
                                    },
                                },
                            },
                        },
                    },
                    output_schema={"report_sections": "array"},
                    tags=["reporting"],
                ),
                handler_key="report-writer",
            ),
            "project-source-loader": ToolModule(
                descriptor=ToolDescriptor(
                    key="project-source-loader",
                    name="Project Source Loader",
                    description="Validate and summarize a local or SSH project source for code review tasks.",
                    category="review",
                    permission_level="safe",
                    input_schema={
                        "type": "object",
                        "properties": {
                            "project_source": {"type": "object"},
                            "source_type": {"type": "string", "enum": ["local", "ssh"]},
                            "root_path": {"type": "string"},
                            "project_path": {"type": "string"},
                            "project_name": {"type": "string"},
                            "branch": {"type": "string"},
                            "commit_range": {"type": "string"},
                            "ssh_host": {"type": "string"},
                            "ssh_port": {"type": "integer"},
                            "ssh_username": {"type": "string"},
                            "ssh_auth_ref": {"type": "string"},
                            "remote_root_path": {"type": "string"},
                            "timeout_seconds": {"type": "number", "default": 20},
                        },
                    },
                    output_schema={"project_source": "object", "source_info": "object"},
                    tags=["code-review", "project-source", "ssh"],
                ),
                handler_key="project-source-loader",
            ),
            "project-tree-scanner": ToolModule(
                descriptor=ToolDescriptor(
                    key="project-tree-scanner",
                    name="Project Tree Scanner",
                    description="Scan a project tree and return module hints, sample files, and extension distribution for review planning.",
                    category="review",
                    permission_level="safe",
                    input_schema={
                        "type": "object",
                        "properties": {
                            "project_source": {"type": "object"},
                            "source_type": {"type": "string", "enum": ["local", "ssh"]},
                            "root_path": {"type": "string"},
                            "project_path": {"type": "string"},
                            "max_depth": {"type": "integer", "default": 3},
                            "max_files": {"type": "integer", "default": 400},
                            "timeout_seconds": {"type": "number", "default": 30},
                        },
                    },
                    output_schema={"tree_summary": "object", "sample_files": "array"},
                    tags=["code-review", "tree", "project-map"],
                ),
                handler_key="project-tree-scanner",
            ),
            "project-file-reader": ToolModule(
                descriptor=ToolDescriptor(
                    key="project-file-reader",
                    name="Project File Reader",
                    description="Read a file from a local or SSH project source with optional line slicing.",
                    category="review",
                    permission_level="safe",
                    input_schema={
                        "type": "object",
                        "properties": {
                            "project_source": {"type": "object"},
                            "source_type": {"type": "string", "enum": ["local", "ssh"]},
                            "root_path": {"type": "string"},
                            "project_path": {"type": "string"},
                            "path": {"type": "string"},
                            "file_path": {"type": "string"},
                            "start_line": {"type": "integer", "default": 1},
                            "end_line": {"type": "integer", "default": 200},
                            "max_chars": {"type": "integer", "default": 16000},
                            "timeout_seconds": {"type": "number", "default": 20},
                        },
                    },
                    output_schema={"content": "string", "file": "object"},
                    tags=["code-review", "file-read", "evidence"],
                ),
                handler_key="project-file-reader",
            ),
            "project-diff-reader": ToolModule(
                descriptor=ToolDescriptor(
                    key="project-diff-reader",
                    name="Project Diff Reader",
                    description="Read git status and diff context from a local or SSH project source.",
                    category="review",
                    permission_level="safe",
                    input_schema={
                        "type": "object",
                        "properties": {
                            "project_source": {"type": "object"},
                            "source_type": {"type": "string", "enum": ["local", "ssh"]},
                            "root_path": {"type": "string"},
                            "project_path": {"type": "string"},
                            "commit_range": {"type": "string"},
                            "diff_mode": {
                                "type": "string",
                                "description": "One of working_tree, staged, or range.",
                                "default": "working_tree",
                            },
                            "paths": {"type": "array", "items": {"type": "string"}},
                            "max_chars": {"type": "integer", "default": 24000},
                            "timeout_seconds": {"type": "number", "default": 20},
                        },
                    },
                    output_schema={"status_lines": "array", "diff_text": "string", "diff_stat": "string"},
                    tags=["code-review", "git", "diff"],
                ),
                handler_key="project-diff-reader",
            ),
            "code-governance-runner": ToolModule(
                descriptor=ToolDescriptor(
                    key="code-governance-runner",
                    name="Code Governance Runner",
                    description=(
                        "Run deterministic code governance pre-scan for a code review campaign. "
                        "It analyzes git diff, changed files, built-in security/database/dependency/test rules, "
                        "optional CI scanner JSON artifacts or installed external scanners, risk score, "
                        "and merge approval decision."
                    ),
                    category="review",
                    permission_level="safe",
                    input_schema={
                        "type": "object",
                        "properties": {
                            "project_source": {"type": "object"},
                            "source_type": {"type": "string", "enum": ["local", "ssh"]},
                            "root_path": {"type": "string"},
                            "project_path": {"type": "string"},
                            "project_name": {"type": "string"},
                            "commit_range": {"type": "string"},
                            "diff_mode": {
                                "type": "string",
                                "description": "One of working_tree, staged, or range.",
                                "default": "working_tree",
                            },
                            "paths": {"type": "array", "items": {"type": "string"}},
                            "excluded_paths": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": (
                                    "Additional paths or directory names to exclude. Code review always excludes "
                                    "dependency and build output directories such as node_modules, dist, build, "
                                    "target, venv, .git, and caches by default."
                                ),
                            },
                            "ignored_paths": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Alias for excluded_paths.",
                            },
                            "diff_text": {"type": "string"},
                            "scanner_artifacts": {
                                "type": "object",
                                "description": "Optional scanner JSON paths, such as semgrep, bandit, pip_audit, npm_audit, or gitleaks.",
                            },
                            "run_external_scanners": {
                                "type": "boolean",
                                "description": "When true, execute installed scanners and merge their JSON findings.",
                                "default": False,
                            },
                            "external_scanners": {
                                "oneOf": [
                                    {"type": "string"},
                                    {"type": "array", "items": {"type": "string"}},
                                ],
                                "description": "Scanners to execute: semgrep, gitleaks, bandit, pip_audit, npm_audit, or all.",
                            },
                            "scanner_timeout_seconds": {
                                "type": "number",
                                "description": "Per-scanner timeout in seconds.",
                                "default": 120,
                            },
                            "skip_code_graph": {
                                "type": "boolean",
                                "description": "Skip lightweight call-chain and architecture graph construction.",
                                "default": False,
                            },
                            "max_graph_files": {
                                "type": "integer",
                                "description": "Maximum source files to include in the lightweight code graph.",
                                "default": 400,
                            },
                            "policy": {
                                "type": "object",
                                "description": "Optional governance policy overrides such as minimum_score and block_on_critical.",
                            },
                            "max_chars": {"type": "integer", "default": 80000},
                        },
                    },
                    output_schema={
                        "approval_decision": "string",
                        "decision": "object",
                        "risk_score": "object",
                        "findings": "array",
                        "changed_files": "array",
                        "code_graph": "object",
                        "scanner_runs": "array",
                        "report_json": "object",
                        "report_markdown": "string",
                    },
                    tags=["code-review", "governance", "ci", "risk-score", "approval"],
                ),
                handler_key="code-governance-runner",
            ),
            "code-review-orchestrator": ToolModule(
                descriptor=ToolDescriptor(
                    key="code-review-orchestrator",
                    name="Code Review Orchestrator",
                    description="Prepare and optionally launch a background multi-agent code review debate campaign for a local or SSH project source.",
                    category="review",
                    permission_level="safe",
                    input_schema={
                        "type": "object",
                        "properties": {
                            "project_source": {
                                "type": "object",
                                "description": "Project source definition for local or SSH-backed review.",
                                "properties": {
                                    "source_type": {"type": "string", "enum": ["local", "ssh"]},
                                    "root_path": {"type": "string"},
                                    "project_name": {"type": "string"},
                                    "branch": {"type": "string"},
                                    "commit_range": {"type": "string"},
                                    "ssh": {
                                        "type": "object",
                                        "properties": {
                                            "host": {"type": "string"},
                                            "port": {"type": "integer"},
                                            "username": {"type": "string"},
                                            "auth_ref": {"type": "string"},
                                            "remote_root_path": {"type": "string"},
                                        },
                                    },
                                },
                            },
                            "source_type": {"type": "string", "enum": ["local", "ssh"]},
                            "root_path": {"type": "string"},
                            "project_path": {"type": "string"},
                            "project_name": {"type": "string"},
                            "branch": {"type": "string"},
                            "commit_range": {"type": "string"},
                            "review_scope": {"type": "string", "description": "Review scope such as project, diff, module, or target-set."},
                            "change_summary": {"type": "string"},
                            "diff_text": {"type": "string"},
                            "targets": {"type": "array", "items": {"type": "string"}},
                            "excluded_paths": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": (
                                    "Additional paths or directory names to exclude from bootstrap, tree scanning, "
                                    "governance, graph building, and reviewer context. Dependency/build output "
                                    "directories are excluded by default."
                                ),
                            },
                            "ignored_paths": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Alias for excluded_paths.",
                            },
                            "ssh_host": {"type": "string"},
                            "ssh_port": {"type": "integer"},
                            "ssh_username": {"type": "string"},
                            "ssh_auth_ref": {"type": "string"},
                            "remote_root_path": {"type": "string"},
                            "worker_model_key": {"type": "string"},
                            "summary_model_key": {"type": "string"},
                            "reviewer_count": {
                                "type": "integer",
                                "description": "Optional reviewer count override for code review debate, typically 2-5.",
                                "minimum": 2,
                                "maximum": 5,
                            },
                            "debate_time_budget_minutes": {
                                "type": "integer",
                                "description": "Optional moderator time budget for the whole debate. The coordinator derives the debate pace from project size and model context, capped at 60 minutes.",
                                "minimum": 5,
                                "maximum": 60,
                                "default": 20,
                            },
                            "email_to": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Optional email recipients for the final debate report.",
                            },
                            "email_subject": {
                                "type": "string",
                                "description": "Optional override for the final debate report email subject.",
                            },
                            "delivery_channel": {
                                "type": "string",
                                "enum": ["artifact", "email"],
                                "description": "Preferred delivery channel for the final report notification.",
                                "default": "artifact",
                            },
                            "launch_workers": {
                                "type": "boolean",
                                "description": "Whether to immediately launch isolated reviewer sessions in the background.",
                                "default": True,
                            },
                        },
                    },
                    output_schema={
                        "approval_decision": "string",
                        "findings": "array",
                        "campaign": "object",
                        "dispatch": "object",
                    },
                    tags=["code-review", "approval", "mode"],
                ),
                handler_key="code-review-orchestrator",
            ),
            "ui-automation-runner": ToolModule(
                descriptor=ToolDescriptor(
                    key="ui-automation-runner",
                    name="UI Automation Runner",
                    description="Mode-scoped entry tool for UI automation workflows.",
                    category="execution",
                    permission_level="ask",
                    input_schema={
                        "type": "object",
                        "properties": {
                            "target_url": {"type": "string"},
                            "objective": {"type": "string"},
                            "project_scope": {"type": "string"},
                            "direction": {"type": "string"},
                            "subdirection": {"type": "string"},
                            "action": {"type": "string"},
                            "max_pages": {"type": "integer"},
                            "max_interactions": {"type": "integer"},
                            "same_origin_only": {"type": "boolean"},
                        },
                    },
                    output_schema={"ui_automation_state": "object", "artifacts": "array"},
                    tags=["ui", "automation", "mode"],
                ),
                handler_key="ui-automation-runner",
            ),
            "api-test-runner": ToolModule(
                descriptor=ToolDescriptor(
                    key="api-test-runner",
                    name="API Test Runner",
                    description="Mode-scoped entry tool for API interface testing workflows with structured phase, verification, evaluation, and report output.",
                    category="execution",
                    permission_level="ask",
                    input_schema={
                        "type": "object",
                        "properties": {
                            "worker_action": {
                                "type": "string",
                                "description": "Optional worker action such as execute_task for dispatched subagent work.",
                            },
                            "task": {
                                "type": "object",
                                "description": "Serialized ApiTestTask payload when worker_action=execute_task.",
                            },
                            "credential_session": {
                                "type": "object",
                                "description": "Optional serialized credential session for worker task execution.",
                            },
                            "auth_token_field": {
                                "type": "string",
                                "description": "Response JSON field used to extract auth tokens from login tasks.",
                            },
                            "endpoint": {"type": "string"},
                            "method": {"type": "string"},
                            "objective": {"type": "string"},
                            "project_hint": {"type": "string"},
                            "domain_hint": {"type": "string"},
                            "scope_preference": {
                                "type": "string",
                                "description": "Endpoint scope preference: all_related, core_only, manual_pick, or single_target.",
                            },
                            "verification_focus": {"type": "string"},
                            "auth_hint": {"type": "string"},
                        },
                    },
                    output_schema={
                        "status": "string",
                        "phase": "string",
                        "summary": "string",
                        "pending_selection": "object",
                        "selected_project": "object",
                        "campaign_id": "string",
                        "task_count": "integer",
                        "report": "object",
                        "report_markdown": "string",
                        "verification_result": "object",
                        "evaluation_result": "object",
                        "artifacts": "array",
                        "errors": "array",
                        "execution_checkpoint": "object",
                        "task_events": "array",
                        "api_testing_state": "object",
                    },
                    tags=["api", "testing", "mode"],
                ),
                handler_key="api-test-runner",
            ),
            "security-scan-runner": ToolModule(
                descriptor=ToolDescriptor(
                    key="security-scan-runner",
                    name="Security Scan Runner",
                    description=(
                        "通用安全扫描 runner，执行安全测试 Campaign 的主入口。"
                        "接受 command_profile 和目标参数，通过结构化 profile 执行安全工具并返回解析后的结果。"
                    ),
                    category="execution",
                    permission_level="ask",
                    input_schema={
                        "type": "object",
                        "properties": {
                            "worker_action": {
                                "type": "string",
                                "description": "执行动作，如 execute_security_task 或 run_campaign。",
                            },
                            "command_profile": {
                                "type": "string",
                                "description": "命令 profile key，如 nmap_tcp_basic、nuclei_baseline。",
                            },
                            "target": {
                                "type": "string",
                                "description": "扫描目标（IP、URL、域名、网段）。",
                            },
                            "arguments": {
                                "type": "object",
                                "description": "传递给命令模板的额外参数。",
                            },
                            "task": {
                                "type": "object",
                                "description": "完整的 SecurityTask 序列化对象（worker 模式）。",
                            },
                            "objective": {"type": "string", "description": "测试目标描述。"},
                        },
                    },
                    output_schema=SECURITY_SCAN_RUNNER_OUTPUT_SCHEMA,
                    tags=["security", "testing", "scan", "runner"],
                ),
                handler_key="security-scan-runner",
            ),
            "network-recon-runner": ToolModule(
                descriptor=ToolDescriptor(
                    key="network-recon-runner",
                    name="Network Recon Runner",
                    description=(
                        "网络侦察 runner，执行端口扫描、服务探测、资产发现等网络层侦察任务。"
                        "支持 nmap_tcp_basic、nmap_service_detect、nmap_full_scan 等 profile。"
                    ),
                    category="execution",
                    permission_level="ask",
                    input_schema={
                        "type": "object",
                        "properties": {
                            "command_profile": {
                                "type": "string",
                                "description": "Profile key: nmap_tcp_basic / nmap_service_detect / nmap_full_scan / nmap_os_detect",
                                "enum": ["nmap_tcp_basic", "nmap_service_detect", "nmap_full_scan", "nmap_os_detect"],
                            },
                            "target": {"type": "string", "description": "目标 IP、域名或网段。"},
                            "ports": {"type": "string", "description": "端口范围，如 80,443,8080 或 1-1000。"},
                            "arguments": {"type": "object", "description": "额外参数。"},
                            "task": {"type": "object", "description": "SecurityTask 对象（worker 模式）。"},
                        },
                        "required": ["target"],
                    },
                    output_schema=SECURITY_RUNNER_OUTPUT_SCHEMA,
                    tags=["security", "network", "recon", "nmap", "runner"],
                ),
                handler_key="network-recon-runner",
            ),
            "web-scan-runner": ToolModule(
                descriptor=ToolDescriptor(
                    key="web-scan-runner",
                    name="Web Scan Runner",
                    description=(
                        "Web 安全扫描 runner，执行目录扫描、漏洞扫描、注入检测等 Web 层安全测试。"
                        "支持 httpx_probe、whatweb_fingerprint、ffuf_common_dirs、nikto_web_scan、"
                        "nuclei_baseline、sqlmap_readonly_probe 等 profile。"
                    ),
                    category="execution",
                    permission_level="ask",
                    input_schema={
                        "type": "object",
                        "properties": {
                            "command_profile": {
                                "type": "string",
                                "description": "Profile key: httpx_probe / whatweb_fingerprint / ffuf_common_dirs / nikto_web_scan / nuclei_baseline / nuclei_cve_scan / sqlmap_readonly_probe",
                            },
                            "target": {"type": "string", "description": "目标 URL 或域名。"},
                            "arguments": {"type": "object", "description": "额外参数。"},
                            "task": {"type": "object", "description": "SecurityTask 对象（worker 模式）。"},
                        },
                        "required": ["target"],
                    },
                    output_schema=SECURITY_RUNNER_OUTPUT_SCHEMA,
                    tags=["security", "web", "scan", "nuclei", "nikto", "runner"],
                ),
                handler_key="web-scan-runner",
            ),
            "service-audit-runner": ToolModule(
                descriptor=ToolDescriptor(
                    key="service-audit-runner",
                    name="Service Audit Runner",
                    description=(
                        "服务审计 runner，执行 TLS/SSL 配置审计、漏洞情报检索等服务层安全检测。"
                        "支持 sslscan_tls_audit、searchsploit_lookup 等 profile。"
                    ),
                    category="execution",
                    permission_level="ask",
                    input_schema={
                        "type": "object",
                        "properties": {
                            "command_profile": {
                                "type": "string",
                                "description": "Profile key: sslscan_tls_audit / searchsploit_lookup",
                            },
                            "target": {"type": "string", "description": "目标地址或查询关键词。"},
                            "query": {"type": "string", "description": "searchsploit 查询词。"},
                            "arguments": {"type": "object", "description": "额外参数。"},
                            "task": {"type": "object", "description": "SecurityTask 对象（worker 模式）。"},
                        },
                    },
                    output_schema=SECURITY_RUNNER_OUTPUT_SCHEMA,
                    tags=["security", "service", "audit", "ssl", "runner"],
                ),
                handler_key="service-audit-runner",
            ),
            "credential-attack-runner": ToolModule(
                descriptor=ToolDescriptor(
                    key="credential-attack-runner",
                    name="Credential Attack Runner",
                    description=(
                        "凭证攻击 runner，执行凭证爆破和弱密码检测（高风险，需审批）。"
                        "支持 hydra_basic_login 等 profile。"
                    ),
                    category="execution",
                    permission_level="restricted",
                    input_schema={
                        "type": "object",
                        "properties": {
                            "command_profile": {
                                "type": "string",
                                "description": "Profile key: hydra_basic_login",
                            },
                            "target": {"type": "string", "description": "目标地址。"},
                            "service": {"type": "string", "description": "目标服务，如 ssh、ftp、http-post-form。"},
                            "userlist": {"type": "string", "description": "用户名字典文件路径。"},
                            "passlist": {"type": "string", "description": "密码字典文件路径。"},
                            "arguments": {"type": "object", "description": "额外参数。"},
                            "task": {"type": "object", "description": "SecurityTask 对象（worker 模式）。"},
                        },
                        "required": ["target", "service"],
                    },
                    output_schema=SECURITY_RUNNER_OUTPUT_SCHEMA,
                    tags=["security", "credential", "attack", "hydra", "runner"],
                ),
                handler_key="credential-attack-runner",
            ),
            "traffic-analysis-runner": ToolModule(
                descriptor=ToolDescriptor(
                    key="traffic-analysis-runner",
                    name="Traffic Analysis Runner",
                    description="流量分析 runner，执行网络流量捕获和 TLS 分析（Phase 2）。",
                    category="execution",
                    permission_level="restricted",
                    input_schema={
                        "type": "object",
                        "properties": {
                            "command_profile": {"type": "string"},
                            "target": {"type": "string"},
                            "arguments": {"type": "object"},
                            "task": {"type": "object"},
                        },
                    },
                    output_schema=SECURITY_RUNNER_OUTPUT_SCHEMA,
                    tags=["security", "traffic", "analysis", "runner"],
                ),
                handler_key="traffic-analysis-runner",
            ),
            "exploit-workbench-runner": ToolModule(
                descriptor=ToolDescriptor(
                    key="exploit-workbench-runner",
                    name="Exploit Workbench Runner",
                    description="漏洞利用工作台 runner，执行 PoC 验证和漏洞利用（高风险，Phase 3/4）。",
                    category="execution",
                    permission_level="restricted",
                    input_schema={
                        "type": "object",
                        "properties": {
                            "command_profile": {"type": "string"},
                            "target": {"type": "string"},
                            "arguments": {"type": "object"},
                            "task": {"type": "object"},
                        },
                    },
                    output_schema=SECURITY_RUNNER_OUTPUT_SCHEMA,
                    tags=["security", "exploit", "runner"],
                ),
                handler_key="exploit-workbench-runner",
            ),
            "performance-test-runner": ToolModule(
                descriptor=ToolDescriptor(
                    key="performance-test-runner",
                    name="Performance Test Runner",
                    description=(
                        "性能/负载测试主入口工具。接受目标、负载模型、SLA 参数，"
                        "驱动 k6 引擎生成脚本、冒烟验证、正式压测、结果解析和报告生成。"
                    ),
                    category="execution",
                    permission_level="ask",
                    input_schema={
                        "type": "object",
                        "properties": {
                            "objective": {"type": "string", "description": "测试目标描述。"},
                            "target_url": {"type": "string", "description": "压测目标 URL。"},
                            "method": {"type": "string", "description": "HTTP 方法。", "default": "GET"},
                            "workload_model": {
                                "type": "string",
                                "description": "负载模型: open (到达率) 或 closed (固定VU)。",
                                "enum": ["open", "closed"],
                            },
                            "target_rate_rps": {"type": "integer", "description": "目标到达率 (rps)，open 模型使用。"},
                            "virtual_users": {"type": "integer", "description": "虚拟用户数，closed 模型使用。"},
                            "duration_seconds": {"type": "integer", "description": "持续时长（秒）。"},
                            "run_intent": {
                                "type": "string",
                                "description": "运行意图: probe (探测基线) 或 regression (回归验证)。",
                                "enum": ["probe", "regression"],
                            },
                            "sla_p95_ms": {"type": "number", "description": "SLA P95 延迟阈值 (ms)。"},
                            "sla_p99_ms": {"type": "number", "description": "SLA P99 延迟阈值 (ms)。"},
                            "sla_error_rate": {"type": "number", "description": "SLA 错误率阈值。"},
                            "headers": {"type": "object", "description": "自定义请求头。"},
                            "body_template": {"description": "请求体模板。"},
                            "confirm_target": {"type": "boolean", "description": "用户已确认目标。"},
                            "worker_action": {"type": "string", "description": "Worker 模式动作。"},
                            "arguments": {"type": "object", "description": "透传参数。"},
                        },
                    },
                    output_schema=PERFORMANCE_RUNNER_OUTPUT_SCHEMA,
                    tags=["performance", "testing", "mode", "k6", "load"],
                ),
                handler_key="performance-test-runner",
            ),
            "perf-plan-compiler": ToolModule(
                descriptor=ToolDescriptor(
                    key="perf-plan-compiler",
                    name="Perf Plan Compiler",
                    description="将性能测试计划编译为引擎脚本，纯计算无副作用。",
                    category="execution",
                    permission_level="safe",
                    input_schema={
                        "type": "object",
                        "properties": {
                            "plan": {"type": "object", "description": "PerfPlan 序列化对象。"},
                            "engine": {"type": "string", "description": "引擎 key，默认 k6。", "default": "k6"},
                        },
                        "required": ["plan"],
                    },
                    output_schema={"script_content": "string", "filename": "string", "data_files": "object"},
                    tags=["performance", "planning", "script"],
                ),
                handler_key="perf-plan-compiler",
            ),
            "perf-result-analyzer": ToolModule(
                descriptor=ToolDescriptor(
                    key="perf-result-analyzer",
                    name="Perf Result Analyzer",
                    description="解析压测 RawMetrics 并生成结构化报告，纯计算无副作用。",
                    category="reporting",
                    permission_level="safe",
                    input_schema={
                        "type": "object",
                        "properties": {
                            "raw_metrics": {"type": "object", "description": "RawMetrics 序列化对象。"},
                            "plan": {"type": "object", "description": "PerfPlan 序列化对象。"},
                            "run": {"type": "object", "description": "PerfRun 序列化对象。"},
                            "baseline_metrics": {"type": "object", "description": "可选基线 PerfMetrics。"},
                        },
                        "required": ["raw_metrics", "plan", "run"],
                    },
                    output_schema={
                        "verdict": "string",
                        "metrics": "object",
                        "sla_result": "object",
                        "error_breakdown": "object",
                        "report_markdown": "string",
                    },
                    tags=["performance", "analysis", "reporting"],
                ),
                handler_key="perf-result-analyzer",
            ),
            "smoke-suite-runner": ToolModule(
                descriptor=ToolDescriptor(
                    key="smoke-suite-runner",
                    name="Smoke Suite Runner",
                    description="Generate, revise, persist, and execute user-approved smoke testing plans with MinIO/PostgreSQL asset tracking.",
                    category="execution",
                    permission_level="ask",
                    input_schema={
                        "type": "object",
                        "properties": {
                            "action": {
                                "type": "string",
                                "enum": ["draft_plan", "revise_plan", "execute_approved_plan", "get_plan"],
                                "description": "冒烟模式动作：生成方案、修订方案、执行已确认方案或读取方案。",
                            },
                            "objective": {"type": "string", "description": "用户冒烟测试目标。"},
                            "target_url": {"type": "string", "description": "被测系统入口地址。"},
                            "project_scope": {"type": "string", "description": "可选项目范围；未提供时按 target_url 自动匹配。"},
                            "api_doc_ids": {"type": "array", "items": {"type": "string"}, "description": "可选 API 文档 ID。"},
                            "attachment_ids": {"type": "array", "items": {"type": "string"}, "description": "可选会话附件 ID。"},
                            "plan_id": {"type": "string", "description": "待修订或执行的方案 ID。"},
                            "approved_plan_id": {"type": "string", "description": "已确认方案 ID。"},
                            "plan": {"type": "object", "description": "可选内联方案对象。"},
                            "user_revision": {"type": "string", "description": "用户对方案的修改意见。"},
                            "selected_case_ids": {"type": "array", "items": {"type": "string"}, "description": "用户勾选执行的用例 ID。"},
                            "selected_indices": {"type": "array", "items": {"type": "integer"}, "description": "用户勾选执行的用例序号。"},
                            "max_cases": {"type": "integer", "description": "最多生成的冒烟用例数。"},
                            "include_api": {"type": "boolean"},
                            "include_ui": {"type": "boolean"},
                            "include_health_check": {"type": "boolean"},
                            "allow_write_operations": {"type": "boolean", "description": "是否允许执行写操作；默认 false。"},
                            "credentials_policy": {"type": "string", "description": "凭据策略，默认 memory_lookup。"},
                        },
                        "required": ["action"],
                    },
                    output_schema={
                        "summary": "string",
                        "plan": "object",
                        "run_result": "object",
                        "plan_uri": "string",
                        "approved_plan_uri": "string",
                        "run_result_uri": "string",
                        "report_uri": "string",
                    },
                    tags=["smoke", "testing", "mode", "approval", "regression-candidate"],
                ),
                handler_key="smoke-suite-runner",
            ),
        }
        self._dynamic_tools: dict[str, ToolModule] = {}

    def list(self) -> list[ToolDescriptor]:
        return [
            *[module.descriptor for module in self._tools.values()],
            *[module.descriptor for module in self._dynamic_tools.values()],
        ]

    def get(self, key: str) -> ToolDescriptor:
        module = self._dynamic_tools.get(key) or self._tools.get(key)
        if module is None:
            raise KeyError(f"Unknown tool: {key}")
        return module.descriptor

    def get_many(self, keys: list[str]) -> list[ToolDescriptor]:
        return [self.get(key) for key in keys if key in self._tools or key in self._dynamic_tools]

    def get_handler_key(self, key: str) -> str | None:
        module = self._dynamic_tools.get(key) or self._tools.get(key)
        if module is None:
            raise KeyError(f"Unknown tool: {key}")
        return module.handler_key

    def has_handler_binding(self, key: str) -> bool:
        module = self._dynamic_tools.get(key) or self._tools.get(key)
        return module is not None and module.handler_key is not None

    def register_dynamic(self, descriptor: ToolDescriptor, handler_key: str) -> None:
        if descriptor.key in self._tools:
            raise ValueError(f"Cannot dynamically override static tool '{descriptor.key}'.")
        self._dynamic_tools[descriptor.key] = ToolModule(
            descriptor=descriptor,
            handler_key=handler_key,
        )

    def unregister_dynamic(self, key: str) -> None:
        self._dynamic_tools.pop(key, None)

    def build_model_tools(self, keys: list[str]) -> list[dict]:
        tools = self.get_many(keys)
        return [
            {
                "name": tool.key,
                "description": tool.description,
                "input_schema": tool.input_schema or {"type": "object", "properties": {}},
            }
            for tool in tools
        ]

from __future__ import annotations

from dataclasses import dataclass

from src.schemas.agent import ToolDescriptor


@dataclass(frozen=True)
class ToolModule:
    descriptor: ToolDescriptor
    handler_key: str | None = None


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
                        },
                    },
                    output_schema={"steps": "array", "artifacts": "array"},
                    tags=["ui", "automation", "mode"],
                ),
                handler_key="ui-automation-runner",
            ),
            "api-test-runner": ToolModule(
                descriptor=ToolDescriptor(
                    key="api-test-runner",
                    name="API Test Runner",
                    description="Mode-scoped entry tool for API interface testing workflows.",
                    category="execution",
                    permission_level="ask",
                    input_schema={
                        "type": "object",
                        "properties": {
                            "endpoint": {"type": "string"},
                            "method": {"type": "string"},
                            "objective": {"type": "string"},
                        },
                    },
                    output_schema={"checks": "array"},
                    tags=["api", "testing", "mode"],
                ),
                handler_key="api-test-runner",
            ),
            "security-scan-runner": ToolModule(
                descriptor=ToolDescriptor(
                    key="security-scan-runner",
                    name="Security Scan Runner",
                    description="Placeholder mode entry tool for future security testing workflows.",
                    category="execution",
                    permission_level="ask",
                    input_schema={"type": "object", "properties": {"objective": {"type": "string"}}},
                    output_schema={"summary": "string"},
                    tags=["security", "testing", "mode", "placeholder"],
                ),
                handler_key="security-scan-runner",
            ),
            "performance-test-runner": ToolModule(
                descriptor=ToolDescriptor(
                    key="performance-test-runner",
                    name="Performance Test Runner",
                    description="Placeholder mode entry tool for future performance testing workflows.",
                    category="execution",
                    permission_level="ask",
                    input_schema={"type": "object", "properties": {"objective": {"type": "string"}}},
                    output_schema={"summary": "string"},
                    tags=["performance", "testing", "mode", "placeholder"],
                ),
                handler_key="performance-test-runner",
            ),
            "smoke-suite-runner": ToolModule(
                descriptor=ToolDescriptor(
                    key="smoke-suite-runner",
                    name="Smoke Suite Runner",
                    description="Placeholder mode entry tool for future smoke testing workflows.",
                    category="execution",
                    permission_level="ask",
                    input_schema={"type": "object", "properties": {"objective": {"type": "string"}}},
                    output_schema={"summary": "string"},
                    tags=["smoke", "testing", "mode", "placeholder"],
                ),
                handler_key="smoke-suite-runner",
            ),
        }

    def list(self) -> list[ToolDescriptor]:
        return [module.descriptor for module in self._tools.values()]

    def get(self, key: str) -> ToolDescriptor:
        if key not in self._tools:
            raise KeyError(f"Unknown tool: {key}")
        return self._tools[key].descriptor

    def get_many(self, keys: list[str]) -> list[ToolDescriptor]:
        return [self._tools[key].descriptor for key in keys if key in self._tools]

    def get_handler_key(self, key: str) -> str | None:
        if key not in self._tools:
            raise KeyError(f"Unknown tool: {key}")
        return self._tools[key].handler_key

    def has_handler_binding(self, key: str) -> bool:
        return key in self._tools and self._tools[key].handler_key is not None

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

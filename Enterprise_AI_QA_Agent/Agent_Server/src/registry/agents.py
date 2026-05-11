from __future__ import annotations

from dataclasses import dataclass

from src.schemas.agent import AgentDescriptor


@dataclass(frozen=True)
class AgentModule:
    descriptor: AgentDescriptor


class AgentRegistry:
    def __init__(self) -> None:
        self._agents: dict[str, AgentModule] = {
            "coordinator": AgentModule(
                descriptor=AgentDescriptor(
                    key="coordinator",
                    name="Coordinator",
                    role="coordinator",
                    summary="Coordinate planning, context assembly, and execution routing.",
                    description="Acts like the Claude Code coordinator: chooses the next execution path, synthesizes context, and orchestrates work.",
                    supported_tools=[
                        "workflow-router",
                        "subagent-dispatch",
                        "knowledge-rag",
                        "attachment-reader",
                        "session-history",
                        "session-timeline",
                        "observation-search",
                        "test-case-generator",
                        "cli-executor",
                        "send-email",
                        "report-writer",
                    ],
                    supported_skills=["requirements-analysis", "risk-scoping", "report-synthesis"],
                    supported_models=["claude-sonnet-4", "gpt-5.4", "qwen-max"],
                    default_model="claude-sonnet-4",
                    tags=["core", "orchestration"],
                )
            ),
            "qa-planner": AgentModule(
                descriptor=AgentDescriptor(
                    key="qa-planner",
                    name="QA Planner",
                    role="planner",
                    summary="Break requirements into test coverage, assertions, and risks.",
                    description="Transforms user intent into executable QA plans, test cases, and verification boundaries.",
                    supported_tools=[
                        "attachment-reader",
                        "session-history",
                        "session-timeline",
                        "observation-search",
                        "knowledge-rag",
                        "test-case-generator",
                        "report-writer",
                    ],
                    supported_skills=["requirements-analysis", "case-design"],
                    supported_models=["claude-sonnet-4", "gpt-5.4", "deepseek-reasoner"],
                    default_model="gpt-5.4",
                    tags=["planning", "qa"],
                )
            ),
            "ops-executor": AgentModule(
                descriptor=AgentDescriptor(
                    key="ops-executor",
                    name="Ops Executor",
                    role="worker",
                    summary="Execute terminal commands, environment diagnostics, and workspace-level operational checks.",
                    description=(
                        "Runs CLI commands inside the workspace with approval gating, captures terminal evidence, "
                        "and can package the results as QA-ready artifacts."
                    ),
                    supported_tools=[
                        "cli-executor",
                        "file-artifact-manager",
                        "send-email",
                        "report-writer",
                        "session-history",
                        "session-timeline",
                        "observation-search",
                    ],
                    supported_skills=["artifact-collection", "report-synthesis"],
                    supported_models=["claude-sonnet-4", "gpt-5.4", "qwen-max"],
                    default_model="claude-sonnet-4",
                    tags=["ops", "cli", "execution"],
                )
            ),
            "ui-executor": AgentModule(
                descriptor=AgentDescriptor(
                    key="ui-executor",
                    name="UI Explorer",
                    role="worker",
                    summary="Understand page structure and build semantic UI graphs from ARIA snapshots.",
                    description="Runs UI exploration only: captures accessibility-tree structure, extracts business context, and writes page/entity/element graph knowledge without tests, assertions, or validation verdicts.",
                    supported_tools=[
                        "ui-page-explorer",
                        "browser-automation",
                        "browser-control",
                        "dom-inspector",
                        "file-artifact-manager",
                        "send-email",
                        "report-writer",
                    ],
                    supported_skills=["ui-exploration", "playwright-cli", "artifact-collection"],
                    supported_models=["claude-sonnet-4", "qwen-max"],
                    default_model="claude-sonnet-4",
                    tags=["ui", "exploration", "aria", "graph"],
                )
            ),
            "api-verifier": AgentModule(
                descriptor=AgentDescriptor(
                    key="api-verifier",
                    name="API Verifier",
                    role="verifier",
                    summary="Validate APIs, payloads, and structured assertions.",
                    description="Runs API checks and produces assertion-ready verification summaries.",
                    supported_tools=["api-tester", "knowledge-rag", "send-email", "report-writer"],
                    supported_skills=["api-validation", "assertion-design"],
                    supported_models=["gpt-5.4", "deepseek-reasoner"],
                    default_model="gpt-5.4",
                    tags=["api", "verification"],
                )
            ),
            "report-analyst": AgentModule(
                descriptor=AgentDescriptor(
                    key="report-analyst",
                    name="Report Analyst",
                    role="reporter",
                    summary="Turn runtime evidence into structured QA output.",
                    description="Produces final findings, summaries, and delivery-ready reports.",
                    supported_tools=[
                        "report-writer",
                        "attachment-reader",
                        "knowledge-rag",
                        "session-history",
                        "session-timeline",
                        "observation-search",
                        "send-email",
                    ],
                    supported_skills=["report-synthesis"],
                    supported_models=["claude-sonnet-4", "gpt-5.4"],
                    default_model="claude-sonnet-4",
                    tags=["reporting"],
                )
            ),
            "code-review-agent": AgentModule(
                descriptor=AgentDescriptor(
                    key="code-review-agent",
                    name="Code Review Agent",
                    role="coordinator",
                    summary="Coordinate time-budgeted code review debates, launch reviewer agents, and produce approval-ready output.",
                    description="Dedicated mode coordinator for code review workflows. It should launch the code-review-orchestrator first, then supervise reviewer debate progress instead of reading repository files directly.",
                    supported_tools=[
                        "code-review-orchestrator",
                        "session-history",
                        "observation-search",
                        "message-dispatch",
                        "send-email",
                        "report-writer",
                    ],
                    supported_skills=["report-synthesis", "requirements-analysis", "risk-scoping"],
                    supported_models=["gpt-5.4", "claude-sonnet-4", "deepseek-reasoner"],
                    default_model="gpt-5.4",
                    tags=["testing", "code-review", "approval"],
                )
            ),
            "code-architecture-reviewer": AgentModule(
                descriptor=AgentDescriptor(
                    key="code-architecture-reviewer",
                    name="Code Architecture Reviewer",
                    role="reviewer",
                    summary="Review module boundaries, dependency flow, and extensibility risks.",
                    description="Specialized code review worker focused on architecture decisions, layering, ownership boundaries, and long-term maintainability tradeoffs.",
                    supported_tools=[
                        "project-source-loader",
                        "project-tree-scanner",
                        "project-file-reader",
                        "project-diff-reader",
                        "session-history",
                        "observation-search",
                        "knowledge-rag",
                        "message-dispatch",
                        "send-email",
                        "report-writer",
                    ],
                    supported_skills=["requirements-analysis", "risk-scoping", "report-synthesis"],
                    supported_models=["gpt-5.4", "claude-sonnet-4", "deepseek-reasoner"],
                    default_model="gpt-5.4",
                    tags=["testing", "code-review", "architecture"],
                )
            ),
            "code-correctness-reviewer": AgentModule(
                descriptor=AgentDescriptor(
                    key="code-correctness-reviewer",
                    name="Code Correctness Reviewer",
                    role="reviewer",
                    summary="Review logic, state transitions, and edge-case correctness.",
                    description="Specialized code review worker focused on functional correctness, failure handling, and invalid state transitions.",
                    supported_tools=[
                        "project-source-loader",
                        "project-tree-scanner",
                        "project-file-reader",
                        "project-diff-reader",
                        "session-history",
                        "observation-search",
                        "knowledge-rag",
                        "message-dispatch",
                        "send-email",
                        "report-writer",
                    ],
                    supported_skills=["requirements-analysis", "risk-scoping", "report-synthesis"],
                    supported_models=["gpt-5.4", "claude-sonnet-4", "deepseek-reasoner"],
                    default_model="gpt-5.4",
                    tags=["testing", "code-review", "correctness"],
                )
            ),
            "code-security-reviewer": AgentModule(
                descriptor=AgentDescriptor(
                    key="code-security-reviewer",
                    name="Code Security Reviewer",
                    role="reviewer",
                    summary="Review command execution, credentials, unsafe input handling, and privilege boundaries.",
                    description="Specialized code review worker focused on exploit paths, trust boundaries, secret handling, and containment measures.",
                    supported_tools=[
                        "project-source-loader",
                        "project-tree-scanner",
                        "project-file-reader",
                        "project-diff-reader",
                        "session-history",
                        "observation-search",
                        "knowledge-rag",
                        "message-dispatch",
                        "send-email",
                        "report-writer",
                    ],
                    supported_skills=["requirements-analysis", "risk-scoping", "report-synthesis"],
                    supported_models=["gpt-5.4", "claude-sonnet-4", "deepseek-reasoner"],
                    default_model="gpt-5.4",
                    tags=["testing", "code-review", "security"],
                )
            ),
            "code-testability-reviewer": AgentModule(
                descriptor=AgentDescriptor(
                    key="code-testability-reviewer",
                    name="Code Testability Reviewer",
                    role="reviewer",
                    summary="Review coverage gaps, replayability, observability, and harness fit.",
                    description="Specialized code review worker focused on missing tests, weak evidence capture, and harness improvements for reliable verification.",
                    supported_tools=[
                        "project-source-loader",
                        "project-tree-scanner",
                        "project-file-reader",
                        "project-diff-reader",
                        "session-history",
                        "observation-search",
                        "knowledge-rag",
                        "message-dispatch",
                        "send-email",
                        "report-writer",
                    ],
                    supported_skills=["requirements-analysis", "risk-scoping", "report-synthesis"],
                    supported_models=["gpt-5.4", "claude-sonnet-4", "deepseek-reasoner"],
                    default_model="gpt-5.4",
                    tags=["testing", "code-review", "testability"],
                )
            ),
            "code-maintainability-reviewer": AgentModule(
                descriptor=AgentDescriptor(
                    key="code-maintainability-reviewer",
                    name="Code Maintainability Reviewer",
                    role="reviewer",
                    summary="Review readability, duplication, complexity, and configuration hygiene.",
                    description="Specialized code review worker focused on code clarity, repeated patterns, maintainability debt, and operational simplicity.",
                    supported_tools=[
                        "project-source-loader",
                        "project-tree-scanner",
                        "project-file-reader",
                        "project-diff-reader",
                        "session-history",
                        "observation-search",
                        "knowledge-rag",
                        "message-dispatch",
                        "send-email",
                        "report-writer",
                    ],
                    supported_skills=["requirements-analysis", "risk-scoping", "report-synthesis"],
                    supported_models=["gpt-5.4", "claude-sonnet-4", "deepseek-reasoner"],
                    default_model="gpt-5.4",
                    tags=["testing", "code-review", "maintainability"],
                )
            ),
            "code-review-synthesizer": AgentModule(
                descriptor=AgentDescriptor(
                    key="code-review-synthesizer",
                    name="Code Review Synthesizer",
                    role="summarizer",
                    summary="Aggregate reviewer debate results into an approval-ready report.",
                    description="Specialized code review worker focused on merging reviewer findings, preserving proposer/support/challenge attribution, and writing the final debate report.",
                    supported_tools=[
                        "project-source-loader",
                        "project-tree-scanner",
                        "session-history",
                        "observation-search",
                        "knowledge-rag",
                        "send-email",
                        "report-writer",
                    ],
                    supported_skills=["requirements-analysis", "report-synthesis"],
                    supported_models=["gpt-5.4", "claude-sonnet-4", "deepseek-reasoner"],
                    default_model="gpt-5.4",
                    tags=["testing", "code-review", "summary"],
                )
            ),
            "ui-automation-agent": AgentModule(
                descriptor=AgentDescriptor(
                    key="ui-automation-agent",
                    name="UI Automation Agent",
                    role="tester",
                    summary="Execute UI automation workflows with page exploration and evidence capture.",
                    description="Dedicated mode agent for UI automation tasks, browser evidence, and repeatable UI execution.",
                    supported_tools=[
                        "ui-automation-runner",
                        "ui-page-explorer",
                        "browser-automation",
                        "browser-control",
                        "dom-inspector",
                        "file-artifact-manager",
                        "report-writer",
                    ],
                    supported_skills=["ui-exploration", "playwright-cli", "artifact-collection"],
                    supported_models=["claude-sonnet-4", "gpt-5.4", "qwen-max"],
                    default_model="claude-sonnet-4",
                    tags=["testing", "ui", "automation"],
                )
            ),
            "api-testing-agent": AgentModule(
                descriptor=AgentDescriptor(
                    key="api-testing-agent",
                    name="API Testing Agent",
                    role="tester",
                    summary="Run API contract, status, and payload validation workflows.",
                    description="Dedicated mode agent for API interface testing with focused verification output.",
                    supported_tools=["api-test-runner", "api-docs-library", "api-tester", "knowledge-rag", "report-writer"],
                    supported_skills=["api-validation", "assertion-design"],
                    supported_models=["gpt-5.4", "deepseek-reasoner", "claude-sonnet-4"],
                    default_model="gpt-5.4",
                    tags=["testing", "api"],
                )
            ),
            "api-executor-worker": AgentModule(
                descriptor=AgentDescriptor(
                    key="api-executor-worker",
                    name="API Executor Worker",
                    role="worker",
                    summary="Execute ready API test tasks from the task pool with HTTP calls and assertion evaluation.",
                    description="Parallel execution worker for API testing campaigns. Receives dispatched tasks, sends HTTP requests, evaluates assertions, and returns structured results.",
                    supported_tools=["api-tester", "api-docs-library", "knowledge-rag", "session-history", "observation-search", "report-writer"],
                    supported_skills=["api-validation", "assertion-design"],
                    supported_models=["gpt-5.4", "deepseek-reasoner", "claude-sonnet-4"],
                    default_model="gpt-5.4",
                    tags=["testing", "api", "worker", "execution"],
                )
            ),
            "api-project-clarifier": AgentModule(
                descriptor=AgentDescriptor(
                    key="api-project-clarifier",
                    name="API Project Clarifier",
                    role="planner",
                    summary="Explain and rank candidate projects when API testing scope is ambiguous.",
                    description="Presents project candidates with rationale, helps the user pick the correct project scope before any test execution begins.",
                    supported_tools=["api-docs-library", "knowledge-rag", "session-history"],
                    supported_skills=["api-validation"],
                    supported_models=["gpt-5.4", "claude-sonnet-4"],
                    default_model="gpt-5.4",
                    tags=["testing", "api", "clarification"],
                )
            ),
            "api-doc-analyst": AgentModule(
                descriptor=AgentDescriptor(
                    key="api-doc-analyst",
                    name="API Doc Analyst",
                    role="planner",
                    summary="Analyze document coverage and endpoint grouping after project selection.",
                    description="Reads API documentation structure, identifies endpoint groups, auth requirements, and coverage gaps to inform campaign planning.",
                    supported_tools=["api-docs-library", "knowledge-rag", "session-history", "report-writer"],
                    supported_skills=["api-validation", "assertion-design"],
                    supported_models=["gpt-5.4", "claude-sonnet-4", "deepseek-reasoner"],
                    default_model="gpt-5.4",
                    tags=["testing", "api", "analysis"],
                )
            ),
            "api-suite-planner": AgentModule(
                descriptor=AgentDescriptor(
                    key="api-suite-planner",
                    name="API Suite Planner",
                    role="planner",
                    summary="Convert user objectives into campaign scope and assertion strategy.",
                    description="Transforms high-level testing goals into concrete endpoint selections, assertion types, and execution ordering for the campaign.",
                    supported_tools=["api-docs-library", "api-test-runner", "knowledge-rag", "session-history", "report-writer"],
                    supported_skills=["api-validation", "assertion-design"],
                    supported_models=["gpt-5.4", "claude-sonnet-4", "deepseek-reasoner"],
                    default_model="gpt-5.4",
                    tags=["testing", "api", "planning"],
                )
            ),
            "api-precondition-planner": AgentModule(
                descriptor=AgentDescriptor(
                    key="api-precondition-planner",
                    name="API Precondition Planner",
                    role="planner",
                    summary="Plan auth, preconditions, data dependencies, and readiness checks.",
                    description="Identifies authentication requirements, test data seeds, environment readiness, and dependency chains before campaign execution.",
                    supported_tools=["api-docs-library", "knowledge-rag", "session-history"],
                    supported_skills=["api-validation"],
                    supported_models=["gpt-5.4", "claude-sonnet-4"],
                    default_model="gpt-5.4",
                    tags=["testing", "api", "precondition"],
                )
            ),
            "api-failure-analyst": AgentModule(
                descriptor=AgentDescriptor(
                    key="api-failure-analyst",
                    name="API Failure Analyst",
                    role="verifier",
                    summary="Analyze API test failures, determine retryability, and identify root causes.",
                    description="Reviews failed API test tasks, classifies failure types (auth/timeout/server/assertion), suggests fixes, and determines if failures are transient or permanent.",
                    supported_tools=["api-docs-library", "knowledge-rag", "session-history", "observation-search", "report-writer"],
                    supported_skills=["api-validation", "assertion-design"],
                    supported_models=["gpt-5.4", "claude-sonnet-4", "deepseek-reasoner"],
                    default_model="gpt-5.4",
                    tags=["testing", "api", "failure-analysis"],
                )
            ),
            "security-testing-agent": AgentModule(
                descriptor=AgentDescriptor(
                    key="security-testing-agent",
                    name="Security Testing Agent",
                    role="tester",
                    summary="Reserved agent for future security testing workflows.",
                    description="Placeholder agent scaffold for security testing mode.",
                    supported_tools=["security-scan-runner", "knowledge-rag", "report-writer", "cli-executor"],
                    supported_skills=[],
                    supported_models=["gpt-5.4", "claude-sonnet-4"],
                    default_model="gpt-5.4",
                    tags=["testing", "security", "placeholder"],
                )
            ),
            "performance-testing-agent": AgentModule(
                descriptor=AgentDescriptor(
                    key="performance-testing-agent",
                    name="Performance Testing Agent",
                    role="tester",
                    summary="Reserved agent for future performance testing workflows.",
                    description="Placeholder agent scaffold for performance testing mode.",
                    supported_tools=["performance-test-runner", "knowledge-rag", "report-writer", "cli-executor"],
                    supported_skills=[],
                    supported_models=["gpt-5.4", "claude-sonnet-4"],
                    default_model="gpt-5.4",
                    tags=["testing", "performance", "placeholder"],
                )
            ),
            "smoke-testing-agent": AgentModule(
                descriptor=AgentDescriptor(
                    key="smoke-testing-agent",
                    name="Smoke Testing Agent",
                    role="tester",
                    summary="Reserved agent for future smoke testing workflows.",
                    description="Placeholder agent scaffold for smoke testing mode.",
                    supported_tools=["smoke-suite-runner", "knowledge-rag", "report-writer"],
                    supported_skills=[],
                    supported_models=["gpt-5.4", "claude-sonnet-4"],
                    default_model="gpt-5.4",
                    tags=["testing", "smoke", "placeholder"],
                )
            ),
        }

    def list(self) -> list[AgentDescriptor]:
        return [module.descriptor for module in self._agents.values()]

    def get(self, key: str) -> AgentDescriptor:
        if key not in self._agents:
            raise KeyError(f"Unknown agent: {key}")
        return self._agents[key].descriptor

    def resolve_for_message(
        self,
        message: str,
        explicit_key: str | None = None,
    ) -> AgentDescriptor:
        if explicit_key:
            return self.get(explicit_key)

        lowered = (message or "").lower()
        if any(token in lowered for token in ["cli", "terminal", "shell", "powershell", "command", "bash", "cmd"]):
            return self.get("ops-executor")
        if any(token in lowered for token in ["api", "interface", "payload", "response"]):
            return self.get("api-verifier")
        if any(token in lowered for token in ["page", "browser", "ui", "selenium", "playwright"]):
            return self.get("ui-executor")
        if any(token in lowered for token in ["history", "session report", "conversation report", "previous questions"]):
            return self.get("report-analyst")
        if any(token in lowered for token in ["report", "summary", "analysis"]):
            return self.get("report-analyst")
        if any(token in lowered for token in ["case", "plan", "scenario", "test plan"]):
            return self.get("qa-planner")
        return self.get("coordinator")

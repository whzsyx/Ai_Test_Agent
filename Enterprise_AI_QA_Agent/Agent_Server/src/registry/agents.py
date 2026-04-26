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
                    role="reviewer",
                    summary="Review code changes, identify risk, and produce structured approval output.",
                    description="Dedicated mode agent for code review workflows, multi-agent orchestration, and approval-ready reporting.",
                    supported_tools=[
                        "code-review-orchestrator",
                        "cli-executor",
                        "session-history",
                        "observation-search",
                        "knowledge-rag",
                        "report-writer",
                        "subagent-dispatch",
                    ],
                    supported_skills=["report-synthesis", "requirements-analysis"],
                    supported_models=["gpt-5.4", "claude-sonnet-4", "deepseek-reasoner"],
                    default_model="gpt-5.4",
                    tags=["testing", "code-review", "approval"],
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
                    supported_tools=["api-test-runner", "api-tester", "knowledge-rag", "report-writer"],
                    supported_skills=["api-validation", "assertion-design"],
                    supported_models=["gpt-5.4", "deepseek-reasoner", "claude-sonnet-4"],
                    default_model="gpt-5.4",
                    tags=["testing", "api"],
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

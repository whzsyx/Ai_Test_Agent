from __future__ import annotations

# Coordinator (intake + orchestration)
COORDINATOR_TOOL_KEYS = [
    "performance-test-runner",
    "knowledge-rag",
    "report-writer",
    "message-dispatch",
    "send-email",
    "file-artifact-manager",
    "subagent-dispatch",
]

# Worker: plan compilation + script generation
PLANNER_TOOL_KEYS = [
    "perf-plan-compiler",
    "knowledge-rag",
    "api-docs-library",
]

# Worker: execution
RUNNER_TOOL_KEYS = [
    "performance-test-runner",
    "cli-executor",
]

# Worker: analysis + reporting
ANALYST_TOOL_KEYS = [
    "perf-result-analyzer",
    "report-writer",
    "observation-search",
]

# All keys registered for this mode (used by manifest)
PERFORMANCE_TESTING_TOOL_KEYS = sorted(set(
    COORDINATOR_TOOL_KEYS
    + PLANNER_TOOL_KEYS
    + RUNNER_TOOL_KEYS
    + ANALYST_TOOL_KEYS
))

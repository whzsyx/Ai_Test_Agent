"""Security Testing Mode tool key definitions.

Separates tool visibility by role: primary agent, worker agents, and reporting.
"""
from __future__ import annotations


# Tools available to the primary security-testing-agent
SECURITY_TESTING_TOOL_KEYS: list[str] = [
    "subagent-dispatch",
    "knowledge-rag",
    "report-writer",
    "observation-search",
    "session-history",
]

# Tools available to security worker agents
SECURITY_WORKER_TOOL_KEYS: list[str] = [
    "security-scan-runner",
    "network-recon-runner",
    "web-scan-runner",
    "service-audit-runner",
    "credential-attack-runner",
    "traffic-analysis-runner",
    "exploit-workbench-runner",
    "knowledge-rag",
    "observation-search",
]

# Tools for reporting phase
SECURITY_REPORTING_TOOL_KEYS: list[str] = [
    "report-writer",
    "knowledge-rag",
    "observation-search",
    "session-history",
]


__all__ = [
    "SECURITY_TESTING_TOOL_KEYS",
    "SECURITY_WORKER_TOOL_KEYS",
    "SECURITY_REPORTING_TOOL_KEYS",
]

from __future__ import annotations

MODE_MANIFEST = {
    "key": "code_review",
    "name": "代码审批模式",
    "summary": "面向代码变更审查、风险识别与审批结论输出。",
    "description": "代码审批模式内置多 Agent 与 Skills 协作链，聚焦 diff、风险、测试影响和审批结论。",
    "category": "testing",
    "is_test_mode": True,
    "default_agent_key": "code-review-agent",
    "allowed_agent_keys": ["code-review-agent", "report-analyst", "ops-executor", "coordinator"],
    "default_skill_keys": ["report-synthesis", "requirements-analysis"],
    "registered_tool_keys": [
        "code-review-orchestrator",
        "cli-executor",
        "session-history",
        "observation-search",
        "knowledge-rag",
        "report-writer",
        "subagent-dispatch",
    ],
    "harness_key": "code_review_harness",
    "placeholder": False,
    "tags": ["testing", "code-review", "approval"],
}

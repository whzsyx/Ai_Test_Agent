from __future__ import annotations

MODE_MANIFEST = {
    "key": "smoke_testing",
    "name": "冒烟测试模式",
    "summary": "面向核心链路快速回归与基础可用性确认。",
    "description": "冒烟测试模式已完成模式骨架、专属 Agent 和工具注册，占位等待后续能力接入。",
    "category": "testing",
    "is_test_mode": True,
    "default_agent_key": "smoke-testing-agent",
    "allowed_agent_keys": ["smoke-testing-agent", "report-analyst"],
    "default_skill_keys": [],
    "registered_tool_keys": [
        "smoke-suite-runner",
        "report-writer",
        "knowledge-rag",
    ],
    "harness_key": "smoke_testing_harness",
    "placeholder": True,
    "tags": ["testing", "smoke", "placeholder"],
}

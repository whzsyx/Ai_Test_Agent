from __future__ import annotations

MODE_MANIFEST = {
    "key": "performance_testing",
    "name": "性能测试模式",
    "summary": "面向基线测试、吞吐/延迟观察与性能证据输出。",
    "description": "性能测试模式已完成模式骨架、专属 Agent 和工具注册，占位等待后续能力接入。",
    "category": "testing",
    "is_test_mode": True,
    "default_agent_key": "performance-testing-agent",
    "allowed_agent_keys": ["performance-testing-agent", "report-analyst"],
    "default_skill_keys": [],
    "registered_tool_keys": [
        "performance-test-runner",
        "knowledge-rag",
        "report-writer",
        "cli-executor",
    ],
    "harness_key": "performance_testing_harness",
    "placeholder": True,
    "tags": ["testing", "performance", "placeholder"],
}

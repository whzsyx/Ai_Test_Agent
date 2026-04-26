from __future__ import annotations

MODE_MANIFEST = {
    "key": "security_testing",
    "name": "安全测试模式",
    "summary": "面向漏洞检查、越权验证与安全风险识别。",
    "description": "安全测试模式已完成模式骨架、专属 Agent 和工具注册，占位等待后续能力接入。",
    "category": "testing",
    "is_test_mode": True,
    "default_agent_key": "security-testing-agent",
    "allowed_agent_keys": ["security-testing-agent", "report-analyst"],
    "default_skill_keys": [],
    "registered_tool_keys": [
        "security-scan-runner",
        "knowledge-rag",
        "report-writer",
        "cli-executor",
    ],
    "harness_key": "security_testing_harness",
    "placeholder": True,
    "tags": ["testing", "security", "placeholder"],
}

from __future__ import annotations

MODE_MANIFEST = {
    "key": "api_testing",
    "name": "API接口测试模式",
    "summary": "面向接口校验、契约检查、响应断言与证据沉淀。",
    "description": "API 接口测试模式提供专属 Agent 和接口测试工具链，统一处理接口验证任务。",
    "category": "testing",
    "is_test_mode": True,
    "default_agent_key": "api-testing-agent",
    "allowed_agent_keys": ["api-testing-agent", "report-analyst"],
    "default_skill_keys": ["api-validation", "assertion-design"],
    "registered_tool_keys": [
        "api-test-runner",
        "api-tester",
        "knowledge-rag",
        "report-writer",
    ],
    "harness_key": "api_testing_harness",
    "placeholder": False,
    "tags": ["testing", "api", "contract"],
}

from __future__ import annotations

MODE_MANIFEST = {
    "key": "performance_testing",
    "name": "性能测试模式",
    "summary": "面向基线测试、吞吐/延迟观察与性能证据输出。",
    "description": (
        "性能测试模式：支持对话式意图采集、k6 引擎脚本生成、docker 容器化执行、"
        "冒烟验证闸门、目标安全护栏、结构化指标解析和独立 verdict 判定。"
    ),
    "category": "testing",
    "is_test_mode": True,
    "default_agent_key": "performance-testing-agent",
    "allowed_agent_keys": [
        "performance-testing-agent",
        "perf-planner",
        "perf-script-builder",
        "perf-runner",
        "perf-analyst",
        "report-analyst",
    ],
    "default_skill_keys": [],
    "registered_tool_keys": [
        "performance-test-runner",
        "perf-plan-compiler",
        "perf-result-analyzer",
        "knowledge-rag",
        "api-docs-library",
        "report-writer",
        "message-dispatch",
        "send-email",
        "file-artifact-manager",
        "cli-executor",
        "subagent-dispatch",
        "observation-search",
        "session-history",
    ],
    "harness_key": "performance_testing_harness",
    "placeholder": False,
    "tags": ["testing", "performance", "k6", "load"],
}

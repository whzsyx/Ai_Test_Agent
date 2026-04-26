from __future__ import annotations

MODE_MANIFEST = {
    "key": "default",
    "name": "默认模式",
    "summary": "处理除测试以外的通用协作、问答、调度与工作台能力。",
    "description": "默认模式承接当前系统已支持的综合能力，优先走 Coordinator 与现有通用工具链。",
    "category": "general",
    "is_test_mode": False,
    "default_agent_key": "coordinator",
    "allowed_agent_keys": ["coordinator", "ops-executor", "report-analyst", "qa-planner"],
    "default_skill_keys": [],
    "registered_tool_keys": [
        "workflow-router",
        "subagent-dispatch",
        "knowledge-rag",
        "session-history",
        "session-timeline",
        "observation-search",
        "cli-executor",
        "report-writer",
        "send-email",
    ],
    "harness_key": "default_conversation_harness",
    "placeholder": False,
    "tags": ["default", "general", "coordinator"],
}

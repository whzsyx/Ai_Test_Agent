from __future__ import annotations

from src.application.testing.direction_service import QATaskState


class QATaskRouterService:
    """Map test task directions to agent/tool harnesses."""

    def route(self, state: QATaskState) -> dict[str, str]:
        if not state.is_test_task:
            return {"agent_key": "", "harness": "base_conversation"}
        if state.direction == "ui":
            return {"agent_key": "ui-executor", "harness": "ui_tool_harness"}
        if state.direction == "api":
            return {"agent_key": "api-verifier", "harness": "api_tool_harness"}
        if state.direction == "security":
            return {"agent_key": "coordinator", "harness": "security_tool_harness"}
        if state.direction == "performance":
            return {"agent_key": "coordinator", "harness": "performance_tool_harness"}
        if state.direction == "mixed":
            return {"agent_key": "coordinator", "harness": "mixed_test_coordinator"}
        return {"agent_key": "qa-planner", "harness": "direction_selection"}

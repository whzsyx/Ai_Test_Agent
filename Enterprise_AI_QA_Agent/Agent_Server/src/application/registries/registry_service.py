from __future__ import annotations

from src.registry.agents import AgentRegistry
from src.registry.mcp import MCPRegistry
from src.registry.modes import ModeRegistry
from src.registry.models import ModelRegistry
from src.registry.skills import SkillRegistry
from src.registry.tools import ToolRegistry
from src.schemas.session import RuntimeMode, SessionMode
from src.application.mcp.manager_service import MCPManagerService


class RegistryService:
    def __init__(
        self,
        agent_registry: AgentRegistry,
        tool_registry: ToolRegistry,
        model_registry: ModelRegistry,
        skill_registry: SkillRegistry,
        mcp_registry: MCPRegistry,
        mode_registry: ModeRegistry,
        mcp_manager_service: MCPManagerService | None = None,
    ) -> None:
        self._agent_registry = agent_registry
        self._tool_registry = tool_registry
        self._model_registry = model_registry
        self._skill_registry = skill_registry
        self._mcp_registry = mcp_registry
        self._mode_registry = mode_registry
        self._mcp_manager_service = mcp_manager_service

    def list_agents(self):
        return self._agent_registry.list()

    def list_tools(self):
        return self._tool_registry.list()

    def list_models(self):
        return self._model_registry.list()

    def list_model_configs(self):
        return self._model_registry.list_configs()

    def list_skills(self):
        return self._skill_registry.list()

    def list_mcp_servers(self):
        return self._mcp_registry.list()

    async def list_managed_mcp_servers(self):
        if self._mcp_manager_service is None:
            return self._mcp_registry.list()
        return await self._mcp_manager_service.list_managed_servers()

    def list_mcp_providers(self):
        if self._mcp_manager_service is None:
            return []
        return self._mcp_manager_service.list_providers()

    def list_modes(self):
        return self._mode_registry.list()

    def framework_summary(self) -> dict[str, object]:
        return {
            "session_modes": [item.value for item in SessionMode],
            "runtime_modes": [item.value for item in RuntimeMode],
            "agent_count": len(self._agent_registry.list()),
            "tool_count": len(self._tool_registry.list()),
            "model_count": len(self._model_registry.list()),
            "skill_count": len(self._skill_registry.list()),
            "mcp_count": len(self._mcp_registry.list()),
            "mode_count": len(self._mode_registry.list()),
        }

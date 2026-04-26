from __future__ import annotations

from pydantic import BaseModel, Field


class ModeDescriptor(BaseModel):
    key: str
    name: str
    summary: str
    description: str
    category: str = "general"
    is_test_mode: bool = False
    default_agent_key: str
    allowed_agent_keys: list[str] = Field(default_factory=list)
    default_skill_keys: list[str] = Field(default_factory=list)
    registered_tool_keys: list[str] = Field(default_factory=list)
    harness_key: str = "base_conversation"
    placeholder: bool = False
    tags: list[str] = Field(default_factory=list)

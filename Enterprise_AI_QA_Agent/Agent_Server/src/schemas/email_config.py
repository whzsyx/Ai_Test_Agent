from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


EmailProvider = str


class EmailConfigRecord(BaseModel):
    id: int | None = None
    config_name: str
    provider: EmailProvider
    owner_agent_key: str = "global"
    api_key: str | None = None
    secret_key: str | None = None
    sender_email: str = ""
    test_email: str | None = None
    test_mode: bool = False
    enabled: bool = False
    is_default: bool = False
    description: str | None = None
    smtp_host: str | None = None
    smtp_port: int | None = None
    smtp_username: str | None = None
    extra_config: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime | None = None
    updated_at: datetime | None = None


class EmailConfigPublic(BaseModel):
    id: int
    config_name: str
    provider: EmailProvider
    enabled: bool = False
    is_default: bool = False
    sender_email: str = ""
    has_api_key: bool = False
    has_secret_key: bool = False
    description: str | None = None
    extra_config: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime | None = None
    updated_at: datetime | None = None


class EmailConfigCreateRequest(BaseModel):
    config_name: str
    provider: EmailProvider = "tencent_agently"
    sender_email: str = ""
    api_key: str | None = None
    secret_key: str | None = None
    enabled: bool = False
    is_default: bool = False
    description: str | None = None
    extra_config: dict[str, Any] = Field(default_factory=dict)


class EmailConfigUpdateRequest(BaseModel):
    config_name: str
    provider: EmailProvider = "tencent_agently"
    sender_email: str = ""
    api_key: str | None = None
    secret_key: str | None = None
    enabled: bool = False
    is_default: bool = False
    description: str | None = None
    extra_config: dict[str, Any] = Field(default_factory=dict)


class EmailConfigActionResponse(BaseModel):
    ok: bool
    message: str
    item: EmailConfigPublic | None = None


class SettingsBundle(BaseModel):
    model_configs: list[dict] = Field(default_factory=list)
    email_configs: list[EmailConfigPublic] = Field(default_factory=list)

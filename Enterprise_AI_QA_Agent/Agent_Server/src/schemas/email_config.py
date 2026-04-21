from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


EmailProvider = str


class EmailConfigRecord(BaseModel):
    id: int | None = None
    config_name: str
    provider: EmailProvider
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
    test_email: str | None = None
    test_mode: bool = False
    description: str | None = None
    smtp_host: str | None = None
    smtp_port: int | None = None
    smtp_username: str | None = None
    extra_config: dict[str, Any] = Field(default_factory=dict)
    has_api_key: bool = False
    has_secret_key: bool = False
    created_at: datetime | None = None
    updated_at: datetime | None = None


class EmailConfigCreateRequest(BaseModel):
    config_name: str
    provider: EmailProvider
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


class EmailConfigUpdateRequest(BaseModel):
    config_name: str
    provider: EmailProvider
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


class EmailConfigActionResponse(BaseModel):
    ok: bool
    message: str
    item: EmailConfigPublic | None = None


class EmailConfigConnectionTestResponse(BaseModel):
    ok: bool
    message: str
    item: EmailConfigPublic
    smtp_host: str | None = None
    smtp_port: int | None = None
    latency_ms: int | None = None
    preview: str | None = None


class SettingsBundle(BaseModel):
    model_configs: list[dict] = Field(default_factory=list)
    email_configs: list[EmailConfigPublic] = Field(default_factory=list)

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from src.domain.channel_strategies import CHANNEL_DEFINITIONS, channel_strategy_factory


ChannelProvider = Literal["qq", "feishu", "weixin"]
ChannelDomain = Literal["qq", "feishu", "lark", "weixin"]
ChannelStatus = Literal["unconfigured", "configured", "disabled"]
ChannelPairingStatus = Literal["pending", "confirmed", "expired"]
ChannelQueueMode = Literal["steer", "followup", "collect", "interrupt"]
ChannelQueueDrop = Literal["summarize", "old", "new"]


def channel_definition(domain: str) -> dict[str, Any]:
    return channel_strategy_factory.get(domain).definition.as_dict()


def validate_provider_domain(provider: str, domain: str) -> None:
    channel_strategy_factory.get(domain).validate_provider(provider)


def clean_public_config(domain: str, value: dict[str, Any] | None) -> dict[str, Any]:
    return channel_strategy_factory.get(domain).clean_public_config(value)


def clean_credentials(domain: str, value: dict[str, Any] | None) -> dict[str, str]:
    return channel_strategy_factory.get(domain).clean_credentials(value)


def compute_channel_status(
    *,
    domain: str,
    enabled: bool,
    public_config: dict[str, Any],
    credential_flags: dict[str, bool],
) -> ChannelStatus:
    return channel_strategy_factory.get(domain).compute_status(
        enabled=enabled,
        public_config=public_config,
        credential_flags=credential_flags,
    )


class ChannelConfigRecord(BaseModel):
    id: int | None = None
    config_name: str
    provider: ChannelProvider
    domain: ChannelDomain
    enabled: bool = False
    public_config: dict[str, Any] = Field(default_factory=dict)
    credential_ciphertext: str | None = None
    credential_version: int = 1
    description: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class ChannelConfigPublic(BaseModel):
    id: int
    config_name: str
    provider: ChannelProvider
    domain: ChannelDomain
    enabled: bool = False
    status: ChannelStatus
    public_config: dict[str, Any] = Field(default_factory=dict)
    credential_fields: dict[str, bool] = Field(default_factory=dict)
    has_credentials: bool = False
    description: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class ChannelConfigCreateRequest(BaseModel):
    config_name: str
    provider: ChannelProvider
    domain: ChannelDomain
    enabled: bool = False
    public_config: dict[str, Any] = Field(default_factory=dict)
    credentials: dict[str, Any] | None = None
    description: str | None = None

    @field_validator("config_name")
    @classmethod
    def _name_required(cls, value: str) -> str:
        text = value.strip()
        if not text:
            raise ValueError("Channel configuration name is required.")
        return text

    @model_validator(mode="after")
    def _validate_pair(self) -> "ChannelConfigCreateRequest":
        validate_provider_domain(self.provider, self.domain)
        self.public_config = clean_public_config(self.domain, self.public_config)
        self.credentials = clean_credentials(self.domain, self.credentials)
        self.description = _clean_optional(self.description)
        return self


class ChannelConfigUpdateRequest(BaseModel):
    config_name: str
    provider: ChannelProvider
    domain: ChannelDomain
    enabled: bool = False
    public_config: dict[str, Any] = Field(default_factory=dict)
    credentials: dict[str, Any] | None = None
    clear_credentials: bool = False
    description: str | None = None

    @field_validator("config_name")
    @classmethod
    def _name_required(cls, value: str) -> str:
        text = value.strip()
        if not text:
            raise ValueError("Channel configuration name is required.")
        return text

    @model_validator(mode="after")
    def _validate_pair(self) -> "ChannelConfigUpdateRequest":
        validate_provider_domain(self.provider, self.domain)
        self.public_config = clean_public_config(self.domain, self.public_config)
        self.credentials = clean_credentials(self.domain, self.credentials)
        self.description = _clean_optional(self.description)
        return self


class ChannelConfigActionResponse(BaseModel):
    ok: bool
    message: str
    item: ChannelConfigPublic | None = None


class ChannelPairingStartRequest(BaseModel):
    config_name: str | None = None
    enabled: bool = True
    device_hint: str | None = None


class ChannelPairingSessionPublic(BaseModel):
    session_id: str
    provider: ChannelProvider
    domain: ChannelDomain
    status: ChannelPairingStatus
    pairing_url: str
    qr_payload: str
    expires_at: datetime
    confirmed_at: datetime | None = None
    interval: int | None = None
    message: str | None = None
    item: ChannelConfigPublic | None = None


class ChannelAdvancedAllowlist(BaseModel):
    enabled: bool = True
    allow_all: bool = False
    qq_users: list[str] = Field(default_factory=list)
    feishu_users: list[str] = Field(default_factory=list)
    weixin_users: list[str] = Field(default_factory=list)
    qq_groups: list[str] = Field(default_factory=list)
    feishu_groups: list[str] = Field(default_factory=list)
    weixin_groups: list[str] = Field(default_factory=list)
    qq_approvers: list[str] = Field(default_factory=list)
    feishu_approvers: list[str] = Field(default_factory=list)
    weixin_approvers: list[str] = Field(default_factory=list)
    qq_admins: list[str] = Field(default_factory=list)
    feishu_admins: list[str] = Field(default_factory=list)
    weixin_admins: list[str] = Field(default_factory=list)

    @field_validator("*", mode="before")
    @classmethod
    def _clean_list_fields(cls, value: Any, info):
        if not str(info.field_name or "").endswith(("_users", "_groups", "_approvers", "_admins")):
            return value
        return _clean_string_list(value)


class ChannelAdvancedSelfUserIds(BaseModel):
    qq: list[str] = Field(default_factory=list)
    feishu: list[str] = Field(default_factory=list)
    weixin: list[str] = Field(default_factory=list)

    @field_validator("*", mode="before")
    @classmethod
    def _clean_ids(cls, value: Any):
        return _clean_string_list(value)


class ChannelAdvancedPairing(BaseModel):
    enabled: bool = True
    request_ttl_minutes: int = Field(default=60, ge=0)
    max_pending_per_platform: int = Field(default=3, ge=0)


class ChannelAdvancedRoute(BaseModel):
    connection_id: str = ""
    platform: str = ""
    chat_type: str = ""
    chat_id: str = ""
    user_id: str = ""
    thread_id: str = ""
    model: str = ""
    tool_approval_mode: str = ""
    workspace_root: str = ""

    @field_validator("*", mode="before")
    @classmethod
    def _clean_text(cls, value: Any):
        if value is None:
            return ""
        return str(value).strip()

    @model_validator(mode="after")
    def _normalize_choices(self) -> "ChannelAdvancedRoute":
        if self.platform not in {"", "qq", "feishu", "lark", "weixin"}:
            self.platform = ""
        if self.chat_type not in {"", "dm", "group", "guild", "direct", "thread"}:
            self.chat_type = ""
        if self.tool_approval_mode not in {"", "ask", "auto", "yolo", "inherit"}:
            self.tool_approval_mode = ""
        return self


class ChannelAdvancedSettings(BaseModel):
    allowlist: ChannelAdvancedAllowlist = Field(default_factory=ChannelAdvancedAllowlist)
    max_steps: int = Field(default=25, ge=0)
    debounce_ms: int = Field(default=1500, ge=0)
    queue_mode: ChannelQueueMode = "steer"
    queue_cap: int = Field(default=20, ge=0)
    queue_drop: ChannelQueueDrop = "summarize"
    ignore_self_messages: bool = True
    self_user_ids: ChannelAdvancedSelfUserIds = Field(default_factory=ChannelAdvancedSelfUserIds)
    pairing: ChannelAdvancedPairing = Field(default_factory=ChannelAdvancedPairing)
    routes: list[ChannelAdvancedRoute] = Field(default_factory=list)


def _clean_optional(value: str | None) -> str | None:
    if value is None:
        return None
    text = value.strip()
    return text or None


def _clean_string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        raw_items = value.replace(",", "\n").splitlines()
    elif isinstance(value, (list, tuple, set)):
        raw_items = list(value)
    else:
        raw_items = [value]
    seen: set[str] = set()
    result: list[str] = []
    for item in raw_items:
        text = str(item).strip()
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text)
    return result

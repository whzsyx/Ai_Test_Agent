from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator


ChannelProvider = Literal["qq", "feishu", "weixin"]
ChannelDomain = Literal["qq", "feishu", "lark", "weixin"]
ChannelStatus = Literal["unconfigured", "configured", "disabled"]


CHANNEL_DEFINITIONS: dict[str, dict[str, Any]] = {
    "qq": {
        "provider": "qq",
        "domain": "qq",
        "public_fields": ("app_id", "sandbox_mode"),
        "required_public": ("app_id",),
        "credential_fields": ("app_secret",),
    },
    "feishu": {
        "provider": "feishu",
        "domain": "feishu",
        "public_fields": ("app_id", "connection_mode"),
        "required_public": ("app_id",),
        "credential_fields": ("app_secret",),
    },
    "lark": {
        "provider": "feishu",
        "domain": "lark",
        "public_fields": ("app_id", "connection_mode"),
        "required_public": ("app_id",),
        "credential_fields": ("app_secret",),
    },
    "weixin": {
        "provider": "weixin",
        "domain": "weixin",
        "public_fields": ("account_id",),
        "required_public": ("account_id",),
        "credential_fields": ("token",),
    },
}


def channel_definition(domain: str) -> dict[str, Any]:
    try:
        return CHANNEL_DEFINITIONS[domain]
    except KeyError as exc:
        raise ValueError(f"Unsupported communication channel domain '{domain}'.") from exc


def validate_provider_domain(provider: str, domain: str) -> None:
    definition = channel_definition(domain)
    expected = str(definition["provider"])
    if provider != expected:
        raise ValueError(f"Domain '{domain}' must use provider '{expected}'.")


def clean_public_config(domain: str, value: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    definition = channel_definition(domain)
    allowed = set(definition["public_fields"])
    cleaned: dict[str, Any] = {}
    for key, item in value.items():
        if key not in allowed:
            continue
        if isinstance(item, str):
            cleaned[key] = item.strip()
        else:
            cleaned[key] = item
    return cleaned


def clean_credentials(domain: str, value: dict[str, Any] | None) -> dict[str, str]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ValueError("Credentials must be an object.")
    definition = channel_definition(domain)
    allowed = set(definition["credential_fields"])
    cleaned: dict[str, str] = {}
    for key, item in value.items():
        if key not in allowed:
            continue
        text = "" if item is None else str(item).strip()
        if text:
            cleaned[key] = text
    return cleaned


def compute_channel_status(
    *,
    domain: str,
    enabled: bool,
    public_config: dict[str, Any],
    credential_flags: dict[str, bool],
) -> ChannelStatus:
    definition = channel_definition(domain)
    for key in definition["required_public"]:
        value = public_config.get(key)
        if value is None or str(value).strip() == "":
            return "unconfigured"
    for key in definition["credential_fields"]:
        if not credential_flags.get(key):
            return "unconfigured"
    return "configured" if enabled else "disabled"


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


def _clean_optional(value: str | None) -> str | None:
    if value is None:
        return None
    text = value.strip()
    return text or None

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from src.domain.channel_strategies import CHANNEL_DEFINITIONS, channel_strategy_factory


ChannelProvider = Literal["qq", "feishu", "weixin"]
ChannelDomain = Literal["qq", "feishu", "lark", "weixin"]
ChannelStatus = Literal["unconfigured", "configured", "disabled"]
ChannelPairingStatus = Literal["pending", "confirmed", "expired"]


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


def _clean_optional(value: str | None) -> str | None:
    if value is None:
        return None
    text = value.strip()
    return text or None

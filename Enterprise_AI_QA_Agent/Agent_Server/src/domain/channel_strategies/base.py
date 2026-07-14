from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any


PAIRING_PUBLIC_FIELDS = frozenset({
    "auth_method",
    "pairing_session_id",
    "paired_device",
    "paired_at",
})


@dataclass(frozen=True)
class ChannelDefinition:
    provider: str
    domain: str
    public_fields: tuple[str, ...]
    required_public: tuple[str, ...]
    credential_fields: tuple[str, ...]
    supports_pairing: bool

    def as_dict(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "domain": self.domain,
            "public_fields": self.public_fields,
            "required_public": self.required_public,
            "credential_fields": self.credential_fields,
            "supports_pairing": self.supports_pairing,
        }


class ChannelStrategy:
    definition: ChannelDefinition

    @property
    def provider(self) -> str:
        return self.definition.provider

    @property
    def domain(self) -> str:
        return self.definition.domain

    @property
    def supports_pairing(self) -> bool:
        return self.definition.supports_pairing

    def validate_provider(self, provider: str) -> None:
        if provider != self.provider:
            raise ValueError(f"Domain '{self.domain}' must use provider '{self.provider}'.")

    def clean_public_config(self, value: dict[str, Any] | None) -> dict[str, Any]:
        if not isinstance(value, dict):
            return {}
        allowed = set(self.definition.public_fields) | PAIRING_PUBLIC_FIELDS
        cleaned: dict[str, Any] = {}
        for key, item in value.items():
            if key not in allowed:
                continue
            cleaned[key] = item.strip() if isinstance(item, str) else item
        return cleaned

    def clean_credentials(self, value: dict[str, Any] | None) -> dict[str, str]:
        if value is None:
            return {}
        if not isinstance(value, dict):
            raise ValueError("Credentials must be an object.")
        allowed = set(self.definition.credential_fields)
        cleaned: dict[str, str] = {}
        for key, item in value.items():
            if key not in allowed:
                continue
            text = "" if item is None else str(item).strip()
            if text:
                cleaned[key] = text
        return cleaned

    def compute_status(
        self,
        *,
        enabled: bool,
        public_config: dict[str, Any],
        credential_flags: dict[str, bool],
    ) -> str:
        if self.supports_pairing and self._is_qr_paired(public_config):
            return "configured" if enabled else "disabled"
        for key in self.definition.required_public:
            value = public_config.get(key)
            if value is None or str(value).strip() == "":
                return "unconfigured"
        for key in self.definition.credential_fields:
            if not credential_flags.get(key):
                return "unconfigured"
        return "configured" if enabled else "disabled"

    def ensure_pairing_supported(self) -> None:
        if not self.supports_pairing:
            raise ValueError(f"{self.domain.upper()} official bot does not support QR pairing.")

    def pairing_config_name(self) -> str:
        self.ensure_pairing_supported()
        return f"{self.domain.upper()} QR Binding"

    def build_pairing_public_config(
        self,
        *,
        existing_public_config: dict[str, Any] | None,
        session_id: str,
        device: str,
        paired_at: datetime,
    ) -> dict[str, Any]:
        self.ensure_pairing_supported()
        public_config = dict(existing_public_config or {})
        public_config.update({
            "auth_method": "qr_pairing",
            "pairing_session_id": session_id,
            "paired_device": device,
            "paired_at": paired_at.isoformat(),
        })
        return self.clean_public_config(public_config)

    def start_pairing(self, *, session_id: str) -> dict[str, Any]:
        self.ensure_pairing_supported()
        raise NotImplementedError(f"{self.domain} does not implement official QR pairing.")

    def poll_pairing(self, session: dict[str, Any]) -> dict[str, Any]:
        self.ensure_pairing_supported()
        raise NotImplementedError(f"{self.domain} does not implement official QR polling.")

    def build_connected_public_config(
        self,
        *,
        existing_public_config: dict[str, Any] | None,
        result: dict[str, Any],
        session_id: str,
        connected_at: datetime,
    ) -> dict[str, Any]:
        public_config = dict(existing_public_config or {})
        public_config.update({
            "auth_method": "official_qr",
            "pairing_session_id": session_id,
            "paired_at": connected_at.isoformat(),
        })
        if result.get("user_id"):
            public_config["paired_device"] = str(result["user_id"])
        return self.clean_public_config(public_config)

    def build_connected_credentials(self, result: dict[str, Any]) -> dict[str, str]:
        return self.clean_credentials(result.get("credentials"))

    @staticmethod
    def _is_qr_paired(public_config: dict[str, Any]) -> bool:
        return (
            public_config.get("auth_method") == "qr_pairing"
            and str(public_config.get("paired_at") or "").strip() != ""
        )

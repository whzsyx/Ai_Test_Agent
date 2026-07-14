from __future__ import annotations

from typing import Any

from .base import ChannelDefinition, ChannelStrategy


class QQChannelStrategy(ChannelStrategy):
    definition = ChannelDefinition(
        provider="qq",
        domain="qq",
        public_fields=("app_id", "sandbox_mode"),
        required_public=("app_id",),
        credential_fields=("app_secret",),
        supports_pairing=False,
    )

    def clean_public_config(self, value: dict[str, Any] | None) -> dict[str, Any]:
        cleaned = super().clean_public_config(value)
        return {
            "app_id": str(cleaned.get("app_id") or "").strip(),
            "sandbox_mode": cleaned.get("sandbox_mode") is True,
        }

    def ensure_pairing_supported(self) -> None:
        raise ValueError("QQ official bot does not support QR pairing. Configure App ID and App Secret instead.")


from __future__ import annotations

import httpx
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from .base import PAIRING_PUBLIC_FIELDS, ChannelDefinition, ChannelStrategy


class FeishuChannelStrategy(ChannelStrategy):
    connection_modes = frozenset({"event_callback", "webhook", "websocket", "reserved"})
    request_timeout = 15.0

    def __init__(self, *, domain: str) -> None:
        self.definition = ChannelDefinition(
            provider="feishu",
            domain=domain,
            public_fields=("app_id", "connection_mode"),
            required_public=("app_id",),
            credential_fields=("app_secret",),
            supports_pairing=True,
        )

    def clean_public_config(self, value: dict[str, Any] | None) -> dict[str, Any]:
        cleaned = super().clean_public_config(value)
        connection_mode = str(cleaned.get("connection_mode") or "event_callback").strip()
        if connection_mode not in self.connection_modes:
            connection_mode = "event_callback"
        result = {
            "app_id": str(cleaned.get("app_id") or "").strip(),
            "connection_mode": connection_mode,
        }
        for key in PAIRING_PUBLIC_FIELDS:
            if key in cleaned:
                result[key] = cleaned[key]
        return result

    def start_pairing(self, *, session_id: str) -> dict[str, Any]:
        data = self._post_registration(
            self._accounts_base("feishu"),
            {
                "action": "begin",
                "archetype": "PersonalAgent",
                "auth_method": "client_secret",
                "request_user_info": "open_id",
            },
        )
        device_code = _string_value(data.get("device_code"))
        verify_url = _string_value(data.get("verification_uri_complete"))
        user_code = _string_value(data.get("user_code"))
        if not device_code or not verify_url:
            raise ValueError("Feishu/Lark authorization response is missing device_code or verification URL.")
        return {
            "provider": self.provider,
            "domain": self.domain,
            "poll_domain": "feishu",
            "device_code": device_code,
            "user_code": user_code,
            "pairing_url": self._registration_qr_url(verify_url),
            "qr_payload": self._registration_qr_url(verify_url),
            "interval": _int_value(data.get("interval"), 5),
            "expire_in": _int_value(data.get("expire_in") or data.get("expires_in"), 300),
            "message": "请使用飞书/Lark 扫码授权。",
        }

    def poll_pairing(self, session: dict[str, Any]) -> dict[str, Any]:
        poll_domain = str(session.get("poll_domain") or self.domain or "feishu")
        if poll_domain not in {"feishu", "lark"}:
            poll_domain = "feishu"
        data, status_code = self._post_registration_result(
            self._accounts_base(poll_domain),
            {"action": "poll", "device_code": str(session.get("device_code") or "")},
        )
        error = _string_value(data.get("error"))
        if error:
            if error in {"authorization_pending", "slow_down"}:
                return {"done": False, "status": "pending", "message": "等待扫码授权。"}
            raise ValueError(_string_value(data.get("error_description")) or error)
        if status_code >= 400:
            raise ValueError(f"HTTP {status_code}")

        detected_domain = self._install_domain(session.get("domain"), data)
        if detected_domain == "lark" and poll_domain != "lark":
            return {
                "done": False,
                "status": "pending",
                "poll_domain": "lark",
                "message": "已识别为 Lark 授权，继续等待授权完成。",
            }

        app_id = _string_value(data.get("client_id"))
        app_secret = _string_value(data.get("client_secret"))
        if not app_id or not app_secret:
            return {"done": False, "status": "pending", "message": "等待授权完成。"}

        domain = self._install_domain(poll_domain or self.domain, data)
        secret_field = "app_secret"
        return {
            "done": True,
            "status": "confirmed",
            "provider": "feishu",
            "domain": domain,
            "app_id": app_id,
            "connection_mode": "websocket",
            "credentials": {secret_field: app_secret},
            "user_id": self._install_user_id(data),
            "message": ("Lark" if domain == "lark" else "飞书") + " 已授权。",
        }

    def build_connected_public_config(
        self,
        *,
        existing_public_config: dict[str, Any] | None,
        result: dict[str, Any],
        session_id: str,
        connected_at,
    ) -> dict[str, Any]:
        public_config = super().build_connected_public_config(
            existing_public_config=existing_public_config,
            result=result,
            session_id=session_id,
            connected_at=connected_at,
        )
        public_config.update({
            "app_id": str(result.get("app_id") or "").strip(),
            "connection_mode": str(result.get("connection_mode") or "websocket").strip(),
        })
        return self.clean_public_config(public_config)

    @staticmethod
    def _accounts_base(domain: str) -> str:
        return "https://accounts.larksuite.com" if domain == "lark" else "https://accounts.feishu.cn"

    @staticmethod
    def _registration_qr_url(raw_url: str) -> str:
        parsed = urlparse(raw_url)
        query = dict(parse_qsl(parsed.query, keep_blank_values=True))
        query.update({"from": "sdk", "tp": "sdk", "source": "go-sdk"})
        return urlunparse(parsed._replace(query=urlencode(query)))

    def _post_registration(self, base_url: str, body: dict[str, str]) -> dict[str, Any]:
        data, status_code = self._post_registration_result(base_url, body)
        if status_code >= 400:
            message = _string_value(data.get("error_description")) or _string_value(data.get("message"))
            raise ValueError(f"HTTP {status_code}: {message}")
        return data

    def _post_registration_result(self, base_url: str, body: dict[str, str]) -> tuple[dict[str, Any], int]:
        with httpx.Client(timeout=self.request_timeout) as client:
            response = client.post(
                f"{base_url.rstrip('/')}/oauth/v1/app/registration",
                data=body,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
        try:
            data = response.json()
        except ValueError as exc:
            raise ValueError(f"Invalid Feishu/Lark authorization response: {exc}") from exc
        if not isinstance(data, dict):
            raise ValueError("Invalid Feishu/Lark authorization response.")
        return data, response.status_code

    @staticmethod
    def _install_domain(fallback: Any, data: dict[str, Any]) -> str:
        user_info = data.get("user_info")
        if isinstance(user_info, dict):
            return "lark" if _string_value(user_info.get("tenant_brand")).lower() == "lark" else "feishu"
        return "lark" if str(fallback or "").strip().lower() == "lark" else "feishu"

    @staticmethod
    def _install_user_id(data: dict[str, Any]) -> str:
        user_info = data.get("user_info")
        if not isinstance(user_info, dict):
            return ""
        return (
            _string_value(user_info.get("open_id"))
            or _string_value(user_info.get("union_id"))
            or _string_value(user_info.get("user_id"))
        )


def _string_value(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _int_value(value: Any, fallback: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return fallback
    return parsed if parsed > 0 else fallback

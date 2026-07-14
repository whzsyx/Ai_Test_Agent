from __future__ import annotations

import httpx
from typing import Any
from urllib.parse import quote

from .base import PAIRING_PUBLIC_FIELDS, ChannelDefinition, ChannelStrategy

DEFAULT_WEIXIN_API = "https://ilinkai.weixin.qq.com"
GET_BOT_QR_PATH = "/ilink/bot/get_bot_qrcode"
GET_QR_STATUS_PATH = "/ilink/bot/get_qrcode_status"
ILINK_APP_ID = "bot"
ILINK_CLIENT_VERSION = (2 << 16) | (2 << 8)


class WeixinChannelStrategy(ChannelStrategy):
    request_timeout = 30.0
    definition = ChannelDefinition(
        provider="weixin",
        domain="weixin",
        public_fields=("account_id", "api_base"),
        required_public=("account_id",),
        credential_fields=("token",),
        supports_pairing=True,
    )

    def clean_public_config(self, value: dict[str, Any] | None) -> dict[str, Any]:
        cleaned = super().clean_public_config(value)
        result = {"account_id": str(cleaned.get("account_id") or "").strip()}
        for key in PAIRING_PUBLIC_FIELDS:
            if key in cleaned:
                result[key] = cleaned[key]
        return result

    def start_pairing(self, *, session_id: str) -> dict[str, Any]:
        qr_resp = self._ilink_get(DEFAULT_WEIXIN_API, f"{GET_BOT_QR_PATH}?bot_type=3")
        qrcode = _string_value(qr_resp.get("qrcode"))
        qrcode_image = _string_value(qr_resp.get("qrcode_img_content"))
        if not qrcode:
            raise ValueError("Weixin QR response is missing qrcode.")
        return {
            "provider": self.provider,
            "domain": self.domain,
            "base_url": DEFAULT_WEIXIN_API,
            "qrcode": qrcode,
            "pairing_url": qrcode_image or qrcode,
            "qr_payload": qrcode_image or qrcode,
            "interval": 3,
            "expire_in": 120,
            "message": "请使用微信扫码完成连接。",
        }

    def poll_pairing(self, session: dict[str, Any]) -> dict[str, Any]:
        base_url = str(session.get("base_url") or DEFAULT_WEIXIN_API)
        qrcode = str(session.get("qrcode") or "")
        if not qrcode:
            raise ValueError("Weixin login session is missing qrcode.")
        status_resp = self._ilink_get(base_url, f"{GET_QR_STATUS_PATH}?qrcode={quote(qrcode)}")
        status = _string_value(status_resp.get("status"))
        if status in {"wait", "", "<nil>"}:
            return {"done": False, "status": "pending", "message": "等待扫码。"}
        if status == "scaned":
            return {"done": False, "status": "pending", "message": "已扫码，请在微信里确认。"}
        if status == "scaned_but_redirect":
            redirect_host = _string_value(status_resp.get("redirect_host"))
            return {
                "done": False,
                "status": "pending",
                "base_url": f"https://{redirect_host}" if redirect_host else base_url,
                "message": "已扫码，正在切换微信授权节点。",
            }
        if status == "expired":
            raise ValueError("Weixin QR code expired; generate a new one.")
        if status != "confirmed":
            return {"done": False, "status": "pending", "message": f"微信扫码状态：{status}"}

        account_id = _string_value(status_resp.get("ilink_bot_id"))
        token = _string_value(status_resp.get("bot_token"))
        user_id = _string_value(status_resp.get("ilink_user_id"))
        response_base_url = _string_value(status_resp.get("baseurl")) or base_url or DEFAULT_WEIXIN_API
        if not account_id or not token:
            raise ValueError("Weixin QR confirmed but credential payload is incomplete.")
        return {
            "done": True,
            "status": "confirmed",
            "provider": self.provider,
            "domain": self.domain,
            "account_id": account_id,
            "base_url": response_base_url,
            "credentials": {"token": token},
            "user_id": user_id,
            "message": "微信已授权。",
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
            "account_id": str(result.get("account_id") or "").strip(),
            "api_base": str(result.get("base_url") or DEFAULT_WEIXIN_API).strip(),
        })
        return self.clean_public_config(public_config)

    def _ilink_get(self, base_url: str, endpoint: str) -> dict[str, Any]:
        with httpx.Client(timeout=self.request_timeout) as client:
            response = client.get(
                f"{base_url.rstrip('/')}/{endpoint.lstrip('/')}",
                headers={
                    "iLink-App-Id": ILINK_APP_ID,
                    "iLink-App-ClientVersion": str(ILINK_CLIENT_VERSION),
                },
            )
        if response.status_code >= 400:
            preview = response.text[:200]
            raise ValueError(f"HTTP {response.status_code}: {preview}")
        try:
            data = response.json()
        except ValueError as exc:
            raise ValueError(f"Invalid Weixin QR response: {exc}") from exc
        if not isinstance(data, dict):
            raise ValueError("Invalid Weixin QR response.")
        return data


def _string_value(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    return "" if text == "<nil>" else text

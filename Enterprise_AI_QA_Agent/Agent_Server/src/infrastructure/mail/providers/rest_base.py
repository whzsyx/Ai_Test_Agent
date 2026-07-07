"""Base class for REST API-backed Agent Mailbox providers."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import httpx

from src.application.mail.contracts import (
    MailCapability,
    MailMessage,
    MailProviderAdapter,
    MailSendRequest,
    MailSendResult,
)

if TYPE_CHECKING:
    from src.schemas.email_config import EmailConfigRecord


class RestMailAdapterBase(MailProviderAdapter):
    """Shared HTTP transport for REST-based Agent Mailbox providers."""

    default_base_url: str = ""
    default_timeout: int = 20

    def _base_url(self, record: "EmailConfigRecord") -> str:
        return (
            (record.extra_config or {}).get("base_url")
            or self.default_base_url
        ).rstrip("/")

    def _headers(self, record: "EmailConfigRecord") -> dict[str, str]:
        headers: dict[str, str] = {"Content-Type": "application/json"}
        if record.api_key:
            headers["Authorization"] = "Bearer " + record.api_key
        return headers

    def _request(
        self,
        method: str,
        record: "EmailConfigRecord",
        path: str,
        *,
        json_body: dict | None = None,
        params: dict | None = None,
        timeout: int | None = None,
    ) -> dict[str, Any]:
        url = self._base_url(record) + path
        resp = httpx.request(
            method,
            url,
            headers=self._headers(record),
            json=json_body,
            params=params,
            timeout=timeout or self.default_timeout,
        )
        resp.raise_for_status()
        return resp.json()

    def _to_mail_message(self, raw: dict[str, Any]) -> MailMessage:
        return MailMessage(
            message_id=raw.get("message_id") or raw.get("id") or "",
            thread_id=raw.get("thread_id"),
            subject=raw.get("subject") or "",
            from_email=raw.get("from") or raw.get("from_email") or "",
            to=raw.get("to") or [],
            snippet=raw.get("snippet") or raw.get("preview") or "",
            body_text=raw.get("body_text") or raw.get("body") or "",
            body_html=raw.get("body_html") or "",
            received_at=raw.get("received_at") or raw.get("date") or None,
            attachments=raw.get("attachments") or [],
            raw=raw,
        )

    def _build_send_result(self, record: "EmailConfigRecord", data: dict) -> MailSendResult:
        return MailSendResult(
            sent=data.get("sent", True),
            provider=self.provider_key,
            from_email=data.get("from", record.sender_email or ""),
            recipient_count=data.get("recipient_count", 0),
            message_id=data.get("message_id"),
        )

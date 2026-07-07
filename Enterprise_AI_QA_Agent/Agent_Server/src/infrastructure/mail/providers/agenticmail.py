"""AgenticMail Agent Mailbox adapter."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from src.application.mail.contracts import (
    MailCapability,
    MailMessage,
    MailSendRequest,
    MailSendResult,
)
from src.infrastructure.mail.providers.rest_base import RestMailAdapterBase

if TYPE_CHECKING:
    from src.schemas.email_config import EmailConfigRecord


class AgenticMailAdapter(RestMailAdapterBase):
    """AgenticMail provider - REST API adapter."""

    provider_key = "agenticmail"
    default_base_url = "http://localhost:8025/v1"

    def capabilities(self) -> set[MailCapability]:
        return {
            MailCapability.SEND,
            MailCapability.LIST,
            MailCapability.READ,
            MailCapability.SEARCH,
            MailCapability.REPLY,
            MailCapability.FORWARD,
            MailCapability.ATTACHMENTS,
            MailCapability.PROVISION_INBOX,
            MailCapability.WEBHOOK,
        }

    def send(self, record: "EmailConfigRecord", request: MailSendRequest) -> MailSendResult:
        data = self._request("POST", record, "/messages/send", json_body={
            "to": request.recipients,
            "subject": request.subject,
            "body": request.content_html or request.content,
            "cc": request.cc,
            "bcc": request.bcc,
        })
        return self._build_send_result(record, data)

    def list_messages(
        self, record: "EmailConfigRecord", options: dict[str, Any] | None = None
    ) -> list[MailMessage]:
        opts = options or {}
        data = self._request("GET", record, "/messages", params=opts)
        return [self._to_mail_message(m) for m in (data.get("messages") or [])]

    def read_message(self, record: "EmailConfigRecord", message_id: str) -> MailMessage:
        data = self._request("GET", record, f"/messages/{message_id}")
        return self._to_mail_message(data.get("message") or data)

    def search_messages(
        self, record: "EmailConfigRecord", query: str, options: dict[str, Any] | None = None
    ) -> list[MailMessage]:
        opts = dict(options or {})
        opts["q"] = query
        data = self._request("GET", record, "/messages/search", params=opts)
        return [self._to_mail_message(m) for m in (data.get("messages") or [])]

    def reply(
        self, record: "EmailConfigRecord", message_id: str, request: MailSendRequest
    ) -> MailSendResult:
        data = self._request("POST", record, f"/messages/{message_id}/reply", json_body={
            "body": request.content_html or request.content,
            "cc": request.cc,
        })
        return self._build_send_result(record, data)

    def forward(
        self, record: "EmailConfigRecord", message_id: str, request: MailSendRequest
    ) -> MailSendResult:
        data = self._request("POST", record, f"/messages/{message_id}/forward", json_body={
            "to": request.recipients,
            "body": request.content_html or request.content,
        })
        return self._build_send_result(record, data)

    def download_attachment(
        self, record: "EmailConfigRecord", message_id: str, attachment_id: str
    ) -> dict[str, Any]:
        data = self._request("GET", record, f"/messages/{message_id}/attachments/{attachment_id}")
        return {"ok": True, **data}

    def provision_inbox(
        self, record: "EmailConfigRecord", options: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        data = self._request("POST", record, "/inboxes", json_body=options or {})
        return {"ok": True, **data}

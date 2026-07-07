"""Contracts for the public mail capability layer.

Defines the capability vocabulary, the provider adapter protocol, and the
request/response value objects shared across all mail providers.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from src.schemas.email_config import EmailConfigRecord


class MailCapability(str, Enum):
    """Capabilities a mail provider may declare support for."""

    SEND = "send"
    LIST = "list"
    READ = "read"
    SEARCH = "search"
    REPLY = "reply"
    FORWARD = "forward"
    ATTACHMENTS = "attachments"
    PROVISION_INBOX = "provision_inbox"
    WEBHOOK = "webhook"


class CapabilityNotSupported(RuntimeError):
    """Raised when a provider is asked to perform a capability it lacks.

    The mail service translates this into the standard
    ``{"ok": False, "error": "capability_not_supported"}`` envelope.
    """

    def __init__(self, provider_key: str, capability: MailCapability) -> None:
        self.provider_key = provider_key
        self.capability = capability
        super().__init__(
            f"Provider '{provider_key}' does not support capability '{capability.value}'."
        )


@dataclass(slots=True)
class MailSendRequest:
    """A provider-agnostic outbound email request."""

    recipients: list[str]
    subject: str
    content: str = ""
    content_html: str = ""
    sender: str = ""
    reply_to: str | None = None
    cc: list[str] = field(default_factory=list)
    bcc: list[str] = field(default_factory=list)
    attachments: list[dict[str, Any]] = field(default_factory=list)


@dataclass(slots=True)
class MailSendResult:
    """The outcome of a send operation, returned to tool callers."""

    sent: bool
    provider: str
    from_email: str
    recipient_count: int
    message_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "sent": self.sent,
            "provider": self.provider,
            "from_email": self.from_email,
            "recipient_count": self.recipient_count,
        }
        if self.message_id is not None:
            payload["message_id"] = self.message_id
        return payload


@dataclass(slots=True)
class MailMessage:
    """A normalized inbound/stored message returned by mailbox providers."""

    message_id: str
    thread_id: str | None
    subject: str
    from_email: str
    to: list[str]
    snippet: str
    body_text: str = ""
    body_html: str = ""
    received_at: str | None = None
    attachments: list[dict[str, Any]] = field(default_factory=list)
    raw: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "message_id": self.message_id,
            "thread_id": self.thread_id,
            "subject": self.subject,
            "from_email": self.from_email,
            "to": list(self.to),
            "snippet": self.snippet,
            "body_text": self.body_text,
            "body_html": self.body_html,
            "received_at": self.received_at,
            "attachments": list(self.attachments),
        }


class MailProviderAdapter(ABC):
    """Base class for every mail provider.

    Subclasses set ``provider_key`` and declare their supported capabilities
    via :meth:`capabilities`. Send-only providers (SMTP, Aliyun) implement
    :meth:`send`; Agent Mailbox providers additionally implement the inbound
    methods. Every non-send method defaults to raising
    :class:`CapabilityNotSupported`, so a provider only overrides what it can do.
    """

    provider_key: str = ""

    def capabilities(self) -> set[MailCapability]:
        """Return the set of capabilities this provider supports."""
        return {MailCapability.SEND}

    def supports(self, capability: MailCapability) -> bool:
        return capability in self.capabilities()

    def _require(self, capability: MailCapability) -> None:
        if not self.supports(capability):
            raise CapabilityNotSupported(self.provider_key, capability)

    @abstractmethod
    def send(self, record: "EmailConfigRecord", request: MailSendRequest) -> MailSendResult:
        """Send an outbound email using the given config record."""
        raise NotImplementedError

    # --- Agent Mailbox capabilities (opt-in) --------------------------------

    def provision_inbox(
        self, record: "EmailConfigRecord", options: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        self._require(MailCapability.PROVISION_INBOX)
        raise NotImplementedError

    def list_messages(
        self, record: "EmailConfigRecord", options: dict[str, Any] | None = None
    ) -> list[MailMessage]:
        self._require(MailCapability.LIST)
        raise NotImplementedError

    def read_message(self, record: "EmailConfigRecord", message_id: str) -> MailMessage:
        self._require(MailCapability.READ)
        raise NotImplementedError

    def search_messages(
        self, record: "EmailConfigRecord", query: str, options: dict[str, Any] | None = None
    ) -> list[MailMessage]:
        self._require(MailCapability.SEARCH)
        raise NotImplementedError

    def reply(
        self, record: "EmailConfigRecord", message_id: str, request: MailSendRequest
    ) -> MailSendResult:
        self._require(MailCapability.REPLY)
        raise NotImplementedError

    def forward(
        self,
        record: "EmailConfigRecord",
        message_id: str,
        request: MailSendRequest,
    ) -> MailSendResult:
        self._require(MailCapability.FORWARD)
        raise NotImplementedError

    def download_attachment(
        self, record: "EmailConfigRecord", message_id: str, attachment_id: str
    ) -> dict[str, Any]:
        self._require(MailCapability.ATTACHMENTS)
        raise NotImplementedError

    def status(self, record: "EmailConfigRecord") -> dict[str, Any]:
        """Return provider connectivity/setup status. Default: capabilities only."""
        return {
            "ok": True,
            "provider": self.provider_key,
            "capabilities": sorted(cap.value for cap in self.capabilities()),
        }

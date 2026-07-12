"""Provider-agnostic mail service.

Wraps the email config store and the provider registry so callers never need
to know which provider backs the active mailbox. This is the single seam the
tool runtime delegates to for both transactional send and Agent Mailbox
capabilities.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from src.application.mail.contracts import (
    CapabilityNotSupported,
    MailCapability,
    MailSendRequest,
    MailSendResult,
)
from src.application.mail.provider_registry import (
    MailProviderRegistry,
    build_default_mail_provider_registry,
)

if TYPE_CHECKING:
    from src.infrastructure.email_config_store import MySQLEmailConfigStore
    from src.schemas.email_config import EmailConfigRecord


CAPABILITY_NOT_SUPPORTED = {"ok": False, "error": "capability_not_supported"}


class MailService:
    """Front door for all mail operations across providers."""

    def __init__(
        self,
        email_config_store: "MySQLEmailConfigStore | None",
        registry: MailProviderRegistry | None = None,
    ) -> None:
        self._email_config_store = email_config_store
        self._registry = registry or build_default_mail_provider_registry()

    # --- config resolution --------------------------------------------------

    def _resolve_active_record(self) -> "EmailConfigRecord":
        if self._email_config_store is None:
            raise RuntimeError("Email config store is not available.")
        records = self._email_config_store.list_all()
        enabled = [item for item in records if item.enabled]
        if not enabled:
            raise RuntimeError("No enabled email configuration is available.")
        return next((item for item in enabled if item.is_default), enabled[0])

    def _resolve_record_by_id(self, config_id: int | None) -> "EmailConfigRecord":
        if config_id is None:
            return self._resolve_active_record()
        if self._email_config_store is None:
            raise RuntimeError("Email config store is not available.")
        return self._email_config_store.get_by_id(config_id)

    # --- transactional send -------------------------------------------------

    def send(
        self,
        recipients: list[str],
        subject: str,
        content: str,
        content_html: str,
        *,
        config_id: int | None = None,
    ) -> dict[str, Any]:
        """Send an email through the active (or specified) provider.

        Preserves the legacy result-dict shape returned by the old
        ``_send_email_message`` so existing tool callers see no change.
        """
        record = self._resolve_record_by_id(config_id)
        adapter = self._registry.resolve(record.provider)
        request = MailSendRequest(
            recipients=recipients,
            subject=subject,
            content=content,
            content_html=content_html,
        )
        result = adapter.send(record, request)
        return result.to_dict()

    def confirm(
        self,
        operation: str,
        confirmation_token: str,
        *,
        config_id: int | None = None,
    ) -> dict[str, Any]:
        """Commit a prepared Agent Mail write operation after user confirmation."""
        record = self._resolve_record_by_id(config_id)
        adapter = self._registry.resolve(record.provider)
        operation_key = str(operation or "").strip().lower()
        method_name = {"send": "send_confirm", "reply": "reply_confirm", "forward": "forward_confirm"}.get(operation_key)
        if not method_name or not hasattr(adapter, method_name):
            raise RuntimeError(
                f"Provider '{record.provider}' does not support confirmation for operation '{operation}'."
            )
        result = getattr(adapter, method_name)(record, confirmation_token)
        return result.to_dict()

    # --- Agent Mailbox capabilities ----------------------------------------

    def status(self, config_id: int | None = None) -> dict[str, Any]:
        record = self._resolve_record_by_id(config_id)
        adapter = self._registry.resolve(record.provider)
        return adapter.status(record)

    def provision_inbox(
        self, config_id: int | None = None, options: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        return self._capability_call(
            MailCapability.PROVISION_INBOX,
            config_id,
            lambda adapter, record: adapter.provision_inbox(record, options),
        )

    def list_messages(
        self, config_id: int | None = None, options: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        return self._capability_call(
            MailCapability.LIST,
            config_id,
            lambda adapter, record: {
                "ok": True,
                "messages": [m.to_dict() for m in adapter.list_messages(record, options)],
            },
        )

    def read_message(self, message_id: str, config_id: int | None = None) -> dict[str, Any]:
        return self._capability_call(
            MailCapability.READ,
            config_id,
            lambda adapter, record: {
                "ok": True,
                "message": adapter.read_message(record, message_id).to_dict(),
            },
        )

    def search_messages(
        self, query: str, config_id: int | None = None, options: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        return self._capability_call(
            MailCapability.SEARCH,
            config_id,
            lambda adapter, record: {
                "ok": True,
                "messages": [
                    m.to_dict() for m in adapter.search_messages(record, query, options)
                ],
            },
        )

    def reply(
        self, message_id: str, request: MailSendRequest, config_id: int | None = None
    ) -> dict[str, Any]:
        return self._capability_call(
            MailCapability.REPLY,
            config_id,
            lambda adapter, record: adapter.reply(record, message_id, request).to_dict(),
        )

    def forward(
        self, message_id: str, request: MailSendRequest, config_id: int | None = None
    ) -> dict[str, Any]:
        return self._capability_call(
            MailCapability.FORWARD,
            config_id,
            lambda adapter, record: adapter.forward(record, message_id, request).to_dict(),
        )

    def download_attachment(
        self, message_id: str, attachment_id: str, config_id: int | None = None
    ) -> dict[str, Any]:
        return self._capability_call(
            MailCapability.ATTACHMENTS,
            config_id,
            lambda adapter, record: adapter.download_attachment(
                record, message_id, attachment_id
            ),
        )

    # --- internals ----------------------------------------------------------

    def _capability_call(self, capability, config_id, fn) -> dict[str, Any]:
        record = self._resolve_record_by_id(config_id)
        adapter = self._registry.resolve(record.provider)
        if not adapter.supports(capability):
            return dict(CAPABILITY_NOT_SUPPORTED)
        try:
            return fn(adapter, record)
        except CapabilityNotSupported:
            return dict(CAPABILITY_NOT_SUPPORTED)

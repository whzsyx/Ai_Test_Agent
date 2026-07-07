"""SMTP transactional-send adapter.

Handles every provider that delivers via SMTP (the historical ``else`` branch
of the old inline send logic). Ported verbatim from
``tool_runtime_service._send_via_smtp_provider`` to preserve behavior.
"""

from __future__ import annotations

import smtplib
from email.message import EmailMessage
from typing import TYPE_CHECKING

from src.application.mail.contracts import (
    MailCapability,
    MailProviderAdapter,
    MailSendRequest,
    MailSendResult,
)

if TYPE_CHECKING:
    from src.schemas.email_config import EmailConfigRecord


class SmtpMailAdapter(MailProviderAdapter):
    """Sends mail over SMTP / SMTP_SSL. Send-only."""

    provider_key = "smtp"

    def capabilities(self) -> set[MailCapability]:
        return {MailCapability.SEND}

    def send(self, record: "EmailConfigRecord", request: MailSendRequest) -> MailSendResult:
        if not record.smtp_host or not record.smtp_port:
            raise RuntimeError("Selected email configuration is missing SMTP host or port.")
        if not record.api_key:
            raise RuntimeError("Selected email configuration is missing SMTP password.")

        message = EmailMessage()
        message["Subject"] = request.subject
        message["From"] = record.sender_email or record.smtp_username or ""
        message["To"] = ", ".join(request.recipients)
        if request.content:
            message.set_content(request.content)
        else:
            message.set_content(" ")
        if request.content_html:
            message.add_alternative(request.content_html, subtype="html")

        username = record.smtp_username or record.sender_email
        use_ssl = int(record.smtp_port) == 465
        if use_ssl:
            with smtplib.SMTP_SSL(record.smtp_host, int(record.smtp_port), timeout=15) as client:
                client.login(username, record.api_key or "")
                client.send_message(message)
        else:
            with smtplib.SMTP(record.smtp_host, int(record.smtp_port), timeout=15) as client:
                client.ehlo()
                try:
                    client.starttls()
                    client.ehlo()
                except smtplib.SMTPException:
                    pass
                client.login(username, record.api_key or "")
                client.send_message(message)

        return MailSendResult(
            sent=True,
            provider=record.provider,
            from_email=record.sender_email or record.smtp_username or "",
            recipient_count=len(request.recipients),
        )

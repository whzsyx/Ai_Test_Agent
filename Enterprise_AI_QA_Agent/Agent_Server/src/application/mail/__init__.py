"""Public mail capability layer.

Provides a provider-agnostic MailService that wraps transactional send
providers (SMTP, Aliyun DirectMail) and Agent Mailbox providers behind a
single capability-based interface.
"""

from __future__ import annotations

from src.application.mail.contracts import (
    CapabilityNotSupported,
    MailCapability,
    MailMessage,
    MailProviderAdapter,
    MailSendRequest,
    MailSendResult,
)
from src.application.mail.mail_service import MailService
from src.application.mail.provider_registry import (
    MailProviderRegistry,
    build_default_mail_provider_registry,
)

__all__ = [
    "CapabilityNotSupported",
    "MailCapability",
    "MailMessage",
    "MailProviderAdapter",
    "MailSendRequest",
    "MailSendResult",
    "MailService",
    "MailProviderRegistry",
    "build_default_mail_provider_registry",
]

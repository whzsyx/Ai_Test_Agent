"""Public mail capability layer.

Provides the native Agent Mail capability layer backed exclusively by the
Tencent agently-cli adapter.
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

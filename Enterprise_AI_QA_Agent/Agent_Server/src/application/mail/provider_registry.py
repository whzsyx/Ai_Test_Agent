"""Mail provider registry and default factory.

Mirrors the ``model_providers`` registry pattern: adapters are keyed by their
``provider_key`` class attribute and resolved via :meth:`resolve`.

Resolution semantics preserve the historical inline behavior
(``provider == "aliyun" -> Aliyun, else -> SMTP``): any provider key that is
not explicitly registered falls back to the SMTP adapter, so all existing
transactional-send providers keep working unchanged.
"""

from __future__ import annotations

from src.application.mail.contracts import MailProviderAdapter
from src.infrastructure.mail.providers import (
    AgentMailAdapter,
    AgenticMailAdapter,
    AliyunMailAdapter,
    AwsAgentMailboxAdapter,
    DeadSimpleEmailAdapter,
    OpenMailAdapter,
    RobotomailAdapter,
    SmtpMailAdapter,
    TencentAgentlyMailAdapter,
)


class MailProviderRegistry:
    """Resolves an ``EmailConfigRecord.provider`` string to an adapter."""

    def __init__(
        self,
        providers: list[MailProviderAdapter],
        *,
        send_fallback: MailProviderAdapter | None = None,
    ) -> None:
        self._providers: dict[str, MailProviderAdapter] = {
            p.provider_key: p for p in providers
        }
        # Fallback preserves the old ``else -> SMTP`` branch for the many
        # transactional providers (sendgrid, mailgun, ...) that deliver via SMTP.
        self._send_fallback = send_fallback

    def resolve(self, provider_key: str) -> MailProviderAdapter:
        normalized = str(provider_key or "").strip().lower()
        provider = self._providers.get(normalized)
        if provider is not None:
            return provider
        if self._send_fallback is not None:
            return self._send_fallback
        raise ValueError(f"Unknown mail provider '{provider_key}'.")

    def get(self, provider_key: str) -> MailProviderAdapter | None:
        return self._providers.get(str(provider_key or "").strip().lower())

    def registered_keys(self) -> list[str]:
        return sorted(self._providers.keys())


def build_default_mail_provider_registry() -> MailProviderRegistry:
    """Build the registry with the built-in adapters.

    Explicitly-registered providers get their own adapter; every other
    provider key falls back to SMTP (matching the legacy behavior).
    """

    smtp = SmtpMailAdapter()
    providers: list[MailProviderAdapter] = [
        AliyunMailAdapter(),
        TencentAgentlyMailAdapter(),
        AgentMailAdapter(),
        RobotomailAdapter(),
        OpenMailAdapter(),
        DeadSimpleEmailAdapter(),
        AgenticMailAdapter(),
        AwsAgentMailboxAdapter(),
        smtp,
    ]
    return MailProviderRegistry(providers, send_fallback=smtp)

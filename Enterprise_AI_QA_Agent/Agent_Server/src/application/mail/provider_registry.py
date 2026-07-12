"""Mail provider registry and default factory.

Mirrors the ``model_providers`` registry pattern: adapters are keyed by their
``provider_key`` class attribute and resolved via :meth:`resolve`.

Every supported Agent Mail vendor has a concrete adapter under
``infrastructure/mail/providers``. Provider differences remain behind the
public mail capability API.
"""

from __future__ import annotations

from src.application.mail.contracts import MailProviderAdapter
from src.infrastructure.mail.providers import (
    AgenticMailAdapter,
    AgentMailAdapter,
    AwsAgentMailboxAdapter,
    DeadSimpleEmailAdapter,
    OpenMailAdapter,
    RobotomailAdapter,
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
    """Build the global multi-provider Agent Mail registry."""

    return MailProviderRegistry([
        TencentAgentlyMailAdapter(), AgentMailAdapter(), RobotomailAdapter(),
        OpenMailAdapter(), DeadSimpleEmailAdapter(), AgenticMailAdapter(),
        AwsAgentMailboxAdapter(),
    ])

"""Schemas for OAuth 2.0 Authorization Code flow endpoints."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class OAuthStartRequest(BaseModel):
    """Payload for POST /api/v1/oauth/start — initiate browser-based OAuth."""

    provider: str
    """Provider preset key (azure_ad / google / github / codebuddy / trae / codex / generic)."""

    redirect_uri: str
    """Callback URL registered with the OAuth provider, e.g. http://localhost:8000/api/v1/oauth/callback"""

    model_name: str | None = None
    """Optional model name tag for audit / display purposes."""


class OAuthStartResponse(BaseModel):
    """Returned by POST /api/v1/oauth/start."""

    state: str
    """Opaque CSRF-safe state token — pass to /status/{state} to poll."""

    authorization_url: str
    """Open this URL in the user's browser to begin the OAuth flow."""

    redirect_uri: str
    """Echo of the redirect_uri so the frontend can display / verify it."""


class OAuthStatusResponse(BaseModel):
    """Returned by GET /api/v1/oauth/status/{state}."""

    state: str
    status: Literal["pending", "completed", "failed"]
    refresh_token: str | None = None
    """Refresh token from the provider (only present on success)."""

    access_token_preview: str | None = None
    """First 20 chars of the access token — for display only."""

    error: str | None = None


class OAuthProviderListResponse(BaseModel):
    """Returned by GET /api/v1/oauth/providers."""

    providers: list[dict]


class OAuthModelItem(BaseModel):
    id: str
    raw_id: str
    name: str


class OAuthModelsResponse(BaseModel):
    """Returned by GET /api/v1/oauth/models."""

    provider: str
    models: list[OAuthModelItem]

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Literal


FlowStatus = Literal["pending", "completed", "failed"]


@dataclass
class PendingAuthFlow:
    provider: str
    client_id: str
    client_secret: str
    token_url: str
    redirect_uri: str
    code_verifier: str
    scope: str
    created_at: float = field(default_factory=time.monotonic)


@dataclass
class CompletedAuthFlow:
    status: FlowStatus
    provider: str = ""
    access_token: str = ""
    refresh_token: str = ""
    error: str = ""
    completed_at: float = field(default_factory=time.monotonic)


@dataclass(frozen=True)
class AuthStartResult:
    state: str
    authorization_url: str
    redirect_uri: str

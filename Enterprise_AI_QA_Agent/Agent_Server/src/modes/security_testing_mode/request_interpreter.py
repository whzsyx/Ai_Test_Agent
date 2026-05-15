"""Request interpretation for Security Testing Mode."""
from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlparse
from uuid import uuid4

from src.modes.security_testing_mode.campaign_state import (
    SecurityTestingRequestState,
    TargetCandidate,
)
from src.modes.security_testing_mode.contracts import REQUEST_CONTEXT_KEY


class SecurityRequestInterpreter:
    """Build structured request and target objects from user/context input."""

    def interpret(self, arguments: dict[str, Any], context: Any) -> SecurityTestingRequestState:
        bundle = getattr(context, "context_bundle", None) or {}
        mode_request = bundle.get(REQUEST_CONTEXT_KEY) or {}
        if not isinstance(mode_request, dict):
            mode_request = {}

        user_message = str(getattr(context, "user_message", "") or "")
        target = str(arguments.get("target") or mode_request.get("target") or "").strip()
        target_url = str(arguments.get("target_url") or mode_request.get("target_url") or "").strip()
        target_host = str(arguments.get("target_host") or mode_request.get("target_host") or "").strip()
        target_network = str(arguments.get("target_network") or mode_request.get("target_network") or "").strip()
        if target and not any([target_url, target_host, target_network]):
            inferred = self.build_target(target)
            if inferred.target_type == "url":
                target_url = target
            elif inferred.target_type == "network":
                target_network = target
            else:
                target_host = target

        return SecurityTestingRequestState(
            objective=str(arguments.get("objective") or mode_request.get("objective") or user_message).strip(),
            target_url=target_url,
            target_host=target_host,
            target_network=target_network,
            target_type=str(arguments.get("target_type") or mode_request.get("target_type") or "").strip(),
            scope_preference=str(arguments.get("scope_preference") or mode_request.get("scope_preference") or "limited").strip(),
            auth_hint=str(arguments.get("auth_hint") or mode_request.get("auth_hint") or "").strip(),
            credentials=dict(arguments.get("credentials") or mode_request.get("credentials") or {}),
            focus_areas=self.to_string_list(arguments.get("focus_areas") or mode_request.get("focus_areas")),
            excluded_areas=self.to_string_list(arguments.get("excluded_areas") or mode_request.get("excluded_areas")),
            risk_tolerance=str(arguments.get("risk_tolerance") or mode_request.get("risk_tolerance") or "medium").strip(),
            report_recipients=self.to_string_list(arguments.get("report_recipients") or mode_request.get("report_recipients")),
            raw_message=user_message,
        )

    def resolve_primary_target(self, request: SecurityTestingRequestState) -> TargetCandidate | None:
        target_value = (
            request.target_url
            or request.target_host
            or request.target_network
            or self.extract_target_from_text(request.raw_message)
        ).strip()
        if not target_value:
            return None
        return self.build_target(target_value)

    def build_target(self, value: str) -> TargetCandidate:
        value = value.strip()
        if re.match(r"^https?://", value, flags=re.IGNORECASE):
            parsed = urlparse(value)
            return TargetCandidate(
                target_id=f"target_{uuid4().hex[:8]}",
                target_type="url",
                value=value.rstrip("/"),
                label=parsed.hostname or value,
                resolved_domain=parsed.hostname or "",
                port=parsed.port,
                protocol=parsed.scheme,
            )
        if "/" in value and re.match(r"^[0-9a-fA-F:.]+/\d{1,3}$", value):
            return TargetCandidate(
                target_id=f"target_{uuid4().hex[:8]}",
                target_type="network",
                value=value,
                label=value,
            )
        return TargetCandidate(
            target_id=f"target_{uuid4().hex[:8]}",
            target_type="host",
            value=value,
            label=value,
            resolved_domain=value if not re.match(r"^\d+\.\d+\.\d+\.\d+$", value) else "",
        )

    def extract_target_from_text(self, text: str) -> str:
        for pattern in (
            r"https?://[^\s,;]+",
            r"\b(?:\d{1,3}\.){3}\d{1,3}(?:/\d{1,2})?\b",
            r"\b[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\b",
        ):
            match = re.search(pattern, text or "")
            if match:
                return match.group(0).rstrip(".,;)")
        return ""

    def to_string_list(self, value: Any) -> list[str]:
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
        if isinstance(value, str) and value.strip():
            return [item.strip() for item in value.split(",") if item.strip()]
        return []


__all__ = ["SecurityRequestInterpreter"]

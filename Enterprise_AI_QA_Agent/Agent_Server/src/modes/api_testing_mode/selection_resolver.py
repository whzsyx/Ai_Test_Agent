"""Resolve user replies that answer pending selections.

Follow-up replies like ``1`` / ``核心接口`` / ``POST /orders`` are structured
selections, not fresh free-form requests. This module converts them into a
normalized choice tied to the current ``PendingSelection``.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from src.modes.api_testing_mode.contracts import (
    SCOPE_ALL_RELATED,
    SCOPE_CORE_ONLY,
    SCOPE_MANUAL_PICK,
    SCOPE_SINGLE_TARGET,
    SELECTION_KIND_CREDENTIAL,
    SELECTION_KIND_ENDPOINT_SCOPE,
    SELECTION_KIND_ENDPOINTS,
    SELECTION_KIND_PROJECT,
)
from src.modes.api_testing_mode.campaign_state import PendingSelection


CONFIRM_TOKENS = {"ok", "yes", "y", "好", "好的", "确认", "确定", "同意", "go", "继续"}
ALL_TOKENS = {"all", "全部", "全部接口", "所有接口", "所有"}
CORE_TOKENS = {"core", "核心", "核心接口", "基础", "主线"}
MANUAL_TOKENS = {"manual", "手动", "手动挑选", "自选", "手选"}
SINGLE_TOKENS = {"single", "single_target", "单个", "只测一个", "一个接口", "单接口"}

HTTP_METHOD_PATTERN = re.compile(
    r"\b(GET|POST|PUT|PATCH|DELETE|OPTIONS|HEAD)\b",
    flags=re.IGNORECASE,
)
LEADING_NUMBER_PATTERN = re.compile(r"^\s*(\d{1,3})(?:[\.\)．）、\s]|$)")
INLINE_NUMBER_PATTERN = re.compile(r"第\s*(\d{1,3})\s*(?:个|条|项)?")
RANGE_PATTERN = re.compile(r"(\d{1,3})\s*[-~到至]\s*(\d{1,3})")


@dataclass
class SelectionResult:
    """Outcome of parsing a user reply against a pending selection."""

    kind: str
    resolved: bool
    option_ids: list[str]  # structured option ids picked from pending.options
    scope: str = ""  # for endpoint_scope kind
    free_text: str = ""
    raw_message: str = ""
    reason: str = ""
    extracted_credentials: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "resolved": self.resolved,
            "option_ids": list(self.option_ids),
            "scope": self.scope,
            "free_text": self.free_text,
            "reason": self.reason,
            "extracted_credentials": self.extracted_credentials,
        }


class SelectionResolver:
    """Deterministic parser for follow-up selection replies."""

    def resolve(
        self,
        *,
        pending: PendingSelection | None,
        message: str,
    ) -> SelectionResult:
        text = (message or "").strip()
        if pending is None:
            return SelectionResult(
                kind="",
                resolved=False,
                option_ids=[],
                raw_message=text,
                reason="No pending selection to resolve.",
            )
        if pending.kind == SELECTION_KIND_PROJECT:
            return self._resolve_options(pending, text, minimum=1, maximum=1)
        if pending.kind == SELECTION_KIND_ENDPOINT_SCOPE:
            return self._resolve_endpoint_scope(pending, text)
        if pending.kind == SELECTION_KIND_ENDPOINTS:
            return self._resolve_options(pending, text, minimum=1, maximum=50)
        if pending.kind == SELECTION_KIND_CREDENTIAL:
            return self._resolve_credential(pending, text)
        return SelectionResult(
            kind=pending.kind,
            resolved=False,
            option_ids=[],
            raw_message=text,
            reason=f"Unsupported selection kind: {pending.kind}",
        )

    # ------------------------------------------------------------------
    # Endpoint scope
    # ------------------------------------------------------------------

    def _resolve_endpoint_scope(
        self,
        pending: PendingSelection,
        text: str,
    ) -> SelectionResult:
        lowered = text.lower()
        if self._contains_any(lowered, CORE_TOKENS):
            return SelectionResult(
                kind=pending.kind,
                resolved=True,
                option_ids=[SCOPE_CORE_ONLY],
                scope=SCOPE_CORE_ONLY,
                raw_message=text,
                reason="Matched core scope tokens.",
            )
        if self._contains_any(lowered, ALL_TOKENS):
            return SelectionResult(
                kind=pending.kind,
                resolved=True,
                option_ids=[SCOPE_ALL_RELATED],
                scope=SCOPE_ALL_RELATED,
                raw_message=text,
                reason="Matched all-related tokens.",
            )
        if self._contains_any(lowered, MANUAL_TOKENS):
            return SelectionResult(
                kind=pending.kind,
                resolved=True,
                option_ids=[SCOPE_MANUAL_PICK],
                scope=SCOPE_MANUAL_PICK,
                raw_message=text,
                reason="Matched manual-pick tokens.",
            )
        if self._contains_any(lowered, SINGLE_TOKENS):
            return SelectionResult(
                kind=pending.kind,
                resolved=True,
                option_ids=[SCOPE_SINGLE_TARGET],
                scope=SCOPE_SINGLE_TARGET,
                raw_message=text,
                reason="Matched single-target tokens.",
            )
        # confirm with default -> use recommended
        if self._contains_any(lowered, CONFIRM_TOKENS) and pending.recommended_option_id:
            return SelectionResult(
                kind=pending.kind,
                resolved=True,
                option_ids=[pending.recommended_option_id],
                scope=pending.recommended_option_id,
                raw_message=text,
                reason="User confirmed default scope.",
            )
        # numeric index
        numbered = self._resolve_numeric_indices(pending, text, minimum=1, maximum=1)
        if numbered:
            option_id = numbered[0]
            return SelectionResult(
                kind=pending.kind,
                resolved=True,
                option_ids=[option_id],
                scope=option_id,
                raw_message=text,
                reason="Matched numeric scope selection.",
            )
        return SelectionResult(
            kind=pending.kind,
            resolved=False,
            option_ids=[],
            raw_message=text,
            reason="Could not identify a known scope option.",
        )

    # ------------------------------------------------------------------
    # Option-based (project / endpoints)
    # ------------------------------------------------------------------

    def _resolve_options(
        self,
        pending: PendingSelection,
        text: str,
        *,
        minimum: int,
        maximum: int,
    ) -> SelectionResult:
        lowered = text.lower()
        if (
            self._contains_any(lowered, CONFIRM_TOKENS)
            and pending.recommended_option_id
        ):
            return SelectionResult(
                kind=pending.kind,
                resolved=True,
                option_ids=[pending.recommended_option_id],
                raw_message=text,
                reason="User confirmed recommended option.",
            )

        if self._contains_any(lowered, ALL_TOKENS) and pending.kind == SELECTION_KIND_ENDPOINTS:
            option_ids = [str(opt.get("id")) for opt in pending.options if opt.get("id")]
            if option_ids:
                return SelectionResult(
                    kind=pending.kind,
                    resolved=True,
                    option_ids=option_ids,
                    raw_message=text,
                    reason="User selected all endpoint options.",
                )

        indexed = self._resolve_numeric_indices(pending, text, minimum=minimum, maximum=maximum)
        if indexed:
            return SelectionResult(
                kind=pending.kind,
                resolved=True,
                option_ids=indexed,
                raw_message=text,
                reason="Resolved numeric selection.",
            )

        matched_by_value = self._resolve_by_option_value(pending, text, maximum=maximum)
        if matched_by_value:
            return SelectionResult(
                kind=pending.kind,
                resolved=True,
                option_ids=matched_by_value,
                raw_message=text,
                reason="Matched options by label or value.",
            )

        return SelectionResult(
            kind=pending.kind,
            resolved=False,
            option_ids=[],
            raw_message=text,
            reason="Could not identify a selected option.",
        )

    # ------------------------------------------------------------------
    # Credential
    # ------------------------------------------------------------------

    def _resolve_credential(
        self,
        pending: PendingSelection,
        text: str,
    ) -> SelectionResult:
        extracted = self._extract_credentials(text)
        if extracted:
            return SelectionResult(
                kind=pending.kind,
                resolved=True,
                option_ids=[],
                free_text=text,
                raw_message=text,
                reason="Extracted credentials from user input.",
                extracted_credentials=extracted,
            )
        return SelectionResult(
            kind=pending.kind,
            resolved=False,
            option_ids=[],
            free_text=text,
            raw_message=text,
            reason="Could not extract credentials from input.",
        )

    def _extract_credentials(self, text: str) -> dict[str, Any] | None:
        if not text:
            return None
        extracted: dict[str, Any] = {}
        # Bearer token patterns
        bearer_match = re.search(r"Bearer\s+([A-Za-z0-9._\-]+)", text, flags=re.IGNORECASE)
        if bearer_match:
            extracted["auth_type"] = "bearer"
            extracted["token"] = bearer_match.group(1).strip()
        # `token=xxx` / `api_key=xxx` / `key=xxx`
        kv_match = re.search(r"(?i)\b(token|api[_-]?key|apikey|auth)\s*[=:]\s*([^\s,;]+)", text)
        if kv_match and "token" not in extracted:
            key_name = kv_match.group(1).lower()
            value = kv_match.group(2).strip().strip('"').strip("'")
            extracted["auth_type"] = "api_key" if "key" in key_name else "bearer"
            extracted["token"] = value
        # Cookie header pasted in
        cookie_match = re.search(r"(?i)cookie\s*:\s*(.+)", text)
        if cookie_match:
            cookie_value = cookie_match.group(1).strip()
            extracted.setdefault("auth_type", "cookie")
            extracted["cookie"] = cookie_value
        # Username/password
        user_match = re.search(r"(?i)(?:user(?:name)?|账号)\s*[=:：]\s*([^\s,;]+)", text)
        pass_match = re.search(r"(?i)(?:pass(?:word)?|密码)\s*[=:：]\s*([^\s,;]+)", text)
        if user_match and pass_match:
            extracted.setdefault("auth_type", "basic")
            extracted["username"] = user_match.group(1).strip()
            extracted["password"] = pass_match.group(1).strip()
        # Naked long token: if the reply is a single long opaque string, treat as bearer
        if not extracted:
            compact = text.strip()
            if re.fullmatch(r"[A-Za-z0-9._\-]{20,}", compact):
                extracted["auth_type"] = "bearer"
                extracted["token"] = compact
        return extracted or None

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _resolve_numeric_indices(
        self,
        pending: PendingSelection,
        text: str,
        *,
        minimum: int,
        maximum: int,
    ) -> list[str]:
        option_ids: list[str] = []
        for option in pending.options:
            option_id = str(option.get("id") or "")
            if option_id:
                option_ids.append(option_id)
        if not option_ids:
            return []

        selected: list[str] = []
        seen: set[str] = set()
        # Range first: "1-3", "2至4"
        for match in RANGE_PATTERN.finditer(text):
            start = int(match.group(1))
            end = int(match.group(2))
            if start > end:
                start, end = end, start
            for idx in range(start, end + 1):
                array_index = idx - 1
                if 0 <= array_index < len(option_ids):
                    option_id = option_ids[array_index]
                    if option_id not in seen:
                        selected.append(option_id)
                        seen.add(option_id)
        # Individual numbers
        if not selected:
            candidates: list[int] = []
            leading = LEADING_NUMBER_PATTERN.match(text)
            if leading:
                candidates.append(int(leading.group(1)))
            candidates.extend(int(match.group(1)) for match in INLINE_NUMBER_PATTERN.finditer(text))
            # Also accept comma-separated list like "1,2,3"
            for raw in re.split(r"[,，、\s]+", text):
                if raw.isdigit():
                    candidates.append(int(raw))
            for idx in candidates:
                array_index = idx - 1
                if 0 <= array_index < len(option_ids):
                    option_id = option_ids[array_index]
                    if option_id not in seen:
                        selected.append(option_id)
                        seen.add(option_id)
        if len(selected) < minimum:
            return []
        if maximum > 0 and len(selected) > maximum:
            selected = selected[:maximum]
        return selected

    def _resolve_by_option_value(
        self,
        pending: PendingSelection,
        text: str,
        *,
        maximum: int,
    ) -> list[str]:
        selected: list[str] = []
        seen: set[str] = set()
        method_match = HTTP_METHOD_PATTERN.search(text)
        method_token = method_match.group(1).upper() if method_match else ""
        lowered = text.lower()
        for option in pending.options:
            option_id = str(option.get("id") or "")
            if not option_id:
                continue
            label = str(option.get("label") or "").lower()
            value = str(option.get("value") or "").lower()
            method = str(option.get("method") or "").upper()
            path = str(option.get("path") or "").lower()
            project_name = str(option.get("project_name") or "").lower()
            # Prefer method + path match
            if method_token and method == method_token and path and path in lowered:
                selected.append(option_id)
                seen.add(option_id)
                continue
            if path and path in lowered:
                selected.append(option_id)
                seen.add(option_id)
                continue
            if value and value in lowered:
                selected.append(option_id)
                seen.add(option_id)
                continue
            if label and label in lowered and label:
                selected.append(option_id)
                seen.add(option_id)
                continue
            if project_name and project_name in lowered:
                selected.append(option_id)
                seen.add(option_id)
                continue
        if maximum > 0 and len(selected) > maximum:
            selected = selected[:maximum]
        return selected

    def _contains_any(self, text: str, tokens: set[str]) -> bool:
        return any(token in text for token in tokens)


__all__ = ["SelectionResolver", "SelectionResult"]

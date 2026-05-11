"""Narrow a large set of endpoints down to a testable scope."""
from __future__ import annotations

from dataclasses import dataclass

from src.modes.api_testing_mode.campaign_state import (
    ApiTestingRequestState,
    EndpointCandidate,
    PendingSelection,
)
from src.modes.api_testing_mode.capability_mapper import (
    CORE_CAPABILITIES,
    MappedEndpoint,
)
from src.modes.api_testing_mode.contracts import (
    SCOPE_ALL_RELATED,
    SCOPE_CORE_ONLY,
    SCOPE_LABELS,
    SCOPE_MANUAL_PICK,
    SCOPE_SINGLE_TARGET,
    SELECTION_KIND_ENDPOINT_SCOPE,
)


# Threshold above which we require the user to pick a scope explicitly.
CLARIFY_IF_ENDPOINTS_EXCEED = 5


@dataclass
class ScopeResolution:
    """Result of resolving an endpoint scope against the candidates."""

    resolved_scope: str
    requires_manual_pick: bool
    selected_endpoints: list[EndpointCandidate]
    reason: str = ""

    def to_dict(self) -> dict:
        return {
            "resolved_scope": self.resolved_scope,
            "requires_manual_pick": self.requires_manual_pick,
            "selected_endpoints": [ep.model_dump() for ep in self.selected_endpoints],
            "reason": self.reason,
        }


class EndpointScopeService:
    """Determine a sensible endpoint subset for a campaign."""

    def build_pending_selection(
        self,
        *,
        project_name: str,
        mapped_endpoints: list[MappedEndpoint],
    ) -> PendingSelection:
        """Return a ``PendingSelection`` asking the user to pick a scope."""
        core_count = sum(1 for item in mapped_endpoints if item.is_core)
        total = len(mapped_endpoints)
        recommended_option_id = (
            SCOPE_CORE_ONLY
            if core_count > 0
            else SCOPE_ALL_RELATED
            if total <= 10
            else SCOPE_MANUAL_PICK
        )
        options = [
            {
                "id": SCOPE_CORE_ONLY,
                "label": SCOPE_LABELS[SCOPE_CORE_ONLY],
                "value": SCOPE_CORE_ONLY,
                "description": f"只测核心能力相关接口，共约 {core_count} 个",
                "recommended": recommended_option_id == SCOPE_CORE_ONLY,
            },
            {
                "id": SCOPE_ALL_RELATED,
                "label": SCOPE_LABELS[SCOPE_ALL_RELATED],
                "value": SCOPE_ALL_RELATED,
                "description": f"测试该项目下全部 {total} 个相关接口",
                "recommended": recommended_option_id == SCOPE_ALL_RELATED,
            },
            {
                "id": SCOPE_MANUAL_PICK,
                "label": SCOPE_LABELS[SCOPE_MANUAL_PICK],
                "value": SCOPE_MANUAL_PICK,
                "description": "展示所有接口让用户手动挑选",
                "recommended": recommended_option_id == SCOPE_MANUAL_PICK,
            },
            {
                "id": SCOPE_SINGLE_TARGET,
                "label": SCOPE_LABELS[SCOPE_SINGLE_TARGET],
                "value": SCOPE_SINGLE_TARGET,
                "description": "只测单个接口，手动选择具体端点",
                "recommended": recommended_option_id == SCOPE_SINGLE_TARGET,
            },
        ]
        return PendingSelection(
            kind=SELECTION_KIND_ENDPOINT_SCOPE,
            prompt=(
                f"项目 {project_name} 共发现 {total} 个接口，请选择测试范围。"
                f" 推荐：{SCOPE_LABELS[recommended_option_id]}。"
            ),
            options=options,
            recommended_option_id=recommended_option_id,
        )

    def should_clarify_scope(
        self,
        *,
        mapped_endpoints: list[MappedEndpoint],
        request: ApiTestingRequestState,
    ) -> tuple[bool, str]:
        if not mapped_endpoints:
            return False, "No endpoints discovered."
        preference = (request.scope_preference or "").strip()
        if preference in {
            SCOPE_ALL_RELATED,
            SCOPE_CORE_ONLY,
            SCOPE_MANUAL_PICK,
            SCOPE_SINGLE_TARGET,
        }:
            return False, "User already specified a scope preference."
        # If user provided a concrete endpoint_hint pointing at a specific path/method,
        # treat as single_target and skip clarification.
        if request.endpoint_hint and len(mapped_endpoints) <= 1:
            return False, "Single endpoint already identified."
        if len(mapped_endpoints) <= 1:
            return False, "Only one endpoint available."
        if len(mapped_endpoints) <= CLARIFY_IF_ENDPOINTS_EXCEED:
            # Still small: allow auto-selecting core if core_count > 0, else all.
            return False, "Endpoint list is small enough to auto-select."
        return True, "Endpoint list is large; user should confirm scope."

    def build_endpoint_selection(
        self,
        *,
        project_name: str,
        mapped_endpoints: list[MappedEndpoint],
        limit: int = 30,
    ) -> PendingSelection:
        """Build a pending endpoint selection (for manual/single scope)."""
        options: list[dict] = []
        for mapped in mapped_endpoints[:limit]:
            endpoint = mapped.endpoint
            options.append(
                {
                    "id": endpoint.endpoint_id,
                    "label": f"{endpoint.method} {endpoint.path}",
                    "value": f"{endpoint.method} {endpoint.path}",
                    "method": endpoint.method,
                    "path": endpoint.path,
                    "summary": endpoint.summary,
                    "capability": mapped.capability,
                    "is_core": mapped.is_core,
                    "project_name": project_name,
                }
            )
        return PendingSelection(
            kind="endpoints",
            prompt=(
                f"{project_name} 共有 {len(mapped_endpoints)} 个可测接口，"
                f"请从列表中选择一个或多个接口（可用序号或直接写 POST /xxx）。"
            ),
            options=options,
            recommended_option_id=options[0]["id"] if options else "",
            allow_free_text=True,
        )

    def resolve_scope(
        self,
        *,
        scope: str,
        mapped_endpoints: list[MappedEndpoint],
        request: ApiTestingRequestState,
    ) -> ScopeResolution:
        """Pick endpoints that match the requested scope."""
        normalized = (scope or "").strip() or SCOPE_CORE_ONLY

        if normalized == SCOPE_ALL_RELATED:
            endpoints = [item.endpoint for item in mapped_endpoints]
            return ScopeResolution(
                resolved_scope=SCOPE_ALL_RELATED,
                requires_manual_pick=False,
                selected_endpoints=endpoints,
                reason=f"Selected all {len(endpoints)} endpoints.",
            )

        if normalized == SCOPE_CORE_ONLY:
            core = [item.endpoint for item in mapped_endpoints if item.is_core]
            if not core:
                endpoints = [item.endpoint for item in mapped_endpoints]
                return ScopeResolution(
                    resolved_scope=SCOPE_ALL_RELATED,
                    requires_manual_pick=False,
                    selected_endpoints=endpoints,
                    reason="No endpoints tagged as core, falling back to all.",
                )
            return ScopeResolution(
                resolved_scope=SCOPE_CORE_ONLY,
                requires_manual_pick=False,
                selected_endpoints=core,
                reason=f"Selected {len(core)} core endpoints.",
            )

        if normalized == SCOPE_SINGLE_TARGET:
            # Prefer an endpoint matching the hint; otherwise require manual pick.
            hinted = self._match_by_hint(mapped_endpoints, request)
            if hinted is not None:
                return ScopeResolution(
                    resolved_scope=SCOPE_SINGLE_TARGET,
                    requires_manual_pick=False,
                    selected_endpoints=[hinted.endpoint],
                    reason="Matched endpoint by user hint.",
                )
            return ScopeResolution(
                resolved_scope=SCOPE_SINGLE_TARGET,
                requires_manual_pick=True,
                selected_endpoints=[],
                reason="Single-target scope requires explicit endpoint selection.",
            )

        if normalized == SCOPE_MANUAL_PICK:
            return ScopeResolution(
                resolved_scope=SCOPE_MANUAL_PICK,
                requires_manual_pick=True,
                selected_endpoints=[],
                reason="Manual pick scope requires explicit endpoint selection.",
            )

        # Unknown scope fallback.
        endpoints = [item.endpoint for item in mapped_endpoints]
        return ScopeResolution(
            resolved_scope=SCOPE_ALL_RELATED,
            requires_manual_pick=False,
            selected_endpoints=endpoints,
            reason=f"Unknown scope '{scope}', falling back to all-related.",
        )

    def _match_by_hint(
        self,
        mapped_endpoints: list[MappedEndpoint],
        request: ApiTestingRequestState,
    ) -> MappedEndpoint | None:
        method_hint = (request.method_hint or "").strip().upper()
        endpoint_hint = (request.endpoint_hint or "").strip().lower()
        if not (method_hint or endpoint_hint):
            return None
        for mapped in mapped_endpoints:
            endpoint = mapped.endpoint
            if method_hint and endpoint.method != method_hint:
                continue
            if endpoint_hint and endpoint_hint not in endpoint.path.lower():
                if endpoint_hint not in (endpoint.full_url or "").lower():
                    continue
            return mapped
        return None

    # Keep ``CORE_CAPABILITIES`` importable without circular deps.
    @property
    def core_capabilities(self) -> frozenset[str]:
        return CORE_CAPABILITIES


__all__ = ["EndpointScopeService", "ScopeResolution", "CLARIFY_IF_ENDPOINTS_EXCEED"]

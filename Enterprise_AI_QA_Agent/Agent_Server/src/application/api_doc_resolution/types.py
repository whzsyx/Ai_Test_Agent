"""API Doc Resolution shared data types.

Pydantic models for the structured results produced by the resolution service.
These are consumed by any mode that integrates API doc resolution (performance,
api_testing, smoke, compatibility, etc.).
"""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from .contracts import (
    AcceptedInput,
    DocResolutionStatus,
    MatchType,
    MissingDocReason,
    ResolutionConfidence,
)


# ---------------------------------------------------------------------------
# Resolved endpoint information
# ---------------------------------------------------------------------------


class ResolvedEndpoint(BaseModel):
    """A successfully resolved endpoint from API documentation."""

    model_config = ConfigDict(extra="allow")

    method: str = ""
    path: str = ""
    full_url: str = ""
    summary: str = ""
    doc_id: str = ""
    endpoint_id: str = ""
    base_url: str = ""
    auth_hint: str = ""  # bearer | cookie | none | ""
    preconditions: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Project discovery result
# ---------------------------------------------------------------------------


class ProjectDiscoveryResult(BaseModel):
    """Result of project document discovery."""

    model_config = ConfigDict(extra="allow")

    ok: bool = False
    project_count: int = 0
    document_count: int = 0
    candidates: list[dict[str, Any]] = Field(default_factory=list)
    selected_project: str = ""
    selected_project_url: str = ""
    needs_clarification: bool = False
    clarification_reason: str = ""
    missing_doc_reason: MissingDocReason | None = None


# ---------------------------------------------------------------------------
# Endpoint resolution result
# ---------------------------------------------------------------------------


class EndpointResolutionResult(BaseModel):
    """Result of endpoint resolution from project documents."""

    model_config = ConfigDict(extra="allow")

    ok: bool = False
    confidence: ResolutionConfidence = "none"
    match_type: MatchType = "none"
    selected_doc_id: str = ""
    selected_endpoint: ResolvedEndpoint | None = None
    candidate_endpoints: list[ResolvedEndpoint] = Field(default_factory=list)
    needs_clarification: bool = False
    clarification_reason: str = ""
    missing_doc_reason: MissingDocReason | None = None
    base_url: str = ""
    auth_hint: str = ""


# ---------------------------------------------------------------------------
# Doc ingest result
# ---------------------------------------------------------------------------


class DocIngestResult(BaseModel):
    """Result of importing a document from attachment or URL."""

    model_config = ConfigDict(extra="allow")

    ok: bool = False
    action: str = ""
    summary: str = ""
    document: dict[str, Any] = Field(default_factory=dict)
    error: str = ""


# ---------------------------------------------------------------------------
# Awaiting input response
# ---------------------------------------------------------------------------


class DocResolutionAwaitingInput(BaseModel):
    """Structured awaiting_input response when documents are missing or ambiguous."""

    model_config = ConfigDict(extra="allow")

    status: str = "awaiting_input"
    ok: bool = True
    phase: str = "awaiting_api_doc_source"
    summary: str = ""
    missing_doc_reason: MissingDocReason | None = None
    requested_project: str = ""
    requested_endpoint_hint: str = ""
    accepted_inputs: list[AcceptedInput] = Field(default_factory=list)
    questions: list[str] = Field(default_factory=list)
    candidates: list[dict[str, Any]] = Field(default_factory=list)

    def to_tool_output(self) -> dict[str, Any]:
        """Convert to a dict suitable for tool output."""
        return self.model_dump(mode="json", exclude_none=True)


# ---------------------------------------------------------------------------
# Doc source history entry (for state persistence)
# ---------------------------------------------------------------------------


class DocSourceHistoryEntry(BaseModel):
    """Record of a document source attempt (for tracking retries and context)."""

    model_config = ConfigDict(extra="allow")

    source_type: str = ""  # attachment | url | library
    source_ref: str = ""  # attachment_id or URL
    timestamp: str = ""
    success: bool = False
    result_doc_id: str = ""
    error: str = ""


# ---------------------------------------------------------------------------
# Full resolution state (embedded in mode state)
# ---------------------------------------------------------------------------


class DocResolutionState(BaseModel):
    """Full state for API doc resolution, embeddable in mode states."""

    model_config = ConfigDict(extra="allow")

    status: DocResolutionStatus = "not_started"
    requested_project: str = ""
    requested_endpoint_hint: str = ""
    missing_doc_reason: MissingDocReason | None = None
    doc_source_history: list[DocSourceHistoryEntry] = Field(default_factory=list)
    resolved_doc_id: str = ""
    resolved_endpoint: ResolvedEndpoint | None = None
    resolved_base_url: str = ""
    resolved_auth_hint: str = ""
    project_candidates: list[dict[str, Any]] = Field(default_factory=list)
    endpoint_candidates: list[dict[str, Any]] = Field(default_factory=list)


__all__ = [
    "ResolvedEndpoint",
    "ProjectDiscoveryResult",
    "EndpointResolutionResult",
    "DocIngestResult",
    "DocResolutionAwaitingInput",
    "DocSourceHistoryEntry",
    "DocResolutionState",
]

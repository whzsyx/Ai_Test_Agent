"""API doc resolution contracts.

Defines the structured types for doc resolution status,
endpoint resolution results, and missing-doc reason codes.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal


MissingDocReason = Literal[
    "no_documents_in_library",
    "no_project_documents",
    "endpoint_not_found_in_docs",
    "ambiguous_document_match",
    "none",
]

AcceptedInput = Literal["attachment", "url", "library"]

ResolutionStatus = Literal[
    "not_started",
    "resolved",
    "awaiting_input",
    "ambiguous",
    "failed",
]

DocResolutionStatus = ResolutionStatus

ResolutionConfidence = Literal["high", "medium", "low", "none"]

MatchType = Literal["endpoint", "document", "none"]


@dataclass
class ResolvedEndpoint:
    """A single resolved endpoint from API docs."""

    method: str = ""
    path: str = ""
    base_url: str = ""
    doc_id: str = ""
    auth_hint: dict[str, Any] = field(default_factory=dict)
    headers: dict[str, str] = field(default_factory=dict)
    body_template: dict[str, Any] | str | None = None

    def model_dump(self) -> dict[str, Any]:
        return {
            "method": self.method,
            "path": self.path,
            "base_url": self.base_url,
            "doc_id": self.doc_id,
            "auth_hint": dict(self.auth_hint),
            "headers": dict(self.headers),
            "body_template": self.body_template,
        }


@dataclass
class DocResolutionResult:
    """Full result of doc + endpoint resolution."""

    status: ResolutionStatus = "failed"
    confidence: str = "low"
    match_type: MatchType = "none"
    missing_doc_reason: MissingDocReason = "none"
    selected_doc_id: str = ""
    selected_doc_title: str = ""
    resolved_endpoint: ResolvedEndpoint | None = None
    project_name: str = ""
    project_url: str = ""
    candidates: list[dict[str, Any]] = field(default_factory=list)
    summary: str = ""
    accepted_inputs: list[str] = field(default_factory=lambda: ["attachment", "url"])

    def model_dump(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "confidence": self.confidence,
            "match_type": self.match_type,
            "missing_doc_reason": self.missing_doc_reason,
            "selected_doc_id": self.selected_doc_id,
            "selected_doc_title": self.selected_doc_title,
            "resolved_endpoint": self.resolved_endpoint.model_dump() if self.resolved_endpoint else None,
            "project_name": self.project_name,
            "project_url": self.project_url,
            "candidates": list(self.candidates),
            "summary": self.summary,
            "accepted_inputs": list(self.accepted_inputs),
        }

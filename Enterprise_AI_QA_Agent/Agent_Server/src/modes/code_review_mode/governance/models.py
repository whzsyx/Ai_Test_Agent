from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


ChangeType = Literal["added", "modified", "deleted", "renamed", "unknown"]
FindingCategory = Literal[
    "security",
    "architecture",
    "database",
    "performance",
    "dependency",
    "secret",
    "test",
    "correctness",
    "maintainability",
]
FindingSeverity = Literal["critical", "high", "medium", "low", "info"]
DecisionStatus = Literal["pass", "warning", "blocked"]


class ChangedFile(BaseModel):
    path: str
    change_type: ChangeType = "unknown"
    language: str = "other"
    additions: int = 0
    deletions: int = 0
    risk_hints: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class GovernanceFinding(BaseModel):
    id: str
    source: str
    category: FindingCategory
    severity: FindingSeverity
    title: str
    summary: str
    file_path: str = ""
    line: int | None = None
    evidence: list[dict[str, Any]] = Field(default_factory=list)
    confidence: float = 0.0
    deterministic: bool = False
    recommendation: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class RiskScore(BaseModel):
    score: int
    level: Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]
    security: int
    performance: int
    architecture: int
    database: int
    dependency: int
    test_coverage: int
    maintainability: int


class ApprovalDecision(BaseModel):
    status: DecisionStatus
    reason: str
    blocking_findings: list[str] = Field(default_factory=list)
    required_actions: list[str] = Field(default_factory=list)
    policy: dict[str, Any] = Field(default_factory=dict)

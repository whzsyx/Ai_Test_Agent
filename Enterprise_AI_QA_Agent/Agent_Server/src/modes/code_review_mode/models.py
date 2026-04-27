from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


ProjectSourceType = Literal["local", "ssh"]
ReviewPointKind = Literal["project", "module", "path", "diff", "file"]
ReviewFindingCategory = Literal["serious_issue", "defect", "risk", "feasible", "excellent"]


class SSHProjectSource(BaseModel):
    host: str = ""
    port: int = 22
    username: str = ""
    auth_ref: str = ""
    remote_root_path: str = ""


class ProjectSource(BaseModel):
    source_type: ProjectSourceType = "local"
    root_path: str = ""
    project_name: str = ""
    branch: str = ""
    commit_range: str = ""
    ssh: SSHProjectSource = Field(default_factory=SSHProjectSource)


class ReviewPoint(BaseModel):
    point_id: str
    title: str
    kind: ReviewPointKind
    target: str
    summary: str


class ReviewTeamMember(BaseModel):
    key: str
    name: str
    agent_key: str
    role: str
    focus: str
    responsibilities: list[str] = Field(default_factory=list)


class DebateRound(BaseModel):
    round_id: str
    name: str
    objective: str


class ReviewReportSkeleton(BaseModel):
    report_title: str
    project_name: str
    approval_time: datetime
    result_sections: list[ReviewFindingCategory] = Field(
        default_factory=lambda: [
            "serious_issue",
            "defect",
            "risk",
            "feasible",
            "excellent",
        ]
    )
    required_fields: list[str] = Field(
        default_factory=lambda: [
            "finding_id",
            "point_id",
            "result_category",
            "summary",
            "proposer_agent",
            "supporting_agents",
            "challenging_agents",
            "evidence_refs",
            "recommended_actions",
            "confidence",
        ]
    )


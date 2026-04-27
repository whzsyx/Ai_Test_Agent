from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from src.modes.code_review_mode.models import DebateRound, ProjectSource, ReviewPoint, ReviewReportSkeleton
from src.modes.code_review_mode.project_source import normalize_project_source, project_source_root
from src.modes.code_review_mode.team import REVIEW_TEAM_MEMBERS, SUMMARY_AGENT

if TYPE_CHECKING:
    from src.application.runtime.tool_runtime_service import ToolExecutionContext


MIN_CROSS_REVIEW_ROUNDS = 1
MAX_CROSS_REVIEW_ROUNDS = 4


def build_code_review_campaign(
    arguments: dict[str, Any],
    context: ToolExecutionContext,
) -> dict[str, Any]:
    project_source = normalize_project_source(arguments)
    review_points = _build_review_points(project_source, arguments)
    cross_review_round_count = _resolve_cross_review_round_count(arguments)
    debate_rounds = _build_debate_rounds(cross_review_round_count)
    total_round_count = len(debate_rounds)

    report = ReviewReportSkeleton(
        report_title=f"《{project_source.project_name or 'Unnamed Project'}》的辩论报告",
        project_name=project_source.project_name or "Unnamed Project",
        approval_time=datetime.utcnow(),
    )

    independent_workers = [
        _build_independent_worker_spec(
            member=member,
            project_source=project_source,
            review_points=review_points,
            arguments=arguments,
            context=context,
            debate_rounds=debate_rounds,
            total_round_count=total_round_count,
        )
        for member in REVIEW_TEAM_MEMBERS
    ]

    followup_workers: list[dict[str, Any]] = []
    for cross_round_number in range(1, cross_review_round_count + 1):
        debate_round_index = cross_round_number + 1
        source_round_index = debate_round_index - 1
        for member in REVIEW_TEAM_MEMBERS:
            followup_workers.append(
                _build_cross_review_worker_spec(
                    member=member,
                    project_source=project_source,
                    review_points=review_points,
                    arguments=arguments,
                    context=context,
                    debate_rounds=debate_rounds,
                    total_round_count=total_round_count,
                    debate_round_index=debate_round_index,
                    source_round_index=source_round_index,
                )
            )

    summary_agent_spec = _build_summary_agent_spec(
        project_source=project_source,
        review_points=review_points,
        arguments=arguments,
        context=context,
        debate_rounds=debate_rounds,
        total_round_count=total_round_count,
        cross_review_round_count=cross_review_round_count,
    )

    campaign_id = str(uuid4())
    review_scope = str(arguments.get("review_scope") or "project").strip() or "project"
    launch_workers = bool(arguments.get("launch_workers", True))
    return {
        "campaign_id": campaign_id,
        "project_source": project_source.model_dump(mode="python"),
        "review_scope": review_scope,
        "review_points": [point.model_dump(mode="python") for point in review_points],
        "review_team": [member.model_dump(mode="python") for member in REVIEW_TEAM_MEMBERS],
        "summary_agent": summary_agent_spec,
        "debate_rounds": [round_.model_dump(mode="python") for round_ in debate_rounds],
        "report_skeleton": report.model_dump(mode="python"),
        "dispatch_payload": {
            "workers": independent_workers,
            "followup_workers": followup_workers,
            "completion_worker": summary_agent_spec,
        },
        "launch_workers": launch_workers,
        "metrics": {
            "reviewer_count": len(REVIEW_TEAM_MEMBERS),
            "debate_round_count": total_round_count,
            "cross_review_round_count": cross_review_round_count,
            "review_point_count": len(review_points),
        },
        "summary": (
            f"Prepared a code review debate campaign for '{project_source.project_name}' with "
            f"{len(REVIEW_TEAM_MEMBERS)} reviewer agents, {len(review_points)} review point(s), "
            f"and {cross_review_round_count} cross-review round(s)."
        ),
    }


def _resolve_cross_review_round_count(arguments: dict[str, Any]) -> int:
    raw_value = arguments.get("cross_review_rounds")
    if raw_value is None:
        raw_value = arguments.get("debate_round_count")
    try:
        resolved = int(raw_value)
    except (TypeError, ValueError):
        resolved = 2
    return max(MIN_CROSS_REVIEW_ROUNDS, min(MAX_CROSS_REVIEW_ROUNDS, resolved))


def _build_debate_rounds(cross_review_round_count: int) -> list[DebateRound]:
    rounds = [
        DebateRound(
            round_id="independent_findings",
            name="Independent Findings",
            objective="Each reviewer inspects the project independently and proposes findings without reading peer outputs.",
        )
    ]
    for cross_round_number in range(1, cross_review_round_count + 1):
        rounds.append(
            DebateRound(
                round_id=f"cross_review_{cross_round_number}",
                name=f"Cross Review Round {cross_round_number}",
                objective=(
                    "Peer reviewers support, challenge, or refine prior findings with stronger evidence, "
                    "severity calibration, and hidden-risk analysis."
                ),
            )
        )
    rounds.append(
        DebateRound(
            round_id="summary_resolution",
            name="Summary Resolution",
            objective="The synthesizer merges debated findings into a final structured decision for the project.",
        )
    )
    return rounds


def _build_review_points(project_source: ProjectSource, arguments: dict[str, Any]) -> list[ReviewPoint]:
    targets = arguments.get("targets")
    normalized_targets = (
        [str(item).strip() for item in targets if str(item).strip()]
        if isinstance(targets, list)
        else []
    )
    review_points: list[ReviewPoint] = []
    if normalized_targets:
        for target in normalized_targets:
            review_points.append(
                ReviewPoint(
                    point_id=str(uuid4()),
                    title=f"Review target: {target}",
                    kind="path",
                    target=target,
                    summary=(
                        "Inspect this target for correctness, architecture, security, testability, "
                        "maintenance cost, and feasible improvements."
                    ),
                )
            )
    else:
        scope_target = project_source_root(project_source)
        review_points.append(
            ReviewPoint(
                point_id=str(uuid4()),
                title=f"Project-wide review: {project_source.project_name}",
                kind="project",
                target=scope_target,
                summary=(
                    "Inspect the whole project scope, debate major findings, and identify severe issues, "
                    "defects, hidden risks, feasible actions, and excellent practices."
                ),
            )
        )
    return review_points


def _build_independent_worker_spec(
    member,
    project_source: ProjectSource,
    review_points: list[ReviewPoint],
    arguments: dict[str, Any],
    context: ToolExecutionContext,
    debate_rounds: list[DebateRound],
    total_round_count: int,
) -> dict[str, Any]:
    reviewer_prompt = _build_independent_reviewer_prompt(
        member_name=member.name,
        focus=member.focus,
        responsibilities=member.responsibilities,
        project_source=project_source,
        review_points=review_points,
        arguments=arguments,
    )
    return {
        "description": f"{member.name} independent review for {project_source.project_name}",
        "prompt": reviewer_prompt,
        "agent_key": member.agent_key,
        "model_key": str(arguments.get("worker_model_key") or "").strip() or None,
        "skill_keys": ["requirements-analysis", "risk-scoping", "report-synthesis"],
        "context": _build_worker_context(
            member=member,
            project_source=project_source,
            review_points=review_points,
            context=context,
            debate_rounds=debate_rounds,
            debate_stage="independent_findings",
            debate_round_index=1,
            total_round_count=total_round_count,
            empty_context_policy="Do not assume any peer output exists during the first pass.",
        ),
    }


def _build_cross_review_worker_spec(
    member,
    project_source: ProjectSource,
    review_points: list[ReviewPoint],
    arguments: dict[str, Any],
    context: ToolExecutionContext,
    debate_rounds: list[DebateRound],
    total_round_count: int,
    debate_round_index: int,
    source_round_index: int,
) -> dict[str, Any]:
    reviewer_prompt = _build_cross_review_prompt(
        member_name=member.name,
        focus=member.focus,
        responsibilities=member.responsibilities,
        project_source=project_source,
        review_points=review_points,
        arguments=arguments,
        debate_round_index=debate_round_index,
        source_round_index=source_round_index,
    )
    return {
        "description": f"{member.name} cross review round {debate_round_index - 1} for {project_source.project_name}",
        "prompt": reviewer_prompt,
        "agent_key": member.agent_key,
        "model_key": str(arguments.get("worker_model_key") or "").strip() or None,
        "skill_keys": ["requirements-analysis", "risk-scoping", "report-synthesis"],
        "context": _build_worker_context(
            member=member,
            project_source=project_source,
            review_points=review_points,
            context=context,
            debate_rounds=debate_rounds,
            debate_stage="cross_review",
            debate_round_index=debate_round_index,
            total_round_count=total_round_count,
            empty_context_policy="You must debate peer findings instead of restarting project discovery.",
            source_stage="independent_findings" if source_round_index == 1 else "cross_review",
            source_round_index=source_round_index,
        ),
    }


def _build_worker_context(
    *,
    member,
    project_source: ProjectSource,
    review_points: list[ReviewPoint],
    context: ToolExecutionContext,
    debate_rounds: list[DebateRound],
    debate_stage: str,
    debate_round_index: int,
    total_round_count: int,
    empty_context_policy: str,
    source_stage: str = "",
    source_round_index: int = 0,
) -> dict[str, Any]:
    dispatch_role = "debate_followup" if debate_stage == "cross_review" else "worker"
    return {
        "campaign_kind": "code_review_debate",
        "campaign_project_name": project_source.project_name,
        "campaign_source": project_source.model_dump(mode="python"),
        "review_points": [point.model_dump(mode="python") for point in review_points],
        "review_focus": member.focus,
        "review_responsibilities": list(member.responsibilities),
        "debate_role": member.key,
        "debate_stage": debate_stage,
        "debate_round_index": debate_round_index,
        "debate_total_round_count": total_round_count,
        "dispatch_role": dispatch_role,
        "debate_rounds": [round_.model_dump(mode="python") for round_ in debate_rounds],
        "empty_context_policy": empty_context_policy,
        "source_stage": source_stage,
        "source_round_index": source_round_index,
        "result_contract": {
            "required_fields": [
                "finding_id",
                "point_id",
                "result_category",
                "summary",
                "risk_analysis",
                "recommended_actions",
                "evidence_refs",
                "confidence",
            ]
        },
        "parent_execution_context": {
            "session_id": context.session_id,
            "turn_id": context.turn_id,
            "trace_id": context.trace_id,
        },
    }


def _build_summary_agent_spec(
    project_source: ProjectSource,
    review_points: list[ReviewPoint],
    arguments: dict[str, Any],
    context: ToolExecutionContext,
    debate_rounds: list[DebateRound],
    total_round_count: int,
    cross_review_round_count: int,
) -> dict[str, Any]:
    email_recipients = [
        str(item).strip()
        for item in (arguments.get("email_to") if isinstance(arguments.get("email_to"), list) else [])
        if str(item).strip()
    ]
    delivery_channel = str(arguments.get("delivery_channel") or "artifact").strip().lower() or "artifact"
    email_subject = (
        str(arguments.get("email_subject") or "").strip()
        or f"{project_source.project_name} 代码审批辩论报告"
    )
    return {
        "description": f"{SUMMARY_AGENT.name} final debate synthesis for {project_source.project_name}",
        "prompt": _build_summary_prompt(
            project_source,
            review_points,
            cross_review_round_count=cross_review_round_count,
            email_recipients=email_recipients,
            delivery_channel=delivery_channel,
            email_subject=email_subject,
        ),
        "agent_key": SUMMARY_AGENT.agent_key,
        "model_key": str(arguments.get("summary_model_key") or arguments.get("worker_model_key") or "").strip() or None,
        "skill_keys": ["report-synthesis", "requirements-analysis"],
        "context": {
            "campaign_kind": "code_review_debate_summary",
            "campaign_project_name": project_source.project_name,
            "campaign_source": project_source.model_dump(mode="python"),
            "review_points": [point.model_dump(mode="python") for point in review_points],
            "debate_rounds": [round_.model_dump(mode="python") for round_ in debate_rounds],
            "debate_round_index": total_round_count,
            "debate_total_round_count": total_round_count,
            "parent_execution_context": {
                "session_id": context.session_id,
                "turn_id": context.turn_id,
                "trace_id": context.trace_id,
            },
            "delivery_preferences": {
                "channel": delivery_channel,
                "email_to": email_recipients,
                "email_subject": email_subject,
            },
        },
        "trigger": "after_cross_review_collection",
    }


def _build_independent_reviewer_prompt(
    *,
    member_name: str,
    focus: str,
    responsibilities: list[str],
    project_source: ProjectSource,
    review_points: list[ReviewPoint],
    arguments: dict[str, Any],
) -> str:
    responsibilities_block = "\n".join(f"- {item}" for item in responsibilities)
    review_points_block = "\n".join(
        f"- [{point.point_id}] {point.title} | target={point.target} | summary={point.summary}"
        for point in review_points
    )
    change_summary = str(arguments.get("change_summary") or "").strip()
    diff_text = str(arguments.get("diff_text") or "").strip()
    diff_block = (
        diff_text
        if diff_text
        else "(No inline diff text was provided. Read project files and git state through registered tools.)"
    )
    return (
        f"You are {member_name} inside the code review debate team.\n"
        f"Primary focus: {focus}\n"
        "This is round 1: independent findings.\n\n"
        "Responsibilities:\n"
        f"{responsibilities_block}\n\n"
        "Project source:\n"
        f"- source_type: {project_source.source_type}\n"
        f"- project_name: {project_source.project_name}\n"
        f"- root_path: {project_source_root(project_source)}\n"
        f"- branch: {project_source.branch or '(unspecified)'}\n"
        f"- commit_range: {project_source.commit_range or '(unspecified)'}\n\n"
        "Recommended tool sequence:\n"
        "- Use the bootstrap digest first.\n"
        "- Read only the smallest number of project files needed to prove your claims.\n"
        "- Do not wait for peer agents in this round.\n\n"
        "Review points:\n"
        f"{review_points_block}\n\n"
        "Change summary:\n"
        f"{change_summary or '(No change summary provided.)'}\n\n"
        "Inline diff snippet:\n"
        f"{diff_block}\n\n"
        "Output contract:\n"
        "- Review the assigned scope and produce your own findings quickly.\n"
        "- Every finding must label exactly one result category: serious_issue, defect, risk, feasible, excellent.\n"
        "- For each finding, explain impact, hidden upstream/downstream risk, practical mitigation, feasibility, and evidence references.\n"
        "- Keep your output structured so peers can attack or support it in later rounds.\n"
    )


def _build_cross_review_prompt(
    *,
    member_name: str,
    focus: str,
    responsibilities: list[str],
    project_source: ProjectSource,
    review_points: list[ReviewPoint],
    arguments: dict[str, Any],
    debate_round_index: int,
    source_round_index: int,
) -> str:
    responsibilities_block = "\n".join(f"- {item}" for item in responsibilities)
    review_points_block = "\n".join(
        f"- [{point.point_id}] {point.title} | target={point.target} | summary={point.summary}"
        for point in review_points
    )
    change_summary = str(arguments.get("change_summary") or "").strip()
    return (
        f"You are {member_name} inside the code review debate team.\n"
        f"Primary focus: {focus}\n"
        f"This is round {debate_round_index}: cross review and rebuttal.\n"
        f"You must build from round {source_round_index} outputs before making new claims.\n\n"
        "Responsibilities:\n"
        f"{responsibilities_block}\n\n"
        "Project source:\n"
        f"- project_name: {project_source.project_name}\n"
        f"- root_path: {project_source_root(project_source)}\n\n"
        "Review points:\n"
        f"{review_points_block}\n\n"
        "Change summary:\n"
        f"{change_summary or '(No change summary provided.)'}\n\n"
        "Debate instructions:\n"
        "- You will receive peer findings from the previous round in the prompt context.\n"
        "- Do not restart broad repository exploration.\n"
        "- For each peer finding, decide whether to support, challenge, or refine it.\n"
        "- Attack weak evidence, missing impact analysis, or overclaimed severity.\n"
        "- Strengthen good findings with extra hidden-risk analysis and better mitigations.\n"
        "- When you disagree, be explicit about why and what evidence would change your mind.\n"
        "- As rounds progress, converge toward the strongest evidence-backed positions instead of repeating round 1.\n\n"
        "Output contract:\n"
        "- Respond with structured debate notes tied to peer finding ids whenever possible.\n"
        "- Include support/challenge/refine positions, evidence, and recommended severity adjustments.\n"
        "- Prefer precise rebuttal over repeating your original round 1 review.\n"
    )


def _build_summary_prompt(
    project_source: ProjectSource,
    review_points: list[ReviewPoint],
    *,
    cross_review_round_count: int,
    email_recipients: list[str],
    delivery_channel: str,
    email_subject: str,
) -> str:
    review_points_block = "\n".join(
        f"- [{point.point_id}] {point.title} | target={point.target}"
        for point in review_points
    )
    email_block = (
        "- Final delivery: keep the report as local artifacts only.\n"
        "- For artifact delivery, use report-writer with template_key=code_review_debate.\n"
        "- Do not call message-dispatch for local artifact delivery. report-writer already persists the required Markdown and HTML artifacts.\n"
        if delivery_channel != "email" or not email_recipients
        else (
            "- Final delivery: first call report-writer with template_key=code_review_debate to persist Markdown and HTML artifacts.\n"
            "- Then call send-email once with the same report content.\n"
            f"- Email recipients: {', '.join(email_recipients)}\n"
            f"- Email subject: {email_subject}\n"
            "- Do not call message-dispatch unless the user explicitly requests an additional delivery channel.\n"
        )
    )
    return (
        f"You are {SUMMARY_AGENT.name} for project '{project_source.project_name}'.\n"
        f"Collect all independent findings and all {cross_review_round_count} cross-review round rebuttals, then produce the final debate report.\n\n"
        "Required report body:\n"
        f"- Report title: 《{project_source.project_name}》的辩论报告\n"
        "- Approval time\n"
        "- Approval result summary with sections: serious_issue, defect, risk, feasible, excellent\n"
        "- Participating agent count\n"
        "- For each result, track which agent proposed it first\n"
        "- Support/challenge relationships among agents\n"
        "- Recommended actions and evidence references\n"
        "- Use report-writer with template_key=code_review_debate for the final Markdown and HTML report artifacts.\n"
        "- After report-writer succeeds, provide a brief completion message and stop. Do not ask follow-up questions.\n\n"
        "Delivery preferences:\n"
        f"{email_block}\n"
        "Review points:\n"
        f"{review_points_block}\n"
    )

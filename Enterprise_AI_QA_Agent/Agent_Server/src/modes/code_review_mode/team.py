from __future__ import annotations

from src.modes.code_review_mode.models import DebateRound, ReviewTeamMember


REVIEW_TEAM_MEMBERS: list[ReviewTeamMember] = [
    ReviewTeamMember(
        key="architecture",
        name="Architecture Reviewer",
        agent_key="code-architecture-reviewer",
        role="reviewer",
        focus="Layering, dependency direction, module boundaries, and long-term extensibility.",
        responsibilities=[
            "Inspect cross-module coupling and boundary leakage.",
            "Highlight architecture debt, abstraction drift, and ownership confusion.",
            "Call out feasible refactors that improve maintainability without destabilizing delivery.",
        ],
    ),
    ReviewTeamMember(
        key="correctness",
        name="Correctness Reviewer",
        agent_key="code-correctness-reviewer",
        role="reviewer",
        focus="Logical correctness, state transitions, data handling, and edge-case safety.",
        responsibilities=[
            "Check control flow, branching, and failure handling.",
            "Identify state inconsistencies and invalid assumptions.",
            "Propose practical bug fixes and validation guards.",
        ],
    ),
    ReviewTeamMember(
        key="security",
        name="Security Reviewer",
        agent_key="code-security-reviewer",
        role="reviewer",
        focus="Credential exposure, command execution, unsafe inputs, and permission boundaries.",
        responsibilities=[
            "Review execution paths that reach shell, network, filesystem, or secrets.",
            "Surface abuse paths, privilege creep, and unsafe defaults.",
            "Recommend contained mitigations with clear blast-radius reduction.",
        ],
    ),
    ReviewTeamMember(
        key="testability",
        name="Testability Reviewer",
        agent_key="code-testability-reviewer",
        role="reviewer",
        focus="Verification gaps, regression exposure, harness fit, and observability coverage.",
        responsibilities=[
            "Check whether behavior can be asserted and replayed reliably.",
            "Identify missing tests, missing trace points, and fragile validation paths.",
            "Suggest focused harness additions that improve confidence quickly.",
        ],
    ),
    ReviewTeamMember(
        key="maintainability",
        name="Maintainability Reviewer",
        agent_key="code-maintainability-reviewer",
        role="reviewer",
        focus="Readability, duplication, naming clarity, configuration hygiene, and operational simplicity.",
        responsibilities=[
            "Highlight repetitive logic and hard-coded behaviors.",
            "Review naming, comments, and local complexity hot spots.",
            "Recommend cleanup actions that lower ongoing maintenance cost.",
        ],
    ),
]

SUMMARY_AGENT = ReviewTeamMember(
    key="synthesizer",
    name="Review Synthesizer",
    agent_key="code-review-synthesizer",
    role="summarizer",
    focus="Aggregate debated findings into a structured approval-ready report.",
    responsibilities=[
        "Group debated findings by severity and review point.",
        "Track which agent first proposed each finding and who supported or challenged it.",
        "Produce the final debate report and approval recommendation.",
    ],
)

DEBATE_ROUNDS: list[DebateRound] = [
    DebateRound(
        round_id="independent_findings",
        name="Independent Findings",
        objective="Each reviewer inspects the project point independently and proposes findings without reading peer outputs.",
    ),
    DebateRound(
        round_id="cross_review",
        name="Cross Review",
        objective="Peer reviewers support, challenge, or refine each finding with evidence and hidden-risk analysis.",
    ),
    DebateRound(
        round_id="summary_resolution",
        name="Summary Resolution",
        objective="The synthesizer merges debated findings into a final structured decision for the project.",
    ),
]


from __future__ import annotations

from src.modes.code_review_mode.models import DebateRound, ReviewTeamMember


REVIEW_TEAM_MEMBERS: list[ReviewTeamMember] = [
    ReviewTeamMember(
        key="architecture",
        name="架构评审官",
        agent_key="code-architecture-reviewer",
        role="reviewer",
        focus="分层结构、依赖方向、模块边界以及长期可扩展性。",
        responsibilities=[
            "检查跨模块耦合和边界渗漏问题。",
            "指出架构债务、抽象漂移和职责归属混乱。",
            "给出在不破坏交付稳定性的前提下可执行的重构建议。",
        ],
    ),
    ReviewTeamMember(
        key="correctness",
        name="正确性评审官",
        agent_key="code-correctness-reviewer",
        role="reviewer",
        focus="逻辑正确性、状态流转、数据处理和边界条件安全。",
        responsibilities=[
            "检查控制流、分支逻辑和异常处理。",
            "识别状态不一致和错误前提假设。",
            "提出可落地的缺陷修复和校验保护措施。",
        ],
    ),
    ReviewTeamMember(
        key="security",
        name="安全评审官",
        agent_key="code-security-reviewer",
        role="reviewer",
        focus="凭据泄露、命令执行、不安全输入以及权限边界。",
        responsibilities=[
            "审查会触达 shell、网络、文件系统或敏感信息的执行路径。",
            "识别滥用路径、权限蔓延和不安全默认配置。",
            "提出可控且能明显缩小影响面的缓解措施。",
        ],
    ),
    ReviewTeamMember(
        key="testability",
        name="可测性评审官",
        agent_key="code-testability-reviewer",
        role="reviewer",
        focus="验证缺口、回归暴露面、Harness 适配度和可观测性覆盖。",
        responsibilities=[
            "检查行为是否可以被稳定断言和可靠回放。",
            "识别缺失的测试、缺失的追踪点和脆弱的验证路径。",
            "建议能快速提升信心的定向 Harness 补强方案。",
        ],
    ),
    ReviewTeamMember(
        key="maintainability",
        name="可维护性评审官",
        agent_key="code-maintainability-reviewer",
        role="reviewer",
        focus="可读性、重复逻辑、命名清晰度、配置卫生和运维简洁性。",
        responsibilities=[
            "指出重复逻辑和硬编码行为。",
            "审查命名、注释和局部复杂度热点。",
            "建议能持续降低维护成本的清理动作。",
        ],
    ),
]

SUMMARY_AGENT = ReviewTeamMember(
    key="synthesizer",
    name="总结审查官",
    agent_key="code-review-synthesizer",
    role="summarizer",
    focus="将辩论后的结论汇总成结构化、可审批的正式报告。",
    responsibilities=[
        "按照严重级别和审查点归类辩论结论。",
        "跟踪每条结论由哪个 agent 首提，以及谁支持或反驳。",
        "产出最终辩论报告和审批建议。",
    ],
)

DEBATE_ROUNDS: list[DebateRound] = [
    DebateRound(
        round_id="independent_findings",
        name="独立审查",
        objective="每位评审官独立审查项目范围，在不读取同伴输出的前提下提出初始结论。",
    ),
    DebateRound(
        round_id="cross_review",
        name="交叉攻防",
        objective="评审官基于证据对已有结论进行支持、质疑或修正，并补充隐患分析。",
    ),
    DebateRound(
        round_id="summary_resolution",
        name="总结裁决",
        objective="总结审查官汇总辩论后的结论，形成项目最终结构化裁决。",
    ),
]

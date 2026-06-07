"""Performance testing intake — conversational slot collection.

Manages the required/optional slots that must be filled before
execution can proceed. Generates follow-up questions when slots are missing.
"""
from __future__ import annotations

from typing import Any

from src.modes.performance_testing_mode.contracts import (
    REQUIRED_SLOTS,
    SLOT_AUTH,
    SLOT_DATA,
    SLOT_ENGINE,
    SLOT_RUN_INTENT,
    SLOT_SLA,
    SLOT_TARGET,
    SLOT_TARGET_CONFIRMED,
    SLOT_WORKLOAD,
)
from src.modes.performance_testing_mode.plan_state import PerfTestingRequestState


SLOT_QUESTIONS: dict[str, str] = {
    SLOT_TARGET: "请提供压测目标 URL（例如 https://api.example.com/v1/users）。",
    SLOT_WORKLOAD: (
        "请描述期望的负载模型：\n"
        "- 到达率模型（open）：指定目标 RPS，如 '100 rps 持续 60 秒'\n"
        "- 固定VU模型（closed）：指定并发用户数，如 '50 个用户持续 2 分钟'\n"
        "或者直接描述场景，如 '模拟 500 用户同时下单'"
    ),
    SLOT_RUN_INTENT: (
        "本次压测的意图是什么？\n"
        "- probe：探测当前系统基线性能（无 pass/fail 判定）\n"
        "- regression：回归验证，对比基线并判定是否达标"
    ),
    SLOT_TARGET_CONFIRMED: (
        "即将对以上目标发起压测，请确认：\n"
        "1. 目标环境是否为测试/预发布环境（非生产）？\n"
        "2. 是否已知晓压测可能产生的负载影响？\n"
        '请回复"确认"以继续。'
    ),
}

OPTIONAL_SLOT_QUESTIONS: dict[str, str] = {
    SLOT_SLA: "是否有 SLA 要求？（如 P95 < 200ms，错误率 < 1%，最低吞吐 > 500 tps）",
    SLOT_AUTH: "目标是否需要认证？请提供 token 或认证方式说明。",
    SLOT_DATA: "是否需要参数化数据？（如用户列表 CSV、商品 ID 池）",
    SLOT_ENGINE: "使用哪个引擎？（默认 k6，也支持 jmeter）",
}


def check_slots_ready(state: PerfTestingRequestState) -> tuple[bool, set[str]]:
    """Check if all required slots are filled.

    Returns (all_ready, missing_slot_names).
    """
    filled = state.filled_slots or {}
    missing = REQUIRED_SLOTS - set(filled.keys())
    return len(missing) == 0, missing


def generate_next_questions(
    state: PerfTestingRequestState,
    max_questions: int = 2,
) -> list[dict[str, str]]:
    """Generate the next batch of questions for unfilled slots."""
    filled = state.filled_slots or {}
    missing = REQUIRED_SLOTS - set(filled.keys())

    questions: list[dict[str, str]] = []

    priority_order = [SLOT_TARGET, SLOT_WORKLOAD, SLOT_RUN_INTENT, SLOT_TARGET_CONFIRMED]
    for slot in priority_order:
        if slot in missing and len(questions) < max_questions:
            if slot == SLOT_TARGET_CONFIRMED and SLOT_TARGET not in filled:
                continue
            questions.append({"slot": slot, "question": SLOT_QUESTIONS[slot]})

    return questions


def build_plan_summary(state: PerfTestingRequestState) -> str:
    """Build a readable summary of collected slots for confirmation."""
    filled = state.filled_slots or {}
    lines = ["## 压测计划摘要\n"]

    if SLOT_TARGET in filled:
        lines.append(f"- **目标**: {filled[SLOT_TARGET]}")
    if SLOT_WORKLOAD in filled:
        lines.append(f"- **负载**: {filled[SLOT_WORKLOAD]}")
    if SLOT_RUN_INTENT in filled:
        lines.append(f"- **意图**: {filled[SLOT_RUN_INTENT]}")
    if SLOT_SLA in filled:
        lines.append(f"- **SLA**: {filled[SLOT_SLA]}")
    if SLOT_AUTH in filled:
        lines.append(f"- **认证**: {filled[SLOT_AUTH]}")
    if SLOT_ENGINE in filled:
        lines.append(f"- **引擎**: {filled[SLOT_ENGINE]}")

    return "\n".join(lines)


def extract_slot_from_response(
    slot_name: str,
    user_message: str,
    current_state: PerfTestingRequestState,
) -> Any | None:
    """Attempt to extract a slot value from user's natural language response.

    Returns the extracted value or None if not determinable.
    """
    msg = user_message.strip().lower()

    if slot_name == SLOT_TARGET_CONFIRMED:
        confirm_keywords = {"确认", "confirm", "是", "yes", "好", "ok", "同意", "继续"}
        if any(kw in msg for kw in confirm_keywords):
            return True
        return None

    if slot_name == SLOT_RUN_INTENT:
        if "probe" in msg or "探测" in msg or "基线" in msg:
            return "probe"
        if "regression" in msg or "回归" in msg or "验证" in msg:
            return "regression"
        return None

    return user_message.strip() if user_message.strip() else None

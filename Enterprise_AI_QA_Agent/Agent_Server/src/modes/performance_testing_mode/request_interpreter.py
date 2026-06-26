"""Performance request interpreter.

Extracts target URL, QPS, duration, thresholds, and other parameters
from natural language input using regex/heuristic matching.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from src.modes.performance_testing_mode.contracts import (
    SLOT_ENGINE,
    SLOT_RUN_INTENT,
    SLOT_SLA,
    SLOT_TARGET,
    SLOT_TARGET_CONFIRMED,
    SLOT_WORKLOAD,
)


@dataclass
class InterpretedSlots:
    slots: dict[str, Any] = field(default_factory=dict)
    confidence: float = 0.0


_URL_PATTERN = re.compile(
    r"(https?://[^\s,，、\]\)）》]+)", re.IGNORECASE
)

_QPS_PATTERNS = [
    re.compile(r"(\d+)\s*(?:rps|qps|req/s|请求/秒)", re.IGNORECASE),
    re.compile(r"(?:到达率|arrival.?rate|rate)\s*[:：]?\s*(\d+)", re.IGNORECASE),
]

_VU_PATTERNS = [
    re.compile(r"(\d+)\s*(?:个?(?:用户|并发|VU|vus|virtual.?users?))", re.IGNORECASE),
    re.compile(r"(?:并发|concurrency|vus?)\s*[:：]?\s*(\d+)", re.IGNORECASE),
]

_DURATION_PATTERNS = [
    re.compile(r"(\d+)\s*(?:秒|s|seconds?)", re.IGNORECASE),
    re.compile(r"(\d+)\s*(?:分钟|分|min|minutes?)", re.IGNORECASE),
]

_P95_PATTERN = re.compile(r"[pP]95\s*[<<=]\s*(\d+(?:\.\d+)?)\s*(?:ms)?", re.IGNORECASE)
_P99_PATTERN = re.compile(r"[pP]99\s*[<<=]\s*(\d+(?:\.\d+)?)\s*(?:ms)?", re.IGNORECASE)
_ERROR_RATE_PATTERN = re.compile(
    r"(?:错误率|error.?rate)\s*[<<=]\s*(\d+(?:\.\d+)?)\s*%?", re.IGNORECASE
)


class PerfRequestInterpreter:
    """Heuristic interpreter that pre-fills slots from user messages."""

    def interpret(self, message: str) -> InterpretedSlots:
        result = InterpretedSlots()
        filled_count = 0

        url = self._extract_url(message)
        if url:
            result.slots[SLOT_TARGET] = url
            filled_count += 1

        workload = self._extract_workload(message)
        if workload:
            result.slots[SLOT_WORKLOAD] = workload
            filled_count += 1

        intent = self._extract_intent(message)
        if intent:
            result.slots[SLOT_RUN_INTENT] = intent
            filled_count += 1

        sla = self._extract_sla(message)
        if sla:
            result.slots[SLOT_SLA] = sla
            filled_count += 1

        engine = self._extract_engine(message)
        if engine:
            result.slots[SLOT_ENGINE] = engine

        result.confidence = min(filled_count / 3.0, 1.0)
        return result

    def _extract_url(self, message: str) -> str | None:
        match = _URL_PATTERN.search(message)
        return match.group(1).rstrip("。.，,") if match else None

    def _extract_workload(self, message: str) -> str | None:
        parts: list[str] = []

        for pat in _QPS_PATTERNS:
            m = pat.search(message)
            if m:
                parts.append(f"rate={m.group(1)}rps")
                break

        for pat in _VU_PATTERNS:
            m = pat.search(message)
            if m:
                parts.append(f"vus={m.group(1)}")
                break

        duration = self._extract_duration_seconds(message)
        if duration:
            parts.append(f"duration={duration}s")

        return " ".join(parts) if parts else None

    def _extract_duration_seconds(self, message: str) -> int | None:
        for pat in _DURATION_PATTERNS:
            m = pat.search(message)
            if m:
                val = int(m.group(1))
                if "分" in pat.pattern or "min" in pat.pattern.lower():
                    return val * 60
                return val
        return None

    def _extract_intent(self, message: str) -> str | None:
        msg = message.lower()
        if any(kw in msg for kw in ["回归", "regression", "验证", "对比基线"]):
            return "regression"
        if any(kw in msg for kw in ["探测", "probe", "基线", "baseline", "摸底"]):
            return "probe"
        return None

    def _extract_sla(self, message: str) -> str | None:
        parts: list[str] = []

        m = _P95_PATTERN.search(message)
        if m:
            parts.append(f"p95<{m.group(1)}ms")

        m = _P99_PATTERN.search(message)
        if m:
            parts.append(f"p99<{m.group(1)}ms")

        m = _ERROR_RATE_PATTERN.search(message)
        if m:
            parts.append(f"error_rate<{m.group(1)}%")

        return ", ".join(parts) if parts else None

    def _extract_engine(self, message: str) -> str | None:
        msg = message.lower()
        if "jmeter" in msg or "jemter" in msg:
            return "jmeter"
        if "k6" in msg:
            return "k6"
        return None

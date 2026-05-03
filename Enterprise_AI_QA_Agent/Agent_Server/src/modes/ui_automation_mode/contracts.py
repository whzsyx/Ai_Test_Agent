from __future__ import annotations

from typing import Any


UI_AUTOMATION_BOSS = {
    "key": "qa_agent",
    "label": "QA_Agent",
    "role": "boss",
    "summary": "The project-level owner that gates knowledge sufficiency, delegates direction work, and persists results.",
}

UI_AUTOMATION_DIRECTIONS: list[dict[str, Any]] = [
    {
        "key": "browser",
        "label": "浏览器",
        "leader": "浏览器组长",
        "summary": "Web browser exploration and UI execution.",
        "available": True,
        "current_employee_runtime": "Legacy UIExplorationService + python_playwright_cli",
    },
    {
        "key": "mini_program",
        "label": "小程序",
        "leader": "小程序组长",
        "summary": "Mini program exploration and task execution.",
        "available": False,
        "current_employee_runtime": "reserved",
    },
    {
        "key": "android",
        "label": "安卓手机",
        "leader": "安卓组长",
        "summary": "Android UI exploration and task execution.",
        "available": False,
        "current_employee_runtime": "reserved",
    },
    {
        "key": "ios",
        "label": "苹果手机",
        "leader": "苹果组长",
        "summary": "iOS UI exploration and task execution.",
        "available": False,
        "current_employee_runtime": "reserved",
    },
    {
        "key": "harmonyos",
        "label": "鸿蒙手机",
        "leader": "鸿蒙组长",
        "summary": "HarmonyOS UI exploration and task execution.",
        "available": False,
        "current_employee_runtime": "reserved",
    },
]

UI_AUTOMATION_SUBDIRECTIONS: list[dict[str, Any]] = [
    {
        "key": "information_exploration",
        "label": "信息探索",
        "employee": "信息探索员工",
        "summary": "Explore the project, collect page relations, and persist interaction knowledge.",
        "available": True,
    },
    {
        "key": "test_execution",
        "label": "测试执行",
        "employee": "测试执行员工",
        "summary": "Generate executable test tasks and run them against the explored project.",
        "available": False,
    },
]


def direction_option(direction_key: str) -> dict[str, Any] | None:
    for item in UI_AUTOMATION_DIRECTIONS:
        if str(item.get("key") or "").strip() == direction_key:
            return dict(item)
    return None


def subdirection_option(subdirection_key: str) -> dict[str, Any] | None:
    for item in UI_AUTOMATION_SUBDIRECTIONS:
        if str(item.get("key") or "").strip() == subdirection_key:
            return dict(item)
    return None

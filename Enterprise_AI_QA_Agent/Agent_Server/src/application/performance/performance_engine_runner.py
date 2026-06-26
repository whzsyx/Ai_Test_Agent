"""Unified performance engine runner entry point.

Per design doc section 10.2.4: unified entry that internally resolves
to k6 or jmeter via the image resolver, then delegates to PerfRunnerService.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any

from src.application.images.image_resolver import ImageResolver
from src.core.config import Settings
from src.modes.performance_testing_mode.plan_state import PerfPlan


@dataclass
class PerfEngineRunnerResult:
    ok: bool
    engine: str = ""
    scenario: str = ""
    selected_image_key: str = ""
    selected_image: str = ""
    reason: str = ""
    run_id: str = ""
    status: str = ""
    fallback_used: bool = False

    def model_dump(self) -> dict[str, Any]:
        return asdict(self)


class PerformanceEngineRunner:
    """Resolve engine image and delegate execution to PerfRunnerService."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._resolver = ImageResolver()

    def select_engine(
        self,
        *,
        engine: str,
        scenario: str = "api_baseline",
    ) -> PerfEngineRunnerResult:
        resolution = self._resolver.resolve_for_engine(engine)
        if not resolution.ok:
            return PerfEngineRunnerResult(
                ok=False,
                engine=engine,
                scenario=scenario,
                reason=f"image_unavailable: {resolution.reason}",
            )

        return PerfEngineRunnerResult(
            ok=True,
            engine=engine,
            scenario=scenario,
            selected_image_key=resolution.selected_image_key,
            selected_image=resolution.selected_image,
            reason=resolution.reason,
        )

    def validate_plan_engine(self, plan: PerfPlan) -> PerfEngineRunnerResult:
        scenario = "complex_flow" if plan.engine == "jmeter" else "api_baseline"
        return self.select_engine(engine=plan.engine, scenario=scenario)

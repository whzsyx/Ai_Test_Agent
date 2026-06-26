"""Image resolver: maps high-level capability intent to concrete images.

The model never picks raw image strings. It expresses intent via
scenario/engine/helper_need, and this resolver returns the best
catalog entry plus structured reasoning.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from src.application.images.image_catalog import CatalogImageEntry, ImageCatalog


@dataclass
class ImageResolutionResult:
    """Structured result of image resolution."""

    ok: bool
    selected_image_key: str = ""
    selected_image: str = ""
    scenario: str = ""
    engine: str = ""
    reason: str = ""
    error_category: str = ""
    fallback_candidates: list[dict[str, Any]] = field(default_factory=list)
    fallback_used: bool = False
    domain: str = ""

    def model_dump(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "selected_image_key": self.selected_image_key,
            "selected_image": self.selected_image,
            "scenario": self.scenario,
            "engine": self.engine,
            "reason": self.reason,
            "error_category": self.error_category,
            "fallback_candidates": list(self.fallback_candidates),
            "fallback_used": self.fallback_used,
            "domain": self.domain,
        }


class ImageResolver:
    """Resolves scenario + engine intent into a concrete catalog image."""

    def __init__(self, catalog: ImageCatalog | None = None) -> None:
        self._catalog = catalog or ImageCatalog()

    @property
    def catalog(self) -> ImageCatalog:
        return self._catalog

    def resolve_image(
        self,
        *,
        domain: str = "performance",
        scenario: str,
        engine: str | None = None,
        helper_need: str | None = None,
        prefer_keys: list[str] | None = None,
        allow_fallback: bool = True,
    ) -> ImageResolutionResult:
        if helper_need:
            return self._resolve_helper(helper_need, scenario, allow_fallback)

        effective_domain = domain
        if engine:
            effective_domain = "performance"

        candidates = self._catalog.find_by_scenario(
            scenario,
            domain=effective_domain,
            engine=engine,
        )

        if prefer_keys:
            preferred = [c for c in candidates if c.image_key in prefer_keys]
            if preferred:
                candidates = preferred

        if not candidates:
            fallbacks = self._catalog.find_fallbacks(f"perf_{engine}_default") if engine else []
            if allow_fallback and fallbacks:
                selected = fallbacks[0]
                return ImageResolutionResult(
                    ok=True,
                    selected_image_key=selected.image_key,
                    selected_image=selected.image,
                    scenario=scenario,
                    engine=engine or "",
                    reason=f"fallback used: {selected.image_key} (primary image unavailable)",
                    fallback_used=True,
                    domain=selected.domain,
                )
            return ImageResolutionResult(
                ok=False,
                scenario=scenario,
                engine=engine or "",
                error_category="image_unavailable",
                reason=f"image_unavailable: no catalog image matches scenario={scenario}, engine={engine}, domain={effective_domain}",
            )

        selected = candidates[0]
        fallback_list = [
            self._entry_to_summary(e) for e in candidates[1:]
        ] if allow_fallback else []

        actual_fallbacks = fallback_list
        if allow_fallback:
            for fe in self._catalog.find_fallbacks(selected.image_key):
                actual_fallbacks.append(self._entry_to_summary(fe))

        return ImageResolutionResult(
            ok=True,
            selected_image_key=selected.image_key,
            selected_image=selected.image,
            scenario=scenario,
            engine=engine or "",
            reason=self._build_reason(selected, scenario, engine),
            fallback_candidates=actual_fallbacks,
            domain=selected.domain,
        )

    def resolve_for_engine(self, engine: str) -> ImageResolutionResult:
        scenario = "api_baseline" if engine == "k6" else "complex_flow"
        return self.resolve_image(
            domain="performance",
            scenario=scenario,
            engine=engine,
        )

    def resolve_by_key(self, image_key: str) -> ImageResolutionResult:
        entry = self._catalog.get(image_key)
        if not entry or not entry.enabled:
            return ImageResolutionResult(
                ok=False,
                selected_image_key=image_key,
                error_category="image_unavailable",
                reason=f"image_unavailable: catalog image key not found or disabled: {image_key}",
            )
        engine = entry.engine_keys[0] if entry.engine_keys else ""
        scenario = entry.scenarios[0] if entry.scenarios else ""
        return ImageResolutionResult(
            ok=True,
            selected_image_key=entry.image_key,
            selected_image=entry.image,
            scenario=scenario,
            engine=engine,
            reason=f"selected {entry.image_key} by configured image_key",
            fallback_candidates=[self._entry_to_summary(e) for e in self._catalog.find_fallbacks(entry.image_key)],
            domain=entry.domain,
        )

    def _resolve_helper(
        self,
        helper_need: str,
        scenario: str,
        allow_fallback: bool,
    ) -> ImageResolutionResult:
        candidates = self._catalog.find_by_scenario(
            helper_need,
            domain="helper",
        )

        if not candidates:
            candidates = self._catalog.list_entries(domain="helper")

        if not candidates:
            return ImageResolutionResult(
                ok=False,
                scenario=scenario,
                error_category="image_unavailable",
                reason=f"image_unavailable: no helper image found for need={helper_need}",
            )

        selected = candidates[0]
        return ImageResolutionResult(
            ok=True,
            selected_image_key=selected.image_key,
            selected_image=selected.image,
            scenario=helper_need,
            reason=f"helper image selected for {helper_need}",
            fallback_candidates=[
                self._entry_to_summary(e) for e in candidates[1:]
            ] if allow_fallback else [],
            domain="helper",
        )

    @staticmethod
    def _build_reason(entry: CatalogImageEntry, scenario: str, engine: str | None) -> str:
        parts = [f"selected {entry.image_key}"]
        if engine:
            parts.append(f"for engine={engine}")
        parts.append(f"matching scenario={scenario}")
        return " ".join(parts)

    @staticmethod
    def _entry_to_summary(entry: CatalogImageEntry) -> dict[str, Any]:
        return {
            "image_key": entry.image_key,
            "image": entry.image,
            "priority": entry.priority,
        }

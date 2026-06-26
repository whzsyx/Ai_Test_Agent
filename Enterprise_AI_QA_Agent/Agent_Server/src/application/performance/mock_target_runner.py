"""Mock target runner using http-echo image for local link verification.

Per design doc section 10.2.3: local mock target, circuit validation.
"""
from __future__ import annotations

import asyncio
import subprocess
import uuid
from dataclasses import dataclass, asdict
from typing import Any

from src.application.images.image_resolver import ImageResolver
from src.core.config import Settings


@dataclass
class MockTargetResult:
    ok: bool
    action: str
    container_name: str = ""
    port: int = 0
    response_text: str = ""
    selected_image_key: str = ""
    selected_image: str = ""
    scenario: str = "local_link_verify"
    reason: str = ""
    stdout: str = ""
    stderr: str = ""
    fallback_used: bool = False

    def model_dump(self) -> dict[str, Any]:
        return asdict(self)


class MockTargetRunner:
    """Start and stop mock HTTP echo targets for link verification."""

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings
        self._resolver = ImageResolver()

    async def start(
        self,
        *,
        port: int = 18080,
        response_text: str = "ok",
    ) -> MockTargetResult:
        resolution = self._resolver.resolve_image(
            domain="helper",
            scenario="local_link_verify",
            helper_need="mock_target",
        )

        if not resolution.ok:
            return MockTargetResult(
                ok=False,
                action="start",
                port=port,
                response_text=response_text,
                reason=f"image_unavailable: {resolution.reason}",
            )

        container_name = f"qa-perf-mock-{uuid.uuid4().hex[:8]}"
        docker_cmd = [
            "docker", "run", "-d",
            "--name", container_name,
            "--label", "enterprise-ai-qa-agent=performance",
            "--label", "performance-engine=helper",
            "-p", f"{port}:5678",
            resolution.selected_image,
            "-text", response_text,
        ]

        try:
            proc = await asyncio.to_thread(
                subprocess.run,
                docker_cmd,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=30,
            )
        except Exception as e:
            return MockTargetResult(
                ok=False,
                action="start",
                container_name=container_name,
                port=port,
                response_text=response_text,
                selected_image_key=resolution.selected_image_key,
                selected_image=resolution.selected_image,
                reason=f"mock_target_start_failed: {e}",
            )

        ok = proc.returncode == 0
        return MockTargetResult(
            ok=ok,
            action="start",
            container_name=container_name,
            port=port,
            response_text=response_text,
            selected_image_key=resolution.selected_image_key,
            selected_image=resolution.selected_image,
            reason=f"mock target started on port {port}" if ok else f"mock target start failed: {proc.stderr[:500]}",
            stdout=proc.stdout[:2000],
            stderr=proc.stderr[:2000],
        )

    async def stop(self, *, container_name: str) -> MockTargetResult:
        try:
            proc = await asyncio.to_thread(
                subprocess.run,
                ["docker", "rm", "-f", container_name],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=15,
            )
        except Exception as e:
            return MockTargetResult(
                ok=False,
                action="stop",
                container_name=container_name,
                reason=f"mock_target_stop_failed: {e}",
            )

        ok = proc.returncode == 0
        return MockTargetResult(
            ok=ok,
            action="stop",
            container_name=container_name,
            reason=f"mock target stopped: {container_name}" if ok else f"mock target stop failed",
            stdout=proc.stdout[:2000],
            stderr=proc.stderr[:2000],
        )

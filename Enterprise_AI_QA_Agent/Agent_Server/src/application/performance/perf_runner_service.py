"""Performance runner service.

Manages backend detection (local/docker), container lifecycle,
smoke validation, concurrency gating, and execution orchestration.
"""
from __future__ import annotations

import asyncio
import json
import shutil
import subprocess
import tempfile
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from src.core.config import Settings
from src.modes.performance_testing_mode.plan_state import PerfPlan, PerfRun, SmokeResult
from .engine_adapter import EngineCommand, PerfEngineAdapter, RawMetrics, RunOptions, ScriptArtifact


@dataclass
class ExecutionResult:
    exit_code: int
    stdout: str
    stderr: str
    summary_json: str = ""
    timed_out: bool = False


class PerfRunnerService:
    """Orchestrates performance test execution with backend detection and safety gates."""

    def __init__(self, settings: Settings):
        self._settings = settings
        self._semaphore = asyncio.Semaphore(settings.performance_max_concurrent_runs)
        self._container_prefix = settings.performance_runner_docker_container_prefix
        self._workdir = settings.performance_runner_docker_workdir
        self._ephemeral = settings.performance_runner_ephemeral

    def detect_backend(self) -> str:
        configured = self._settings.performance_runner_backend
        if configured != "auto":
            return configured

        if shutil.which("k6"):
            return "local"
        if shutil.which("docker"):
            return "docker"
        raise RuntimeError(
            "无法探测到可用的压测后端。\n"
            "以下任一工具：\n"
            "  - k6: https://grafana.com/docs/k6/latest/set-up/install-k6/\n"
            "  - Docker: https://docs.docker.com/get-docker/\n"
            "或在配置中设置 PERFORMANCE_RUNNER_BACKEND=local|docker"
        )

    async def execute(
        self,
        plan: PerfPlan,
        script: ScriptArtifact,
        run_opts: RunOptions,
        engine_adapter: PerfEngineAdapter,
    ) -> PerfRun:
        backend = self.detect_backend()
        run_id = f"perf-run-{uuid.uuid4().hex[:8]}"
        container_name = f"{self._container_prefix}-{run_id}"

        run = PerfRun(
            run_id=run_id,
            plan_id=plan.plan_id,
            engine=plan.engine,
            backend=backend,
            container_or_cluster=container_name if backend == "docker" else "local",
            status="running",
            started_at=datetime.utcnow().isoformat(),
        )

        async with self._semaphore:
            try:
                cmd = engine_adapter.run_command(script, run_opts)
                if backend == "docker":
                    result = await self._run_in_docker(cmd, script, container_name, run_opts.timeout_seconds)
                else:
                    result = await self._run_local(cmd, script, run_opts.timeout_seconds)

                run.exit_code = result.exit_code
                run.stdout_tail = result.stdout[-2000:] if result.stdout else ""
                run.status = "timed_out" if result.timed_out else ("completed" if result.exit_code == 0 else "failed")

                if result.summary_json:
                    run.result_artifact = f"inline:summary.json"
                    raw_metrics = engine_adapter.parse_results(result.summary_json)
                    run.engine_thresholds = raw_metrics.thresholds

            except Exception as e:
                run.status = "failed"
                run.stdout_tail = str(e)
            finally:
                run.completed_at = datetime.utcnow().isoformat()
                if backend == "docker" and self._ephemeral:
                    await self._cleanup_container(container_name)

        return run

    async def run_smoke(
        self,
        plan: PerfPlan,
        script: ScriptArtifact,
        engine_adapter: PerfEngineAdapter,
    ) -> SmokeResult:
        smoke_opts = engine_adapter.build_smoke_options(plan)
        backend = self.detect_backend()
        container_name = f"{self._container_prefix}-smoke-{uuid.uuid4().hex[:6]}"

        try:
            cmd = engine_adapter.run_command(script, smoke_opts)
            if backend == "docker":
                result = await self._run_in_docker(cmd, script, container_name, smoke_opts.timeout_seconds)
            else:
                result = await self._run_local(cmd, script, smoke_opts.timeout_seconds)

            return self._validate_smoke(result, plan)
        except Exception as e:
            return SmokeResult(passed=False, detail=f"冒烟执行异常: {e}")
        finally:
            if backend == "docker" and self._ephemeral:
                await self._cleanup_container(container_name)

    def _validate_smoke(self, result: ExecutionResult, plan: PerfPlan) -> SmokeResult:
        if result.timed_out:
            return SmokeResult(passed=False, detail="冒烟验证超时")

        if result.exit_code != 0 and not result.summary_json:
            return SmokeResult(
                passed=False,
                detail=f"冒烟执行失败 (exit_code={result.exit_code}): {result.stderr[:500]}",
            )

        checked_status: list[int] = []
        extracted: dict[str, bool] = {}

        if result.summary_json:
            try:
                data = json.loads(result.summary_json)
                metrics = data.get("metrics", {})
                http_reqs = metrics.get("http_reqs", {})
                values = http_reqs.get("values", {}) if isinstance(http_reqs.get("values"), dict) else {}
                count = int(values.get("count", 0))
                failed_rate = float(
                    metrics.get("http_req_failed", {}).get("values", {}).get("rate", 1)
                    if isinstance(metrics.get("http_req_failed", {}).get("values"), dict) else 1
                )

                if count == 0:
                    return SmokeResult(passed=False, detail="冒烟验证无请求完成")

                if failed_rate > 0.5:
                    return SmokeResult(
                        passed=False,
                        checked_status=checked_status,
                        detail=f"冒烟验证失败率过高: {failed_rate*100:.0f}%（预期状态码可能不匹配）",
                    )
            except (json.JSONDecodeError, TypeError, KeyError):
                pass

        for var in plan.smoke.expect_extract:
            found = var.lower() in result.stdout.lower()
            extracted[var] = found
            if not found:
                return SmokeResult(
                    passed=False,
                    extracted=extracted,
                    detail=f"关联变量 '{var}' 未在响应中提取成功",
                )

        return SmokeResult(passed=True, checked_status=checked_status, extracted=extracted, detail="冒烟验证通过")

    async def _run_in_docker(
        self,
        cmd: EngineCommand,
        script: ScriptArtifact,
        container_name: str,
        timeout_seconds: int,
    ) -> ExecutionResult:
        with tempfile.TemporaryDirectory(prefix="perf-") as tmpdir:
            script_path = Path(tmpdir) / script.filename
            script_path.write_text(script.script_content, encoding="utf-8")

            summary_path = Path(tmpdir) / "summary.json"

            docker_cmd = [
                "docker", "run", "--rm",
                "--name", container_name,
                "-v", f"{tmpdir}:{cmd.workdir}",
            ]

            if cmd.cpus:
                docker_cmd.extend(["--cpus", cmd.cpus])
            if cmd.memory:
                docker_cmd.extend(["--memory", cmd.memory])

            for k, v in cmd.env.items():
                docker_cmd.extend(["-e", f"{k}={v}"])

            docker_cmd.append(cmd.image)
            docker_cmd.extend(cmd.command)

            try:
                proc = await asyncio.to_thread(
                    subprocess.run,
                    docker_cmd,
                    capture_output=True,
                    text=True,
                    timeout=timeout_seconds,
                )
                summary_json = ""
                if summary_path.exists():
                    summary_json = summary_path.read_text(encoding="utf-8")

                return ExecutionResult(
                    exit_code=proc.returncode,
                    stdout=proc.stdout or "",
                    stderr=proc.stderr or "",
                    summary_json=summary_json,
                )
            except subprocess.TimeoutExpired:
                await self._cleanup_container(container_name)
                return ExecutionResult(exit_code=-1, stdout="", stderr="timeout", timed_out=True)

    async def _run_local(
        self,
        cmd: EngineCommand,
        script: ScriptArtifact,
        timeout_seconds: int,
    ) -> ExecutionResult:
        with tempfile.TemporaryDirectory(prefix="perf-") as tmpdir:
            script_path = Path(tmpdir) / script.filename
            script_path.write_text(script.script_content, encoding="utf-8")

            local_cmd = []
            for part in cmd.command:
                local_cmd.append(part.replace("/work/", f"{tmpdir}/"))

            summary_path = Path(tmpdir) / "summary.json"

            env = dict(cmd.env)

            try:
                proc = await asyncio.to_thread(
                    subprocess.run,
                    local_cmd,
                    capture_output=True,
                    text=True,
                    timeout=timeout_seconds,
                    cwd=tmpdir,
                    env=None,
                )
                summary_json = ""
                if summary_path.exists():
                    summary_json = summary_path.read_text(encoding="utf-8")

                return ExecutionResult(
                    exit_code=proc.returncode,
                    stdout=proc.stdout or "",
                    stderr=proc.stderr or "",
                    summary_json=summary_json,
                )
            except subprocess.TimeoutExpired:
                return ExecutionResult(exit_code=-1, stdout="", stderr="timeout", timed_out=True)

    async def _cleanup_container(self, container_name: str) -> None:
        try:
            await asyncio.to_thread(
                subprocess.run,
                ["docker", "rm", "-f", container_name],
                capture_output=True,
                timeout=15,
            )
        except Exception:
            pass

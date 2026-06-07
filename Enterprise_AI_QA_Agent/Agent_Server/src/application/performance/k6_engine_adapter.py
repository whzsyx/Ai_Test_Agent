"""K6 engine adapter.

Translates PerfPlan into k6 JavaScript, builds container commands,
and parses k6 summary JSON into unified RawMetrics.
"""
from __future__ import annotations

import json
import re
from typing import Any

from src.modes.performance_testing_mode.plan_state import PerfPlan, PerfTarget, RampStage
from .engine_adapter import EngineCommand, PerfEngineAdapter, RawMetrics, RunOptions, ScriptArtifact


class K6EngineAdapter:
    """Default engine adapter using grafana/k6."""

    engine_key: str = "k6"
    default_image: str = "grafana/k6:latest"

    def __init__(self, image: str = "", rewrite_localhost: bool = True):
        self._image = image or self.default_image
        self._rewrite_localhost = rewrite_localhost

    def build_script(self, plan: PerfPlan) -> ScriptArtifact:
        lines: list[str] = []
        lines.append('import http from "k6/http";')
        lines.append('import { check, sleep } from "k6";')

        if plan.data_params:
            lines.append('import { SharedArray } from "k6/data";')
            lines.append('import papaparse from "https://jslib.k6.io/papaparse/5.1.1/index.js";')

        lines.append("")

        # Data CSV loading
        for dp in plan.data_params:
            safe_name = re.sub(r"[^a-zA-Z0-9_]", "_", dp.name)
            lines.append(f'const {safe_name}Data = new SharedArray("{dp.name}", function () {{')
            lines.append(f'  return papaparse.parse(open("/work/data/{dp.name}.csv"), {{ header: true }}).data;')
            lines.append("});")
            lines.append("")

        # Options block
        lines.append("export const options = {")
        lines.extend(self._build_options_block(plan))
        lines.append("};")
        lines.append("")

        # Default function
        lines.append("export default function () {")
        lines.extend(self._build_default_function(plan))
        lines.append("}")

        script_content = "\n".join(lines)
        data_files: dict[str, str] = {}
        for dp in plan.data_params:
            if dp.ref:
                data_files[f"data/{dp.name}.csv"] = dp.ref

        return ScriptArtifact(
            engine="k6",
            script_content=script_content,
            filename="script.js",
            data_files=data_files,
        )

    def run_command(self, script: ScriptArtifact, run_opts: RunOptions) -> EngineCommand:
        cmd = ["k6", "run", "--summary-export", run_opts.summary_export_path]
        if run_opts.is_smoke:
            cmd.extend(["--vus", str(run_opts.smoke_vus), "--iterations", str(run_opts.smoke_iterations)])
        cmd.extend(run_opts.extra_args)
        cmd.append(f"/work/{script.filename}")

        return EngineCommand(
            image=self._image,
            command=cmd,
            workdir="/work",
            env=run_opts.environment,
        )

    def parse_results(self, summary_json: str) -> RawMetrics:
        try:
            data = json.loads(summary_json)
        except (json.JSONDecodeError, TypeError):
            return RawMetrics()

        metrics = data.get("metrics", {})

        http_reqs = metrics.get("http_reqs", {})
        http_req_duration = metrics.get("http_req_duration", {})
        http_req_failed = metrics.get("http_req_failed", {})

        samples = int(http_reqs.get("values", {}).get("count", 0) if isinstance(http_reqs.get("values"), dict) else 0)
        duration_values = http_req_duration.get("values", {}) if isinstance(http_req_duration.get("values"), dict) else {}

        rate = http_reqs.get("values", {}).get("rate", 0) if isinstance(http_reqs.get("values"), dict) else 0

        failed_values = http_req_failed.get("values", {}) if isinstance(http_req_failed.get("values"), dict) else {}
        error_rate = float(failed_values.get("rate", 0))

        thresholds = {}
        root_thresholds = data.get("root_group", {}).get("checks", [])
        if "thresholds" in data:
            for k, v in data["thresholds"].items():
                thresholds[k] = v

        return RawMetrics(
            samples=samples,
            throughput_tps=float(rate),
            avg_ms=float(duration_values.get("avg", 0)),
            min_ms=float(duration_values.get("min", 0)),
            max_ms=float(duration_values.get("max", 0)),
            p50_ms=float(duration_values.get("med", 0)),
            p90_ms=float(duration_values.get("p(90)", 0)),
            p95_ms=float(duration_values.get("p(95)", 0)),
            p99_ms=float(duration_values.get("p(99)", 0)),
            error_rate=error_rate,
            error_count=int(samples * error_rate) if samples else 0,
            thresholds=thresholds,
            raw_data=data,
        )

    def build_smoke_options(self, plan: PerfPlan) -> RunOptions:
        return RunOptions(
            timeout_seconds=60,
            is_smoke=True,
            smoke_vus=plan.smoke.vus,
            smoke_iterations=plan.smoke.iterations,
        )

    def rewrite_target_url(self, url: str) -> str:
        if not self._rewrite_localhost:
            return url
        return re.sub(
            r"(https?://)(localhost|127\.0\.0\.1)",
            r"\1host.docker.internal",
            url,
        )

    # -----------------------------------------------------------------------
    # Private helpers
    # -----------------------------------------------------------------------

    def _build_options_block(self, plan: PerfPlan) -> list[str]:
        lines: list[str] = []
        wl = plan.workload

        if wl.model == "open":
            lines.append("  scenarios: {")
            lines.append("    load: {")
            if wl.mode == "constant_arrival_rate":
                lines.append('      executor: "constant-arrival-rate",')
                lines.append(f"      rate: {wl.target_rate_rps or 50},")
                lines.append('      timeUnit: "1s",')
                lines.append(f"      duration: \"{wl.hold_seconds}s\",")
                lines.append(f"      preAllocatedVUs: {wl.virtual_users or 100},")
                lines.append(f"      maxVUs: {plan.limits.max_vus},")
            else:
                lines.append('      executor: "ramping-arrival-rate",')
                lines.append('      timeUnit: "1s",')
                lines.append(f"      preAllocatedVUs: {wl.virtual_users or 100},")
                lines.append(f"      maxVUs: {plan.limits.max_vus},")
                lines.append("      stages: [")
                for stage in wl.ramp_stages:
                    lines.append(f'        {{ target: {stage.target}, duration: "{stage.duration}" }},')
                if not wl.ramp_stages:
                    target_rps = wl.target_rate_rps or 50
                    lines.append(f'        {{ target: {target_rps // 2}, duration: "{wl.hold_seconds // 3}s" }},')
                    lines.append(f'        {{ target: {target_rps}, duration: "{wl.hold_seconds // 3}s" }},')
                    lines.append(f'        {{ target: {target_rps}, duration: "{wl.hold_seconds // 3}s" }},')
                lines.append("      ],")
            lines.append("    },")
            lines.append("  },")
        else:
            if wl.mode == "ramping_vus" or wl.ramp_stages:
                lines.append("  stages: [")
                for stage in wl.ramp_stages:
                    lines.append(f'    {{ target: {stage.target}, duration: "{stage.duration}" }},')
                if not wl.ramp_stages:
                    vus = wl.virtual_users or 50
                    lines.append(f'    {{ target: {vus // 2}, duration: "{wl.hold_seconds // 3}s" }},')
                    lines.append(f'    {{ target: {vus}, duration: "{wl.hold_seconds // 3}s" }},')
                    lines.append(f'    {{ target: {vus}, duration: "{wl.hold_seconds // 3}s" }},')
                lines.append("  ],")
            else:
                lines.append(f"  vus: {wl.virtual_users or 50},")
                lines.append(f'  duration: "{wl.hold_seconds}s",')

        # Thresholds from SLA
        thresholds: dict[str, list[str]] = {}
        if plan.sla.p95_ms:
            thresholds.setdefault("http_req_duration", []).append(f"p(95)<{int(plan.sla.p95_ms)}")
        if plan.sla.p99_ms:
            thresholds.setdefault("http_req_duration", []).append(f"p(99)<{int(plan.sla.p99_ms)}")
        if plan.sla.error_rate is not None:
            thresholds["http_req_failed"] = [f"rate<{plan.sla.error_rate}"]

        if thresholds:
            lines.append("  thresholds: {")
            for metric, checks in thresholds.items():
                formatted = ", ".join(f'"{c}"' for c in checks)
                lines.append(f"    \"{metric}\": [{formatted}],")
            lines.append("  },")

        return lines

    def _build_default_function(self, plan: PerfPlan) -> list[str]:
        lines: list[str] = []
        indent = "  "

        # Data variable selection
        for dp in plan.data_params:
            safe_name = re.sub(r"[^a-zA-Z0-9_]", "_", dp.name)
            if dp.uniqueness == "per_iteration":
                lines.append(f"{indent}const {safe_name} = {safe_name}Data[__ITER % {safe_name}Data.length];")
            else:
                lines.append(f"{indent}const {safe_name} = {safe_name}Data[Math.floor(Math.random() * {safe_name}Data.length)];")

        # HTTP requests for each target
        for i, target in enumerate(plan.targets):
            url = self.rewrite_target_url(target.url)
            var_name = f"res{i}" if len(plan.targets) > 1 else "res"

            if target.method.upper() == "GET":
                lines.append(f'{indent}const {var_name} = http.get("{url}", {{')
            else:
                body = self._build_body_expr(target, plan)
                lines.append(f'{indent}const {var_name} = http.{target.method.lower()}("{url}", {body}, {{')

            # Headers
            if target.headers:
                lines.append(f"{indent}  headers: {json.dumps(target.headers)},")
            lines.append(f"{indent}}});")
            lines.append("")

            # Checks
            lines.append(f'{indent}check({var_name}, {{')
            lines.append(f'{indent}  "status is expected": (r) => r.status >= 200 && r.status < 400,')
            lines.append(f"{indent}}});")

            # Correlations (extract from response)
            for corr in plan.correlations:
                if corr.from_path:
                    lines.append(f'{indent}const {corr.extract} = {var_name}.json("{corr.from_path}");')

            lines.append("")

        # Think time
        if plan.workload.think_time_ms > 0:
            lines.append(f"{indent}sleep({plan.workload.think_time_ms / 1000});")

        return lines

    def _build_body_expr(self, target: PerfTarget, plan: PerfPlan) -> str:
        if target.body_template is None:
            return "null"
        if isinstance(target.body_template, str):
            return f"`{target.body_template}`"
        return f"JSON.stringify({json.dumps(target.body_template)})"

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from typing import Any

from src.core.config import Settings
from src.infrastructure.postgres_runtime import postgres_connect
from src.infrastructure.storage_utils import make_json_safe
from src.modes.smoke_testing_mode.contracts import (
    RegressionCandidateCase,
    SmokeExecutionPlan,
    SmokeRunResult,
)


class SmokeCatalogStore:
    """PostgreSQL catalog for MinIO-backed smoke plans and run history."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self.plan_table = "agent_smoke_plan_catalog"
        self.version_table = "agent_smoke_plan_versions"
        self.run_table = "agent_smoke_run_history"
        self.regression_table = "agent_smoke_regression_candidates"

    async def initialize(self) -> None:
        await asyncio.to_thread(self._initialize_sync)

    async def save_plan(self, plan: SmokeExecutionPlan) -> None:
        await asyncio.to_thread(self._save_plan_sync, plan)

    async def save_plan_version(
        self,
        plan: SmokeExecutionPlan,
        *,
        plan_uri: str,
        plan_md_uri: str,
        revision_reason: str = "",
        user_revision: str = "",
    ) -> None:
        await asyncio.to_thread(
            self._save_plan_version_sync,
            plan,
            plan_uri,
            plan_md_uri,
            revision_reason,
            user_revision,
        )

    async def get_plan_record(self, plan_id: str) -> dict[str, Any] | None:
        return await asyncio.to_thread(self._get_plan_record_sync, plan_id)

    async def save_run(self, result: SmokeRunResult) -> None:
        await asyncio.to_thread(self._save_run_sync, result)

    async def save_regression_candidates(self, items: list[RegressionCandidateCase]) -> None:
        await asyncio.to_thread(self._save_regression_candidates_sync, items)

    def _initialize_sync(self) -> None:
        with postgres_connect(self._settings) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    CREATE TABLE IF NOT EXISTS {self.plan_table} (
                        plan_id TEXT PRIMARY KEY,
                        project_scope TEXT NOT NULL,
                        target_url TEXT NOT NULL DEFAULT '',
                        title TEXT NOT NULL DEFAULT '',
                        status TEXT NOT NULL DEFAULT '',
                        current_version INTEGER NOT NULL DEFAULT 1,
                        approved_version INTEGER NULL,
                        selected_case_count INTEGER NOT NULL DEFAULT 0,
                        total_case_count INTEGER NOT NULL DEFAULT 0,
                        last_run_status TEXT NOT NULL DEFAULT '',
                        last_run_at TIMESTAMPTZ NULL,
                        plan_uri TEXT NOT NULL DEFAULT '',
                        approved_plan_uri TEXT NOT NULL DEFAULT '',
                        run_result_uri TEXT NOT NULL DEFAULT '',
                        report_uri TEXT NOT NULL DEFAULT '',
                        created_by_session_id TEXT NOT NULL DEFAULT '',
                        metadata JSONB NOT NULL DEFAULT '{{}}'::jsonb,
                        created_at TIMESTAMPTZ NOT NULL,
                        updated_at TIMESTAMPTZ NOT NULL
                    )
                    """
                )
                cur.execute(
                    f"""
                    CREATE TABLE IF NOT EXISTS {self.version_table} (
                        id TEXT PRIMARY KEY,
                        plan_id TEXT NOT NULL,
                        version INTEGER NOT NULL,
                        revision_reason TEXT NOT NULL DEFAULT '',
                        user_revision TEXT NOT NULL DEFAULT '',
                        plan_uri TEXT NOT NULL DEFAULT '',
                        plan_md_uri TEXT NOT NULL DEFAULT '',
                        case_count INTEGER NOT NULL DEFAULT 0,
                        selected_case_count INTEGER NOT NULL DEFAULT 0,
                        risk_summary JSONB NOT NULL DEFAULT '{{}}'::jsonb,
                        created_at TIMESTAMPTZ NOT NULL,
                        UNIQUE(plan_id, version)
                    )
                    """
                )
                cur.execute(
                    f"""
                    CREATE TABLE IF NOT EXISTS {self.run_table} (
                        run_id TEXT PRIMARY KEY,
                        plan_id TEXT NOT NULL,
                        plan_version INTEGER NOT NULL,
                        project_scope TEXT NOT NULL DEFAULT '',
                        status TEXT NOT NULL DEFAULT '',
                        verdict TEXT NOT NULL DEFAULT '',
                        total_cases INTEGER NOT NULL DEFAULT 0,
                        passed_cases INTEGER NOT NULL DEFAULT 0,
                        failed_cases INTEGER NOT NULL DEFAULT 0,
                        blocked_cases INTEGER NOT NULL DEFAULT 0,
                        started_at TIMESTAMPTZ NOT NULL,
                        completed_at TIMESTAMPTZ NULL,
                        run_result_uri TEXT NOT NULL DEFAULT '',
                        report_uri TEXT NOT NULL DEFAULT '',
                        evidence_manifest_uri TEXT NOT NULL DEFAULT '',
                        metadata JSONB NOT NULL DEFAULT '{{}}'::jsonb
                    )
                    """
                )
                cur.execute(
                    f"""
                    CREATE TABLE IF NOT EXISTS {self.regression_table} (
                        case_id TEXT PRIMARY KEY,
                        source_plan_id TEXT NOT NULL,
                        source_run_id TEXT NOT NULL DEFAULT '',
                        project_scope TEXT NOT NULL DEFAULT '',
                        case_type TEXT NOT NULL DEFAULT '',
                        title TEXT NOT NULL DEFAULT '',
                        case_uri TEXT NOT NULL DEFAULT '',
                        stability_score DOUBLE PRECISION NOT NULL DEFAULT 0,
                        status TEXT NOT NULL DEFAULT '',
                        run_count INTEGER NOT NULL DEFAULT 0,
                        pass_count INTEGER NOT NULL DEFAULT 0,
                        fail_count INTEGER NOT NULL DEFAULT 0,
                        flaky_count INTEGER NOT NULL DEFAULT 0,
                        blocked_count INTEGER NOT NULL DEFAULT 0,
                        last_status TEXT NOT NULL DEFAULT '',
                        last_passed_at TIMESTAMPTZ NULL,
                        updated_at TIMESTAMPTZ NOT NULL
                    )
                    """
                )
                cur.execute(f"CREATE INDEX IF NOT EXISTS idx_{self.plan_table}_project_updated ON {self.plan_table} (project_scope, updated_at DESC)")
                cur.execute(f"CREATE INDEX IF NOT EXISTS idx_{self.run_table}_plan_started ON {self.run_table} (plan_id, started_at DESC)")

    def _save_plan_sync(self, plan: SmokeExecutionPlan) -> None:
        now = datetime.now(timezone.utc)
        selected_count = sum(1 for item in plan.cases if item.selected)
        plan_uri = plan.minio_uris.get(f"plan.v{plan.version}.json") or plan.minio_uris.get("plan_uri") or ""
        approved_uri = plan.minio_uris.get("approved_plan_uri") or ""
        with postgres_connect(self._settings) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    INSERT INTO {self.plan_table} (
                        plan_id, project_scope, target_url, title, status, current_version,
                        approved_version, selected_case_count, total_case_count, plan_uri,
                        approved_plan_uri, created_by_session_id, metadata, created_at, updated_at
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s,
                        %s, %s, %s, %s,
                        %s, %s, %s::jsonb, %s, %s
                    )
                    ON CONFLICT (plan_id) DO UPDATE SET
                        project_scope = EXCLUDED.project_scope,
                        target_url = EXCLUDED.target_url,
                        title = EXCLUDED.title,
                        status = EXCLUDED.status,
                        current_version = EXCLUDED.current_version,
                        approved_version = COALESCE(EXCLUDED.approved_version, {self.plan_table}.approved_version),
                        selected_case_count = EXCLUDED.selected_case_count,
                        total_case_count = EXCLUDED.total_case_count,
                        plan_uri = EXCLUDED.plan_uri,
                        approved_plan_uri = COALESCE(NULLIF(EXCLUDED.approved_plan_uri, ''), {self.plan_table}.approved_plan_uri),
                        metadata = EXCLUDED.metadata,
                        updated_at = EXCLUDED.updated_at
                    """,
                    (
                        plan.plan_id,
                        plan.project_scope,
                        plan.target_url,
                        plan.title,
                        plan.status,
                        plan.version,
                        plan.version if plan.status == "approved_for_execution" else None,
                        selected_count,
                        len(plan.cases),
                        plan_uri,
                        approved_uri,
                        "",
                        json.dumps(make_json_safe(plan.model_dump(mode="json")), ensure_ascii=False),
                        now,
                        now,
                    ),
                )

    def _save_plan_version_sync(
        self,
        plan: SmokeExecutionPlan,
        plan_uri: str,
        plan_md_uri: str,
        revision_reason: str,
        user_revision: str,
    ) -> None:
        selected_count = sum(1 for item in plan.cases if item.selected)
        with postgres_connect(self._settings) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    INSERT INTO {self.version_table} (
                        id, plan_id, version, revision_reason, user_revision,
                        plan_uri, plan_md_uri, case_count, selected_case_count,
                        risk_summary, created_at
                    ) VALUES (
                        %s, %s, %s, %s, %s,
                        %s, %s, %s, %s,
                        %s::jsonb, %s
                    )
                    ON CONFLICT (plan_id, version) DO UPDATE SET
                        revision_reason = EXCLUDED.revision_reason,
                        user_revision = EXCLUDED.user_revision,
                        plan_uri = EXCLUDED.plan_uri,
                        plan_md_uri = EXCLUDED.plan_md_uri,
                        case_count = EXCLUDED.case_count,
                        selected_case_count = EXCLUDED.selected_case_count,
                        risk_summary = EXCLUDED.risk_summary
                    """,
                    (
                        f"{plan.plan_id}_v{plan.version}",
                        plan.plan_id,
                        plan.version,
                        revision_reason,
                        user_revision,
                        plan_uri,
                        plan_md_uri,
                        len(plan.cases),
                        selected_count,
                        json.dumps(make_json_safe(plan.risk_summary), ensure_ascii=False),
                        datetime.now(timezone.utc),
                    ),
                )

    def _get_plan_record_sync(self, plan_id: str) -> dict[str, Any] | None:
        with postgres_connect(self._settings) as conn:
            with conn.cursor() as cur:
                cur.execute(f"SELECT * FROM {self.plan_table} WHERE plan_id = %s", (plan_id,))
                row = cur.fetchone()
        return dict(row) if row else None

    def _save_run_sync(self, result: SmokeRunResult) -> None:
        completed = _parse_dt(result.completed_at)
        with postgres_connect(self._settings) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    INSERT INTO {self.run_table} (
                        run_id, plan_id, plan_version, project_scope, status, verdict,
                        total_cases, passed_cases, failed_cases, blocked_cases,
                        started_at, completed_at, run_result_uri, report_uri,
                        evidence_manifest_uri, metadata
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s,
                        %s, %s, %s, %s,
                        %s, %s, %s, %s,
                        %s, %s::jsonb
                    )
                    ON CONFLICT (run_id) DO UPDATE SET
                        status = EXCLUDED.status,
                        verdict = EXCLUDED.verdict,
                        total_cases = EXCLUDED.total_cases,
                        passed_cases = EXCLUDED.passed_cases,
                        failed_cases = EXCLUDED.failed_cases,
                        blocked_cases = EXCLUDED.blocked_cases,
                        completed_at = EXCLUDED.completed_at,
                        run_result_uri = EXCLUDED.run_result_uri,
                        report_uri = EXCLUDED.report_uri,
                        evidence_manifest_uri = EXCLUDED.evidence_manifest_uri,
                        metadata = EXCLUDED.metadata
                    """,
                    (
                        result.run_id,
                        result.plan_id,
                        result.plan_version,
                        result.project_scope,
                        result.status,
                        result.verdict,
                        result.total_cases,
                        result.passed_cases,
                        result.failed_cases,
                        result.blocked_cases,
                        _parse_dt(result.started_at) or datetime.now(timezone.utc),
                        completed,
                        result.minio_uris.get("run_result_uri", ""),
                        result.minio_uris.get("report_uri", ""),
                        result.minio_uris.get("evidence_manifest_uri", ""),
                        json.dumps(make_json_safe(result.model_dump(mode="json")), ensure_ascii=False),
                    ),
                )
                cur.execute(
                    f"""
                    UPDATE {self.plan_table}
                    SET last_run_status = %s,
                        last_run_at = %s,
                        run_result_uri = %s,
                        report_uri = %s,
                        updated_at = %s
                    WHERE plan_id = %s
                    """,
                    (
                        result.status,
                        completed or datetime.now(timezone.utc),
                        result.minio_uris.get("run_result_uri", ""),
                        result.minio_uris.get("report_uri", ""),
                        datetime.now(timezone.utc),
                        result.plan_id,
                    ),
                )

    def _save_regression_candidates_sync(self, items: list[RegressionCandidateCase]) -> None:
        if not items:
            return
        with postgres_connect(self._settings) as conn:
            with conn.cursor() as cur:
                for item in items:
                    cur.execute(
                        f"""
                        INSERT INTO {self.regression_table} (
                            case_id, source_plan_id, source_run_id, project_scope, case_type,
                            title, case_uri, stability_score, status, run_count, pass_count,
                            fail_count, flaky_count, blocked_count, last_status,
                            last_passed_at, updated_at
                        ) VALUES (
                            %s, %s, %s, %s, %s,
                            %s, %s, %s, %s, %s, %s,
                            %s, %s, %s, %s,
                            %s, %s
                        )
                        ON CONFLICT (case_id) DO UPDATE SET
                            source_run_id = EXCLUDED.source_run_id,
                            case_uri = EXCLUDED.case_uri,
                            stability_score = EXCLUDED.stability_score,
                            status = EXCLUDED.status,
                            run_count = {self.regression_table}.run_count + 1,
                            pass_count = {self.regression_table}.pass_count + EXCLUDED.pass_count,
                            fail_count = {self.regression_table}.fail_count + EXCLUDED.fail_count,
                            flaky_count = {self.regression_table}.flaky_count + EXCLUDED.flaky_count,
                            blocked_count = {self.regression_table}.blocked_count + EXCLUDED.blocked_count,
                            last_status = EXCLUDED.last_status,
                            last_passed_at = COALESCE(EXCLUDED.last_passed_at, {self.regression_table}.last_passed_at),
                            updated_at = EXCLUDED.updated_at
                        """,
                        (
                            item.case_id,
                            item.source_plan_id,
                            item.source_run_id,
                            item.project_scope,
                            item.case_type,
                            item.title,
                            item.case_uri,
                            item.stability_score,
                            item.status,
                            item.run_count,
                            item.pass_count,
                            item.fail_count,
                            item.flaky_count,
                            item.blocked_count,
                            item.last_status,
                            _parse_dt(item.last_passed_at),
                            _parse_dt(item.updated_at) or datetime.now(timezone.utc),
                        ),
                    )


def _parse_dt(value: str) -> datetime | None:
    if not value:
        return None
    try:
        normalized = value.replace("Z", "+00:00")
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


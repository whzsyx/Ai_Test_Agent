"""Performance metrics store.

Persists PerfRun records and provides baseline lookup
for regression comparison.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any

from src.core.config import Settings
from src.modes.performance_testing_mode.plan_state import PerfMetrics, PerfRun

logger = logging.getLogger(__name__)


class PerfMetricsStore:
    """PostgreSQL-backed store for performance run records."""

    def __init__(self, settings: Settings):
        self._settings = settings
        self._table = settings.postgres_perf_runs_table
        self._initialized = False

    async def _get_connection(self):
        try:
            import asyncpg
            return await asyncpg.connect(
                host=self._settings.postgres_host if hasattr(self._settings, "postgres_host") else "localhost",
                port=self._settings.postgres_port if hasattr(self._settings, "postgres_port") else 5432,
                user=self._settings.postgres_user if hasattr(self._settings, "postgres_user") else "postgres",
                password=self._settings.postgres_password if hasattr(self._settings, "postgres_password") else "",
                database=self._settings.postgres_db if hasattr(self._settings, "postgres_db") else "qa_agent",
            )
        except ImportError:
            logger.warning("asyncpg not installed, perf metrics store disabled")
            return None
        except Exception as e:
            logger.warning(f"Failed to connect to postgres: {e}")
            return None

    async def initialize(self) -> bool:
        conn = await self._get_connection()
        if conn is None:
            return False

        try:
            await conn.execute(f"""
                CREATE TABLE IF NOT EXISTS {self._table} (
                    run_id TEXT PRIMARY KEY,
                    plan_id TEXT NOT NULL,
                    engine TEXT NOT NULL DEFAULT 'k6',
                    backend TEXT NOT NULL DEFAULT 'docker',
                    status TEXT NOT NULL DEFAULT 'pending',
                    run_intent TEXT NOT NULL DEFAULT 'probe',
                    target_url TEXT,
                    metrics_json JSONB,
                    verdict TEXT,
                    started_at TIMESTAMPTZ,
                    completed_at TIMESTAMPTZ,
                    created_at TIMESTAMPTZ DEFAULT NOW()
                )
            """)
            await conn.execute(f"""
                CREATE INDEX IF NOT EXISTS idx_{self._table}_plan_id
                ON {self._table} (plan_id)
            """)
            await conn.execute(f"""
                CREATE INDEX IF NOT EXISTS idx_{self._table}_target_url
                ON {self._table} (target_url)
            """)
            self._initialized = True
            return True
        except Exception as e:
            logger.warning(f"Failed to initialize perf metrics table: {e}")
            return False
        finally:
            await conn.close()

    async def save_run(
        self,
        run: PerfRun,
        metrics: PerfMetrics | None = None,
        verdict: str | None = None,
        target_url: str = "",
        run_intent: str = "probe",
    ) -> bool:
        conn = await self._get_connection()
        if conn is None:
            return False

        try:
            metrics_json = json.dumps(metrics.model_dump()) if metrics else None
            await conn.execute(
                f"""
                INSERT INTO {self._table}
                    (run_id, plan_id, engine, backend, status, run_intent, target_url,
                     metrics_json, verdict, started_at, completed_at)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
                ON CONFLICT (run_id) DO UPDATE SET
                    status = EXCLUDED.status,
                    metrics_json = EXCLUDED.metrics_json,
                    verdict = EXCLUDED.verdict,
                    completed_at = EXCLUDED.completed_at
                """,
                run.run_id,
                run.plan_id,
                run.engine,
                run.backend,
                run.status,
                run_intent,
                target_url,
                metrics_json,
                verdict,
                datetime.fromisoformat(run.started_at) if run.started_at else None,
                datetime.fromisoformat(run.completed_at) if run.completed_at else None,
            )
            return True
        except Exception as e:
            logger.warning(f"Failed to save perf run: {e}")
            return False
        finally:
            await conn.close()

    async def get_baseline(self, target_url: str) -> PerfMetrics | None:
        """Get the most recent successful baseline metrics for a target URL."""
        conn = await self._get_connection()
        if conn is None:
            return None

        try:
            row = await conn.fetchrow(
                f"""
                SELECT metrics_json FROM {self._table}
                WHERE target_url = $1
                  AND status = 'completed'
                  AND verdict IN ('baseline', 'pass')
                  AND metrics_json IS NOT NULL
                ORDER BY completed_at DESC
                LIMIT 1
                """,
                target_url,
            )
            if row and row["metrics_json"]:
                data = json.loads(row["metrics_json"]) if isinstance(row["metrics_json"], str) else row["metrics_json"]
                return PerfMetrics(**data)
            return None
        except Exception as e:
            logger.warning(f"Failed to get baseline: {e}")
            return None
        finally:
            await conn.close()

    async def list_runs(
        self,
        target_url: str | None = None,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        conn = await self._get_connection()
        if conn is None:
            return []

        try:
            if target_url:
                rows = await conn.fetch(
                    f"""
                    SELECT run_id, plan_id, engine, status, run_intent, target_url,
                           verdict, started_at, completed_at
                    FROM {self._table}
                    WHERE target_url = $1
                    ORDER BY created_at DESC
                    LIMIT $2
                    """,
                    target_url,
                    limit,
                )
            else:
                rows = await conn.fetch(
                    f"""
                    SELECT run_id, plan_id, engine, status, run_intent, target_url,
                           verdict, started_at, completed_at
                    FROM {self._table}
                    ORDER BY created_at DESC
                    LIMIT $1
                    """,
                    limit,
                )
            return [dict(row) for row in rows]
        except Exception as e:
            logger.warning(f"Failed to list runs: {e}")
            return []
        finally:
            await conn.close()

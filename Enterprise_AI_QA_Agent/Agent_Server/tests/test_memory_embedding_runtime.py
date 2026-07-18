from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from src.application.context.embedding_runtime_service import EmbeddingBatchResult
from src.application.context.memory_runtime_service import MemoryRuntimeService
from src.application.runtime.tool_runtime_service import (
    ToolExecutionContext,
    ToolRuntimeService,
)
from src.schemas.memory import MemoryPoint


class _EmbeddingService:
    def __init__(self) -> None:
        self.calls: list[list[str]] = []

    async def embed_texts(self, texts, **_kwargs):
        self.calls.append(list(texts))
        return EmbeddingBatchResult(
            vectors=[[1.0, 0.0, 0.0] for _ in texts],
            model_name="embedding-test",
            provider="openai",
            adapter="openai_compatible_embeddings",
            original_dimension=3,
            stored_dimension=3,
            latency_ms=1,
        )


class _MemoryStore:
    backend = "test"

    def __init__(self) -> None:
        self.search_requests = []
        self.write_requests = []

    async def initialize(self):
        return None

    async def refresh_connection_status(self):
        return self.backend

    async def search(self, request):
        self.search_requests.append(request)
        return []

    async def count_documents(self, _request):
        return 0

    async def write(self, request):
        self.write_requests.append(request)
        return MemoryPoint(
            id="memory-1",
            scope=request.scope,
            kind=request.kind,
            content=request.content,
            summary=request.summary,
            tags=request.tags,
            session_id=request.session_id,
            turn_id=request.turn_id,
            trace_id=request.trace_id,
            source=request.source,
            stale=request.stale,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
            metadata=request.metadata,
        )

    async def list_points(self, _request):
        return []

    async def count_missing_embeddings(self):
        return 12


def test_memory_runtime_attaches_query_and_write_embeddings() -> None:
    async def run() -> None:
        store = _MemoryStore()
        embedding = _EmbeddingService()
        service = MemoryRuntimeService(
            store,
            embedding_runtime_service=embedding,
        )

        await service.retrieve_for_turn(
            "session-1",
            "trace-1",
            "find my previous login test",
            {"mode_key": "security_testing"},
        )
        assert store.search_requests[0].metadata_filters["__query_embedding"] == [
            1.0,
            0.0,
            0.0,
        ]

        await service.write_page_memory(
            "session-1",
            "turn-1",
            "trace-1",
            "Login",
            "https://example.test/login",
            "Login form discovered",
        )
        metadata = store.write_requests[0].metadata
        assert metadata["embedding"] == [1.0, 0.0, 0.0]
        assert metadata["embedding_model"] == "embedding-test"

    asyncio.run(run())


def test_embedding_backfill_is_preview_only_by_default() -> None:
    async def run() -> None:
        embedding = _EmbeddingService()
        service = MemoryRuntimeService(
            _MemoryStore(),
            embedding_runtime_service=embedding,
        )
        result = await service.backfill_missing_embeddings(limit=5)
        assert result == {
            "execute": False,
            "missing_total": 12,
            "requested": 5,
            "updated": 0,
        }
        assert embedding.calls == []

    asyncio.run(run())


class _HistoryStore:
    def __init__(self) -> None:
        self.question_calls = 0

    async def get_session(self, _session_id):
        raise AssertionError("all_sessions must not load a full current session")

    async def list_recent_questions(self, **_kwargs):
        self.question_calls += 1
        return [
            {
                "session_id": "session-2",
                "role": "user",
                "content": "What failed last time?",
                "created_at": "2026-07-18T12:00:00+00:00",
            }
        ]


def test_all_session_questions_use_one_batch_query_path() -> None:
    async def run() -> None:
        store = _HistoryStore()
        service = ToolRuntimeService.__new__(ToolRuntimeService)
        service._session_store = store
        result = await service._run_session_history(
            {"action": "list_questions", "scope": "all_sessions", "limit": 10},
            ToolExecutionContext(
                session_id="current-session",
                turn_id="turn-1",
                trace_id="trace-1",
                user_message="history",
                normalized_input="history",
                context_bundle={},
            ),
        )

        assert store.question_calls == 1
        assert result["questions"][0]["content"] == "What failed last time?"

    asyncio.run(run())

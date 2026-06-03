from __future__ import annotations

from contextlib import AsyncExitStack
from typing import Any


class SseMcpTransport:
    def __init__(
        self,
        *,
        endpoint_url: str,
        headers: dict[str, str] | None = None,
        timeout_seconds: float = 45.0,
    ) -> None:
        self._endpoint_url = endpoint_url
        self._headers = dict(headers or {})
        self._timeout_seconds = timeout_seconds
        self._stack: AsyncExitStack | None = None
        self._session: Any = None

    async def open(self) -> Any:
        from mcp import ClientSession
        from mcp.client.sse import sse_client

        stack = AsyncExitStack()
        self._stack = stack
        try:
            read_stream, write_stream = await stack.enter_async_context(
                sse_client(
                    self._endpoint_url,
                    headers=self._headers or None,
                    timeout=self._timeout_seconds,
                )
            )
            session = await stack.enter_async_context(ClientSession(read_stream, write_stream))
            self._session = session
            return session
        except BaseException:
            await self._close_stack(stack)
            self._stack = None
            self._session = None
            raise

    async def close(self) -> None:
        if self._stack is not None:
            await self._close_stack(self._stack)
        self._stack = None
        self._session = None

    async def _close_stack(self, stack: AsyncExitStack) -> None:
        try:
            await stack.aclose()
        except RuntimeError as exc:
            if "cancel scope" not in str(exc).lower():
                raise

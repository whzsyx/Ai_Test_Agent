from __future__ import annotations

from contextlib import AsyncExitStack
from typing import Any


class StdioMcpTransport:
    def __init__(
        self,
        *,
        command: str,
        args: list[str],
        env: dict[str, str] | None = None,
        cwd: str | None = None,
    ) -> None:
        self._command = command
        self._args = list(args)
        self._env = dict(env or {})
        self._cwd = cwd or None
        self._stack: AsyncExitStack | None = None
        self._session: Any = None

    async def open(self) -> Any:
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client

        stack = AsyncExitStack()
        self._stack = stack
        params = StdioServerParameters(
            command=self._command,
            args=self._args,
            env=self._env or None,
            cwd=self._cwd,
        )
        try:
            read_stream, write_stream = await stack.enter_async_context(stdio_client(params))
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

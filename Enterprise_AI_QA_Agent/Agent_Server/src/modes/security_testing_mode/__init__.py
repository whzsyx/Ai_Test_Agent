from __future__ import annotations

from typing import TYPE_CHECKING

from .manifest import MODE_MANIFEST

if TYPE_CHECKING:
    from .runtime import SecurityTestingModeRuntime


def __getattr__(name: str):
    if name == "SecurityTestingModeRuntime":
        from .runtime import SecurityTestingModeRuntime

        return SecurityTestingModeRuntime
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

__all__ = ["MODE_MANIFEST", "SecurityTestingModeRuntime"]

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


@dataclass(slots=True)
class ToolResult:
    name: str
    payload: dict[str, Any]


class AgentTool(Protocol):
    name: str

    async def __call__(self, **kwargs: Any) -> ToolResult: ...

from __future__ import annotations

from typing import Protocol

from agent_trader.ingestion.models import RawEvent


class SourceAdapter(Protocol):
    name: str

    async def fetch(self) -> list[RawEvent]: ...
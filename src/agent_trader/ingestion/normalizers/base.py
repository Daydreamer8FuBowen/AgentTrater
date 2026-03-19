from __future__ import annotations

from typing import Protocol

from agent_trader.ingestion.models import NormalizedEvent, RawEvent, ResearchTrigger


class EventNormalizer(Protocol):
    async def normalize(self, raw_event: RawEvent) -> NormalizedEvent: ...
    async def to_trigger(self, normalized_event: NormalizedEvent) -> ResearchTrigger: ...
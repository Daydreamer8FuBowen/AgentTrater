from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from agent_trader.domain.models import TriggerKind


@dataclass(slots=True)
class RawEvent:
    source: str
    payload: dict[str, Any]
    received_at: datetime = field(default_factory=datetime.utcnow)
    id: UUID = field(default_factory=uuid4)


@dataclass(slots=True)
class NormalizedEvent:
    trigger_kind: TriggerKind
    symbol: str
    title: str
    content: str
    metadata: dict[str, Any]
    id: UUID = field(default_factory=uuid4)


@dataclass(slots=True)
class ResearchTrigger:
    trigger_kind: TriggerKind
    symbol: str
    summary: str
    metadata: dict[str, Any]
    id: UUID = field(default_factory=uuid4)
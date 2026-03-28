from __future__ import annotations

from dataclasses import asdict, is_dataclass
from datetime import datetime
from typing import Any

from agent_trader.core.time import ensure_utc


def serialize_datetime(value: datetime) -> str:
    return ensure_utc(value).isoformat().replace("+00:00", "Z")


def serialize_temporal_payload(value: Any) -> Any:
    if isinstance(value, datetime):
        return serialize_datetime(value)
    if is_dataclass(value):
        return serialize_temporal_payload(asdict(value))
    if isinstance(value, dict):
        return {key: serialize_temporal_payload(item) for key, item in value.items()}
    if isinstance(value, list):
        return [serialize_temporal_payload(item) for item in value]
    if isinstance(value, tuple):
        return [serialize_temporal_payload(item) for item in value]
    return value

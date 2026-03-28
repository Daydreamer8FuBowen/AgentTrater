from __future__ import annotations

from datetime import date, datetime, time, timezone
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo

if TYPE_CHECKING:
    from agent_trader.domain.models import ExchangeKind

UTC_ZONE = timezone.utc
ASIA_SHANGHAI = ZoneInfo("Asia/Shanghai")

_MARKET_TIMEZONES: dict[str, ZoneInfo] = {
    "sse": ASIA_SHANGHAI,
    "sh": ASIA_SHANGHAI,
    "szse": ASIA_SHANGHAI,
    "sz": ASIA_SHANGHAI,
}


def utc_now() -> datetime:
    return datetime.now(UTC_ZONE)


def ensure_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC_ZONE)
    return value.astimezone(UTC_ZONE)


def utc_from_timestamp(value: int | float) -> datetime:
    return datetime.fromtimestamp(value, UTC_ZONE)


def _market_key(market: str | ExchangeKind | None) -> str:
    if market is None:
        return ""
    if hasattr(market, "value"):
        return str(market.value).strip().lower()
    return str(market).strip().lower()


def market_timezone(market: str | ExchangeKind | None) -> ZoneInfo:
    return _MARKET_TIMEZONES.get(_market_key(market), UTC_ZONE)


def to_market_time(value: datetime, market: str | ExchangeKind | None) -> datetime:
    return ensure_utc(value).astimezone(market_timezone(market))


def market_date(value: datetime, market: str | ExchangeKind | None) -> date:
    return to_market_time(value, market).date()


def market_time_of_day(value: datetime, market: str | ExchangeKind | None) -> time:
    return to_market_time(value, market).time()


def market_time_to_utc(value: datetime, market: str | ExchangeKind | None) -> datetime:
    if value.tzinfo is None:
        value = value.replace(tzinfo=market_timezone(market))
    return value.astimezone(UTC_ZONE)

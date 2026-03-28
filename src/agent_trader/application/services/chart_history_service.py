from __future__ import annotations

import math
from datetime import date, datetime, time, timedelta, timezone
from typing import Any

from motor.motor_asyncio import AsyncIOMotorDatabase

from agent_trader.application.data_access.gateway import DataAccessGateway
from agent_trader.application.data_access.kline_utils import (
    MAX_KLINE_BARS,
    get_bar_close_time,
)
from agent_trader.core.time import (
    ensure_utc,
    market_time_to_utc,
    to_market_time,
    utc_from_timestamp,
)
from agent_trader.domain.models import BarInterval, Candle, ExchangeKind
from agent_trader.ingestion.models import KlineQuery
from agent_trader.storage.base import CandleRepository
from agent_trader.storage.mongo.documents import BasicInfoDocument

_RESOLUTION_TO_INTERVAL = {
    "1": "1m",
    "3": "3m",
    "5": "5m",
    "15": "15m",
    "30": "30m",
    "60": "1h",
    "240": "4h",
    "D": "1d",
    "W": "1w",
    "M": "1mo",
}


class ChartHistoryService:
    def __init__(
        self,
        candle_repository: CandleRepository,
        gateway: DataAccessGateway,
        database: AsyncIOMotorDatabase | None = None,
    ) -> None:
        self._candle_repository = candle_repository
        self._gateway = gateway
        self._database = database

    async def get_tv_history(
        self,
        *,
        symbol: str,
        resolution: str,
        from_ts: int,
        to_ts: int,
        countback: int | None = None,
    ) -> dict[str, Any]:
        interval = self._to_interval(resolution)
        start_time = utc_from_timestamp(from_ts)
        end_time = utc_from_timestamp(to_ts)
        if end_time < start_time:
            raise ValueError("invalid time range")

        normalized_symbol = symbol.strip().upper()
        market = _infer_market(normalized_symbol)
        expected_count = _estimate_expected_count(start_time, end_time, interval, market)

        rows = await self._load_history_rows(
            symbol=normalized_symbol,
            interval=interval,
            start_time=start_time,
            end_time=end_time,
            market=market,
            countback=countback,
            expected_count=expected_count,
        )
        if not rows:
            return {"s": "no_data"}

        # 按 bar_time 升序排列并去重（防御仓储层或补数流程引入重复时间戳）
        deduped: dict[Any, dict[str, Any]] = {}
        for row in rows:
            bt = row["bar_time"]
            existing = deduped.get(bt)
            if existing is None or (
                float(row.get("close") or 0) > 0 and float(existing.get("close") or 0) == 0
            ):
                deduped[bt] = row
        ordered_rows = sorted(deduped.values(), key=lambda item: item["bar_time"])
        if countback is not None and countback > 0 and len(ordered_rows) > countback:
            ordered_rows = ordered_rows[-countback:]

        return {
            "s": "ok",
            "t": [int(item["bar_time"].timestamp()) for item in ordered_rows],
            "o": [float(item.get("open", 0.0) or 0.0) for item in ordered_rows],
            "h": [float(item.get("high", 0.0) or 0.0) for item in ordered_rows],
            "l": [float(item.get("low", 0.0) or 0.0) for item in ordered_rows],
            "c": [float(item.get("close", 0.0) or 0.0) for item in ordered_rows],
            "v": [float(item.get("volume", 0.0) or 0.0) for item in ordered_rows],
        }

    def _to_interval(self, resolution: str) -> str:
        value = resolution.strip().upper()
        if value not in _RESOLUTION_TO_INTERVAL:
            raise ValueError(f"unsupported resolution: {resolution}")
        return _RESOLUTION_TO_INTERVAL[value]

    async def _load_history_rows(
        self,
        *,
        symbol: str,
        interval: str,
        start_time: datetime,
        end_time: datetime,
        market: ExchangeKind | None,
        countback: int | None,
        expected_count: int,
    ) -> list[dict[str, Any]]:
        query_limit = max(expected_count, countback or 0, 1)
        rows = await self._query_rows(
            symbol=symbol,
            interval=interval,
            start_time=start_time,
            end_time=end_time,
            limit=query_limit,
        )
        if not _needs_backfill(rows, start_time, end_time, interval, expected_count):
            return rows

        bar_interval = _to_bar_interval(interval)
        candles = await self._fetch_candles_chunked(
            symbol=symbol,
            bar_interval=bar_interval,
            start_time=start_time,
            end_time=end_time,
            market=market,
            total_expected=expected_count,
        )
        if candles:
            await self._candle_repository.write_batch(candles)
            rows = await self._query_rows(
                symbol=symbol,
                interval=interval,
                start_time=start_time,
                end_time=end_time,
                limit=query_limit,
            )
            return rows
        return rows

    async def _fetch_candles_chunked(
        self,
        *,
        symbol: str,
        bar_interval: BarInterval,
        start_time: datetime,
        end_time: datetime,
        market: ExchangeKind | None,
        total_expected: int,
    ) -> list[Candle]:
        """按 MAX_KLINE_BARS 上限分段拉取 K 线，并合并结果。"""
        chunks = _build_fetch_chunks(start_time, end_time, bar_interval, market, total_expected)
        all_candles: list[Candle] = []
        available_sources = await self._get_available_sources_for_symbol(symbol)
        for chunk_start, chunk_end in chunks:
            extra = {"available_sources": available_sources} if available_sources else {}
            result = await self._gateway.fetch_klines(
                KlineQuery(
                    symbol=symbol,
                    start_time=chunk_start,
                    end_time=chunk_end,
                    interval=bar_interval,
                    market=market,
                    extra=extra,
                )
            )
            all_candles.extend(
                _record_to_candle(record, market, result.source) for record in result.payload
            )
        return all_candles

    async def _query_rows(
        self,
        *,
        symbol: str,
        interval: str,
        start_time: datetime,
        end_time: datetime,
        limit: int,
    ) -> list[dict[str, Any]]:
        result = await self._candle_repository.query_history(
            symbol=symbol,
            interval=interval,
            start_time=start_time,
            end_time=end_time,
            limit=limit,
        )
        return list(result)

    async def _get_available_sources_for_symbol(self, symbol: str) -> list[str] | None:
        if self._database is None:
            return None
        normalized = symbol.strip().upper()
        collection = self._database[BasicInfoDocument.collection_name]
        doc = await collection.find_one(
            {"symbol": normalized},
            {"_id": 0, "primary_source": 1, "source_trace": 1},
        )
        if not doc:
            return None
        sources: list[str] = []
        primary = doc.get("primary_source")
        if isinstance(primary, str) and primary.strip():
            p = primary.strip()
            if p not in sources:
                sources.append(p)
        trace = doc.get("source_trace") or []
        if isinstance(trace, list):
            for item in trace:
                if isinstance(item, str):
                    s = item.strip()
                    if s and s not in sources:
                        sources.append(s)
        return sources or None


_INTERVAL_STEP: dict[BarInterval, timedelta] = {
    BarInterval.M1: timedelta(minutes=1),
    BarInterval.M3: timedelta(minutes=3),
    BarInterval.M5: timedelta(minutes=5),
    BarInterval.M15: timedelta(minutes=15),
    BarInterval.M30: timedelta(minutes=30),
    BarInterval.H1: timedelta(hours=1),
    BarInterval.H4: timedelta(hours=4),
    BarInterval.D1: timedelta(days=1),
    BarInterval.W1: timedelta(weeks=1),
    BarInterval.MN1: timedelta(days=31),
}


def _build_fetch_chunks(
    start_time: datetime,
    end_time: datetime,
    interval: BarInterval,
    market: ExchangeKind | None,
    total_expected: int,
) -> list[tuple[datetime, datetime]]:
    """将时间范围切割成若干相邻子段，每段预估 bar 数不超过 MAX_KLINE_BARS。

    各子段首尾相接（chunk_i 的 end == chunk_{i+1} 的 start），边界处数据源
    因日期对齐可能重复拉取，InfluxDB 写入时会按 timestamp+tags 自动覆盖。
    """
    del interval, market
    n_chunks = max(math.ceil(total_expected / MAX_KLINE_BARS), 1)
    start_minute = int(ensure_utc(start_time).timestamp() // 60)
    end_minute = int(ensure_utc(end_time).timestamp() // 60)
    total_minutes = max(end_minute - start_minute, 0)

    chunks: list[tuple[datetime, datetime]] = []
    for i in range(n_chunks):
        chunk_start_minute = start_minute + (total_minutes * i) // n_chunks
        chunk_end_minute = (
            end_minute
            if i == n_chunks - 1
            else start_minute + (total_minutes * (i + 1)) // n_chunks
        )
        chunk_start = datetime.fromtimestamp(chunk_start_minute * 60, tz=timezone.utc)
        chunk_end = datetime.fromtimestamp(chunk_end_minute * 60, tz=timezone.utc)
        chunks.append((chunk_start, chunk_end))
    return chunks


_INTERVAL_TO_BAR_INTERVAL: dict[str, BarInterval] = {
    "1m": BarInterval.M1,
    "3m": BarInterval.M3,
    "5m": BarInterval.M5,
    "15m": BarInterval.M15,
    "30m": BarInterval.M30,
    "1h": BarInterval.H1,
    "4h": BarInterval.H4,
    "1d": BarInterval.D1,
    "1w": BarInterval.W1,
    "1mo": BarInterval.MN1,
}

_A_SHARE_SESSIONS = (
    (time(9, 30), time(11, 30)),
    (time(13, 0), time(15, 0)),
)


def _to_bar_interval(interval: str) -> BarInterval:
    try:
        return _INTERVAL_TO_BAR_INTERVAL[interval]
    except KeyError as exc:
        raise ValueError(f"unsupported interval: {interval}") from exc


def _infer_market(symbol: str) -> ExchangeKind | None:
    if symbol.endswith(".SH"):
        return ExchangeKind.SSE
    if symbol.endswith(".SZ"):
        return ExchangeKind.SZSE
    return None


def _estimate_expected_count(
    start_time: datetime,
    end_time: datetime,
    interval: str,
    market: ExchangeKind | None,
) -> int:
    bar_interval = _to_bar_interval(interval)
    expected_times = _expected_bar_times(start_time, end_time, bar_interval, market)
    if expected_times:
        return len(expected_times)
    delta = get_bar_close_time(ensure_utc(start_time), bar_interval) - ensure_utc(start_time)
    if delta.total_seconds() <= 0:
        return 1
    return (
        int(
            (ensure_utc(end_time) - ensure_utc(start_time)).total_seconds() // delta.total_seconds()
        )
        + 1
    )


def _needs_backfill(
    rows: list[dict[str, Any]],
    start_time: datetime,
    end_time: datetime,
    interval: str,
    expected_count: int,
) -> bool:
    if not rows:
        return True
    ordered_rows = sorted(rows, key=lambda item: item["bar_time"])
    expected = _expected_bar_times(
        start_time,
        end_time,
        _to_bar_interval(interval),
        _infer_market(str(ordered_rows[0].get("symbol", ""))),
    )
    if expected:
        actual = {ensure_utc(item["bar_time"]) for item in ordered_rows}
        return any(bar_time not in actual for bar_time in expected)
    if ordered_rows[0]["bar_time"] > ensure_utc(start_time):
        return True
    if ordered_rows[-1]["bar_time"] < ensure_utc(end_time) and expected_count > len(ordered_rows):
        return True
    if expected_count > len(ordered_rows):
        return True
    return False


def _record_to_candle(record: Any, market: ExchangeKind | None, source: str) -> Candle:
    interval = _to_bar_interval(record.interval)
    open_time = ensure_utc(record.bar_time)
    return Candle(
        symbol=record.symbol.strip().upper(),
        interval=interval,
        open_time=open_time,
        close_time=get_bar_close_time(open_time, interval),
        open_price=record.open or 0.0,
        high_price=record.high or 0.0,
        low_price=record.low or 0.0,
        close_price=record.close or 0.0,
        volume=record.volume or 0.0,
        turnover=record.amount,
        trade_count=None,
        exchange=market or ExchangeKind.OTHER,
        adjusted=record.adjusted,
        source=source,
    )


def _expected_bar_times(
    start_time: datetime,
    end_time: datetime,
    interval: BarInterval,
    market: ExchangeKind | None,
) -> list[datetime]:
    if interval == BarInterval.D1 and market in {ExchangeKind.SSE, ExchangeKind.SZSE}:
        return [
            market_time_to_utc(datetime.combine(day, time.min), market)
            for day in _business_days(start_time.date(), end_time.date())
        ]
    if interval == BarInterval.M5 and market in {ExchangeKind.SSE, ExchangeKind.SZSE}:
        return _a_share_session_bar_times(start_time, end_time, market)
    return []


def _a_share_session_bar_times(
    start_time: datetime, end_time: datetime, market: ExchangeKind
) -> list[datetime]:
    result: list[datetime] = []
    local_start = to_market_time(start_time, market)
    local_end = to_market_time(end_time, market)
    day = local_start.date()
    while day <= local_end.date():
        if day.weekday() < 5:
            for session_start, session_end in _A_SHARE_SESSIONS:
                cursor = datetime.combine(day, session_start)
                close_time = datetime.combine(day, session_end)
                while cursor <= close_time:
                    cursor_utc = market_time_to_utc(cursor, market)
                    if start_time <= cursor_utc <= end_time:
                        result.append(cursor_utc)
                    cursor += timedelta(minutes=5)
        day += timedelta(days=1)
    return result


def _business_days(start_date: date, end_date: date) -> list[date]:
    result: list[date] = []
    cursor = start_date
    while cursor <= end_date:
        if cursor.weekday() < 5:
            result.append(cursor)
        cursor += timedelta(days=1)
    return result

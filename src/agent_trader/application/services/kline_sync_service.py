from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta

from agent_trader.core.config import KlineSyncConfig
from agent_trader.domain.models import BarInterval, Candle, ExchangeKind
from agent_trader.ingestion.models import KlineFetchResult, KlineQuery, KlineRecord
from agent_trader.storage.base import CandleRepository, UnitOfWork
from agent_trader.storage.mongo.documents import BackfillProgressDocument
from agent_trader.application.data_access.gateway import DataAccessGateway

_A_SHARE_SESSIONS = (
    (time(9, 30), time(11, 30)),
    (time(13, 0), time(15, 0)),
)
_INTERVAL_DELTA = {
    BarInterval.M5: timedelta(minutes=5),
    BarInterval.D1: timedelta(days=1),
}


@dataclass(slots=True, frozen=True)
class TieredSymbols:
    market: str
    positions: tuple[str, ...]
    candidates: tuple[str, ...]
    others: tuple[str, ...]

    @property
    def positions_and_candidates(self) -> tuple[str, ...]:
        return self.positions + self.candidates

    @property
    def all_symbols(self) -> tuple[str, ...]:
        return self.positions + self.candidates + self.others


class TierCollectionService:
    """按市场汇总 Tier A/B/C symbol 集合。"""

    def __init__(self, uow_factory: Callable[[], UnitOfWork]) -> None:
        self._uow_factory = uow_factory

    async def collect(self, market: str) -> TieredSymbols:
        normalized_market = _normalize_market_name(market)

        async with self._uow_factory() as uow:
            positions = await uow.positions.list_active()
            candidates = await uow.candidates.list_active()

            basic_symbols: set[str] = set()
            for storage_market in _to_basic_info_markets(normalized_market):
                basic_symbols.update(await uow.basic_infos.list_symbols_by_market(storage_market))
        eligible_symbols = {_normalize_symbol(symbol) for symbol in basic_symbols}

        position_symbols = sorted(
            {
                _normalize_symbol(getattr(item, "symbol", ""))
                for item in positions
                if _symbol_in_market(getattr(item, "symbol", ""), normalized_market)
                and _normalize_symbol(getattr(item, "symbol", "")) in eligible_symbols
            }
        )
        position_set = set(position_symbols)

        candidate_symbols = sorted(
            {
                _normalize_symbol(getattr(item, "symbol", ""))
                for item in candidates
                if _symbol_in_market(getattr(item, "symbol", ""), normalized_market)
                and _normalize_symbol(getattr(item, "symbol", "")) in eligible_symbols
                and _normalize_symbol(getattr(item, "symbol", "")) not in position_set
            }
        )
        candidate_set = set(candidate_symbols)

        other_symbols = sorted(
            {
                symbol
                for symbol in eligible_symbols
                if symbol not in position_set
                and symbol not in candidate_set
            }
        )

        return TieredSymbols(
            market=normalized_market,
            positions=tuple(position_symbols),
            candidates=tuple(candidate_symbols),
            others=tuple(other_symbols),
        )


class KlineSyncService:
    """后台 K 线同步服务。

    规则：
    - 周末不请求实时任务。
    - 工作日请求返回空数据时，写入 0 值 bar 作为节假日占位。
    - 5m 仅覆盖 positions/candidates，1d 覆盖全量 A/B/C。
    """

    def __init__(
        self,
        *,
        gateway: DataAccessGateway,
        candle_repository: CandleRepository,
        uow_factory: Callable[[], UnitOfWork],
        tier_collection_service: TierCollectionService,
        config: KlineSyncConfig,
        now_provider: Callable[[], datetime] | None = None,
    ) -> None:
        self._gateway = gateway
        self._candle_repository = candle_repository
        self._uow_factory = uow_factory
        self._tier_collection_service = tier_collection_service
        self._config = config
        self._now_provider = now_provider or datetime.utcnow

    async def sync_realtime_m5_positions(self, market: str) -> dict[str, int | str]:
        """同步 Tier A（持仓）在最近一个 5 分钟窗口的实时 K 线。

        行为要点：
        - 周末直接跳过，避免无效请求。
        - 时间窗口固定为“当前对齐 5m bar”的前一个 bar。
        - 仅处理 `tiers.positions`。
        """
        now = self._now_provider()
        if _is_weekend(now.date()):
            return {"market": market, "synced": 0, "skipped": 0, "failed": 0, "mode": "weekend_skip"}

        tiers = await self._tier_collection_service.collect(market)
        end_time = _align_time(now, BarInterval.M5)
        start_time = end_time - _INTERVAL_DELTA[BarInterval.M5]
        return await self._sync_symbol_set(
            symbols=tiers.positions,
            market=tiers.market,
            interval=BarInterval.M5,
            start_time=start_time,
            end_time=end_time,
        )

    async def sync_realtime_m5_candidates(self, market: str) -> dict[str, int | str]:
        """同步 Tier B（候选池）在最近一个 5 分钟窗口的实时 K 线。

        与 `sync_realtime_m5_positions` 的差异仅在 symbol 集合：
        - 该函数只处理 `tiers.candidates`。
        """
        now = self._now_provider()
        if _is_weekend(now.date()):
            return {"market": market, "synced": 0, "skipped": 0, "failed": 0, "mode": "weekend_skip"}

        tiers = await self._tier_collection_service.collect(market)
        end_time = _align_time(now, BarInterval.M5)
        start_time = end_time - _INTERVAL_DELTA[BarInterval.M5]
        return await self._sync_symbol_set(
            symbols=tiers.candidates,
            market=tiers.market,
            interval=BarInterval.M5,
            start_time=start_time,
            end_time=end_time,
        )

    async def sync_daily_d1_all(self, market: str) -> dict[str, int | str]:
        """同步当日 D1（日线）数据，覆盖 Tier A/B/C 全量 symbol。

        行为要点：
        - 周末跳过。
        - 时间窗口为当天 `00:00:00` 到 `23:59:59.999999`。
        - 使用 `tiers.all_symbols` 进行全量日线刷新。
        """
        now = self._now_provider()
        if _is_weekend(now.date()):
            return {"market": market, "synced": 0, "skipped": 0, "failed": 0, "mode": "weekend_skip"}

        tiers = await self._tier_collection_service.collect(market)
        start_time = datetime.combine(now.date(), time.min)
        end_time = datetime.combine(now.date(), time.max)
        return await self._sync_symbol_set(
            symbols=tiers.all_symbols,
            market=tiers.market,
            interval=BarInterval.D1,
            start_time=start_time,
            end_time=end_time,
        )

    async def sync_backfill(self, market: str) -> dict[str, dict[str, int | str | float]]:
        """回补入口：串行执行 D1 回补和 M5 回补，并返回汇总结果。"""
        d1_summary = await self.sync_backfill_d1_all(market)
        m5_summary = await self.sync_backfill_m5_positions_candidates(market)
        return {"d1": d1_summary, "m5": m5_summary}

    async def sync_backfill_d1_all(self, market: str) -> dict[str, int | str | float]:
        """按配置窗口回补 D1 数据，覆盖 Tier A/B/C。

        - 回补起点：`now - d1_window_days`。
        - 回补终点：当前自然日结束。
        - 进度标记：`progress_tier=ABC`。
        """
        now = self._now_provider()
        tiers = await self._tier_collection_service.collect(market)
        normalized_market = tiers.market
        d1_start = datetime.combine(now.date() - timedelta(days=self._config.d1_window_days), time.min)
        d1_end = datetime.combine(now.date(), time.max)
        return await self._sync_symbol_set(
            symbols=tiers.all_symbols,
            market=normalized_market,
            interval=BarInterval.D1,
            start_time=d1_start,
            end_time=d1_end,
            progress_tier="ABC",
        )

    async def sync_backfill_m5_positions_candidates(self, market: str) -> dict[str, int | str | float]:
        """按配置窗口回补 M5 数据，覆盖 Tier A+B，并按时间分块执行。

        - 回补起点：`now - m5_window_days`（按 5m 对齐）。
        - 回补终点：`now`（按 5m 对齐）。
        - 分块粒度：`m5_backfill_chunk_days`，降低单次请求/写入压力。
        - 进度标记：`progress_tier=AB`。
        """
        now = self._now_provider()
        tiers = await self._tier_collection_service.collect(market)
        normalized_market = tiers.market
        m5_start = _align_time(now - timedelta(days=self._config.m5_window_days), BarInterval.M5)
        m5_end = _align_time(now, BarInterval.M5)
        return await self._sync_symbol_set_chunked(
            symbols=tiers.positions_and_candidates,
            market=normalized_market,
            interval=BarInterval.M5,
            start_time=m5_start,
            end_time=m5_end,
            chunk_days=self._config.m5_backfill_chunk_days,
            progress_tier="AB",
        )

    async def _sync_symbol_set(
        self,
        *,
        symbols: Sequence[str],
        market: str,
        interval: BarInterval,
        start_time: datetime,
        end_time: datetime,
        progress_tier: str | None = None,
    ) -> dict[str, int | str | float]:
        synced = 0
        failed = 0
        skipped = 0
        for symbol in symbols:
            try:
                await self._sync_single_symbol(
                    symbol=symbol,
                    market=market,
                    interval=interval,
                    start_time=start_time,
                    end_time=end_time,
                )
                synced += 1
            except ValueError:
                skipped += 1
            except Exception:
                failed += 1

        completion_ratio = 1.0 if not symbols else synced / len(symbols)
        if progress_tier is not None:
            await self._upsert_progress(
                market=market,
                interval=interval,
                tier=progress_tier,
                target_start=start_time,
                target_end=end_time,
                cursor=end_time,
                completion_ratio=completion_ratio,
                status="completed" if failed == 0 else "failed",
            )
        return {
            "market": market,
            "interval": interval.value,
            "synced": synced,
            "skipped": skipped,
            "failed": failed,
            "completion_ratio": completion_ratio,
        }

    async def _sync_symbol_set_chunked(
        self,
        *,
        symbols: Sequence[str],
        market: str,
        interval: BarInterval,
        start_time: datetime,
        end_time: datetime,
        chunk_days: int,
        progress_tier: str,
    ) -> dict[str, int | str | float]:
        synced = 0
        failed = 0
        skipped = 0
        cursor = start_time
        last_cursor = start_time
        while cursor <= end_time:
            chunk_end = min(cursor + timedelta(days=chunk_days) - _INTERVAL_DELTA[interval], end_time)
            for symbol in symbols:
                try:
                    await self._sync_single_symbol(
                        symbol=symbol,
                        market=market,
                        interval=interval,
                        start_time=cursor,
                        end_time=chunk_end,
                    )
                    synced += 1
                except ValueError:
                    skipped += 1
                except Exception:
                    failed += 1

            last_cursor = chunk_end
            completion_ratio = _completion_ratio(start_time, end_time, chunk_end)
            await self._upsert_progress(
                market=market,
                interval=interval,
                tier=progress_tier,
                target_start=start_time,
                target_end=end_time,
                cursor=chunk_end,
                completion_ratio=completion_ratio,
                status="running" if chunk_end < end_time else ("completed" if failed == 0 else "failed"),
            )
            cursor = chunk_end + _INTERVAL_DELTA[interval]

        symbol_count = max(len(symbols), 1)
        chunk_count = max(int(((end_time - start_time).days // max(chunk_days, 1)) + 1), 1)
        return {
            "market": market,
            "interval": interval.value,
            "synced": synced,
            "skipped": skipped,
            "failed": failed,
            "completion_ratio": _completion_ratio(start_time, end_time, last_cursor),
            "batches": chunk_count,
            "expected_items": symbol_count * chunk_count,
        }

    async def _sync_single_symbol(
        self,
        *,
        symbol: str,
        market: str,
        interval: BarInterval,
        start_time: datetime,
        end_time: datetime,
    ) -> None:
        exchange = _to_exchange_kind(market)
        now = self._now_provider()
        try:
            result = await self._gateway.fetch_klines(
                KlineQuery(
                    symbol=symbol,
                    start_time=start_time,
                    end_time=end_time,
                    interval=interval,
                    market=exchange,
                )
            )
        except Exception:
            await self._mark_failure(symbol=symbol, market=market, interval=interval, fetched_at=now)
            raise

        candles = self._to_candles_or_zero_fill(
            symbol=symbol,
            market=exchange,
            interval=interval,
            result=result,
            start_time=start_time,
            end_time=end_time,
        )
        if not candles:
            raise ValueError("weekend window, no candles generated")

        await self._candle_repository.write_batch(candles)
        await self._mark_success(
            symbol=symbol,
            market=market,
            interval=interval,
            fetched_at=now,
            last_bar_time=candles[-1].open_time,
            last_close_time=candles[-1].close_time,
        )

    def _to_candles_or_zero_fill(
        self,
        *,
        symbol: str,
        market: ExchangeKind,
        interval: BarInterval,
        result: KlineFetchResult,
        start_time: datetime,
        end_time: datetime,
    ) -> list[Candle]:
        if result.payload:
            return [self._to_candle(record, market, result.source) for record in result.payload]
        return _generate_zero_candles(
            symbol=symbol,
            market=market,
            interval=interval,
            start_time=start_time,
            end_time=end_time,
        )

    def _to_candle(self, record: KlineRecord, market: ExchangeKind, source: str) -> Candle:
        delta = _INTERVAL_DELTA.get(_interval_from_value(record.interval), timedelta(days=1))
        return Candle(
            symbol=_normalize_symbol(record.symbol),
            interval=_interval_from_value(record.interval),
            open_time=record.bar_time,
            close_time=record.bar_time + delta,
            open_price=record.open or 0.0,
            high_price=record.high or 0.0,
            low_price=record.low or 0.0,
            close_price=record.close or 0.0,
            volume=record.volume or 0.0,
            turnover=record.amount,
            trade_count=None,
            exchange=market,
            adjusted=record.adjusted,
            source=source,
        )

    async def _mark_success(
        self,
        *,
        symbol: str,
        market: str,
        interval: BarInterval,
        fetched_at: datetime,
        last_bar_time: datetime,
        last_close_time: datetime,
    ) -> None:
        async with self._uow_factory() as uow:
            state = await uow.kline_sync_states.get_or_create(symbol, market, interval.value)
            state.last_bar_time = last_bar_time
            state.last_fetched_at = fetched_at
            state.lag_seconds = max((fetched_at - last_close_time).total_seconds(), 0.0)
            state.consecutive_failures = 0
            state.status = "ok" if state.lag_seconds <= (_INTERVAL_DELTA[interval].total_seconds() * 2) else "lagging"
            await uow.kline_sync_states.update(state)

    async def _mark_failure(
        self,
        *,
        symbol: str,
        market: str,
        interval: BarInterval,
        fetched_at: datetime,
    ) -> None:
        async with self._uow_factory() as uow:
            state = await uow.kline_sync_states.get_or_create(symbol, market, interval.value)
            state.last_fetched_at = fetched_at
            state.consecutive_failures = getattr(state, "consecutive_failures", 0) + 1
            state.status = "failed"
            await uow.kline_sync_states.update(state)

    async def _upsert_progress(
        self,
        *,
        market: str,
        interval: BarInterval,
        tier: str,
        target_start: datetime,
        target_end: datetime,
        cursor: datetime,
        completion_ratio: float,
        status: str,
    ) -> None:
        async with self._uow_factory() as uow:
            existing = await uow.backfill_progress.get(market, interval.value, tier)
            if existing is None:
                progress = BackfillProgressDocument(
                    market=market,
                    interval=interval.value,
                    tier=tier,
                    target_start=target_start,
                    target_end=target_end,
                    cursor=cursor,
                    completion_ratio=completion_ratio,
                    status=status,
                )
                await uow.backfill_progress.upsert(progress)
                return

            existing.target_start = target_start
            existing.target_end = target_end
            existing.cursor = cursor
            existing.completion_ratio = completion_ratio
            existing.status = status
            await uow.backfill_progress.upsert(existing)


def _generate_zero_candles(
    *,
    symbol: str,
    market: ExchangeKind,
    interval: BarInterval,
    start_time: datetime,
    end_time: datetime,
) -> list[Candle]:
    bar_times = _expected_bar_times(start_time=start_time, end_time=end_time, interval=interval, market=market)
    delta = _INTERVAL_DELTA[interval]
    return [
        Candle(
            symbol=_normalize_symbol(symbol),
            interval=interval,
            open_time=bar_time,
            close_time=bar_time + delta,
            open_price=0.0,
            high_price=0.0,
            low_price=0.0,
            close_price=0.0,
            volume=0.0,
            turnover=0.0,
            trade_count=0,
            exchange=market,
            adjusted=False,
            source="synthetic_zero_fill",
        )
        for bar_time in bar_times
    ]


def _expected_bar_times(
    *,
    start_time: datetime,
    end_time: datetime,
    interval: BarInterval,
    market: ExchangeKind,
) -> list[datetime]:
    if interval == BarInterval.D1:
        dates = _business_days(start_time.date(), end_time.date())
        return [datetime.combine(day, time.min) for day in dates]
    if interval == BarInterval.M5 and market in {ExchangeKind.SSE, ExchangeKind.SZSE}:
        return _a_share_session_bar_times(start_time, end_time)
    raise ValueError(f"unsupported zero-fill interval: {interval.value}")


def _a_share_session_bar_times(start_time: datetime, end_time: datetime) -> list[datetime]:
    result: list[datetime] = []
    day = start_time.date()
    while day <= end_time.date():
        if not _is_weekend(day):
            for session_start, session_end in _A_SHARE_SESSIONS:
                cursor = _align_time(datetime.combine(day, session_start), BarInterval.M5)
                close_time = datetime.combine(day, session_end)
                while cursor <= close_time:
                    if start_time <= cursor <= end_time:
                        result.append(cursor)
                    cursor += _INTERVAL_DELTA[BarInterval.M5]
        day += timedelta(days=1)
    return result


def _business_days(start_date: date, end_date: date) -> list[date]:
    result: list[date] = []
    cursor = start_date
    while cursor <= end_date:
        if not _is_weekend(cursor):
            result.append(cursor)
        cursor += timedelta(days=1)
    return result


def _completion_ratio(start_time: datetime, end_time: datetime, cursor: datetime) -> float:
    total_seconds = max((end_time - start_time).total_seconds(), 1.0)
    progressed = min(max((cursor - start_time).total_seconds(), 0.0), total_seconds)
    return progressed / total_seconds


def _align_time(value: datetime, interval: BarInterval) -> datetime:
    if interval == BarInterval.M5:
        minute = (value.minute // 5) * 5
        return value.replace(minute=minute, second=0, microsecond=0)
    if interval == BarInterval.D1:
        return datetime.combine(value.date(), time.min)
    raise ValueError(f"unsupported alignment interval: {interval.value}")


def _interval_from_value(value: str) -> BarInterval:
    for interval in BarInterval:
        if interval.value == value:
            return interval
    raise ValueError(f"unsupported interval value: {value}")


def _to_exchange_kind(market: str) -> ExchangeKind:
    normalized = _normalize_market_name(market)
    if normalized == "sse":
        return ExchangeKind.SSE
    if normalized == "szse":
        return ExchangeKind.SZSE
    return ExchangeKind.OTHER


def _to_basic_info_markets(market: str) -> tuple[str, ...]:
    normalized = _normalize_market_name(market)
    if normalized == "sse":
        return ("sh",)
    if normalized == "szse":
        return ("sz",)
    return (normalized,)


def _normalize_market_name(market: str) -> str:
    normalized = market.strip().lower()
    if normalized in {"sh", "sse"}:
        return "sse"
    if normalized in {"sz", "szse"}:
        return "szse"
    return normalized


def _symbol_in_market(symbol: str, market: str) -> bool:
    normalized_symbol = _normalize_symbol(symbol)
    normalized_market = _normalize_market_name(market)
    if normalized_market == "sse":
        return normalized_symbol.endswith(".SH")
    if normalized_market == "szse":
        return normalized_symbol.endswith(".SZ")
    return True


def _normalize_symbol(symbol: str) -> str:
    raw = symbol.strip()
    if not raw:
        return raw
    if raw.endswith((".sh", ".sz")):
        code, suffix = raw.split(".", 1)
        return f"{code}.{suffix.upper()}"
    return raw.upper()


def _is_weekend(value: date) -> bool:
    return value.weekday() >= 5
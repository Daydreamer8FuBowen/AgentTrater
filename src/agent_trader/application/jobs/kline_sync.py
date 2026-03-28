from __future__ import annotations

import logging
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta

from agent_trader.application.data_access.gateway import DataAccessGateway
from agent_trader.core.config import KlineSyncConfig
from agent_trader.core.time import (
    ensure_utc,
    market_date,
    market_time_to_utc,
    to_market_time,
    utc_now,
)
from agent_trader.domain.models import BarInterval, Candle, ExchangeKind
from agent_trader.ingestion.models import KlineFetchResult, KlineQuery, KlineRecord
from agent_trader.storage.base import CandleRepository, UnitOfWork

logger = logging.getLogger(__name__)

_A_SHARE_MORNING_SESSION = (time(9, 30), time(11, 30))
_A_SHARE_AFTERNOON_SESSION = (time(13, 0), time(15, 0))
_A_SHARE_D1_OPEN_TIME = time(9, 0)
_INTERVAL_DELTA = {
    BarInterval.M5: timedelta(minutes=5),
    BarInterval.D1: timedelta(days=1),
}


@dataclass(slots=True, frozen=True)
class TieredSymbols:
    market: ExchangeKind
    positions: tuple[str, ...]
    candidates: tuple[str, ...]
    others: tuple[str, ...]

    @property
    def positions_and_candidates(self) -> tuple[str, ...]:
        return self.positions + self.candidates

    @property
    def all_symbols(self) -> tuple[str, ...]:
        return self.positions + self.candidates + self.others

    def slice_all_symbols(self, cursor: int, batch_size: int) -> tuple[str, ...]:
        return self.all_symbols[cursor : cursor + batch_size]

    def slice_positions_and_candidates(self, cursor: int, batch_size: int) -> tuple[str, ...]:
        combined = self.positions_and_candidates
        return combined[cursor : cursor + batch_size]


class TierCollectionService:
    """按市场汇总 Tier A/B/C symbol 集合。"""

    def __init__(self, uow_factory: Callable[[], UnitOfWork]) -> None:
        self._uow_factory = uow_factory

    async def collect(self, market: ExchangeKind) -> TieredSymbols:
        normalized_market = market

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
                if symbol not in position_set and symbol not in candidate_set
            }
        )

        return TieredSymbols(
            market=normalized_market,
            positions=tuple(position_symbols),
            candidates=tuple(candidate_symbols),
            others=tuple(other_symbols),
        )


class KlineSyncService:
    """按市场执行实时与历史 K 线同步。"""

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
        self._now_provider = now_provider or utc_now

    async def sync_market(self, market: ExchangeKind) -> dict[str, object]:
        # 记录 job 入口：哪个 market 被触发
        now = self._now_provider()
        tiers = await self._tier_collection_service.collect(market)
        job_name = f"kline_market_sync_{tiers.market}"
        logger.info(
            "[%s] 开始 market 同步 market=%s now=%s", job_name, tiers.market, now.isoformat()
        )

        # 根据当前时间决定是实时模式还是历史模式
        if _is_market_trading_time(now, tiers.market):
            realtime = await self._sync_realtime_market(tiers, now)
            logger.info("[%s] 实时同步完成 market=%s result=%s", job_name, tiers.market, realtime)
            return {"market": tiers.market, "mode": "realtime", "realtime_m5": realtime}

        history = await self._sync_history_market(tiers, now)
        logger.info("[%s] 历史同步完成 market=%s result=%s", job_name, tiers.market, history)
        return {"market": tiers.market, "mode": "history", "history": history}

    async def sync_realtime_m5_positions(self, market: ExchangeKind) -> dict[str, int | str]:
        tiers = await self._tier_collection_service.collect(market)
        return await self._sync_realtime_tier_symbols(
            market=tiers.market,
            symbols=tiers.positions,
            tier_name="positions",
            now=self._now_provider(),
        )

    async def sync_realtime_m5_candidates(self, market: ExchangeKind) -> dict[str, int | str]:
        tiers = await self._tier_collection_service.collect(market)
        return await self._sync_realtime_tier_symbols(
            market=tiers.market,
            symbols=tiers.candidates,
            tier_name="candidates",
            now=self._now_provider(),
        )

    async def sync_backfill_d1_all(self, market: ExchangeKind) -> dict[str, int | str | float]:
        tiers = await self._tier_collection_service.collect(market)
        summary = await self._sync_history_interval(
            market=tiers.market,
            symbols=tiers.all_symbols,
            interval=BarInterval.D1,
            now=self._now_provider(),
        )
        summary["tier"] = "all"
        return summary

    async def sync_backfill_m5_positions_candidates(
        self, market: ExchangeKind
    ) -> dict[str, int | str | float]:
        tiers = await self._tier_collection_service.collect(market)
        summary = await self._sync_history_interval(
            market=tiers.market,
            symbols=tiers.positions_and_candidates,
            interval=BarInterval.M5,
            now=self._now_provider(),
        )
        summary["tier"] = "positions_and_candidates"
        return summary

    async def _sync_realtime_market(
        self, tiers: TieredSymbols, now: datetime
    ) -> dict[str, dict[str, int | str]]:
        positions = await self._sync_realtime_tier_symbols(
            market=tiers.market,
            symbols=tiers.positions,
            tier_name="positions",
            now=now,
        )
        candidates = await self._sync_realtime_tier_symbols(
            market=tiers.market,
            symbols=tiers.candidates,
            tier_name="candidates",
            now=now,
        )
        return {"positions": positions, "candidates": candidates}

    async def _sync_history_market(
        self, tiers: TieredSymbols, now: datetime
    ) -> dict[str, dict[str, int | str | float]]:
        d1_summary = await self._sync_history_interval(
            market=tiers.market,
            symbols=tiers.all_symbols,
            interval=BarInterval.D1,
            now=now,
        )
        m5_summary = await self._sync_history_interval(
            market=tiers.market,
            symbols=tiers.positions_and_candidates,
            interval=BarInterval.M5,
            now=now,
        )
        return {"1d": d1_summary, "5m": m5_summary}

    async def _sync_realtime_tier_symbols(
        self,
        *,
        market: ExchangeKind,
        symbols: Sequence[str],
        tier_name: str,
        now: datetime,
    ) -> dict[str, int | str]:
        # 如果当前并非交易时间，跳过实时同步
        if not _is_market_trading_time(now, market):
            logger.info(
                "[kline_market_sync_%s] 非交易时间，跳过实时同步 tier=%s symbols=%d",
                market,
                tier_name,
                len(symbols),
            )
            return {
                "market": market,
                "tier": tier_name,
                "synced": 0,
                "skipped": len(symbols),
                "failed": 0,
                "mode": "not_trading",
            }

        window = _realtime_m5_window(now, market)
        if window is None:
            logger.info(
                "[kline_market_sync_%s] 等待第一个 5m 完成后再同步 tier=%s", market, tier_name
            )
            return {
                "market": market,
                "tier": tier_name,
                "synced": 0,
                "skipped": len(symbols),
                "failed": 0,
                "mode": "await_bar_close",
            }

        start_time, end_time = window
        return await self._sync_symbol_set(
            symbols=symbols,
            market=market,
            interval=BarInterval.M5,
            start_time=start_time,
            end_time=end_time,
            target_latest=end_time,
            mode="realtime",
            tier_name=tier_name,
        )

    async def _sync_history_interval(
        self,
        *,
        market: ExchangeKind,
        symbols: Sequence[str],
        interval: BarInterval,
        now: datetime,
    ) -> dict[str, int | str | float]:
        # 历史回溯入口，记录将要处理的符号数量与 window 配置
        if not symbols:
            return {
                "market": market,
                "interval": interval.value,
                "synced": 0,
                "skipped": 0,
                "failed": 0,
                "completion_ratio": 1.0,
                "mode": "history",
            }
        logger.info(
            "[kline_market_sync_%s] 历史回溯 interval=%s symbols=%d d1_window=%d m5_window=%d",
            market,
            interval.value,
            len(symbols),
            self._config.d1_window_days,
            self._config.m5_window_days,
        )

        synced = 0
        skipped = 0
        failed = 0
        target_latest = _latest_completed_bar_start(now, market, interval)
        if target_latest is None:
            return {
                "market": market,
                "interval": interval.value,
                "synced": 0,
                "skipped": len(symbols),
                "failed": 0,
                "completion_ratio": 0.0,
                "mode": "history",
            }
        batch_synced, batch_skipped, batch_failed = await self._sync_history_batch(
            market=market,
            interval=interval,
            symbols=symbols,
            target_latest=target_latest,
            now=now,
        )
        synced += batch_synced
        skipped += batch_skipped
        failed += batch_failed

        completion_ratio = 1.0 if not symbols else synced / len(symbols)
        return {
            "market": market,
            "interval": interval.value,
            "synced": synced,
            "skipped": skipped,
            "failed": failed,
            "completion_ratio": completion_ratio,
            "mode": "history",
        }

    async def _sync_history_batch(
        self,
        *,
        market: ExchangeKind,
        interval: BarInterval,
        symbols: Sequence[str],
        target_latest: datetime,
        now: datetime,
    ) -> tuple[int, int, int]:
        synced = 0
        skipped = 0
        failed = 0
        states = await self._get_sync_states(symbols=symbols, market=market, interval=interval)
        for symbol in symbols:
            state = states.get(symbol)
            try:
                if self._is_symbol_already_latest(
                    state=state,
                    market=market,
                    interval=interval,
                    target_latest=target_latest,
                ):
                    skipped += 1
                    logger.info(
                        "[kline_market_sync_%s] symbol=%s interval=%s 状态已最新，跳过历史更新",
                        market,
                        symbol,
                        interval.value,
                    )
                    continue
                ranges = await self._build_history_ranges(
                    symbol=symbol,
                    market=market,
                    interval=interval,
                    state=state,
                    target_latest=target_latest,
                    now=now,
                )
                if not ranges:
                    skipped += 1
                    continue
                for start_time, end_time in ranges:
                    outcome = await self._sync_single_symbol(
                        symbol=symbol,
                        market=market,
                        interval=interval,
                        start_time=start_time,
                        end_time=end_time,
                        state=state,
                        target_latest=target_latest,
                    )
                    if outcome == "failed":
                        failed += 1
                        break
                else:
                    synced += 1
            except ValueError:
                skipped += 1
            except Exception:
                logger.exception(
                    "K线历史同步失败 symbol=%s market=%s interval=%s",
                    symbol,
                    market,
                    interval.value,
                )
                failed += 1
        return synced, skipped, failed

    async def _build_history_ranges(
        self,
        *,
        symbol: str,
        market: ExchangeKind,
        interval: BarInterval,
        state: object | None,
        target_latest: datetime,
        now: datetime,
    ) -> list[tuple[datetime, datetime]]:
        if state is not None and _should_skip_history_sync(
            state_last_bar_time=getattr(state, "last_bar_time", None),
            market=market,
            interval=interval,
            now=now,
            target_latest=target_latest,
        ):
            return []

        start_time = _history_sync_start(
            state_last_bar_time=getattr(state, "last_bar_time", None)
            if state is not None
            else None,
            interval=interval,
            market=market,
            now=now,
            d1_window_days=self._config.d1_window_days,
            m5_window_days=self._config.m5_window_days,
        )
        if start_time > target_latest:
            return []

        if interval == BarInterval.M5:
            return _chunked_time_ranges(
                start_time=start_time,
                end_time=target_latest,
                interval=interval,
                chunk_days=max(self._config.m5_backfill_chunk_days, 1),
            )
        return [(start_time, target_latest)]

    async def _sync_symbol_set(
        self,
        *,
        symbols: Sequence[str],
        market: ExchangeKind,
        interval: BarInterval,
        start_time: datetime,
        end_time: datetime,
        target_latest: datetime,
        mode: str,
        tier_name: str | None = None,
    ) -> dict[str, int | str]:
        # 同步一组 symbol（可以是 positions / candidates / batch）
        synced = 0
        failed = 0
        skipped = 0
        logger.info(
            "[kline_market_sync_%s] 准备同步 symbol set count=%d interval=%s range=[%s,%s] "
            "mode=%s tier=%s",
            market,
            len(symbols),
            interval.value,
            start_time.isoformat(),
            end_time.isoformat(),
            mode,
            tier_name,
        )
        states = await self._get_sync_states(symbols=symbols, market=market, interval=interval)
        for symbol in symbols:
            logger.debug(
                "[kline_market_sync_%s] 开始 symbol=%s interval=%s range=[%s,%s]",
                market,
                symbol,
                interval.value,
                start_time.isoformat(),
                end_time.isoformat(),
            )
            try:
                outcome = await self._sync_single_symbol(
                    symbol=symbol,
                    market=market,
                    interval=interval,
                    start_time=start_time,
                    end_time=end_time,
                    state=states.get(symbol),
                    target_latest=target_latest,
                )
                if outcome == "synced":
                    synced += 1
                elif outcome == "failed":
                    failed += 1
                else:
                    skipped += 1
            except ValueError:
                logger.info("[kline_market_sync_%s] symbol=%s 无数据或被跳过", market, symbol)
                skipped += 1
            except Exception:
                logger.exception(
                    "K线同步失败 symbol=%s market=%s interval=%s range=[%s,%s]",
                    symbol,
                    market,
                    interval.value,
                    start_time.isoformat(),
                    end_time.isoformat(),
                )
                failed += 1
        summary: dict[str, int | str] = {
            "market": market,
            "interval": interval.value,
            "synced": synced,
            "skipped": skipped,
            "failed": failed,
            "mode": mode,
        }
        if tier_name is not None:
            summary["tier"] = tier_name
        return summary

    async def _sync_single_symbol(
        self,
        *,
        symbol: str,
        market: ExchangeKind,
        interval: BarInterval,
        start_time: datetime,
        end_time: datetime,
        state: object | None,
        target_latest: datetime,
    ) -> str:
        exchange = _to_exchange_kind(market)
        now = self._now_provider()
        if self._is_symbol_already_latest(
            state=state,
            market=market,
            interval=interval,
            target_latest=target_latest,
        ):
            logger.info(
                "[kline_market_sync_%s] symbol=%s interval=%s 已同步到最新，跳过接口请求",
                market,
                symbol,
                interval.value,
            )
            return "skipped"
        available_sources = await self._get_available_sources_for_symbol(symbol)
        extra = {"available_sources": available_sources} if available_sources else {}
        try:
            job_name = f"kline_market_sync_{market}"
            # 记录单个 symbol 的请求信息：范围、周期与可用源限制
            logger.info(
                "[%s] 请求 K 线 symbol=%s interval=%s range=[%s,%s] available_sources=%s",
                job_name,
                symbol,
                interval.value,
                start_time.isoformat(),
                end_time.isoformat(),
                available_sources,
            )
            result = await self._gateway.fetch_klines(
                KlineQuery(
                    symbol=symbol,
                    start_time=start_time,
                    end_time=end_time,
                    interval=interval,
                    market=exchange,
                    extra=extra,
                )
            )
        except Exception:
            logger.exception(
                "K线接口请求失败，跳过当前 symbol symbol=%s market=%s interval=%s",
                symbol,
                market,
                interval.value,
            )
            await self._mark_failure(
                symbol=symbol, market=market, interval=interval, fetched_at=now
            )
            return "skipped"

        candles = self._to_candles(result=result, market=exchange)
        if not candles:
            logger.info(
                "[%s] 接口无可写入数据，跳过 symbol=%s interval=%s",
                job_name,
                symbol,
                interval.value,
            )
            return "skipped"
        # 成功获取 candles 后，记录数量、首尾时间与价格范围
        try:
            first_time = candles[0].open_time.isoformat()
            last_time = candles[-1].open_time.isoformat()
            closes = [c.close_price for c in candles if c.close_price is not None]
            min_close = min(closes) if closes else None
            max_close = max(closes) if closes else None
            logger.info(
                "[%s] 获取到 K 线 symbol=%s bars=%d first=%s last=%s close_range=[%s,%s]",
                job_name,
                symbol,
                len(candles),
                first_time,
                last_time,
                min_close,
                max_close,
            )
        except Exception:
            logger.debug("[%s] 获取 K 线后统计信息失败 symbol=%s", job_name, symbol, exc_info=True)

        await self._candle_repository.write_batch(candles)
        await self._mark_success(
            symbol=symbol,
            market=market,
            interval=interval,
            fetched_at=now,
            last_bar_time=candles[-1].open_time,
        )
        return "synced"

    def _to_candles(self, *, result: KlineFetchResult, market: ExchangeKind) -> list[Candle]:
        return [self._to_candle(record, market, result.source) for record in result.payload]

    def _to_candle(self, record: KlineRecord, market: ExchangeKind, source: str) -> Candle:
        interval = _interval_from_value(record.interval)
        delta = _INTERVAL_DELTA[interval]
        return Candle(
            symbol=_normalize_symbol(record.symbol),
            interval=interval,
            open_time=ensure_utc(record.bar_time),
            close_time=ensure_utc(record.bar_time + delta),
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

    async def _get_sync_states(
        self,
        *,
        symbols: Sequence[str],
        market: ExchangeKind,
        interval: BarInterval,
    ) -> dict[str, object]:
        states: dict[str, object] = {}
        if not symbols:
            return states
        async with self._uow_factory() as uow:
            for symbol in symbols:
                state = await uow.kline_sync_states.get(symbol, market, interval.value)
                if state is not None:
                    states[symbol] = state
        return states

    async def _get_available_sources_for_symbol(self, symbol: str) -> list[str] | None:
        async with self._uow_factory() as uow:
            return await uow.basic_infos.get_available_sources_by_symbol(symbol)

    def _is_symbol_already_latest(
        self,
        *,
        state: object | None,
        market: ExchangeKind,
        interval: BarInterval,
        target_latest: datetime,
    ) -> bool:
        if state is None:
            return False
        state_last_bar_time = getattr(state, "last_bar_time", None)
        if state_last_bar_time is None:
            return False
        if interval == BarInterval.D1 and _is_weekend_non_trading_market(market):
            return market_date(state_last_bar_time, market) >= market_date(target_latest, market)
        return ensure_utc(state_last_bar_time) >= ensure_utc(target_latest)

    async def _mark_success(
        self,
        *,
        symbol: str,
        market: ExchangeKind,
        interval: BarInterval,
        fetched_at: datetime,
        last_bar_time: datetime,
    ) -> None:
        async with self._uow_factory() as uow:
            state = await uow.kline_sync_states.get_or_create(symbol, market, interval.value)
            state.last_bar_time = last_bar_time
            state.last_fetched_at = fetched_at
            state.status = "ok"
            await uow.kline_sync_states.update(state)

    async def _mark_failure(
        self,
        *,
        symbol: str,
        market: ExchangeKind,
        interval: BarInterval,
        fetched_at: datetime,
    ) -> None:
        async with self._uow_factory() as uow:
            state = await uow.kline_sync_states.get_or_create(symbol, market, interval.value)
            state.last_fetched_at = fetched_at
            state.status = "failed"
            await uow.kline_sync_states.update(state)


def _chunked_time_ranges(
    *,
    start_time: datetime,
    end_time: datetime,
    interval: BarInterval,
    chunk_days: int,
) -> list[tuple[datetime, datetime]]:
    ranges: list[tuple[datetime, datetime]] = []
    cursor = start_time
    while cursor <= end_time:
        chunk_end = min(cursor + timedelta(days=chunk_days) - _INTERVAL_DELTA[interval], end_time)
        ranges.append((cursor, chunk_end))
        cursor = chunk_end + _INTERVAL_DELTA[interval]
    return ranges


def _history_sync_start(
    *,
    state_last_bar_time: datetime | None,
    interval: BarInterval,
    market: ExchangeKind,
    now: datetime,
    d1_window_days: int,
    m5_window_days: int,
) -> datetime:
    if state_last_bar_time is not None:
        return ensure_utc(state_last_bar_time) + _INTERVAL_DELTA[interval]

    current_day = market_date(now, market)
    if interval == BarInterval.D1:
        return market_time_to_utc(
            datetime.combine(current_day - timedelta(days=d1_window_days), _A_SHARE_D1_OPEN_TIME),
            market,
        )
    if interval == BarInterval.M5:
        return market_time_to_utc(
            datetime.combine(
                current_day - timedelta(days=m5_window_days), _A_SHARE_MORNING_SESSION[0]
            ),
            market,
        )
    raise ValueError(f"unsupported interval: {interval.value}")


def _should_skip_history_sync(
    *,
    state_last_bar_time: datetime | None,
    market: ExchangeKind,
    interval: BarInterval,
    now: datetime,
    target_latest: datetime,
) -> bool:
    if state_last_bar_time is None:
        return False

    last_bar_time = ensure_utc(state_last_bar_time)
    if not _is_trade_day(now, market):
        return last_bar_time >= target_latest

    expected_latest = _expected_trade_day_latest(now, market, interval)
    if expected_latest is None:
        return last_bar_time >= target_latest
    return last_bar_time >= expected_latest


def _expected_trade_day_latest(
    now: datetime, market: ExchangeKind, interval: BarInterval
) -> datetime | None:
    current_day = market_date(now, market)
    if interval == BarInterval.D1:
        return market_time_to_utc(datetime.combine(current_day, _A_SHARE_D1_OPEN_TIME), market)
    if interval == BarInterval.M5:
        return market_time_to_utc(datetime.combine(current_day, time(14, 55)), market)
    return None


def _latest_completed_bar_start(
    now: datetime, market: ExchangeKind, interval: BarInterval
) -> datetime | None:
    local_now = to_market_time(now, market)
    current_day = local_now.date()

    if interval == BarInterval.D1:
        if _is_weekend(current_day) and _is_weekend_non_trading_market(market):
            previous_day = _previous_business_day(current_day)
            return market_time_to_utc(datetime.combine(previous_day, _A_SHARE_D1_OPEN_TIME), market)
        if _is_market_trading_time(now, market):
            previous_day = _previous_business_day(current_day)
            return market_time_to_utc(datetime.combine(previous_day, _A_SHARE_D1_OPEN_TIME), market)
        return market_time_to_utc(datetime.combine(current_day, _A_SHARE_D1_OPEN_TIME), market)

    if interval == BarInterval.M5:
        return _latest_completed_m5_bar_start(local_now, market)

    raise ValueError(f"unsupported interval: {interval.value}")


def _latest_completed_m5_bar_start(local_now: datetime, market: ExchangeKind) -> datetime | None:
    current_day = local_now.date()
    if _is_weekend(current_day) and _is_weekend_non_trading_market(market):
        return None

    time_now = local_now.time()
    if time_now < time(9, 35):
        return None
    if _A_SHARE_MORNING_SESSION[0] <= time_now <= _A_SHARE_MORNING_SESSION[1]:
        minute = ((local_now.minute - 5) // 5) * 5
        return market_time_to_utc(local_now.replace(minute=minute, second=0, microsecond=0), market)
    if time(11, 30) < time_now < time(13, 0):
        return market_time_to_utc(datetime.combine(current_day, time(11, 30)), market)
    if _A_SHARE_AFTERNOON_SESSION[0] <= time_now <= _A_SHARE_AFTERNOON_SESSION[1]:
        minute = ((local_now.minute - 5) // 5) * 5
        return market_time_to_utc(local_now.replace(minute=minute, second=0, microsecond=0), market)
    return market_time_to_utc(datetime.combine(current_day, time(15, 0)), market)


def _realtime_m5_window(
    now: datetime, market: ExchangeKind
) -> tuple[datetime, datetime] | None:
    end_time = _latest_completed_bar_start(now, market, BarInterval.M5)
    if end_time is None:
        return None
    current_day = market_date(now, market)
    start_time = market_time_to_utc(
        datetime.combine(current_day, _A_SHARE_MORNING_SESSION[0]), market
    )
    return start_time, end_time


def _is_market_trading_time(now: datetime, market: ExchangeKind) -> bool:
    if not _is_trade_day(now, market):
        return False
    current = to_market_time(now, market).time()
    return (
        _A_SHARE_MORNING_SESSION[0] <= current <= _A_SHARE_MORNING_SESSION[1]
        or _A_SHARE_AFTERNOON_SESSION[0] <= current <= _A_SHARE_AFTERNOON_SESSION[1]
    )


def _is_trade_day(value: datetime, market: ExchangeKind) -> bool:
    market_day = market_date(value, market)
    if _is_weekend_non_trading_market(market):
        return not _is_weekend(market_day)
    return True


def _previous_business_day(value: date) -> date:
    cursor = value - timedelta(days=1)
    while _is_weekend(cursor):
        cursor -= timedelta(days=1)
    return cursor


def _interval_from_value(value: str) -> BarInterval:
    for interval in BarInterval:
        if interval.value == value:
            return interval
    raise ValueError(f"unsupported interval value: {value}")


def _to_exchange_kind(market: ExchangeKind) -> ExchangeKind:
    return market


def _to_basic_info_markets(market: ExchangeKind) -> tuple[ExchangeKind, ...]:
    return (market,)


def _is_a_share_market(market: ExchangeKind) -> bool:
    return market in {ExchangeKind.SSE, ExchangeKind.SZSE}


def _symbol_in_market(symbol: str, market: ExchangeKind) -> bool:
    normalized_symbol = _normalize_symbol(symbol)
    if market == ExchangeKind.SSE:
        return normalized_symbol.endswith(".SH")
    if market == ExchangeKind.SZSE:
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


def _is_weekend_non_trading_market(market: ExchangeKind) -> bool:
    return market in {
        ExchangeKind.SSE,
        ExchangeKind.SZSE,
        ExchangeKind.HKEX,
        ExchangeKind.NASDAQ,
        ExchangeKind.NYSE,
    }

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# InMemoryEventStore 是一个“测试用内存数据库容器”，用于在不连真实 Mongo/Influx 的情况下，临时保存各类仓储数据。

@dataclass
class InMemoryEventStore:
    task_runs: list[Any] = field(default_factory=list)
    task_events: list[Any] = field(default_factory=list)
    task_artifacts: list[Any] = field(default_factory=list)
    news_items: list[Any] = field(default_factory=list)
    basic_info_items: dict[str, Any] = field(default_factory=dict)
    candidates: list[Any] = field(default_factory=list)
    positions: list[Any] = field(default_factory=list)
    memories: list[Any] = field(default_factory=list)
    signals: list[Any] = field(default_factory=list)
    candles: list[Any] = field(default_factory=list)
    kline_sync_states: dict[str, Any] = field(default_factory=dict)  # key: "symbol:market:interval"
    backfill_progress: dict[str, Any] = field(default_factory=dict)  # key: "market:interval:tier"
    commit_count: int = 0
    rollback_count: int = 0


class _InMemoryTaskRunRepository:
    def __init__(self, store: InMemoryEventStore) -> None:
        self._store = store

    async def add(self, task_run: Any) -> Any:
        self._store.task_runs.append(task_run)
        return task_run

    async def get(self, run_id: str) -> Any | None:
        for task_run in self._store.task_runs:
            if getattr(task_run, "run_id", None) == run_id:
                return task_run
        return None

    async def mark_running(self, run_id: str) -> None:
        task_run = await self.get(run_id)
        if task_run is not None:
            task_run.status = "running"

    async def mark_completed(self, run_id: str, *, result_summary: str | None) -> None:
        task_run = await self.get(run_id)
        if task_run is not None:
            task_run.status = "completed"
            task_run.result["summary"] = result_summary

    async def mark_failed(self, run_id: str, *, error_message: str) -> None:
        task_run = await self.get(run_id)
        if task_run is not None:
            task_run.status = "failed"
            task_run.error = {"message": error_message}


class _InMemoryTaskEventRepository:
    def __init__(self, store: InMemoryEventStore) -> None:
        self._store = store

    async def add(self, event: Any) -> Any:
        self._store.task_events.append(event)
        return event


class _InMemoryTaskArtifactRepository:
    def __init__(self, store: InMemoryEventStore) -> None:
        self._store = store

    async def add(self, artifact: Any) -> Any:
        self._store.task_artifacts.append(artifact)
        return artifact


class _InMemoryNewsRepository:
    def __init__(self, store: InMemoryEventStore) -> None:
        self._store = store

    async def add(self, news: Any) -> Any:
        self._store.news_items.append(news)
        return news

    async def add_many(self, items: list[Any]) -> list[Any]:
        self._store.news_items.extend(items)
        return items

    async def exists_by_dedupe_key(self, dedupe_key: str) -> bool:
        return any(getattr(item, "dedupe_key", None) == dedupe_key for item in self._store.news_items)


class _InMemoryBasicInfoRepository:
    def __init__(self, store: InMemoryEventStore) -> None:
        self._store = store

    async def upsert_many_by_symbol(self, items: list[Any]) -> dict[str, int]:
        requested = len(items)
        matched = 0
        upserted = 0
        for item in items:
            symbol = getattr(item, "symbol", None)
            if not symbol:
                continue
            if symbol in self._store.basic_info_items:
                matched += 1
            else:
                upserted += 1
            self._store.basic_info_items[symbol] = item

        return {
            "requested": requested,
            "matched": matched,
            "modified": matched,
            "upserted": upserted,
        }

    async def list_symbols_by_market(self, market: str) -> list[str]:
        return [
            sym
            for sym, item in self._store.basic_info_items.items()
            if getattr(item, "market", None) == market
            and getattr(item, "status", None) not in {"delisted", "0", 0}
            and (
                market not in {"sh", "sz"}
                or (
                    getattr(item, "security_type", None) == "stock"
                    and "ST" not in str(getattr(item, "name", "") or "")
                )
            )
        ]


class _InMemoryCandidateRepository:
    def __init__(self, store: InMemoryEventStore) -> None:
        self._store = store

    async def upsert(self, candidate: Any) -> Any:
        self._store.candidates.append(candidate)
        return candidate

    async def list_active(self) -> list[Any]:
        return list(self._store.candidates)


class _InMemoryPositionRepository:
    def __init__(self, store: InMemoryEventStore) -> None:
        self._store = store

    async def upsert(self, position: Any) -> Any:
        self._store.positions.append(position)
        return position

    async def list_active(self) -> list[Any]:
        return list(self._store.positions)


class _InMemoryMemoryRepository:
    def __init__(self, store: InMemoryEventStore) -> None:
        self._store = store

    async def add(self, record: Any) -> Any:
        self._store.memories.append(record)
        return record


class _InMemorySignalRepository:
    def __init__(self, store: InMemoryEventStore) -> None:
        self._store = store

    async def write(self, snapshot: Any) -> None:
        self._store.signals.append(snapshot)


class _InMemoryCandleRepository:
    def __init__(self, store: InMemoryEventStore) -> None:
        self._store = store

    async def write(self, candle: Any) -> None:
        self._store.candles.append(candle)

    async def write_batch(self, candles: list[Any]) -> None:
        self._store.candles.extend(candles)


class _InMemoryKlineSyncStateRepository:
    def __init__(self, store: InMemoryEventStore) -> None:
        self._store = store

    async def get_or_create(self, symbol: str, market: str, interval: str) -> Any:
        key = f"{symbol}:{market}:{interval}"
        if key not in self._store.kline_sync_states:
            self._store.kline_sync_states[key] = {
                "state_id": key,
                "symbol": symbol,
                "market": market,
                "interval": interval,
                "last_bar_time": None,
                "last_fetched_at": None,
                "lag_seconds": 0.0,
                "consecutive_failures": 0,
                "status": "ok",
            }
        return type("SyncState", (), self._store.kline_sync_states[key])()

    async def update(self, state: Any) -> None:
        key = f"{state.symbol}:{state.market}:{state.interval}"
        self._store.kline_sync_states[key] = {
            "state_id": getattr(state, "state_id", key),
            "symbol": state.symbol,
            "market": state.market,
            "interval": state.interval,
            "last_bar_time": getattr(state, "last_bar_time", None),
            "last_fetched_at": getattr(state, "last_fetched_at", None),
            "lag_seconds": getattr(state, "lag_seconds", 0.0),
            "consecutive_failures": getattr(state, "consecutive_failures", 0),
            "status": getattr(state, "status", "ok"),
        }


class _InMemoryBackfillProgressRepository:
    def __init__(self, store: InMemoryEventStore) -> None:
        self._store = store

    async def get(self, market: str, interval: str, tier: str) -> Any | None:
        key = f"{market}:{interval}:{tier}"
        return self._store.backfill_progress.get(key)

    async def upsert(self, progress: Any) -> None:
        market = getattr(progress, "market", "")
        interval = getattr(progress, "interval", "")
        tier = getattr(progress, "tier", "")
        key = f"{market}:{interval}:{tier}"
        self._store.backfill_progress[key] = progress

    async def update_cursor(self, progress_id: str, cursor: Any, completion_ratio: float) -> None:
        for prog in self._store.backfill_progress.values():
            if getattr(prog, "progress_id", None) == progress_id:
                prog.cursor = cursor
                prog.completion_ratio = completion_ratio
                break


class InMemoryUnitOfWork:
    def __init__(self, store: InMemoryEventStore | None = None) -> None:
        self.store = store or InMemoryEventStore()
        self.task_runs = _InMemoryTaskRunRepository(self.store)
        self.task_events = _InMemoryTaskEventRepository(self.store)
        self.task_artifacts = _InMemoryTaskArtifactRepository(self.store)
        self.news = _InMemoryNewsRepository(self.store)
        self.basic_infos = _InMemoryBasicInfoRepository(self.store)
        self.candidates = _InMemoryCandidateRepository(self.store)
        self.positions = _InMemoryPositionRepository(self.store)
        self.memories = _InMemoryMemoryRepository(self.store)
        self.signals = _InMemorySignalRepository(self.store)
        self.candles = _InMemoryCandleRepository(self.store)
        self.kline_sync_states = _InMemoryKlineSyncStateRepository(self.store)
        self.backfill_progress = _InMemoryBackfillProgressRepository(self.store)

    async def __aenter__(self) -> InMemoryUnitOfWork:
        return self

    async def __aexit__(self, exc_type: object, exc: object, tb: object) -> None:
        del exc, tb
        if exc_type is None:
            await self.commit()
            return
        await self.rollback()

    async def commit(self) -> None:
        self.store.commit_count += 1

    async def rollback(self) -> None:
        self.store.rollback_count += 1

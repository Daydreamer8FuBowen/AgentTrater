from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class InMemoryEventStore:
    task_runs: list[Any] = field(default_factory=list)
    task_events: list[Any] = field(default_factory=list)
    task_artifacts: list[Any] = field(default_factory=list)
    news_items: list[Any] = field(default_factory=list)
    candidates: list[Any] = field(default_factory=list)
    memories: list[Any] = field(default_factory=list)
    signals: list[Any] = field(default_factory=list)
    candles: list[Any] = field(default_factory=list)
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


class _InMemoryCandidateRepository:
    def __init__(self, store: InMemoryEventStore) -> None:
        self._store = store

    async def upsert(self, candidate: Any) -> Any:
        self._store.candidates.append(candidate)
        return candidate

    async def list_active(self) -> list[Any]:
        return list(self._store.candidates)


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


class InMemoryUnitOfWork:
    def __init__(self, store: InMemoryEventStore | None = None) -> None:
        self.store = store or InMemoryEventStore()
        self.task_runs = _InMemoryTaskRunRepository(self.store)
        self.task_events = _InMemoryTaskEventRepository(self.store)
        self.task_artifacts = _InMemoryTaskArtifactRepository(self.store)
        self.news = _InMemoryNewsRepository(self.store)
        self.candidates = _InMemoryCandidateRepository(self.store)
        self.memories = _InMemoryMemoryRepository(self.store)
        self.signals = _InMemorySignalRepository(self.store)
        self.candles = _InMemoryCandleRepository(self.store)

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

from __future__ import annotations

import asyncio
import importlib
from types import SimpleNamespace

import pytest

from agent_trader.core.config import Settings
from agent_trader.worker.main import WorkerRuntime, bootstrap_worker, main, run_worker_forever

worker_runtime = importlib.import_module("agent_trader.worker.runtime")


class _FakeDatabase:
    def __getitem__(self, name: str) -> object:
        return object()


class _FakeConnections:
    def __init__(self, events: list[str]) -> None:
        self._events = events
        self.started = False
        self.closed = False
        self.mongo_manager = SimpleNamespace(database=_FakeDatabase())
        self.influx_manager = object()

    async def start(self) -> None:
        self.started = True
        self._events.append("connections.start")

    async def close(self) -> None:
        self.closed = True
        self._events.append("connections.close")


class _FakeScheduler:
    def __init__(self, events: list[str]) -> None:
        self._events = events
        self.running = False
        self._jobs = ["job-1", "job-2"]

    def start(self) -> None:
        self.running = True
        self._events.append("scheduler.start")

    def shutdown(self, wait: bool = False) -> None:  # noqa: FBT001, FBT002
        del wait
        self.running = False
        self._events.append("scheduler.shutdown")

    def get_jobs(self) -> list[str]:
        return self._jobs


@pytest.mark.asyncio
async def test_bootstrap_worker_auto_registers_jobs_after_connections_started(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[str] = []
    fake_connections = _FakeConnections(events)
    fake_scheduler = _FakeScheduler(events)

    class _FakeAppConnectionManager:
        @classmethod
        def from_settings(cls, settings: Settings) -> _FakeConnections:  # noqa: ARG003
            return fake_connections

    def _fake_create_scheduler(settings: Settings | None = None) -> _FakeScheduler:  # noqa: ARG001
        assert fake_connections.started
        events.append("create_scheduler")
        return fake_scheduler

    def _fake_build_source_registry(settings: Settings) -> object:  # noqa: ARG001
        class _FakeRegistry:
            def names(self):
                return []

            def get(self, name):
                return None

        assert fake_connections.started
        events.append("build_source_registry")
        return _FakeRegistry()

    def _fake_build_factory(**kwargs: object) -> object:  # noqa: ARG001
        assert fake_connections.started
        events.append("build_service_factory")
        return lambda: object()

    def _fake_register_jobs(*args: object, **kwargs: object) -> None:  # noqa: ARG001
        assert fake_connections.started
        events.append("register_jobs")

    async def _fake_health_check(selector: object) -> None:
        assert fake_connections.started
        events.append("health_check_sources")

    monkeypatch.setattr(worker_runtime, "AppConnectionManager", _FakeAppConnectionManager)
    monkeypatch.setattr(worker_runtime, "configure_logging", lambda level: None)
    monkeypatch.setattr(worker_runtime, "_health_check_sources", _fake_health_check)
    monkeypatch.setattr(worker_runtime, "create_scheduler", _fake_create_scheduler)
    monkeypatch.setattr(worker_runtime, "_build_source_registry", _fake_build_source_registry)
    monkeypatch.setattr(worker_runtime, "build_kline_sync_service_factory", _fake_build_factory)
    monkeypatch.setattr(worker_runtime, "build_company_detail_sync_service_factory", _fake_build_factory)
    monkeypatch.setattr(worker_runtime, "register_kline_sync_jobs", _fake_register_jobs)
    monkeypatch.setattr(worker_runtime, "register_company_detail_sync_jobs", _fake_register_jobs)

    runtime = await bootstrap_worker(settings=Settings())

    assert runtime.connections is fake_connections
    assert runtime.scheduler is fake_scheduler
    assert fake_connections.started
    assert fake_scheduler.running
    assert events == [
        "connections.start",
        "build_source_registry",
        "health_check_sources",
        "create_scheduler",
        "build_service_factory",
        "register_jobs",
        "build_service_factory",
        "register_jobs",
        "scheduler.start",
    ]


@pytest.mark.asyncio
async def test_worker_runtime_stop_shuts_scheduler_and_connections() -> None:
    events: list[str] = []
    runtime = WorkerRuntime(connections=_FakeConnections(events), scheduler=_FakeScheduler(events))
    runtime.scheduler.start()

    await runtime.stop()

    assert events == ["scheduler.start", "scheduler.shutdown", "connections.close"]


@pytest.mark.asyncio
async def test_run_worker_forever_waits_shutdown_and_stops_runtime(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[str] = []
    shutdown_event = asyncio.Event()

    class _FakeRuntime:
        async def stop(self) -> None:
            events.append("runtime.stop")

    async def _fake_bootstrap(settings: Settings | None = None) -> _FakeRuntime:  # noqa: ARG001
        events.append("bootstrap")
        shutdown_event.set()
        return _FakeRuntime()

    monkeypatch.setattr(worker_runtime, "bootstrap_worker", _fake_bootstrap)

    await run_worker_forever(shutdown_event=shutdown_event, register_signals=False)

    assert events == ["bootstrap", "runtime.stop"]


def test_main_runs_worker_loop(monkeypatch: pytest.MonkeyPatch) -> None:
    events: list[str] = []

    def _fake_run(coro: object) -> None:
        events.append("asyncio.run")
        assert asyncio.iscoroutine(coro)
        coro.close()

    monkeypatch.setattr(worker_runtime.asyncio, "run", _fake_run)

    main()

    assert events == ["asyncio.run"]

from __future__ import annotations

from datetime import datetime

import pytest

from agent_trader.core.config import Settings
from agent_trader.worker import jobs


class _FakeScheduler:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def add_job(self, func: object, trigger: str, **kwargs: object) -> None:
        self.calls.append({"func": func, "trigger": trigger, "kwargs": kwargs})


class _FakeService:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    async def sync_realtime_m5_positions(self, market: str) -> None:
        self.calls.append(("realtime_positions", market))

    async def sync_realtime_m5_candidates(self, market: str) -> None:
        self.calls.append(("realtime_candidates", market))

    async def sync_backfill_d1_all(self, market: str) -> None:
        self.calls.append(("backfill_d1", market))

    async def sync_backfill_m5_positions_candidates(self, market: str) -> None:
        self.calls.append(("backfill_m5", market))


def test_register_kline_sync_jobs_uses_interval_backfill_schedule() -> None:
    scheduler = _FakeScheduler()

    jobs.register_kline_sync_jobs(
        scheduler,
        service_factory=lambda: _FakeService(),
        settings=Settings(sync_enabled_markets="sse"),
    )

    backfill_calls = [
        call
        for call in scheduler.calls
        if str(call["kwargs"].get("id", "")).startswith("backfill_")
    ]

    assert len(backfill_calls) == 2
    assert all(call["trigger"] == "interval" for call in backfill_calls)
    assert all(call["kwargs"].get("minutes") == jobs._BACKFILL_CHECK_INTERVAL_MINUTES for call in backfill_calls)


def test_is_market_trading_time_for_a_share_sessions() -> None:
    # Monday 10:00 in trading session
    assert jobs._is_market_trading_time("sse", datetime(2026, 3, 23, 10, 0, 0)) is True
    # Monday 12:00 lunch break
    assert jobs._is_market_trading_time("sse", datetime(2026, 3, 23, 12, 0, 0)) is False
    # Saturday should be closed
    assert jobs._is_market_trading_time("sse", datetime(2026, 3, 21, 10, 0, 0)) is False


@pytest.mark.asyncio
async def test_realtime_job_skips_outside_trading_time(monkeypatch: pytest.MonkeyPatch) -> None:
    service = _FakeService()

    monkeypatch.setattr(jobs, "_should_run_realtime", lambda market: False)

    await jobs._run_realtime_positions(service_factory=lambda: service, market="sse")
    await jobs._run_realtime_candidates(service_factory=lambda: service, market="sse")

    assert service.calls == []


@pytest.mark.asyncio
async def test_backfill_job_runs_in_non_trading_time(monkeypatch: pytest.MonkeyPatch) -> None:
    service = _FakeService()

    monkeypatch.setattr(jobs, "_should_run_backfill", lambda market: True)

    await jobs._run_backfill_d1(service_factory=lambda: service, market="sse")
    await jobs._run_backfill_m5(service_factory=lambda: service, market="sse")

    assert service.calls == [("backfill_d1", "sse"), ("backfill_m5", "sse")]

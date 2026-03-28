from __future__ import annotations

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
        self.calls: list[str] = []

    async def sync_market(self, market: str) -> None:
        self.calls.append(market)

    async def sync_backfill_d1_all(self, market: str) -> None:
        self.calls.append(f"{market}:d1")

    async def sync_backfill_m5_positions_candidates(self, market: str) -> None:
        self.calls.append(f"{market}:m5")


def test_register_kline_sync_jobs_registers_startup_and_daily_history_jobs_per_market() -> None:
    scheduler = _FakeScheduler()
    settings = Settings(
        SYNC_ENABLED_MARKETS="sse,szse",
        SYNC_REALTIME_M5_INTERVAL_SECONDS=30,
    )

    jobs.register_kline_sync_jobs(
        scheduler,
        service_factory=lambda: _FakeService(),
        settings=settings,
    )

    assert len(scheduler.calls) == 4
    registered = {str(call["kwargs"]["id"]): call for call in scheduler.calls}

    for market in ("sse", "szse"):
        startup_entry = registered[f"kline_history_update_startup_{market}"]
        assert startup_entry["func"] is jobs._run_market_history_update
        assert startup_entry["trigger"] == "date"
        assert startup_entry["kwargs"]["run_date"] is not None
        assert startup_entry["kwargs"]["kwargs"]["market"] == market
        assert startup_entry["kwargs"]["replace_existing"] is True
        assert startup_entry["kwargs"]["coalesce"] is True
        assert startup_entry["kwargs"]["max_instances"] == 1

        daily_entry = registered[f"kline_history_update_daily_{market}"]
        assert daily_entry["func"] is jobs._run_market_history_update
        assert daily_entry["trigger"] == "cron"
        assert daily_entry["kwargs"]["hour"] == 23
        assert daily_entry["kwargs"]["minute"] == 0
        assert daily_entry["kwargs"]["kwargs"]["market"] == market
        assert daily_entry["kwargs"]["replace_existing"] is True
        assert daily_entry["kwargs"]["coalesce"] is True
        assert daily_entry["kwargs"]["max_instances"] == 1


@pytest.mark.asyncio
async def test_run_market_history_update_calls_service() -> None:
    service = _FakeService()

    await jobs._run_market_history_update(service_factory=lambda: service, market="sse")

    assert service.calls == ["sse:d1", "sse:m5"]

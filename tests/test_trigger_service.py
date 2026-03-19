from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from agent_trader.application.services.trigger_service import TriggerService
from agent_trader.domain.models import TriggerKind
from agent_trader.ingestion.models import ResearchTrigger


class DummyUnitOfWork:
    def __init__(self) -> None:
        self.opportunities = AsyncMock()
        self.research_tasks = AsyncMock()
        self.commit = AsyncMock()
        self.rollback = AsyncMock()

    async def __aenter__(self) -> "DummyUnitOfWork":
        return self

    async def __aexit__(self, exc_type: object, exc: object, tb: object) -> None:
        if exc_type is None:
            await self.commit()
            return
        await self.rollback()


@pytest.mark.asyncio
async def test_submit_trigger_persists_entities_once_and_invokes_graph() -> None:
    uow = DummyUnitOfWork()
    router_graph = AsyncMock()
    service = TriggerService(unit_of_work=uow, router_graph=router_graph)

    trigger = ResearchTrigger(
        trigger_kind=TriggerKind.NEWS,
        symbol="AAPL",
        summary="Apple receives a strong product demand signal.",
        metadata={"source": "unit-test"},
    )

    result = await service.submit_trigger(trigger)

    assert result["status"] == "queued"
    assert result["job_id"]
    uow.opportunities.add.assert_awaited_once()
    uow.research_tasks.add.assert_awaited_once()
    uow.commit.assert_awaited_once()
    uow.rollback.assert_not_awaited()
    router_graph.invoke.assert_awaited_once()


@pytest.mark.asyncio
async def test_submit_trigger_rolls_back_on_router_failure_after_persist_commit_boundary() -> None:
    uow = DummyUnitOfWork()
    router_graph = AsyncMock()
    router_graph.invoke.side_effect = RuntimeError("graph failed")
    service = TriggerService(unit_of_work=uow, router_graph=router_graph)

    trigger = ResearchTrigger(
        trigger_kind=TriggerKind.NEWS,
        symbol="AAPL",
        summary="Apple receives a strong product demand signal.",
        metadata={"source": "unit-test"},
    )

    with pytest.raises(RuntimeError, match="graph failed"):
        await service.submit_trigger(trigger)

    uow.opportunities.add.assert_awaited_once()
    uow.research_tasks.add.assert_awaited_once()
    uow.commit.assert_awaited_once()
    uow.rollback.assert_not_awaited()
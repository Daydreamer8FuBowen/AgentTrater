from __future__ import annotations

from datetime import datetime

import pytest

from agent_trader.application.data_access.gateway import BasicInfoSourceFetchOutcome
from agent_trader.application.services.basic_info_aggregation_service import BasicInfoAggregationService
from agent_trader.domain.models import ExchangeKind
from agent_trader.ingestion.models import (
    BasicInfoFetchResult,
    BasicInfoRecord,
    DataCapability,
    DataRouteKey,
)
from tests.support.in_memory_uow import InMemoryUnitOfWork


class _StubGateway:
    def __init__(self, outcomes: list[BasicInfoSourceFetchOutcome]) -> None:
        self._outcomes = outcomes

    async def fetch_basic_info_from_all_sources(
        self,
        market: ExchangeKind | None = None,  # noqa: ARG002
    ) -> list[BasicInfoSourceFetchOutcome]:
        return self._outcomes


def _fetch_result(
    source: str,
    payload: list[BasicInfoRecord],
    market: ExchangeKind | None,
) -> BasicInfoFetchResult:
    return BasicInfoFetchResult(
        source=source,
        route_key=DataRouteKey(
            capability=DataCapability.KLINE,
            market=market,
            interval=None,
        ),
        payload=payload,
    )


@pytest.mark.asyncio
async def test_sync_basic_info_snapshot_merge_uses_priority_and_fill_only() -> None:
    primary_payload = [
        BasicInfoRecord(
            symbol="000001.SZ",
            name="Primary Name",
            industry=None,
            area=None,
            market="sz",
            list_date=datetime(1991, 4, 3),
            status="1",
            delist_date=None,
            security_type=None,
        )
    ]
    fallback_payload = [
        BasicInfoRecord(
            symbol="sz.000001",
            name="Fallback Name",
            industry="Bank",
            area="Shenzhen",
            market="szse",
            list_date=datetime(1991, 4, 3),
            status="0",
            delist_date=None,
            security_type="2",
        )
    ]

    outcomes = [
        BasicInfoSourceFetchOutcome(
            source_name="tushare",
            result=_fetch_result("tushare", primary_payload, ExchangeKind.SZSE),
        ),
        BasicInfoSourceFetchOutcome(
            source_name="baostock",
            result=_fetch_result("baostock", fallback_payload, ExchangeKind.SZSE),
        ),
    ]

    uow = InMemoryUnitOfWork()
    service = BasicInfoAggregationService(
        gateway=_StubGateway(outcomes),
        uow_factory=lambda: uow,
    )

    summary = await service.sync_basic_info_snapshot(market=ExchangeKind.SZSE)

    assert summary["dedup_count"] == 1
    assert summary["persisted"]["upserted"] == 1

    saved = uow.store.basic_info_items["000001.SZ"]
    assert saved.name == "Primary Name"
    assert saved.industry == "Bank"
    assert saved.area == "Shenzhen"
    assert saved.status == "1"
    assert saved.security_type == "2"
    assert saved.source_trace == ["tushare", "baostock"]
    assert sorted(saved.conflict_fields) == ["name", "status"]


@pytest.mark.asyncio
async def test_sync_basic_info_snapshot_normalizes_symbol_and_keeps_failures() -> None:
    payload_one = [
        BasicInfoRecord(
            symbol="600000",
            name="浦发银行",
            industry="Bank",
            area=None,
            market="sh",
            list_date=None,
            status="1",
            delist_date=None,
            security_type=2,
        )
    ]
    payload_two = [
        BasicInfoRecord(
            symbol="600000.SH",
            name="浦发",
            industry=None,
            area="Shanghai",
            market="sse",
            list_date=None,
            status="1",
            delist_date=None,
            security_type=None,
        )
    ]

    outcomes = [
        BasicInfoSourceFetchOutcome(
            source_name="primary",
            result=_fetch_result("primary", payload_one, ExchangeKind.SSE),
        ),
        BasicInfoSourceFetchOutcome(
            source_name="fallback",
            result=_fetch_result("fallback", payload_two, ExchangeKind.SSE),
        ),
        BasicInfoSourceFetchOutcome(source_name="broken", result=None, error="timeout"),
    ]

    uow = InMemoryUnitOfWork()
    service = BasicInfoAggregationService(
        gateway=_StubGateway(outcomes),
        uow_factory=lambda: uow,
    )

    summary = await service.sync_basic_info_snapshot(market=ExchangeKind.SSE)

    assert summary["requested_sources"] == 3
    assert summary["failed_sources"] == [{"source": "broken", "error": "timeout"}]
    assert summary["dedup_count"] == 1

    saved = uow.store.basic_info_items["600000.SH"]
    assert saved.market == "sh"
    assert saved.name == "浦发银行"
    assert saved.area == "Shanghai"
    assert saved.security_type == "2"

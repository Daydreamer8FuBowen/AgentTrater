from __future__ import annotations

from dataclasses import asdict, is_dataclass
from datetime import datetime
from typing import Any, Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from agent_trader.api.dependencies import (
    get_basic_info_aggregation_service,
    get_data_access_gateway,
)
from agent_trader.api.time_serialization import serialize_temporal_payload
from agent_trader.application.data_access.gateway import DataAccessGateway
from agent_trader.application.services.basic_info_aggregation_service import (
    BasicInfoAggregationService,
)
from agent_trader.domain.models import BarInterval, ExchangeKind
from agent_trader.ingestion.models import (
    DataFetchResult,
    FinancialReportQuery,
    KlineQuery,
    NewsQuery,
)

router = APIRouter(prefix="/data", tags=["data"])


class KlineRequest(BaseModel):
    symbol: str = Field(min_length=1, max_length=32)
    start_time: datetime
    end_time: datetime
    interval: BarInterval
    market: ExchangeKind | None = None
    adjusted: bool = False
    extra: dict[str, Any] = Field(default_factory=dict)


class NewsRequest(BaseModel):
    symbol: str | None = None
    start_time: datetime | None = None
    end_time: datetime | None = None
    market: ExchangeKind | None = None
    keywords: list[str] = Field(default_factory=list)
    extra: dict[str, Any] = Field(default_factory=dict)


class FinancialReportRequest(BaseModel):
    symbol: str = Field(min_length=1, max_length=32)
    start_time: datetime | None = None
    end_time: datetime | None = None
    market: ExchangeKind | None = None
    extra: dict[str, Any] = Field(default_factory=dict)


class RouteKeyResponse(BaseModel):
    capability: str
    market: str | None = None
    interval: str | None = None
    storage_key: str


class KlineRecordResponse(BaseModel):
    symbol: str
    bar_time: datetime
    interval: str
    open: float | None = None
    high: float | None = None
    low: float | None = None
    close: float | None = None
    volume: float | None = None
    amount: float | None = None
    change_pct: float | None = None
    turnover_rate: float | None = None
    adjusted: bool
    is_trading: bool | None = None


class BasicInfoRecordResponse(BaseModel):
    symbol: str
    name: str | None = None
    industry: str | None = None
    area: str | None = None
    market: str | None = None
    list_date: datetime | None = None
    status: str | None = None
    delist_date: datetime | None = None
    security_type: str | None = None
    act_ent_type: str | None = None
    pe_ttm: float | None = None
    pe: float | None = None
    pb: float | None = None
    grossprofit_margin: float | None = None
    netprofit_margin: float | None = None
    roe: float | None = None
    debt_to_assets: float | None = None
    revenue: float | None = None
    net_profit: float | None = None


class NewsRecordResponse(BaseModel):
    published_at: datetime | None = None
    title: str
    content: str
    source_channel: str
    url: str | None = None
    symbols: list[str]


class FinancialReportRecordResponse(BaseModel):
    symbol: str
    report_type: str
    report_date: datetime | None = None
    published_at: datetime | None = None
    report_year: int | None = None
    report_quarter: int | None = None
    metrics: dict[str, Any] = Field(default_factory=dict)


class KlineFetchResponse(BaseModel):
    source: str
    route_key: RouteKeyResponse
    data_kind: Literal["kline"]
    schema_version: str
    fetched_at: datetime
    payload: list[KlineRecordResponse]
    metadata: dict[str, Any] = Field(default_factory=dict)


class BasicInfoFetchResponse(BaseModel):
    source: str
    route_key: RouteKeyResponse
    data_kind: Literal["basic_info"]
    schema_version: str
    fetched_at: datetime
    payload: list[BasicInfoRecordResponse]
    metadata: dict[str, Any] = Field(default_factory=dict)


class NewsFetchResponse(BaseModel):
    source: str
    route_key: RouteKeyResponse
    data_kind: Literal["news"]
    schema_version: str
    fetched_at: datetime
    payload: list[NewsRecordResponse]
    metadata: dict[str, Any] = Field(default_factory=dict)


class FinancialReportFetchResponse(BaseModel):
    source: str
    route_key: RouteKeyResponse
    data_kind: Literal["financial_report"]
    schema_version: str
    fetched_at: datetime
    payload: list[FinancialReportRecordResponse]
    metadata: dict[str, Any] = Field(default_factory=dict)


class PersistStatsResponse(BaseModel):
    requested: int
    matched: int
    modified: int
    upserted: int


class FailedSourceResponse(BaseModel):
    source: str
    error: str


class BasicInfoRefreshResponse(BaseModel):
    requested_sources: int
    input_count: int
    dedup_count: int
    persisted: PersistStatsResponse
    failed_sources: list[FailedSourceResponse] = Field(default_factory=list)


def _serialize_payload_item(item: Any) -> Any:
    if is_dataclass(item):
        return serialize_temporal_payload(asdict(item))
    return serialize_temporal_payload(item)


def _serialize_fetch_result(result: DataFetchResult) -> dict[str, Any]:
    return {
        "source": result.source,
        "route_key": {
            "capability": result.route_key.capability.value,
            "market": result.route_key.market.value if result.route_key.market else None,
            "interval": result.route_key.interval.value if result.route_key.interval else None,
            "storage_key": result.route_key.as_storage_key(),
        },
        "data_kind": result.data_kind,
        "schema_version": result.schema_version,
        "fetched_at": serialize_temporal_payload(result.fetched_at),
        "payload": [_serialize_payload_item(item) for item in result.payload],
        "metadata": serialize_temporal_payload(result.metadata),
    }


def _to_kline_response(result: DataFetchResult) -> KlineFetchResponse:
    return KlineFetchResponse.model_validate(_serialize_fetch_result(result))


def _to_basic_info_response(result: DataFetchResult) -> BasicInfoFetchResponse:
    return BasicInfoFetchResponse.model_validate(_serialize_fetch_result(result))


def _to_news_response(result: DataFetchResult) -> NewsFetchResponse:
    return NewsFetchResponse.model_validate(_serialize_fetch_result(result))


def _to_financial_report_response(result: DataFetchResult) -> FinancialReportFetchResponse:
    return FinancialReportFetchResponse.model_validate(_serialize_fetch_result(result))


@router.post("/klines", response_model=KlineFetchResponse)
async def fetch_klines(
    payload: KlineRequest,
    gateway: DataAccessGateway = Depends(get_data_access_gateway),
) -> KlineFetchResponse:
    result = await gateway.fetch_klines(
        KlineQuery(
            symbol=payload.symbol,
            start_time=payload.start_time,
            end_time=payload.end_time,
            interval=payload.interval,
            market=payload.market,
            adjusted=payload.adjusted,
            extra=payload.extra,
        )
    )
    return _to_kline_response(result)


@router.post("/news", response_model=NewsFetchResponse)
async def fetch_news(
    payload: NewsRequest,
    gateway: DataAccessGateway = Depends(get_data_access_gateway),
) -> NewsFetchResponse:
    result = await gateway.fetch_news(
        NewsQuery(
            symbol=payload.symbol,
            start_time=payload.start_time,
            end_time=payload.end_time,
            market=payload.market,
            keywords=payload.keywords,
            extra=payload.extra,
        )
    )
    return _to_news_response(result)


@router.post("/financial-reports", response_model=FinancialReportFetchResponse)
async def fetch_financial_reports(
    payload: FinancialReportRequest,
    gateway: DataAccessGateway = Depends(get_data_access_gateway),
) -> FinancialReportFetchResponse:
    result = await gateway.fetch_financial_reports(
        FinancialReportQuery(
            symbol=payload.symbol,
            start_time=payload.start_time,
            end_time=payload.end_time,
            market=payload.market,
            extra=payload.extra,
        )
    )
    return _to_financial_report_response(result)


@router.get("/basic-info", response_model=BasicInfoFetchResponse)
async def fetch_basic_info(
    market: ExchangeKind | None = None,
    gateway: DataAccessGateway = Depends(get_data_access_gateway),
) -> BasicInfoFetchResponse:
    result = await gateway.fetch_basic_info(market=market)
    return _to_basic_info_response(result)


@router.post("/basic-info/refresh", response_model=BasicInfoRefreshResponse)
async def refresh_basic_info(
    market: ExchangeKind | None = None,
    service: BasicInfoAggregationService = Depends(get_basic_info_aggregation_service),
) -> BasicInfoRefreshResponse:
    summary = await service.sync_basic_info_snapshot(market=market)
    return BasicInfoRefreshResponse.model_validate(summary)

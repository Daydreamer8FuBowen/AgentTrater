"""DataAccessGateway 单元测试。

覆盖场景：
  1. 纯 mock provider：验证选择器的回退与优先级重排逻辑（不依赖网络）。
  2. 真实 provider (BaoStockSource)：验证网关端到端数据获取与优先级管理。
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

import pytest

from agent_trader.application.data_access.gateway import (
    DataAccessGateway,
    DataSourceRegistry,
    SourceSelectionAdapter,
)
from agent_trader.domain.models import BarInterval, ExchangeKind
from agent_trader.ingestion.models import (
    BasicInfoFetchResult,
    BasicInfoRecord,
    DataCapability,
    DataRouteKey,
    KlineFetchResult,
    KlineRecord,
    KlineQuery,
)
from agent_trader.ingestion.sources.baostock_source import BaoStockSource


# ---------------------------------------------------------------------------
# 测试辅助：内存优先级仓库（代替真实 MongoDB，使测试完全隔离）
# ---------------------------------------------------------------------------

@dataclass
class _RouteDoc:
    """单条路由优先级记录，对应 MongoDB source_priority_routes 集合中的文档结构。"""
    route_id: str
    priorities: list[str]  # 按优先级排列的数据源名称列表，第 0 位为当前首选源
    enabled: bool = True


class _InMemoryPriorityRepository:
    """纯内存的优先级仓库，实现与真实 MongoRoutePriorityRepository 相同的接口。"""

    def __init__(self) -> None:
        # key = route_key.as_storage_key()，如 "kline:sse:5m"
        self._items: dict[str, _RouteDoc] = {}

    async def get(self, route_key: DataRouteKey) -> _RouteDoc | None:
        """按路由键查询优先级记录，找不到时返回 None。"""
        return self._items.get(route_key.as_storage_key())

    async def upsert(self, route_key: DataRouteKey, *, priorities: list[str], enabled: bool = True, metadata: dict | None = None) -> _RouteDoc:  # noqa: ARG002
        """创建或覆写路由记录（等效于 MongoDB upsert）。"""
        route = _RouteDoc(route_id=route_key.as_storage_key(), priorities=list(priorities), enabled=enabled)
        self._items[route.route_id] = route
        return route

    async def reorder(self, route_key: DataRouteKey, *, priorities: list[str]) -> None:
        """就地替换优先级顺序。SourceSelectionAdapter 在源失败后调用此方法将失败源移至末尾。"""
        route_id = route_key.as_storage_key()
        route = self._items[route_id]
        route.priorities = list(priorities)


# ---------------------------------------------------------------------------
# 测试辅助：mock 数据源 provider（不访问网络，仅控制成功/失败行为）
# ---------------------------------------------------------------------------

class _FailingProvider:
    """模拟主源宕机：任何 K 线请求都抛出 RuntimeError，触发网关的回退逻辑。"""

    name = "primary"

    async def fetch_klines_unified(self, query: KlineQuery) -> KlineFetchResult:  # noqa: ARG002
        raise RuntimeError("source down")  # 让 SourceSelectionAdapter 捕获后尝试下一个源

    async def fetch_basic_info(self, market: ExchangeKind | None = None) -> BasicInfoFetchResult:  # noqa: ARG002
        raise RuntimeError("source down")


class _SuccessProvider:
    """模拟备用源：始终成功返回一条占位记录，用于验证回退路径。"""

    name = "fallback"

    async def fetch_klines_unified(self, query: KlineQuery) -> KlineFetchResult:
        route_key = DataRouteKey(
            capability=DataCapability.KLINE,
            market=query.market,
            interval=query.interval,
        )
        # payload 仅含 symbol 占位，足以让断言区分来源
        return KlineFetchResult(
            source=self.name,
            route_key=route_key,
            payload=[
                KlineRecord(
                    symbol=query.symbol,
                    bar_time=query.start_time,
                    interval=query.interval.value,
                    open=None,
                    high=None,
                    low=None,
                    close=None,
                    volume=None,
                    amount=None,
                    change_pct=None,
                    turnover_rate=None,
                    adjusted=query.adjusted,
                )
            ],
        )

    async def fetch_basic_info(self, market: ExchangeKind | None = None) -> BasicInfoFetchResult:
        route_key = DataRouteKey(
            capability=DataCapability.KLINE,
            market=market,
            interval=None,
        )
        return BasicInfoFetchResult(
            source=self.name,
            route_key=route_key,
            payload=[
                BasicInfoRecord(
                    symbol="600000.SH",
                    name="Fallback Co",
                    industry=None,
                    area=None,
                    market="sh",
                    list_date=None,
                    status="1",
                )
            ],
        )


class _PrimarySuccessProvider:
    """模拟主源正常：始终成功，用于断言「主源可用时优先级不变」的场景。"""

    name = "primary"

    async def fetch_klines_unified(self, query: KlineQuery) -> KlineFetchResult:
        route_key = DataRouteKey(
            capability=DataCapability.KLINE,
            market=query.market,
            interval=query.interval,
        )
        return KlineFetchResult(
            source=self.name,
            route_key=route_key,
            payload=[
                KlineRecord(
                    symbol=query.symbol,
                    bar_time=query.start_time,
                    interval=query.interval.value,
                    open=None,
                    high=None,
                    low=None,
                    close=None,
                    volume=None,
                    amount=None,
                    change_pct=None,
                    turnover_rate=None,
                    adjusted=query.adjusted,
                )
            ],
        )

    async def fetch_basic_info(self, market: ExchangeKind | None = None) -> BasicInfoFetchResult:
        route_key = DataRouteKey(
            capability=DataCapability.KLINE,
            market=market,
            interval=None,
        )
        return BasicInfoFetchResult(
            source=self.name,
            route_key=route_key,
            payload=[
                BasicInfoRecord(
                    symbol="600000.SH",
                    name="Primary Co",
                    industry=None,
                    area=None,
                    market="sh",
                    list_date=None,
                    status="1",
                )
            ],
        )


class _NoBasicInfoProvider:
    """模拟不支持 basic_info 能力的数据源。"""

    name = "no_basic"


# ---------------------------------------------------------------------------
# 测试组 1：纯 mock provider（无网络，快速，确定性行为）
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_gateway_fallback_and_promote_success_source() -> None:
    """主源失败时网关应回退到备用源，并将备用源提升为优先级首位。"""
    # arrange：path = kline:sse:5m，初始顺序 primary → fallback
    route_key = DataRouteKey(
        capability=DataCapability.KLINE,
        market=ExchangeKind.SSE,
        interval=BarInterval.M5,
    )

    priority_repo = _InMemoryPriorityRepository()
    await priority_repo.upsert(route_key, priorities=["primary", "fallback"])

    # primary 会抛 RuntimeError；fallback 正常返回
    registry = DataSourceRegistry()
    registry.register(_FailingProvider())
    registry.register(_SuccessProvider())

    selector = SourceSelectionAdapter(
        registry=registry,
        priority_repository=priority_repo,
    )
    gateway = DataAccessGateway(selector)

    query = KlineQuery(
        symbol="000001.SZ",
        start_time=datetime(2026, 1, 1),
        end_time=datetime(2026, 1, 2),
        interval=BarInterval.M5,
        market=ExchangeKind.SSE,
    )

    # act
    result = await gateway.fetch_klines(query)

    # assert：数据来自 fallback，且 reorder 已将其升至首位
    assert result.source == "fallback"
    updated = await priority_repo.get(route_key)
    assert updated is not None
    assert updated.priorities == ["fallback", "primary"]


@pytest.mark.asyncio
async def test_gateway_primary_success_keeps_priority_order() -> None:
    """主源成功时网关直接返回，不应触发任何优先级重排。"""
    # arrange：初始顺序 primary → fallback，两个源均正常
    route_key = DataRouteKey(
        capability=DataCapability.KLINE,
        market=ExchangeKind.SSE,
        interval=BarInterval.M5,
    )

    priority_repo = _InMemoryPriorityRepository()
    await priority_repo.upsert(route_key, priorities=["primary", "fallback"])

    registry = DataSourceRegistry()
    registry.register(_PrimarySuccessProvider())  # 主源正常
    registry.register(_SuccessProvider())          # 备用源也正常，但不应被调用

    selector = SourceSelectionAdapter(
        registry=registry,
        priority_repository=priority_repo,
    )

    query = KlineQuery(
        symbol="000001.SZ",
        start_time=datetime(2026, 1, 1),
        end_time=datetime(2026, 1, 2),
        interval=BarInterval.M5,
        market=ExchangeKind.SSE,
    )

    # act
    gateway = DataAccessGateway(selector)
    result = await gateway.fetch_klines(query)

    # assert：数据来自 primary，优先级顺序不变
    assert result.source == "primary"
    updated = await priority_repo.get(route_key)
    assert updated is not None
    assert updated.priorities == ["primary", "fallback"]


@pytest.mark.asyncio
async def test_gateway_fetch_basic_info_fallback_and_promote_success_source() -> None:
    """basic_info 路由应与其它能力一样支持回退与优先级重排。"""
    route_key = DataRouteKey(
        capability=DataCapability.KLINE,
        market=ExchangeKind.SSE,
        interval=None,
    )

    priority_repo = _InMemoryPriorityRepository()
    await priority_repo.upsert(route_key, priorities=["primary", "fallback"])

    registry = DataSourceRegistry()
    registry.register(_FailingProvider())
    registry.register(_SuccessProvider())

    selector = SourceSelectionAdapter(
        registry=registry,
        priority_repository=priority_repo,
    )
    gateway = DataAccessGateway(selector)

    result = await gateway.fetch_basic_info(market=ExchangeKind.SSE)

    assert result.source == "fallback"
    assert result.data_kind == "basic_info"
    assert result.payload[0].symbol == "600000.SH"
    updated = await priority_repo.get(route_key)
    assert updated is not None
    assert updated.priorities == ["fallback", "primary"]


@pytest.mark.asyncio
async def test_gateway_fetch_basic_info_from_all_sources_with_error_isolation() -> None:
    """全源拉取应遵循优先顺序，并隔离单源失败。"""
    route_key = DataRouteKey(
        capability=DataCapability.KLINE,
        market=ExchangeKind.SSE,
        interval=None,
    )

    priority_repo = _InMemoryPriorityRepository()
    await priority_repo.upsert(route_key, priorities=["primary", "fallback"]) 

    registry = DataSourceRegistry()
    registry.register(_PrimarySuccessProvider())
    registry.register(_SuccessProvider())
    registry.register(_NoBasicInfoProvider())

    selector = SourceSelectionAdapter(
        registry=registry,
        priority_repository=priority_repo,
    )
    gateway = DataAccessGateway(selector)

    outcomes = await gateway.fetch_basic_info_from_all_sources(market=ExchangeKind.SSE)

    assert [item.source_name for item in outcomes] == ["primary", "fallback", "no_basic"]
    assert outcomes[0].result is not None
    assert outcomes[0].result.source == "primary"
    assert outcomes[1].result is not None
    assert outcomes[1].result.source == "fallback"
    assert outcomes[2].result is None
    assert outcomes[2].error == "missing basic_info ability"


# ---------------------------------------------------------------------------
# 测试组 2：真实 provider（需网络，验证端到端数据获取与优先级管理）
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_gateway_register_real_provider_and_fetch_klines() -> None:
    """将真实 BaoStockSource 注册到 DataSourceRegistry，通过网关获取真实 K 线数据。

    结构与 mock 测试完全一致，唯一区别是 registry.register() 传入真实 provider。
    """
    # arrange：注册 BaoStock 为唯一数据源，优先级仓库使用内存实现
    route_key = DataRouteKey(
        capability=DataCapability.KLINE,
        market=ExchangeKind.SZSE,
        interval=BarInterval.D1,
    )

    priority_repo = _InMemoryPriorityRepository()
    await priority_repo.upsert(route_key, priorities=["baostock"])

    registry = DataSourceRegistry()
    registry.register(BaoStockSource())  # 真实 provider，调用 BaoStock 公开 API
    # 按配置注册 TuShare：通过应用配置系统加载 token，以保持与应用启动时相同的行为。
    # 使用 get_settings() 读取配置，若未配置 token 则跳过注册，保证测试在无 token 环境下可运行。
    try:
        from agent_trader.core.config import get_settings
        from agent_trader.ingestion.sources.tushare_source import TuShareSource

        settings = get_settings()
        if settings.tushare.token:
            registry.register(TuShareSource.from_settings(settings))
    except Exception:
        # 若导入或初始化失败（例如 tushare 未安装），保持向后兼容性并继续仅使用 BaoStock
        pass

    selector = SourceSelectionAdapter(
        registry=registry,
        priority_repository=priority_repo,
    )
    gateway = DataAccessGateway(selector)

    query = KlineQuery(
        symbol="000001.SZ",          # 平安银行
        start_time=datetime(2025, 1, 1),
        end_time=datetime(2025, 1, 10),
        interval=BarInterval.D1,
        market=ExchangeKind.SZSE,
        adjusted=True,               # 前复权
    )

    # act：网关按优先级选 baostock，发起真实 HTTP 请求
    result = await gateway.fetch_klines(query)

    # assert：来源正确、路由键一致、返回真实数据、元数据 count 与 payload 长度匹配
    assert result.source == "baostock"
    assert result.route_key == route_key
    assert len(result.payload) > 0
    assert result.metadata is not None
    assert result.metadata.get("count") == len(result.payload)


@pytest.mark.asyncio
async def test_gateway_fallback_to_real_provider_and_reorder_priority() -> None:
    """主源（mock）失败后，网关回退到真实 BaoStockSource 并将其提升为首位。

    混合场景：一个 mock 失败源 + 一个真实 provider，验证回退 + 优先级重排的完整链路。
    """
    # arrange：初始顺序 primary（会失败） → baostock（真实）
    route_key = DataRouteKey(
        capability=DataCapability.KLINE,
        market=ExchangeKind.SZSE,
        interval=BarInterval.D1,
    )

    priority_repo = _InMemoryPriorityRepository()
    await priority_repo.upsert(route_key, priorities=["primary", "baostock"])

    registry = DataSourceRegistry()
    registry.register(_FailingProvider())  # 模拟主源宕机，触发 fallback
    registry.register(BaoStockSource())    # 真实备用源，提供实际市场数据

    selector = SourceSelectionAdapter(
        registry=registry,
        priority_repository=priority_repo,
    )
    gateway = DataAccessGateway(selector)

    query = KlineQuery(
        symbol="000001.SZ",
        start_time=datetime(2025, 1, 1),
        end_time=datetime(2025, 1, 10),
        interval=BarInterval.D1,
        market=ExchangeKind.SZSE,
        adjusted=True,
    )

    # act：primary 抛错 → selector 捕获 → 将 primary 移至末尾 → 调用 baostock
    result = await gateway.fetch_klines(query)

    # assert 1：数据确实来自真实的 BaoStock 源
    assert result.source == "baostock"
    assert len(result.payload) > 0

    # assert 2：优先级已被重排，baostock 升至首位，primary 降至末位
    updated = await priority_repo.get(route_key)
    assert updated is not None
    assert updated.priorities == ["baostock", "primary"]


@pytest.mark.asyncio
async def test_gateway_register_real_provider_and_fetch_basic_info() -> None:
    """将真实 BaoStockSource 注册到网关，通过 basic_info 统一入口获取标准化标的信息。"""
    route_key = DataRouteKey(
        capability=DataCapability.KLINE,
        market=ExchangeKind.SSE,
        interval=None,
    )

    priority_repo = _InMemoryPriorityRepository()
    await priority_repo.upsert(route_key, priorities=["baostock"])

    registry = DataSourceRegistry()
    registry.register(BaoStockSource())

    selector = SourceSelectionAdapter(
        registry=registry,
        priority_repository=priority_repo,
    )
    gateway = DataAccessGateway(selector)

    result = await gateway.fetch_basic_info(market=ExchangeKind.SSE)

    assert result.source == "baostock"
    assert result.route_key == route_key
    assert result.data_kind == "basic_info"
    assert len(result.payload) > 0
    assert result.payload[0].symbol
    assert result.metadata.get("count") == len(result.payload)

from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace

import pytest

# 被测服务与相关模型配置
from agent_trader.application.services.kline_sync_service import KlineSyncService, TierCollectionService, TieredSymbols
from agent_trader.core.config import KlineSyncConfig
from agent_trader.domain.models import BarInterval, ExchangeKind
from agent_trader.ingestion.models import DataCapability, DataRouteKey, KlineFetchResult
# 测试用的内存 UoW / 事件存储
from support.in_memory_uow import InMemoryEventStore, InMemoryUnitOfWork


# 一个简单的 Gateway stub：用于模拟 fetch_klines 返回指定结果，并记录调用参数
class _StubGateway:
    def __init__(self, result: KlineFetchResult) -> None:
        self._result = result
        self.calls: list[object] = []  # 记录被调用时传入的 query

    async def fetch_klines(self, query: object) -> KlineFetchResult:
        self.calls.append(query)
        return self._result


# 一个简单的内存 candles 存储，用于检查写入的批次
class _InMemoryCandleRepository:
    def __init__(self) -> None:
        self.batches: list[list[object]] = []  # 每次 write / write_batch 会把数据加入此列表

    async def write(self, candle: object) -> None:
        self.batches.append([candle])

    async def write_batch(self, candles: list[object]) -> None:
        self.batches.append(candles)


# Tier 服务的 stub：直接返回预设的 tiers，方便测试分层逻辑
class _StubTierService:
    def __init__(self, tiers: TieredSymbols) -> None:
        self._tiers = tiers

    async def collect(self, market: str) -> TieredSymbols:  # noqa: ARG002
        return self._tiers


# 测试：TierCollectionService 应能把 positions / candidates / others 划分到 A/B/C
@pytest.mark.asyncio
async def test_tier_collection_service_split_abc() -> None:
    store = InMemoryEventStore()
    # 在内存 store 中预置 positions（持仓）和 candidates（候选）数据
    store.positions = [
        SimpleNamespace(symbol="600000.SH"),
        SimpleNamespace(symbol="600051.SH"),
        SimpleNamespace(symbol="000001.SZ"),
    ]
    store.candidates = [
        SimpleNamespace(symbol="600000.SH"),
        SimpleNamespace(symbol="600010.SH"),
        SimpleNamespace(symbol="600052.SH"),
        SimpleNamespace(symbol="600053.SH"),
        SimpleNamespace(symbol="000002.SZ"),
    ]
    # basic_info_items 同时作为 Tier 白名单，SH/SZ 市场需要额外过滤 status/security_type/ST。
    store.basic_info_items = {
        "600000.SH": SimpleNamespace(symbol="600000.SH", market="sh", status="1", security_type="stock", name="浦发银行"),
        "600010.SH": SimpleNamespace(symbol="600010.SH", market="sh", status="1", security_type="stock", name="包钢股份"),
        "600050.SH": SimpleNamespace(symbol="600050.SH", market="sh", status="1", security_type="stock", name="中国联通"),
        "600051.SH": SimpleNamespace(symbol="600051.SH", market="sh", status="0", security_type="stock", name="停牌示例"),
        "600052.SH": SimpleNamespace(symbol="600052.SH", market="sh", status="1", security_type="fund", name="示例基金"),
        "600053.SH": SimpleNamespace(symbol="600053.SH", market="sh", status="1", security_type="stock", name="ST示例"),
        "000001.SZ": SimpleNamespace(symbol="000001.SZ", market="sz", status="1", security_type="stock", name="平安银行"),
        "000002.SZ": SimpleNamespace(symbol="000002.SZ", market="sz", status="1", security_type="stock", name="万科A"),
    }

    # 用内存 UoW 构造 TierCollectionService 并执行 collect
    service = TierCollectionService(uow_factory=lambda: InMemoryUnitOfWork(store=store))
    tiers = await service.collect("sse")

    # 断言：market 被传递并标准化，positions/candidates/others 被正确分组
    assert tiers.market == "sse"
    assert tiers.positions == ("600000.SH",)
    assert tiers.candidates == ("600010.SH",)
    assert tiers.others == ("600050.SH",)


@pytest.mark.asyncio
async def test_tier_collection_service_applies_market_specific_basic_info_filters_for_sz() -> None:
    store = InMemoryEventStore()
    store.positions = [
        SimpleNamespace(symbol="000001.SZ"),
        SimpleNamespace(symbol="000003.SZ"),
    ]
    store.candidates = [
        SimpleNamespace(symbol="000002.SZ"),
        SimpleNamespace(symbol="000004.SZ"),
        SimpleNamespace(symbol="600000.SH"),
    ]
    store.basic_info_items = {
        "000001.SZ": SimpleNamespace(symbol="000001.SZ", market="sz", status="1", security_type="stock", name="平安银行"),
        "000002.SZ": SimpleNamespace(symbol="000002.SZ", market="sz", status="1", security_type="stock", name="万科A"),
        "000003.SZ": SimpleNamespace(symbol="000003.SZ", market="sz", status="0", security_type="stock", name="停牌示例"),
        "000004.SZ": SimpleNamespace(symbol="000004.SZ", market="sz", status="1", security_type="stock", name="ST示例"),
        "000005.SZ": SimpleNamespace(symbol="000005.SZ", market="sz", status="1", security_type="fund", name="示例ETF"),
        "000006.SZ": SimpleNamespace(symbol="000006.SZ", market="sz", status="1", security_type="stock", name="招商地产"),
        "600000.SH": SimpleNamespace(symbol="600000.SH", market="sh", status="1", security_type="stock", name="浦发银行"),
    }

    service = TierCollectionService(uow_factory=lambda: InMemoryUnitOfWork(store=store))
    tiers = await service.collect("szse")

    assert tiers.market == "szse"
    assert tiers.positions == ("000001.SZ",)
    assert tiers.candidates == ("000002.SZ",)
    assert tiers.others == ("000006.SZ",)


# 测试：当实时 M5 同步对 positions 调用数据源得到空 payload（周内工作日无数据）时，
# 服务应生成“synthetic_zero_fill” 的合成 K 线并写入 candles（零值填充）
@pytest.mark.asyncio
async def test_sync_realtime_m5_positions_workday_empty_payload_zero_fill() -> None:
    store = InMemoryEventStore()
    uow = InMemoryUnitOfWork(store=store)

    # 模拟 gateway 返回空的 payload（即没有真实 K 线数据）
    gateway = _StubGateway(
        KlineFetchResult(
            source="stub",
            route_key=DataRouteKey(
                capability=DataCapability.KLINE,
                market=ExchangeKind.SSE,
                interval=BarInterval.M5,
            ),
            payload=[],  # 空结果，触发 zero-fill 分支
        )
    )
    candles = _InMemoryCandleRepository()
    # Tier 服务返回只有一个 position，便于断言只对该 symbol 进行同步
    tier_service = _StubTierService(
        TieredSymbols(
            market="sse",
            positions=("600000.SH",),
            candidates=(),
            others=(),
        )
    )

    # 构造 KlineSyncService，使用内存 UoW、stub gateway、内存 candles，以及固定的 now（周一）
    service = KlineSyncService(
        gateway=gateway,
        candle_repository=candles,
        uow_factory=lambda: uow,
        tier_collection_service=tier_service,
        config=KlineSyncConfig(
            enabled_markets=["sse"],
            d1_window_days=730,
            m5_window_days=60,
            realtime_m5_interval_seconds=60,
            d1_sync_hour=17,
            backfill_batch_symbols=20,
            m5_backfill_chunk_days=20,
        ),
        now_provider=lambda: datetime(2026, 3, 23, 10, 1, 0),  # Monday（工作日）
    )

    # 执行同步（仅 positions 的实时 M5 同步）
    summary = await service.sync_realtime_m5_positions("sse")

    # 断言：summary 表示有 1 个同步（synced），没有失败；gateway 被调用一次
    assert summary["synced"] == 1
    assert summary["failed"] == 0
    assert len(gateway.calls) == 1
    # candles 仓库应写入一批数据（一次 batch），并且该 batch 包含两条 candle：
    # - 一条为合成的零填充 bar（时间点与窗口相关）
    # - 另一条可能为 position 的 marker（实现细节取决于服务）
    assert len(candles.batches) == 1
    assert len(candles.batches[0]) == 2
    # 验证写入的所有条目都来源于 synthetic_zero_fill（服务为无数据情况生成的标记）
    assert all(item.source == "synthetic_zero_fill" for item in candles.batches[0])
    # 验证合成的 K 线确实为零值（open/high/low/close/volume 均为 0.0）
    assert all(item.open_price == 0.0 for item in candles.batches[0])
    assert all(item.high_price == 0.0 for item in candles.batches[0])
    assert all(item.low_price == 0.0 for item in candles.batches[0])
    assert all(item.close_price == 0.0 for item in candles.batches[0])
    assert all(item.volume == 0.0 for item in candles.batches[0])
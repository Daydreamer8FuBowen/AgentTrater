#!/usr/bin/env python
"""
演示脚本：事件驱动系统完整流程

这个脚本展示了 AgentTrader 中事件的完整生命周期：
1. 事件定义
2. 事件创建（数据源适配器）
3. 事件规范化（规范化器）
4. 事件处理（Agent 系统）

运行：uv run python -m scripts.demo_events
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)


# ============================================================================
# 1. 事件定义层
# ============================================================================

class TriggerKind(str, Enum):
    """系统支持的事件类型"""
    NEWS = "news"
    ANNOUNCEMENT = "announcement"
    INDICATOR = "indicator"
    DISCUSSION = "discussion"


# ============================================================================
# 2. 事件数据模型
# ============================================================================

@dataclass(slots=True)
class RawEvent:
    """层级 1：原始事件（从外部 API 来）"""
    source: str
    payload: dict[str, Any]
    received_at: datetime = field(default_factory=datetime.utcnow)
    id: UUID = field(default_factory=uuid4)

    def __str__(self):
        return f"RawEvent(source={self.source}, id={self.id})"


@dataclass(slots=True)
class NormalizedEvent:
    """层级 2：规范化事件（系统内部统一格式）"""
    trigger_kind: TriggerKind
    symbol: str
    title: str
    content: str
    metadata: dict[str, Any]

    def __str__(self):
        return (
            f"NormalizedEvent("
            f"kind={self.trigger_kind.value}, "
            f"symbol={self.symbol}, "
            f"title={self.title[:30]}...)"
        )


@dataclass(slots=True)
class ResearchTrigger:
    """层级 3：研究触发对象（提交给 Agent 系统）"""
    trigger_kind: TriggerKind
    symbol: str
    summary: str
    metadata: dict[str, Any]
    id: UUID = field(default_factory=uuid4)

    def __str__(self):
        return (
            f"ResearchTrigger("
            f"kind={self.trigger_kind.value}, "
            f"symbol={self.symbol}, "
            f"id={self.id})"
        )


# ============================================================================
# 3. 数据源适配器示例 1：模拟 K 线数据源
# ============================================================================

class MockKLineSource:
    """模拟 K 线数据源（如 TuShare）"""
    
    name = "mock_kline_source"
    
    async def fetch_klines(self, symbol: str) -> list[RawEvent]:
        """
        获取 K 线数据
        
        返回 RawEvent 列表，payload 包含原始数据
        """
        logger.info(f"[数据源] 正在获取 {symbol} 的 K 线数据...")
        
        # 模拟从外部 API 获取的原始数据
        mock_data = [
            {
                "ts_code": symbol,
                "trade_date": "20240115",
                "open": 100.0,
                "high": 106.5,
                "low": 99.5,
                "close": 106.5,
                "vol": 1000000,
                "amount": 106000000,
                "change_pct": 6.5,  # 涨幅 6.5%
            },
            {
                "ts_code": symbol,
                "trade_date": "20240116",
                "open": 106.5,
                "high": 108.0,
                "low": 105.5,
                "close": 107.8,
                "vol": 1500000,
                "amount": 162000000,
                "change_pct": 1.2,
            },
        ]
        
        # 转换为 RawEvent
        events = []
        for data in mock_data:
            event = RawEvent(
                source="tushare:kline",
                payload=data,
            )
            events.append(event)
            logger.info(f"  ✓ 生成 RawEvent: {event}")
        
        return events


# ============================================================================
# 4. 数据源适配器示例 2：模拟财经新闻源
# ============================================================================

class MockNewsSource:
    """模拟财经新闻数据源"""
    
    name = "mock_news_source"
    
    async def fetch_news(self, symbol: str) -> list[RawEvent]:
        """获取相关新闻"""
        logger.info(f"[数据源] 正在获取 {symbol} 的财经新闻...")
        
        # 模拟新闻数据
        news_list = [
            {
                "symbol": symbol,
                "title": "平安银行发布 2024 年年报，净利润超预期",
                "content": "平安银行公布 2024 年年交易报告，全年净利润 XXX 亿元，同比增长 XX%",
                "source": "新华社",
                "published_at": "2024-01-15 09:00:00",
                "url": "http://example.com/news/1",
            },
        ]
        
        events = []
        for news in news_list:
            event = RawEvent(
                source="news_api:announcement",
                payload=news,
            )
            events.append(event)
            logger.info(f"  ✓ 生成 RawEvent: {event}")
        
        return events


# ============================================================================
# 5. 事件规范化器
# ============================================================================

class KLineNormalizer:
    """K 线数据规范化器"""
    
    async def normalize(self, raw_event: RawEvent) -> NormalizedEvent | None:
        """
        规范化 K 线数据
        
        规则：
        - 涨幅 > 5%：标记为 INDICATOR 事件
        - 否则：忽略
        """
        payload = raw_event.payload
        change_pct = payload.get("change_pct", 0)
        symbol = payload.get("ts_code", "unknown")
        
        # 异常判断
        if abs(change_pct) > 5:
            logger.info(f"[规范化器] 检测到异常波动: {symbol} {change_pct}%")
            
            return NormalizedEvent(
                trigger_kind=TriggerKind.INDICATOR,
                symbol=symbol,
                title=f"{symbol} 异常波动 {change_pct}%",
                content=(
                    f"日期: {payload.get('trade_date')}\n"
                    f"收盘价: {payload.get('close')}\n"
                    f"涨跌幅: {change_pct}%"
                ),
                metadata=payload,
            )
        
        # 普通波动，不触发
        logger.info(f"[规范化器] K 线数据 {symbol} 波动正常 ({change_pct}%)")
        return None
    
    async def to_trigger(self, normalized: NormalizedEvent) -> ResearchTrigger:
        """转换为研究触发对象"""
        return ResearchTrigger(
            trigger_kind=normalized.trigger_kind,
            symbol=normalized.symbol,
            summary=normalized.title,
            metadata=normalized.metadata,
        )


class NewsNormalizer:
    """新闻数据规范化器"""
    
    async def normalize(self, raw_event: RawEvent) -> NormalizedEvent | None:
        """规范化新闻数据"""
        payload = raw_event.payload
        symbol = payload.get("symbol", "unknown")
        
        logger.info(f"[规范化器] 处理新闻: {symbol}")
        
        return NormalizedEvent(
            trigger_kind=TriggerKind.ANNOUNCEMENT,
            symbol=symbol,
            title=payload.get("title", ""),
            content=payload.get("content", ""),
            metadata=payload,
        )
    
    async def to_trigger(self, normalized: NormalizedEvent) -> ResearchTrigger:
        """转换为研究触发对象"""
        return ResearchTrigger(
            trigger_kind=normalized.trigger_kind,
            symbol=normalized.symbol,
            summary=normalized.title,
            metadata=normalized.metadata,
        )


# ============================================================================
# 6. Agent 系统处理（简化版）
# ============================================================================

class TriggerRouter:
    """触发路由 - 根据事件类型分发"""
    
    async def route(self, trigger: ResearchTrigger):
        """路由处理"""
        logger.info(f"\n🤖 [Agent系统] 接收到触发: {trigger}")
        
        if trigger.trigger_kind == TriggerKind.INDICATOR:
            logger.info(f"  ➜ 转发给: 技术面研究 Agent")
            await self._process_indicator(trigger)
        
        elif trigger.trigger_kind == TriggerKind.ANNOUNCEMENT:
            logger.info(f"  ➜ 转发给: 基本面研究 Agent")
            await self._process_announcement(trigger)
    
    async def _process_indicator(self, trigger: ResearchTrigger):
        """处理技术指标事件"""
        logger.info(f"    📊 技术面 Agent 开始分析 {trigger.symbol}")
        # 模拟分析过程
        await asyncio.sleep(0.1)
        logger.info(f"    ✓ 分析结果: 建议关注 {trigger.symbol}")
    
    async def _process_announcement(self, trigger: ResearchTrigger):
        """处理公告事件"""
        logger.info(f"    📰 基本面 Agent 开始研究 {trigger.symbol}")
        # 模拟研究过程
        await asyncio.sleep(0.1)
        logger.info(f"    ✓ 研究结果: 该公告为重大利好")


# ============================================================================
# 7. 完整演示流程
# ============================================================================

async def demo_event_flow():
    """演示完整的事件处理流程"""
    
    print("\n" + "=" * 80)
    print("🎬 AgentTrader 事件驱动系统演示")
    print("=" * 80)
    print(
        "\n演示流程："
        "\n  1️⃣  数据源适配器 获取原始数据 (RawEvent)"
        "\n  2️⃣  事件规范化器 转换为统一格式 (NormalizedEvent)"
        "\n  3️⃣  生成研究触发 (ResearchTrigger)"
        "\n  4️⃣  Agent 系统 处理触发"
    )
    print("\n" + "-" * 80 + "\n")
    
    symbol = "000001.SZ"  # 平安银行
    router = TriggerRouter()
    
    # ========== 场景 1：K 线数据 ==========
    print("【场景 1】监控 K 线数据\n")
    
    kline_source = MockKLineSource()
    kline_normalizer = KLineNormalizer()
    
    # 第 1 步：获取原始事件
    raw_events = await kline_source.fetch_klines(symbol)
    
    # 第 2 步：规范化
    for raw_event in raw_events:
        logger.info(f"\n[规范化] 处理: {raw_event}")
        normalized = await kline_normalizer.normalize(raw_event)
        
        # 第 3 步：如果满足条件，生成触发对象
        if normalized:
            logger.info(f"[触发] {normalized}")
            
            # 第 4 步：提交给 Agent 系统
            trigger = await kline_normalizer.to_trigger(normalized)
            await router.route(trigger)
        else:
            logger.info("[筛选] 事件未满足触发条件，已过滤")
    
    # ========== 场景 2：财经新闻 ==========
    print("\n" + "-" * 80)
    print("\n【场景 2】监控财经新闻\n")
    
    news_source = MockNewsSource()
    news_normalizer = NewsNormalizer()
    
    # 获取新闻
    raw_events = await news_source.fetch_news(symbol)
    
    # 规范化和处理
    for raw_event in raw_events:
        logger.info(f"\n[规范化] 处理: {raw_event}")
        normalized = await news_normalizer.normalize(raw_event)
        
        if normalized:
            logger.info(f"[触发] {normalized}")
            trigger = await news_normalizer.to_trigger(normalized)
            await router.route(trigger)
    
    # 总结
    print("\n" + "=" * 80)
    print("✅ 演示完成")
    print("=" * 80)
    print(
        "\n核心要点："
        "\n  1. 事件定义：TriggerKind Enum 定义系统支持的所有事件类型"
        "\n  2. 事件转换：RawEvent → NormalizedEvent → ResearchTrigger"
        "\n  3. 数据源适配：每个外部 API 需要一个 SourceAdapter"
        "\n  4. 规范化处理：每个数据源需要一个 EventNormalizer"
        "\n  5. Agent 路由：根据事件类型分发给不同的 Agent 处理"
        "\n\n下一步："
        "\n  📖 阅读完整文档: docs/DEVELOPER_GUIDE_CN.md"
        "\n  🛠️  实现你的第一个数据源: src/agent_trader/ingestion/sources/"
        "\n  ⚙️  配置定时任务: src/agent_trader/worker/tasks.py"
    )
    print("=" * 80 + "\n")


async def main():
    """主函数"""
    await demo_event_flow()


if __name__ == "__main__":
    asyncio.run(main())

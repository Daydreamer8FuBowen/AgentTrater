"""
TuShare 数据规范化器

将 TuShare 的原始数据转换为系统内部的标准化格式。
支持将 K 线数据、基本信息等转换为研究触发事件。
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from agent_trader.domain.models import BarInterval, TriggerKind
from agent_trader.ingestion.models import NormalizedEvent, RawEvent, ResearchTrigger

logger = logging.getLogger(__name__)


class TuShareNormalizer:
    """
    TuShare 数据规范化器，负责将原始 TuShare 数据转换为标准化格式。

    支持的转换：
    - daily：日线数据 → NormalizedEvent
    - daily_basic：每日基础信息 → NormalizedEvent
    - stock_basic：股票基本信息 → NormalizedEvent
    """

    async def normalize(self, raw_event: RawEvent) -> NormalizedEvent | None:
        """
        将 TuShare RawEvent 转换为标准 NormalizedEvent。

        Args:
            raw_event: TuShare 原始事件

        Returns:
            标准化事件，若无法转换则返回 None

        Raises:
            ValueError: 若数据格式无效
        """
        source = raw_event.source
        payload = raw_event.payload

        # 根据数据源类型调用对应的转换方法
        if source == "tushare" or source.startswith("tushare:"):
            # 根据 source 子类型优先判断
            if "daily_basic" in source:
                return self._normalize_daily_basic(payload)
            elif "stock_basic" in source:
                return self._normalize_stock_basic(payload)
            elif "trade_date" in payload:
                return self._normalize_kline(payload)

        logger.warning(f"Unknown TuShare source type: {source}")
        return None

    async def to_trigger(self, normalized_event: NormalizedEvent) -> ResearchTrigger:
        """
        将规范化事件转换为研究触发对象。

        将事件转换为一个可被系统处理的研究任务。

        Args:
            normalized_event: 规范化事件

        Returns:
            研究触发对象
        """
        return ResearchTrigger(
            trigger_kind=normalized_event.trigger_kind,
            symbol=normalized_event.symbol,
            summary=normalized_event.title,
            metadata={
                "content": normalized_event.content,
                **normalized_event.metadata,
            },
        )

    def _normalize_kline(self, payload: dict[str, Any]) -> NormalizedEvent:
        """
        转换 K 线数据。

        Args:
            payload: TuShare 日线数据

        Returns:
            标准化事件
        """
        symbol = payload.get("ts_code", "unknown")
        trade_date = payload.get("trade_date", "")
        close = payload.get("close", 0)
        change_pct = payload.get("change_pct", 0)

        # 根据涨跌幅判断触发类型
        if isinstance(change_pct, str):
            change_pct = float(change_pct)

        if change_pct > 5:
            title = f"{symbol} 异常上涨 {change_pct}%"
        elif change_pct < -5:
            title = f"{symbol} 异常下跌 {change_pct}%"
        else:
            title = f"{symbol} 价格变化 {change_pct}%"

        return NormalizedEvent(
            trigger_kind=TriggerKind.INDICATOR,
            symbol=symbol,
            title=title,
            content=f"日线收盘价：{close}，涨跌幅：{change_pct}%",
            metadata={
                "trade_date": str(trade_date),
                "close": close,
                "change_pct": change_pct,
                "open": payload.get("open", 0),
                "high": payload.get("high", 0),
                "low": payload.get("low", 0),
                "vol": payload.get("vol", 0),
                "amount": payload.get("amount", 0),
            },
        )

    def _normalize_daily_basic(self, payload: dict[str, Any]) -> NormalizedEvent:
        """
        转换每日基础信息数据。

        Args:
            payload: TuShare 每日基础信息

        Returns:
            标准化事件
        """
        symbol = payload.get("ts_code", "unknown")
        pe = payload.get("pe", 0)
        pb = payload.get("pb", 0)

        return NormalizedEvent(
            trigger_kind=TriggerKind.INDICATOR,
            symbol=symbol,
            title=f"{symbol} 基本面数据更新",
            content=f"PE: {pe}, PB: {pb}",
            metadata={
                "pe": pe,
                "pb": pb,
                "dv_ratio": payload.get("dv_ratio", 0),
                "dv_ttm": payload.get("dv_ttm", 0),
                "total_mv": payload.get("total_mv", 0),
                "trade_date": payload.get("trade_date", ""),
            },
        )

    def _normalize_stock_basic(self, payload: dict[str, Any]) -> NormalizedEvent:
        """
        转换股票基本信息数据。

        Args:
            payload: TuShare 股票基本信息

        Returns:
            标准化事件
        """
        symbol = payload.get("ts_code", "unknown")
        name = payload.get("name", "")
        industry = payload.get("industry", "")

        return NormalizedEvent(
            trigger_kind=TriggerKind.ANNOUNCEMENT,
            symbol=symbol,
            title=f"纳入监控：{name}",
            content=f"行业：{industry}，首次加入监控列表",
            metadata={
                "name": name,
                "industry": industry,
                "area": payload.get("area", ""),
                "market": payload.get("market", ""),
                "list_date": payload.get("list_date", ""),
            },
        )

"""
TuShare 数据源适配器

提供从 TuShare 获取中国股票市场数据的接口。
TuShare 是一个提供 A 股、港股、期货等多市场数据的数据库。

支持的数据类型：
- K线数据（日线、周线、月线等）
- 财报数据
- 行业信息
- 股票基本信息
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Any

import tushare as ts

from agent_trader.domain.models import BarInterval, ExchangeKind
from agent_trader.ingestion.models import (
    DataCapability,
    DataRouteKey,
    FetchMode,
    KlineQuery,
    NewsQuery,
    RawEvent,
    SourceCapabilitySpec,
    SourceFetchResult,
)

logger = logging.getLogger(__name__)

# BarInterval → TuShare 频率标识映射（本适配器仅支持 5min 和 日线）
_INTERVAL_TO_FREQ: dict[BarInterval, str] = {
    BarInterval.M5: "5min",
    BarInterval.D1: "D",
}

# TuShare 支持的新闻源（news API 的 src 参数）
_NEWS_SRCS = ("sina", "wallstreetcn", "10jqka", "eastmoney", "yuncaijing", "guba_eastmoney", "rss")

# 此数据源的能力声明
_SUPPORTED_KLINE_INTERVALS = tuple(_INTERVAL_TO_FREQ.keys())
_A_SHARE_MARKETS = (ExchangeKind.SSE, ExchangeKind.SZSE)


class TuShareSource:
    """
    TuShare 数据源适配器，负责从 TuShare API 获取原始股票数据。

    Attributes:
        token (str): TuShare API token，用于认证请求
        pro (tushare.TushareAPI): TuShare Pro API 客户端实例
        http_url (str): TuShare 数据源 URL（通常是国内加速节点）
    """

    def __init__(self, token: str, http_url: str = "http://lianghua.nanyangqiankun.top"):
        """
        初始化 TuShare 数据源。

        Args:
            token: TuShare API token（从 https://tushare.pro 获取）
            http_url: TuShare HTTP 数据源 URL，默认为国内加速节点
        """
        if not token:
            raise ValueError("TuShare token 不能为空，请在环境变量或配置中设置 TUSHARE_TOKEN")

        self.token = token
        self.http_url = http_url
        self.pro = ts.pro_api(token)
        # 关键配置：确保 token 和 HTTP URL 正确设置
        # 这两行代码保证能正常获取数据（特别是通过国内代理的情况）
        self.pro._DataApi__token = token
        self.pro._DataApi__http_url = http_url
        self.name = "tushare"

    @classmethod
    def from_settings(cls, settings: Any) -> TuShareSource:
        """
        从统一配置系统创建 TuShareSource 实例。

        Args:
            settings: 从 get_settings() 获取的 Settings 实例

        Returns:
            TuShareSource 实例

        Raises:
            ValueError: 如果配置中没有提供有效的 token
        """
        tushare_config = settings.tushare
        return cls(token=tushare_config.token, http_url=tushare_config.http_url)

    # ------------------------------------------------------------------
    # 统一数据能力接口（KlineDataSource / NewsDataSource 协议实现）
    # ------------------------------------------------------------------

    def capabilities(self) -> list[SourceCapabilitySpec]:
        """声明此数据源支持的能力范围，供 DataSourceRegistry 查询。"""
        return [
            SourceCapabilitySpec(
                source=self.name,
                capability=DataCapability.KLINE,
                modes=(FetchMode.REALTIME, FetchMode.HISTORY, FetchMode.INCREMENTAL),
                markets=_A_SHARE_MARKETS,
                intervals=_SUPPORTED_KLINE_INTERVALS,
            ),
            SourceCapabilitySpec(
                source=self.name,
                capability=DataCapability.NEWS,
                modes=(FetchMode.REALTIME, FetchMode.HISTORY, FetchMode.INCREMENTAL),
                markets=(),  # 新闻不区分市场
            ),
        ]

    async def fetch_klines_unified(self, query: KlineQuery) -> SourceFetchResult:
        """实现 KlineDataSource 协议。

        通过 ``ts.pro_bar`` 获取各周期 K 线，支持前复权/后复权。

        Args:
            query: K 线查询参数，包含 symbol、时间范围、周期、复权标志等。

        Returns:
            SourceFetchResult，payload 中每条记录包含 TuShare 原始字段
            以及归一化的 ``bar_time`` (datetime) 和 ``freq`` (str)。

        Raises:
            ValueError: 不支持的 BarInterval（如 M3、H4）。
            Exception: TuShare API 调用失败时向上传播，由 Gateway/选择器处理熔断。
        """
        freq = _INTERVAL_TO_FREQ.get(query.interval)
        if freq is None:
            raise ValueError(
                f"TuShare 不支持 BarInterval={query.interval.value}，"
                f"支持范围：{list(_INTERVAL_TO_FREQ.keys())}"
            )

        adj: str | None = "qfq" if query.adjusted else None
        # 日线以上用 YYYYMMDD；分钟线也接受 YYYYMMDD（TuShare 内部会处理）
        start_str = query.start_time.strftime("%Y%m%d")
        end_str = query.end_time.strftime("%Y%m%d")

        route_key = DataRouteKey(
            capability=DataCapability.KLINE,
            mode=query.mode,
            market=query.market,
            interval=query.interval,
        )

        df = await asyncio.to_thread(
            ts.pro_bar,
            ts_code=query.symbol,
            adj=adj,
            start_date=start_str,
            end_date=end_str,
            freq=freq,
            api=self.pro,
        )

        if df is None or df.empty:
            logger.warning(
                "fetch_klines_unified: no data symbol=%s freq=%s [%s, %s]",
                query.symbol, freq, start_str, end_str,
            )
            return SourceFetchResult(
                source=self.name,
                route_key=route_key,
                payload=[],
                metadata={"symbol": query.symbol, "freq": freq, "count": 0},
            )

        payload: list[dict[str, Any]] = []
        for _, row in df.iterrows():
            record: dict[str, Any] = row.to_dict()
            # 归一化时间字段：分钟线用 trade_time，日线用 trade_date
            if "trade_time" in record and record["trade_time"] is not None:
                record["bar_time"] = datetime.strptime(
                    str(record["trade_time"]), "%Y-%m-%d %H:%M:%S"
                )
            elif "trade_date" in record and record["trade_date"] is not None:
                record["bar_time"] = datetime.strptime(
                    str(record["trade_date"]), "%Y%m%d"
                )
            record["_freq"] = freq
            payload.append(record)

        logger.info(
            "fetch_klines_unified: fetched %d bars symbol=%s freq=%s",
            len(payload), query.symbol, freq,
        )
        return SourceFetchResult(
            source=self.name,
            route_key=route_key,
            payload=payload,
            metadata={"symbol": query.symbol, "freq": freq, "count": len(payload)},
        )

    async def fetch_news_unified(self, query: NewsQuery) -> SourceFetchResult:
        """实现 NewsDataSource 协议。

        通过 TuShare ``news`` 接口按时间段拉取新闻，支持：
        - 多新闻源（通过 ``query.extra["src"]`` 指定，默认 ``"sina"``）
        - 关键词过滤（在 title + content 中做 OR 匹配，不区分大小写）
        - 股票代码过滤（对 ``channels`` 字段做包含匹配）

        出于权限成本考虑，默认只查询单个 src；如需多源聚合，可在
        ``query.extra["src"]`` 中传入逗号分隔的字符串，例如
        ``"sina,eastmoney"``，本方法会并发获取并合并去重。

        Args:
            query: 新闻查询参数。

        Returns:
            SourceFetchResult，payload 中每条记录包含 TuShare 原始字段。

        Raises:
            Exception: TuShare API 调用失败时向上传播。
        """
        route_key = DataRouteKey(
            capability=DataCapability.NEWS,
            mode=query.mode,
            market=query.market,
        )

        # 解析新闻数据源（可在 extra 中覆盖，逗号分隔支持多源）
        raw_src: str = query.extra.get("src", "sina")
        sources = [s.strip() for s in raw_src.split(",") if s.strip() in _NEWS_SRCS]
        if not sources:
            logger.warning("fetch_news_unified: unknown src=%s, fallback to sina", raw_src)
            sources = ["sina"]

        # 构建时间参数（TuShare 要求 "YYYYMMDD HH:MM:SS" 格式）
        start_str = (
            query.start_time.strftime("%Y%m%d %H:%M:%S") if query.start_time else None
        )
        end_str = (
            query.end_time.strftime("%Y%m%d %H:%M:%S") if query.end_time else None
        )

        async def _fetch_one_src(src: str) -> list[dict[str, Any]]:
            kwargs: dict[str, Any] = {"src": src}
            if start_str:
                kwargs["start_date"] = start_str
            if end_str:
                kwargs["end_date"] = end_str
            df = await asyncio.to_thread(self.pro.news, **kwargs)
            if df is None or df.empty:
                return []
            return [row.to_dict() for _, row in df.iterrows()]

        # 并发拉取多个新闻源
        results: list[list[dict[str, Any]]] = await asyncio.gather(
            *[_fetch_one_src(src) for src in sources]
        )

        # 合并、去重（以 datetime+title 为唯一键）
        seen: set[tuple[str, str]] = set()
        merged: list[dict[str, Any]] = []
        for records in results:
            for rec in records:
                key = (str(rec.get("datetime", "")), str(rec.get("title", "")))
                if key in seen:
                    continue
                seen.add(key)
                merged.append(rec)

        # 关键词过滤（OR 语义，不区分大小写）
        if query.keywords:
            kws = [kw.lower() for kw in query.keywords]
            merged = [
                rec for rec in merged
                if any(
                    kw in (rec.get("title", "") + " " + rec.get("content", "")).lower()
                    for kw in kws
                )
            ]

        # 股票代码过滤（模糊匹配 channels 字段）
        if query.symbol:
            sym = query.symbol
            merged = [
                rec for rec in merged
                if sym in str(rec.get("channels", ""))
            ]

        logger.info(
            "fetch_news_unified: fetched %d records src=%s keywords=%s symbol=%s",
            len(merged), sources, query.keywords, query.symbol,
        )
        return SourceFetchResult(
            source=self.name,
            route_key=route_key,
            payload=merged,
            metadata={
                "sources": sources,
                "count": len(merged),
                "keywords": query.keywords,
                "symbol": query.symbol,
            },
        )

    async def fetch_basic_info(self) -> list[RawEvent]:
        """
        异步获取股票基本信息。

        Returns:
            RawEvent 列表，每条股票信息作为一个事件
        """
        try:
            df = await asyncio.to_thread(self.pro.stock_basic, exchange="", list_status="L")

            if df is None or df.empty:
                logger.warning("No stock basic info found")
                return []

            events = []
            for _, row in df.iterrows():
                event = RawEvent(
                    source=f"{self.name}:stock_basic",
                    payload=row.to_dict(),
                )
                events.append(event)

            logger.info(f"Fetched {len(events)} stock basic infos")
            return events

        except Exception as e:
            logger.error(f"Error fetching stock basic info: {e}")
            return []

    async def fetch_daily_basic(
        self,
        trade_date: str | None = None,
    ) -> list[RawEvent]:
        """
        异步获取每日基础信息（PE、PB 等）。

        Args:
            trade_date: 交易日期（格式：YYYYMMDD），若为 None，则取最近交易日

        Returns:
            RawEvent 列表
        """
        try:
            if trade_date is None:
                # 获取最近交易日
                trade_date = (datetime.now() - timedelta(days=1)).strftime("%Y%m%d")

            df = await asyncio.to_thread(
                self.pro.daily_basic,
                trade_date=trade_date,
            )

            if df is None or df.empty:
                logger.warning(f"No daily basic data found for {trade_date}")
                return []

            events = []
            for _, row in df.iterrows():
                event = RawEvent(
                    source=f"{self.name}:daily_basic",
                    payload=row.to_dict(),
                )
                events.append(event)

            logger.info(f"Fetched {len(events)} daily basic records")
            return events

        except Exception as e:
            logger.error(f"Error fetching daily basic: {e}")
            return []

    async def fetch(self) -> list[RawEvent]:
        """
        默认的 fetch 方法，获取最近一个交易日的基础面数据。

        实现 SourceAdapter 协议的要求方法。K 线数据请使用 fetch_klines_unified()。

        Returns:
            RawEvent 列表
        """
        try:
            return await self.fetch_daily_basic()
        except Exception as e:
            logger.error(f"Error in default fetch: {e}")
            return []

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
from datetime import datetime
from typing import Any

import tushare as ts

from agent_trader.domain.models import BarInterval, ExchangeKind
from agent_trader.ingestion.models import (
    BasicInfoFetchResult,
    BasicInfoRecord,
    DataCapability,
    DataRouteKey,
    FinancialReportFetchResult,
    FinancialReportRecord,
    FinancialReportQuery,
    KlineFetchResult,
    KlineRecord,
    KlineQuery,
    NewsFetchResult,
    NewsRecord,
    NewsQuery,
    SourceCapabilitySpec,
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
    # 约定：basic_info 与 kline 绑定出现，不单独拆分协议。
    # ------------------------------------------------------------------

    def capabilities(self) -> list[SourceCapabilitySpec]:
        """声明此数据源支持的能力范围，供 DataSourceRegistry 查询。"""
        return [
            SourceCapabilitySpec(
                source=self.name,
                capability=DataCapability.KLINE,
                markets=_A_SHARE_MARKETS,
                intervals=_SUPPORTED_KLINE_INTERVALS,
            ),
            SourceCapabilitySpec(
                source=self.name,
                capability=DataCapability.NEWS,
                markets=(),  # 新闻不区分市场
            ),
            SourceCapabilitySpec(
                source=self.name,
                capability=DataCapability.FINANCIAL_REPORT,
                markets=_A_SHARE_MARKETS,
            ),
        ]

    async def fetch_klines_unified(self, query: KlineQuery) -> KlineFetchResult:
        """实现 KlineDataSource 协议。

        通过 ``ts.pro_bar`` 获取各周期 K 线，支持前复权/后复权。

        Args:
            query: K 线查询参数，包含 symbol、时间范围、周期、复权标志等。

        Returns:
            KlineFetchResult，payload 中每条记录均为统一字段的 K 线结构。

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
            return KlineFetchResult(
                source=self.name,
                route_key=route_key,
                payload=[],
                metadata={"symbol": query.symbol, "freq": freq, "count": 0},
            )

        payload: list[KlineRecord] = []
        for _, row in df.iterrows():
            payload.append(_normalize_tushare_kline_record(row.to_dict(), query.interval, query.adjusted))

        logger.info(
            "fetch_klines_unified: fetched %d bars symbol=%s freq=%s",
            len(payload), query.symbol, freq,
        )
        return KlineFetchResult(
            source=self.name,
            route_key=route_key,
            payload=payload,
            metadata={"symbol": query.symbol, "freq": freq, "count": len(payload)},
        )

    async def fetch_news_unified(self, query: NewsQuery) -> NewsFetchResult:
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
            NewsFetchResult，payload 中每条记录均为统一字段的新闻结构。

        Raises:
            Exception: TuShare API 调用失败时向上传播。
        """
        route_key = DataRouteKey(
            capability=DataCapability.NEWS,
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
        return NewsFetchResult(
            source=self.name,
            route_key=route_key,
            payload=[_normalize_tushare_news_record(record) for record in merged],
            metadata={
                "sources": sources,
                "count": len(merged),
                "keywords": query.keywords,
                "symbol": query.symbol,
            },
        )

    async def fetch_basic_info(self, market: ExchangeKind | None = None) -> BasicInfoFetchResult:
        """异步获取股票基本信息，返回统一结果容器。"""
        route_key = DataRouteKey(
            capability=DataCapability.KLINE,
            market=market,
        )

        try:
            df = await asyncio.to_thread(self.pro.stock_basic, exchange="", list_status="L")

            if df is None or df.empty:
                logger.warning("No stock basic info found")
                return BasicInfoFetchResult(
                    source=self.name,
                    route_key=route_key,
                    payload=[],
                    metadata={"dataset": "stock_basic", "count": 0},
                )

            payload = [_normalize_tushare_basic_info_record(row.to_dict()) for _, row in df.iterrows()]
            logger.info("Fetched %d stock basic infos", len(payload))
            return BasicInfoFetchResult(
                source=self.name,
                route_key=route_key,
                payload=payload,
                metadata={"dataset": "stock_basic", "count": len(payload)},
            )

        except Exception as e:
            logger.error(f"Error fetching stock basic info: {e}")
            return BasicInfoFetchResult(
                source=self.name,
                route_key=route_key,
                payload=[],
                metadata={"dataset": "stock_basic", "count": 0, "error": str(e)},
            )

    async def fetch_financial_reports_unified(
        self,
        query: FinancialReportQuery,
    ) -> FinancialReportFetchResult:
        """通过 TuShare ``fina_indicator`` 获取统一格式财务数据。"""
        route_key = DataRouteKey(
            capability=DataCapability.FINANCIAL_REPORT,
            market=query.market,
        )

        params: dict[str, Any] = {"ts_code": query.symbol}
        if query.start_time:
            params["start_date"] = query.start_time.strftime("%Y%m%d")
        if query.end_time:
            params["end_date"] = query.end_time.strftime("%Y%m%d")
        params.update(query.extra)

        df = await asyncio.to_thread(self.pro.fina_indicator, **params)
        if df is None or df.empty:
            return FinancialReportFetchResult(
                source=self.name,
                route_key=route_key,
                payload=[],
                metadata={"symbol": query.symbol, "count": 0},
            )

        payload = [_normalize_tushare_financial_record(row.to_dict()) for _, row in df.iterrows()]
        return FinancialReportFetchResult(
            source=self.name,
            route_key=route_key,
            payload=payload,
            metadata={"symbol": query.symbol, "count": len(payload)},
        )


def _normalize_tushare_kline_record(
    record: dict[str, Any],
    interval: BarInterval,
    adjusted: bool,
) -> KlineRecord:
    bar_time = _parse_tushare_bar_time(record)
    return KlineRecord(
        symbol=str(record.get("ts_code", "")),
        bar_time=bar_time,
        interval=interval.value,
        open=_to_float(record.get("open")),
        high=_to_float(record.get("high")),
        low=_to_float(record.get("low")),
        close=_to_float(record.get("close")),
        volume=_to_float(record.get("vol")),
        amount=_to_float(record.get("amount")),
        change_pct=_to_float(record.get("pct_chg", record.get("change_pct"))),
        turnover_rate=_to_float(record.get("turnover_rate", record.get("turnover_rate_f"))),
        adjusted=adjusted,
    )


def _normalize_tushare_news_record(record: dict[str, Any]) -> NewsRecord:
    channels = str(record.get("channels", "")).strip()
    return NewsRecord(
        published_at=_parse_datetime_value(record.get("datetime")),
        title=str(record.get("title", "")),
        content=str(record.get("content", "")),
        source_channel=str(record.get("src", "")),
        url=record.get("url"),
        symbols=_extract_symbols_from_channels(channels),
    )


def _normalize_tushare_basic_info_record(record: dict[str, Any]) -> BasicInfoRecord:
    return BasicInfoRecord(
        symbol=str(record.get("ts_code", "")),
        name=record.get("name"),
        industry=record.get("industry"),
        area=record.get("area"),
        market=record.get("market"),
        list_date=_parse_compact_date(record.get("list_date")),
        status=record.get("list_status"),
    )


def _normalize_tushare_financial_record(record: dict[str, Any]) -> FinancialReportRecord:
    return FinancialReportRecord(
        symbol=str(record.get("ts_code", "")),
        report_type=str(record.get("end_type", "fina_indicator") or "fina_indicator"),
        report_date=_parse_compact_date(record.get("end_date")),
        published_at=_parse_compact_date(record.get("ann_date")),
        report_year=_extract_year(record.get("end_date")),
        report_quarter=_extract_quarter(record.get("end_date")),
        metrics={
            "eps": _to_float(record.get("eps")),
            "dt_eps": _to_float(record.get("dt_eps")),
            "total_revenue_ps": _to_float(record.get("total_revenue_ps")),
            "netprofit_margin": _to_float(record.get("netprofit_margin")),
            "roe": _to_float(record.get("roe")),
            "roa": _to_float(record.get("roa")),
            "debt_to_assets": _to_float(record.get("debt_to_assets")),
        },
    )


def _extract_year(value: Any) -> int | None:
    text = str(value or "").strip()
    if len(text) >= 4 and text[:4].isdigit():
        return int(text[:4])
    return None


def _extract_quarter(value: Any) -> int | None:
    text = str(value or "").strip()
    if len(text) != 8 or not text.isdigit():
        return None
    month = int(text[4:6])
    if month <= 3:
        return 1
    if month <= 6:
        return 2
    if month <= 9:
        return 3
    return 4


def _parse_tushare_bar_time(record: dict[str, Any]) -> datetime:
    trade_time = record.get("trade_time")
    if trade_time not in (None, ""):
        return datetime.strptime(str(trade_time), "%Y-%m-%d %H:%M:%S")

    trade_date = record.get("trade_date")
    if trade_date in (None, ""):
        raise ValueError("TuShare K 线记录缺少 trade_time/trade_date")
    return datetime.strptime(str(trade_date), "%Y%m%d")


def _parse_compact_date(value: Any) -> datetime | None:
    if value in (None, ""):
        return None

    text = str(value).strip()
    if not text:
        return None
    if len(text) == 8 and text.isdigit():
        return datetime.strptime(text, "%Y%m%d")
    return datetime.strptime(text, "%Y-%m-%d")


def _parse_datetime_value(value: Any) -> datetime | None:
    if value in (None, ""):
        return None

    text = str(value).strip()
    if not text:
        return None
    if len(text) == 14 and text.isdigit():
        return datetime.strptime(text, "%Y%m%d%H%M%S")
    if len(text) == 19:
        return datetime.strptime(text, "%Y-%m-%d %H:%M:%S")
    if len(text) == 17:
        return datetime.strptime(text, "%Y%m%d %H:%M:%S")
    return datetime.fromisoformat(text)


def _extract_symbols_from_channels(channels: str) -> list[str]:
    items = []
    for raw_item in channels.split(","):
        item = raw_item.strip()
        if not item or "." not in item:
            continue
        code, suffix = item.split(".", maxsplit=1)
        upper_suffix = suffix.upper()
        if upper_suffix in {"SZ", "SH"} and code.isdigit():
            items.append(f"{code}.{upper_suffix}")
    return items


def _to_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    return float(value)

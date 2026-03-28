from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Any

import tushare as ts

from agent_trader.core.time import ensure_utc, market_time_to_utc, to_market_time
from agent_trader.domain.models import BarInterval, ExchangeKind
from agent_trader.ingestion.models import (
    BasicInfoFetchResult,
    BasicInfoRecord,
    CompanyFinancialIndicatorFetchResult,
    CompanyFinancialIndicatorRecord,
    CompanyIncomeStatementFetchResult,
    CompanyIncomeStatementRecord,
    CompanyValuationFetchResult,
    CompanyValuationRecord,
    DataCapability,
    DataRouteKey,
    KlineFetchResult,
    KlineQuery,
    KlineRecord,
    SourceCapabilitySpec,
)
from agent_trader.ingestion.sources.utils import (
    infer_market_from_symbol,
    normalize_a_share_symbol,
    normalize_utc_minute,
    to_a_share_daily_bar_start_utc,
)

# 模块级日志器：统一记录 TuShare source 的调用异常与诊断信息。
logger = logging.getLogger(__name__)

# 统一周期到 TuShare freq 参数的映射表。
_INTERVAL_TO_FREQ: dict[BarInterval, str] = {
    BarInterval.D1: "D",
}
# 该 source 对外声明的可用 K 线周期集合。
_SUPPORTED_KLINE_INTERVALS = tuple(_INTERVAL_TO_FREQ.keys())
# 该 source 当前支持的市场范围（A 股沪深）。
_A_SHARE_MARKETS = (ExchangeKind.SSE, ExchangeKind.SZSE)
# TuShare 中按“日期粒度”查询时使用的 freq 集合。
_DAYLIKE_FREQS = {"D", "W", "M"}
_COMPANY_DETAIL_LOOKBACK_YEARS = 5


class TuShareCompanyDetailAbility:
    def __init__(self, pro: Any, source_name: str) -> None:
        self._pro = pro
        self._source_name = source_name

    async def fetch_company_valuation_unified(
        self,
        symbol: str,
        market: ExchangeKind | None = None,
    ) -> CompanyValuationFetchResult:
        canonical_symbol = normalize_a_share_symbol(symbol, market)
        valuation = await self._fetch_stock_valuation(canonical_symbol, market)
        route_key = DataRouteKey(
            capability=DataCapability.COMPANY_DETAIL,
            market=market,
            interval=None,
        )
        payload = [valuation] if valuation is not None else []
        return CompanyValuationFetchResult(
            source=self._source_name,
            route_key=route_key,
            payload=payload,
            metadata={"symbol": canonical_symbol, "count": len(payload)},
        )

    async def fetch_company_financial_indicators_unified(
        self,
        symbol: str,
        market: ExchangeKind | None = None,
    ) -> CompanyFinancialIndicatorFetchResult:
        canonical_symbol = normalize_a_share_symbol(symbol, market)
        start_date, end_date = _build_recent_years_date_window(_COMPANY_DETAIL_LOOKBACK_YEARS)
        financial_indicators = await self._fetch_financial_indicators(
            canonical_symbol,
            market,
            start_date,
            end_date,
        )
        route_key = DataRouteKey(
            capability=DataCapability.COMPANY_DETAIL,
            market=market,
            interval=None,
        )
        return CompanyFinancialIndicatorFetchResult(
            source=self._source_name,
            route_key=route_key,
            payload=financial_indicators,
            metadata={
                "symbol": canonical_symbol,
                "start_date": start_date,
                "end_date": end_date,
                "count": len(financial_indicators),
            },
        )

    async def fetch_company_income_statements_unified(
        self,
        symbol: str,
        market: ExchangeKind | None = None,
    ) -> CompanyIncomeStatementFetchResult:
        canonical_symbol = normalize_a_share_symbol(symbol, market)
        start_date, end_date = _build_recent_years_date_window(_COMPANY_DETAIL_LOOKBACK_YEARS)
        income_statements = await self._fetch_income_statements(
            canonical_symbol,
            market,
            start_date,
            end_date,
        )
        route_key = DataRouteKey(
            capability=DataCapability.COMPANY_DETAIL,
            market=market,
            interval=None,
        )
        return CompanyIncomeStatementFetchResult(
            source=self._source_name,
            route_key=route_key,
            payload=income_statements,
            metadata={
                "symbol": canonical_symbol,
                "start_date": start_date,
                "end_date": end_date,
                "count": len(income_statements),
            },
        )

    async def _fetch_stock_valuation(
        self,
        symbol: str,
        market: ExchangeKind | None,
    ) -> CompanyValuationRecord | None:
        try:
            df = await asyncio.to_thread(
                self._pro.daily_basic,
                ts_code=symbol,
                trade_date="",
                fields="ts_code,trade_date,pe,pe_ttm,pb",
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("TuShare daily_basic failed symbol=%s error=%s", symbol, exc)
            return None
        if df is None or df.empty:
            return None
        rows = [row.to_dict() for _, row in df.iterrows()]
        sorted_rows = sorted(
            rows,
            key=lambda item: _to_date_sort_key(item.get("trade_date")),
            reverse=True,
        )
        latest = sorted_rows[0]
        return CompanyValuationRecord(
            trade_date=_parse_compact_date(latest.get("trade_date"), market),
            pe_ttm=_to_float(latest.get("pe_ttm")),
            pe=_to_float(latest.get("pe")),
            pb=_to_float(latest.get("pb")),
        )

    async def _fetch_financial_indicators(
        self,
        symbol: str,
        market: ExchangeKind | None,
        start_date: str,
        end_date: str,
    ) -> list[CompanyFinancialIndicatorRecord]:
        try:
            df = await asyncio.to_thread(
                self._pro.fina_indicator,
                ts_code=symbol,
                start_date=start_date,
                end_date=end_date,
                fields="ts_code,end_date,grossprofit_margin,netprofit_margin,roe,debt_to_assets",
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("TuShare fina_indicator failed symbol=%s error=%s", symbol, exc)
            return []
        if df is None or df.empty:
            return []
        rows = [row.to_dict() for _, row in df.iterrows()]
        sorted_rows = sorted(rows, key=lambda item: _to_date_sort_key(item.get("end_date")))
        return [
            CompanyFinancialIndicatorRecord(
                report_date=_parse_compact_date(item.get("end_date"), market),
                grossprofit_margin=_to_float(item.get("grossprofit_margin")),
                netprofit_margin=_to_float(item.get("netprofit_margin")),
                roe=_to_float(item.get("roe")),
                debt_to_assets=_to_float(item.get("debt_to_assets")),
            )
            for item in sorted_rows
        ]

    async def _fetch_income_statements(
        self,
        symbol: str,
        market: ExchangeKind | None,
        start_date: str,
        end_date: str,
    ) -> list[CompanyIncomeStatementRecord]:
        try:
            df = await asyncio.to_thread(
                self._pro.income,
                ts_code=symbol,
                start_date=start_date,
                end_date=end_date,
                fields="ts_code,end_date,report_type,total_revenue,n_income",
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("TuShare income failed symbol=%s error=%s", symbol, exc)
            return []
        if df is None or df.empty:
            return []
        rows = [row.to_dict() for _, row in df.iterrows()]
        sorted_rows = sorted(rows, key=lambda item: _to_date_sort_key(item.get("end_date")))
        return [
            CompanyIncomeStatementRecord(
                report_date=_parse_compact_date(item.get("end_date"), market),
                report_type=_to_optional_str(item.get("report_type")),
                revenue=_to_float(item.get("total_revenue")),
                net_profit=_to_float(item.get("n_income")),
            )
            for item in sorted_rows
        ]


class TuShareSource:
    """TuShare 统一数据源适配器。

    架构说明：
    - 本类是 sources 层 provider 实现，遵循统一 K 线能力契约。
    - 在路由架构中与 BaoStock 并列，网关根据 route_key 与优先级选择实际 provider。
    - 本类内部完成 token 连接配置、symbol/time 字段规范化与统一结果封装，
      保障上层调用不依赖 TuShare 原生字段结构。
    """

    def __init__(self, token: str, http_url: str | None = None) -> None:
        if not token:
            raise ValueError("TuShare token 不能为空，请在环境变量或配置中设置 TUSHARE_TOKEN")
        self.token = token
        self.http_url = (http_url or "").strip()
        if self.http_url:
            self.pro = ts.pro_api(token)
            self.pro._DataApi__token = token
            self.pro._DataApi__http_url = self.http_url
        else:
            ts.set_token(token)
            self.pro = ts.pro_api()
        self.name = "tushare"
        self.company_detail_ability = TuShareCompanyDetailAbility(self.pro, self.name)

    @classmethod
    def from_settings(cls, settings: Any) -> TuShareSource:
        config = settings.tushare
        return cls(token=config.token, http_url=config.http_url)

    def capabilities(self) -> list[SourceCapabilitySpec]:
        return [
            SourceCapabilitySpec(
                source=self.name,
                capability=DataCapability.KLINE,
                markets=_A_SHARE_MARKETS,
                intervals=_SUPPORTED_KLINE_INTERVALS,
            ),
            SourceCapabilitySpec(
                source=self.name,
                capability=DataCapability.COMPANY_DETAIL,
                markets=_A_SHARE_MARKETS,
            ),
        ]

    async def fetch_klines_unified(self, query: KlineQuery) -> KlineFetchResult:
        """获取 K 线并保证 payload 按 bar_time 递增（从旧到新）排序。"""
        freq = _INTERVAL_TO_FREQ.get(query.interval)
        if freq is None:
            raise ValueError(f"TuShare 不支持 BarInterval={query.interval.value}")
        start_utc = normalize_utc_minute(query.start_time, field_name="start_time")
        end_utc = normalize_utc_minute(query.end_time, field_name="end_time")
        if end_utc < start_utc:
            raise ValueError("end_time 不能早于 start_time")
        canonical_symbol = normalize_a_share_symbol(query.symbol, query.market)
        start_str = _format_kline_query_time(start_utc, query.market, freq)
        end_str = _format_kline_query_time(end_utc, query.market, freq)
        route_key = DataRouteKey(
            capability=DataCapability.KLINE,
            market=query.market,
            interval=query.interval,
        )
        df = await asyncio.to_thread(
            ts.pro_bar,
            ts_code=canonical_symbol,
            adj="qfq" if query.adjusted else None,
            start_date=start_str,
            end_date=end_str,
            freq=freq,
            api=self.pro,
        )
        if df is None or df.empty:
            return KlineFetchResult(
                source=self.name,
                route_key=route_key,
                payload=[],
                metadata={"symbol": canonical_symbol, "freq": freq, "count": 0},
            )
        payload = [
            _normalize_tushare_kline_record(row.to_dict(), query.interval, query.adjusted)
            for _, row in df.iterrows()
        ]
        payload = [item for item in payload if start_utc <= ensure_utc(item.bar_time) <= end_utc]
        payload = sorted(payload, key=lambda item: ensure_utc(item.bar_time))
        return KlineFetchResult(
            source=self.name,
            route_key=route_key,
            payload=payload,
            metadata={"symbol": canonical_symbol, "freq": freq, "count": len(payload)},
        )

    async def fetch_basic_info(self, market: ExchangeKind | None = None) -> BasicInfoFetchResult:
        route_key = DataRouteKey(
            capability=DataCapability.KLINE,
            market=market,
        )
        try:
            df = await asyncio.to_thread(
                self.pro.stock_basic,
                exchange="",
                list_status="L",
                fields="ts_code,name,industry,area,list_date,list_status",
            )
        except Exception as exc:  # noqa: BLE001
            logger.error("Error fetching TuShare basic info: %s", exc)
            return BasicInfoFetchResult(
                source=self.name,
                route_key=route_key,
                payload=[],
                metadata={"dataset": "stock_basic", "count": 0, "error": str(exc)},
            )
        if df is None or df.empty:
            return BasicInfoFetchResult(
                source=self.name,
                route_key=route_key,
                payload=[],
                metadata={"dataset": "stock_basic", "count": 0},
            )
        
        raw_items = [
            _normalize_tushare_basic_info_record(row.to_dict()) for _, row in df.iterrows()
        ]
        payload = [item for item in raw_items if item is not None]
        if market in {ExchangeKind.SSE, ExchangeKind.SZSE}:
            suffix = "SH" if market == ExchangeKind.SSE else "SZ"
            payload = [item for item in payload if item.symbol.endswith(f".{suffix}")]
        return BasicInfoFetchResult(
            source=self.name,
            route_key=route_key,
            payload=payload,
            metadata={"dataset": "stock_basic", "count": len(payload)},
        )

    async def fetch_company_valuation_unified(
        self,
        symbol: str,
        market: ExchangeKind | None = None,
    ) -> CompanyValuationFetchResult:
        return await self.company_detail_ability.fetch_company_valuation_unified(symbol, market)

    async def fetch_company_financial_indicators_unified(
        self,
        symbol: str,
        market: ExchangeKind | None = None,
    ) -> CompanyFinancialIndicatorFetchResult:
        return await self.company_detail_ability.fetch_company_financial_indicators_unified(symbol, market)

    async def fetch_company_income_statements_unified(
        self,
        symbol: str,
        market: ExchangeKind | None = None,
    ) -> CompanyIncomeStatementFetchResult:
        return await self.company_detail_ability.fetch_company_income_statements_unified(symbol, market)


def _normalize_tushare_kline_record(
    record: dict[str, Any],
    interval: BarInterval,
    adjusted: bool,
) -> KlineRecord:
    symbol = normalize_a_share_symbol(str(record.get("ts_code", "")))
    return KlineRecord(
        symbol=symbol,
        bar_time=_parse_tushare_bar_time(record, interval),
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


def _normalize_tushare_basic_info_record(record: dict[str, Any]) -> BasicInfoRecord | None:
    try:
        symbol = normalize_a_share_symbol(str(record.get("ts_code", "")))
        if not symbol:
            return None
        market = infer_market_from_symbol(symbol)
        return BasicInfoRecord(
            symbol=symbol,
            name=record.get("name"),
            industry=record.get("industry"),
            area=record.get("area"),
            market=market,
            list_date=_parse_compact_date(record.get("list_date"), market),
            status="1" if record.get("list_status") == "L" else "0",
            act_ent_type=record.get("act_ent_type"),
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("Skip malformed TuShare stock_basic record: %s ; error=%s", record, exc)
        return None


def _parse_tushare_bar_time(record: dict[str, Any], interval: BarInterval) -> datetime:
    symbol = normalize_a_share_symbol(str(record.get("ts_code", "")))
    market = infer_market_from_symbol(symbol)
    trade_time = record.get("trade_time")
    if trade_time not in (None, ""):
        parsed = datetime.strptime(str(trade_time), "%Y-%m-%d %H:%M:%S")
        return market_time_to_utc(parsed, market)

    trade_date = record.get("trade_date")
    if trade_date in (None, ""):
        raise ValueError("TuShare K 线记录缺少 trade_time/trade_date")
    parsed = datetime.strptime(str(trade_date), "%Y%m%d")
    if interval == BarInterval.D1:
        return to_a_share_daily_bar_start_utc(parsed, market)
    return market_time_to_utc(parsed, market)


def _format_kline_query_time(dt: datetime, market: ExchangeKind | None, freq: str) -> str:
    local = to_market_time(dt, market)
    if freq in _DAYLIKE_FREQS:
        return local.strftime("%Y%m%d")
    return local.strftime("%Y%m%d %H:%M:%S")


def _parse_compact_date(value: Any, market: ExchangeKind | None) -> datetime | None:
    if value in (None, ""):
        return None
    text = str(value).strip()
    if not text:
        return None
    if len(text) == 8 and text.isdigit():
        return market_time_to_utc(datetime.strptime(text, "%Y%m%d"), market)
    return market_time_to_utc(datetime.strptime(text, "%Y-%m-%d"), market)


def _to_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    return float(value)


def _build_recent_years_date_window(years: int) -> tuple[str, str]:
    now = datetime.now()
    start_year = now.year - years
    try:
        start = datetime(start_year, now.month, now.day)
    except ValueError:
        start = datetime(start_year, now.month, 28)
    return start.strftime("%Y%m%d"), now.strftime("%Y%m%d")


def _to_date_sort_key(value: Any) -> str:
    if value in (None, ""):
        return ""
    return str(value).strip()


def _to_optional_str(value: Any) -> str | None:
    if value in (None, ""):
        return None
    text = str(value).strip()
    return text or None

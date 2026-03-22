"""
BaoStock 数据源适配器

提供从 BaoStock 获取中国 A 股市场数据的统一接口。

支持的数据类型：
- K 线数据（5/15/30/60 分钟，日/周/月）
- 财务报表数据（盈利、营运、成长、资产负债、现金流、杜邦、业绩预告、业绩快报）
- 股票基本信息
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Any, Callable, TypeVar

import baostock as bs

from agent_trader.domain.models import BarInterval, ExchangeKind
from agent_trader.ingestion.models import (
    DataCapability,
    DataRouteKey,
    FetchMode,
    FinancialReportQuery,
    KlineQuery,
    RawEvent,
    SourceCapabilitySpec,
    SourceFetchResult,
)

logger = logging.getLogger(__name__)

_T = TypeVar("_T")

_INTERVAL_TO_FREQ: dict[BarInterval, str] = {
    BarInterval.M5: "5",
    BarInterval.M15: "15",
    BarInterval.M30: "30",
    BarInterval.H1: "60",
    BarInterval.D1: "d",
    BarInterval.W1: "w",
    BarInterval.MN1: "m",
}

_SUPPORTED_KLINE_INTERVALS = tuple(_INTERVAL_TO_FREQ.keys())
_A_SHARE_MARKETS = (ExchangeKind.SSE, ExchangeKind.SZSE)
_DAYLIKE_FREQS = {"d", "w", "m"}
_DAYLIKE_FIELDS = (
    "date,code,open,high,low,close,preclose,volume,amount,adjustflag,turn,"
    "tradestatus,pctChg,peTTM,pbMRQ,psTTM,pcfNcfTTM,isST"
)
_MINUTE_FIELDS = "date,time,code,open,high,low,close,volume,amount,adjustflag"
_VALUE_SKIP_FIELDS = {"code", "symbol", "date", "time", "pubDate", "statDate"}
_QUARTERLY_REPORT_TYPES = {
    "profit": "query_profit_data",
    "operation": "query_operation_data",
    "growth": "query_growth_data",
    "balance": "query_balance_data",
    "cash_flow": "query_cash_flow_data",
    "dupont": "query_dupont_data",
}
_DATE_RANGE_REPORT_TYPES = {
    "forecast": "query_forecast_report",
    "performance_express": "query_performance_express_report",
}
_DEFAULT_REPORT_TYPES = tuple(_QUARTERLY_REPORT_TYPES.keys()) + tuple(_DATE_RANGE_REPORT_TYPES.keys())


class BaoStockSource:
    """BaoStock 数据源适配器。"""

    def __init__(
        self,
        user_id: str = "anonymous",
        password: str = "123456",
        *,
        options: int = 0,
    ) -> None:
        self.user_id = user_id
        self.password = password
        self.options = options
        self.name = "baostock"

    @classmethod
    def from_settings(cls, settings: Any) -> BaoStockSource:
        """从统一配置系统创建 BaoStockSource 实例。"""
        baostock_config = settings.baostock
        return cls(
            user_id=baostock_config.user_id,
            password=baostock_config.password,
            options=baostock_config.options,
        )

    def capabilities(self) -> list[SourceCapabilitySpec]:
        """声明此数据源支持的能力范围。"""
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
                capability=DataCapability.FINANCIAL_REPORT,
                modes=(FetchMode.HISTORY, FetchMode.INCREMENTAL),
                markets=_A_SHARE_MARKETS,
            ),
        ]

    async def fetch_klines_unified(self, query: KlineQuery) -> SourceFetchResult:
        """通过 BaoStock 获取统一格式的 K 线数据。"""
        freq = _INTERVAL_TO_FREQ.get(query.interval)
        if freq is None:
            raise ValueError(
                f"BaoStock 不支持 BarInterval={query.interval.value}，"
                f"支持范围：{list(_INTERVAL_TO_FREQ.keys())}"
            )

        code = _to_baostock_symbol(query.symbol, query.market)
        fields = _DAYLIKE_FIELDS if freq in _DAYLIKE_FREQS else _MINUTE_FIELDS
        route_key = DataRouteKey(
            capability=DataCapability.KLINE,
            mode=query.mode,
            market=query.market,
            interval=query.interval,
        )

        payload = await asyncio.to_thread(
            self._query_kline_payload,
            code,
            fields,
            query.start_time.strftime("%Y-%m-%d"),
            query.end_time.strftime("%Y-%m-%d"),
            freq,
            "2" if query.adjusted else "3",
        )

        logger.info(
            "fetch_klines_unified: fetched %d bars symbol=%s freq=%s",
            len(payload),
            query.symbol,
            freq,
        )
        return SourceFetchResult(
            source=self.name,
            route_key=route_key,
            payload=payload,
            metadata={"symbol": query.symbol, "freq": freq, "count": len(payload)},
        )

    async def fetch_financial_reports_unified(
        self,
        query: FinancialReportQuery,
    ) -> SourceFetchResult:
        """通过 BaoStock 获取财务报表与业绩类数据。"""
        route_key = DataRouteKey(
            capability=DataCapability.FINANCIAL_REPORT,
            mode=query.mode,
            market=query.market,
        )

        code = _to_baostock_symbol(query.symbol, query.market)
        report_types = _resolve_report_types(query.extra)
        payload = await asyncio.to_thread(
            self._query_financial_payload,
            code,
            report_types,
            query.start_time,
            query.end_time,
        )

        logger.info(
            "fetch_financial_reports_unified: fetched %d records symbol=%s report_types=%s",
            len(payload),
            query.symbol,
            report_types,
        )
        return SourceFetchResult(
            source=self.name,
            route_key=route_key,
            payload=payload,
            metadata={
                "symbol": query.symbol,
                "report_types": report_types,
                "count": len(payload),
            },
        )

    async def fetch_basic_info(self) -> list[RawEvent]:
        """异步获取股票基础信息。"""
        try:
            payload = await asyncio.to_thread(self._query_stock_basic_payload)
        except Exception as exc:  # noqa: BLE001
            logger.error("Error fetching BaoStock basic info: %s", exc)
            return []

        return [
            RawEvent(source=f"{self.name}:stock_basic", payload=record)
            for record in payload
        ]

    async def fetch(self) -> list[RawEvent]:
        """默认 fetch 返回股票基础信息。"""
        return await self.fetch_basic_info()

    def _query_kline_payload(
        self,
        code: str,
        fields: str,
        start_date: str,
        end_date: str,
        frequency: str,
        adjustflag: str,
    ) -> list[dict[str, Any]]:
        def operation() -> list[dict[str, Any]]:
            result = bs.query_history_k_data_plus(
                code,
                fields,
                start_date=start_date,
                end_date=end_date,
                frequency=frequency,
                adjustflag=adjustflag,
            )
            payload = self._rows_from_result(result)
            for record in payload:
                record["symbol"] = _to_canonical_symbol(str(record.get("code", code)))
                record["bar_time"] = _parse_bar_time(record)
                record["_freq"] = frequency
            return payload

        return self._run_with_session(operation)

    def _query_stock_basic_payload(self) -> list[dict[str, Any]]:
        def operation() -> list[dict[str, Any]]:
            result = bs.query_stock_basic()
            payload = self._rows_from_result(result)
            for record in payload:
                code = str(record.get("code", ""))
                if code:
                    record["symbol"] = _to_canonical_symbol(code)
            return payload

        return self._run_with_session(operation)

    def _query_financial_payload(
        self,
        code: str,
        report_types: tuple[str, ...],
        start_time: datetime | None,
        end_time: datetime | None,
    ) -> list[dict[str, Any]]:
        def operation() -> list[dict[str, Any]]:
            payload: list[dict[str, Any]] = []
            for report_type in report_types:
                if report_type in _QUARTERLY_REPORT_TYPES:
                    method = getattr(bs, _QUARTERLY_REPORT_TYPES[report_type])
                    for year, quarter in _iter_quarters(start_time, end_time):
                        result = method(code, year=year, quarter=quarter)
                        for record in self._rows_from_result(result):
                            record["symbol"] = _to_canonical_symbol(str(record.get("code", code)))
                            record["_report_type"] = report_type
                            record["_report_year"] = year
                            record["_report_quarter"] = quarter
                            payload.append(record)
                    continue

                method = getattr(bs, _DATE_RANGE_REPORT_TYPES[report_type])
                result = method(
                    code,
                    start_date=_format_date(start_time),
                    end_date=_format_date(end_time),
                )
                for record in self._rows_from_result(result):
                    record["symbol"] = _to_canonical_symbol(str(record.get("code", code)))
                    record["_report_type"] = report_type
                    payload.append(record)
            return payload

        return self._run_with_session(operation)

    def _run_with_session(self, operation: Callable[[], _T]) -> _T:
        login_result = bs.login(self.user_id, self.password, self.options)
        if getattr(login_result, "error_code", "0") != "0":
            raise RuntimeError(f"BaoStock login failed: {login_result.error_msg}")

        try:
            return operation()
        finally:
            try:
                bs.logout(self.user_id)
            except Exception:  # noqa: BLE001
                logger.warning("BaoStock logout failed for user=%s", self.user_id)

    def _rows_from_result(self, result: Any) -> list[dict[str, Any]]:
        if getattr(result, "error_code", "0") != "0":
            raise RuntimeError(f"BaoStock query failed: {result.error_msg}")

        fields = list(getattr(result, "fields", []))
        rows: list[dict[str, Any]] = []
        while result.next():
            raw_row = result.get_row_data()
            record = dict(zip(fields, raw_row, strict=False))
            rows.append(_coerce_record_values(record))
        return rows


def _to_baostock_symbol(symbol: str, market: ExchangeKind | None = None) -> str:
    text = symbol.strip()
    lower = text.lower()
    if lower.startswith(("sh.", "sz.")):
        return lower

    if "." in text:
        code, suffix = text.split(".", maxsplit=1)
        suffix = suffix.upper()
        if suffix == "SH":
            return f"sh.{code}"
        if suffix == "SZ":
            return f"sz.{code}"

    if market == ExchangeKind.SSE or text.startswith(("6", "9")):
        return f"sh.{text}"
    if market == ExchangeKind.SZSE or text.startswith(("0", "2", "3")):
        return f"sz.{text}"
    raise ValueError(f"无法将 symbol={symbol} 归一化为 BaoStock code")


def _to_canonical_symbol(symbol: str) -> str:
    text = symbol.strip().lower()
    if text.startswith("sh."):
        return f"{text[3:]}.SH"
    if text.startswith("sz."):
        return f"{text[3:]}.SZ"
    return symbol


def _parse_bar_time(record: dict[str, Any]) -> datetime:
    time_value = record.get("time")
    if isinstance(time_value, str) and time_value.strip():
        digits = "".join(ch for ch in time_value if ch.isdigit())
        if len(digits) >= 14:
            return datetime.strptime(digits[:14], "%Y%m%d%H%M%S")

    date_value = str(record.get("date", "")).strip()
    if not date_value:
        raise ValueError("BaoStock K 线记录缺少 date/time 字段")
    return datetime.strptime(date_value, "%Y-%m-%d")


def _coerce_record_values(record: dict[str, Any]) -> dict[str, Any]:
    coerced: dict[str, Any] = {}
    for key, value in record.items():
        if key in _VALUE_SKIP_FIELDS or value in (None, ""):
            coerced[key] = value
            continue

        if not isinstance(value, str):
            coerced[key] = value
            continue

        text = value.strip()
        if not text:
            coerced[key] = None
            continue

        try:
            if any(ch in text for ch in (".", "e", "E")):
                coerced[key] = float(text)
            else:
                coerced[key] = int(text)
            continue
        except ValueError:
            coerced[key] = value
    return coerced


def _resolve_report_types(extra: dict[str, Any]) -> tuple[str, ...]:
    requested = extra.get("report_types") if extra else None
    if requested is None:
        return _DEFAULT_REPORT_TYPES

    if isinstance(requested, str):
        items = [item.strip() for item in requested.split(",") if item.strip()]
    else:
        items = [str(item).strip() for item in requested if str(item).strip()]

    invalid = [item for item in items if item not in _DEFAULT_REPORT_TYPES]
    if invalid:
        raise ValueError(f"BaoStock 不支持的财报类型：{invalid}")
    return tuple(items) if items else _DEFAULT_REPORT_TYPES


def _iter_quarters(
    start_time: datetime | None,
    end_time: datetime | None,
) -> list[tuple[int, int]]:
    start = start_time or end_time or datetime.utcnow()
    end = end_time or start
    if start > end:
        start, end = end, start

    year = start.year
    quarter = _quarter_of(start)
    end_year = end.year
    end_quarter = _quarter_of(end)
    quarters: list[tuple[int, int]] = []
    while (year, quarter) <= (end_year, end_quarter):
        quarters.append((year, quarter))
        quarter += 1
        if quarter > 4:
            year += 1
            quarter = 1
    return quarters


def _quarter_of(value: datetime) -> int:
    return (value.month - 1) // 3 + 1


def _format_date(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.strftime("%Y-%m-%d")
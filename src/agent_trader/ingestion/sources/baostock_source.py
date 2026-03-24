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
    SourceCapabilitySpec,
)

logger = logging.getLogger(__name__)

_T = TypeVar("_T")

_INTERVAL_TO_FREQ: dict[BarInterval, str] = {
    BarInterval.M5: "5",
    BarInterval.D1: "d"
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
_BAOSTOCK_SECURITY_TYPE_MAP: dict[str, str] = {
    "1": "stock",
    "2": "index",
    "4": "bond",
    "5": "fund",
}


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
        """从统一配置系统创建 BaoStockSource 实例。

        Args:
            settings: 包含 `baostock` 配置属性的配置对象。

        Returns:
            已用配置初始化的 `BaoStockSource` 实例。
        """
        baostock_config = settings.baostock
        return cls(
            user_id=baostock_config.user_id,
            password=baostock_config.password,
            options=baostock_config.options,
        )

    def capabilities(self) -> list[SourceCapabilitySpec]:
        """声明此数据源支持的能力范围。

        返回对外暴露的能力清单，用于路由和能力匹配。
        """
        return [
            SourceCapabilitySpec(
                source=self.name,
                capability=DataCapability.KLINE,
                markets=_A_SHARE_MARKETS,
                intervals=_SUPPORTED_KLINE_INTERVALS,
            ),
            SourceCapabilitySpec(
                source=self.name,
                capability=DataCapability.FINANCIAL_REPORT,
                markets=_A_SHARE_MARKETS,
            ),
        ]

    async def fetch_klines_unified(self, query: KlineQuery) -> KlineFetchResult:
        """通过 BaoStock 获取统一格式的 K 线数据。

        接受 `KlineQuery`，调用内部同步查询并将结果封装为 `KlineFetchResult`。
        若请求的 `interval` 不受支持，会抛出 `ValueError`。
        """
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
            query.interval,
            query.adjusted,
        )

        logger.info(
            "fetch_klines_unified: fetched %d bars symbol=%s freq=%s",
            len(payload),
            query.symbol,
            freq,
        )
        return KlineFetchResult(
            source=self.name,
            route_key=route_key,
            payload=payload,
            metadata={"symbol": query.symbol, "freq": freq, "count": len(payload)},
        )

    async def fetch_financial_reports_unified(
        self,
        query: FinancialReportQuery,
    ) -> FinancialReportFetchResult:
        """通过 BaoStock 获取财务报表与业绩类数据。

        根据 `query.extra` 中的类型选择要查询的报表种类，返回 `FinancialReportFetchResult`。
        查询在后台线程中运行，避免阻塞事件循环。
        """
        route_key = DataRouteKey(
            capability=DataCapability.FINANCIAL_REPORT,
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
        return FinancialReportFetchResult(
            source=self.name,
            route_key=route_key,
            payload=payload,
            metadata={
                "symbol": query.symbol,
                "report_types": report_types,
                "count": len(payload),
            },
        )

    async def fetch_basic_info(self, market: ExchangeKind | None = None) -> BasicInfoFetchResult:
        """异步获取股票基础信息，返回统一结果容器。

        在后台线程执行 _query_stock_basic_payload，并对异常做捕获，保证
        返回值始终为 `BasicInfoFetchResult`（即使 payload 为空）。
        """
        route_key = DataRouteKey(
            capability=DataCapability.KLINE,
            market=market,
        )
        try:
            payload = await asyncio.to_thread(self._query_stock_basic_payload)
        except Exception as exc:  # noqa: BLE001
            logger.error("Error fetching BaoStock basic info: %s", exc)
            return BasicInfoFetchResult(
                source=self.name,
                route_key=route_key,
                payload=[],
                metadata={"dataset": "stock_basic", "count": 0, "error": str(exc)},
            )

        return BasicInfoFetchResult(
            source=self.name,
            route_key=route_key,
            payload=payload,
            metadata={"dataset": "stock_basic", "count": len(payload)},
        )

    def _query_kline_payload(
        self,
        code: str,
        fields: str,
        start_date: str,
        end_date: str,
        frequency: str,
        adjustflag: str,
        interval: BarInterval,
        adjusted: bool,
    ) -> list[KlineRecord]:
        """在同步上下文中调用 BaoStock 的历史行情接口并返回标准化的 K 线记录列表。

        Args:
            code: BaoStock 风格的股票代码（例如 `sh.600000`）。
            fields: 查询字段字符串。
            start_date: 开始日期，格式 `YYYY-MM-DD`。
            end_date: 结束日期，格式 `YYYY-MM-DD`。
            frequency: BaoStock 使用的频率字符串（如 "5","d"）。
            adjustflag: 复权标志（BaoStock 要求的编码）。
            interval: 我们内部使用的 `BarInterval`，用于标准化记录。
            adjusted: 是否已复权，用于结果标注。

        Returns:
            标准化后的 `KlineRecord` 列表。
        """

        def operation() -> list[KlineRecord]:
            result = bs.query_history_k_data_plus(
                code,
                fields,
                start_date=start_date,
                end_date=end_date,
                frequency=frequency,
                adjustflag=adjustflag,
            )
            rows = self._rows_from_result(result)
            return [
                _normalize_baostock_kline_record(record, interval, adjusted, code)
                for record in rows
            ]

        return self._run_with_session(operation)

    def _query_stock_basic_payload(self) -> list[BasicInfoRecord]:
        """在同步上下文中调用 BaoStock 的股票基础信息查询并返回标准化记录。

        返回一个 `BasicInfoRecord` 列表，用于后续封装到 `BasicInfoFetchResult`。
        """

        def operation() -> list[BasicInfoRecord]:
            result = bs.query_stock_basic()
            rows = self._rows_from_result(result)
            return [_normalize_baostock_basic_info_record(record) for record in rows]

        return self._run_with_session(operation)

    def _query_financial_payload(
        self,
        code: str,
        report_types: tuple[str, ...],
        start_time: datetime | None,
        end_time: datetime | None,
    ) -> list[FinancialReportRecord]:
        """在同步上下文中查询指定代码及报表类型的财务数据并标准化为记录列表。

        支持按季度类型和按时间范围的报表方法。
        """

        def operation() -> list[FinancialReportRecord]:
            payload: list[FinancialReportRecord] = []
            for report_type in report_types:
                if report_type in _QUARTERLY_REPORT_TYPES:
                    method = getattr(bs, _QUARTERLY_REPORT_TYPES[report_type])
                    for year, quarter in _iter_quarters(start_time, end_time):
                        result = method(code, year=year, quarter=quarter)
                        for record in self._rows_from_result(result):
                            payload.append(
                                _normalize_baostock_financial_record(
                                    record,
                                    symbol_hint=code,
                                    report_type=report_type,
                                    report_year=year,
                                    report_quarter=quarter,
                                )
                            )
                    continue

                method = getattr(bs, _DATE_RANGE_REPORT_TYPES[report_type])
                result = method(
                    code,
                    start_date=_format_date(start_time),
                    end_date=_format_date(end_time),
                )
                for record in self._rows_from_result(result):
                    payload.append(
                        _normalize_baostock_financial_record(
                            record,
                            symbol_hint=code,
                            report_type=report_type,
                        )
                    )
            return payload

        return self._run_with_session(operation)

    def _run_with_session(self, operation: Callable[[], _T]) -> _T:
        """使用 baostock 的登录会话执行传入的同步操作。

        负责登录、执行 `operation`，以及在 finally 中尝试登出以释放会话。
        若登录失败，抛出 `RuntimeError`。
        """

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
        """将 baostock 查询结果对象转换为字典列表并做值类型强转。

        Args:
            result: baostock 返回的查询结果对象。

        Returns:
            一个由字段-值映射字典组成的列表，值已通过 `_coerce_record_values` 转换。
        """

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
    """将外部符号形式归一化为 BaoStock 要求的代码格式。

    支持的输入形式包括 `sh.600000`, `600000.SH`, `600000` 等，
    并可根据传入的 `market` 推断前缀。

    Raises:
        ValueError: 无法识别或归一化输入符号时抛出。
    """

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
    """将 BaoStock 风格的代码或类似形式转换为标准展示形式。

    例如：`sh.600000` -> `600000.SH`，`sz.000001` -> `000001.SZ`。
    对于不匹配的输入，原样返回。
    """

    text = symbol.strip().lower()
    if text.startswith("sh."):
        return f"{text[3:]}.SH"
    if text.startswith("sz."):
        return f"{text[3:]}.SZ"
    return symbol


def _parse_bar_time(record: dict[str, Any]) -> datetime:
    """从 baostock 的 K 线记录解析出时间戳。

    优先解析 `time` 字段（可能包含完整的时间字符串），
    否则回退到 `date` 字段并按日解析。

    Raises:
        ValueError: 当既没有时间也没有日期信息时抛出。
    """

    time_value = record.get("time")
    if isinstance(time_value, str) and time_value.strip():
        digits = "".join(ch for ch in time_value if ch.isdigit())
        if len(digits) >= 14:
            return datetime.strptime(digits[:14], "%Y%m%d%H%M%S")

    date_value = str(record.get("date", "")).strip()
    if not date_value:
        raise ValueError("BaoStock K 线记录缺少 date/time 字段")
    return datetime.strptime(date_value, "%Y-%m-%d")


def _normalize_baostock_kline_record(
    record: dict[str, Any],
    interval: BarInterval,
    adjusted: bool,
    symbol_hint: str,
) -> KlineRecord:
    """将单条 baostock 原始 K 线字典标准化为 `KlineRecord`。

    Args:
        record: 原始字典形式的行数据。
        interval: 目标 `BarInterval`，用于填充 `interval` 字段。
        adjusted: 标记该记录是否为复权数据。
        symbol_hint: 当记录中缺少 code 字段时使用的符号提示。
    """

    return KlineRecord(
        symbol=_to_canonical_symbol(str(record.get("code", symbol_hint))),
        bar_time=_parse_bar_time(record),
        interval=interval.value,
        open=_to_float(record.get("open")),
        high=_to_float(record.get("high")),
        low=_to_float(record.get("low")),
        close=_to_float(record.get("close")),
        volume=_to_float(record.get("volume")),
        amount=_to_float(record.get("amount")),
        change_pct=_to_float(record.get("pctChg")),
        turnover_rate=_to_float(record.get("turn")),
        is_trading=_to_bool(record.get("tradestatus")),
        adjusted=adjusted,
    )


def _normalize_baostock_basic_info_record(record: dict[str, Any]) -> BasicInfoRecord:
    """将 baostock 返回的股票基础信息行转换为 `BasicInfoRecord`。

    该转换会尝试解析代码、名称、上市日期与交易所信息，并统一符号格式。
    """

    code = str(record.get("code", ""))
    return BasicInfoRecord(
        symbol=_to_canonical_symbol(code) if code else "",
        name=record.get("code_name", record.get("name")),
        industry=None,
        area=None,
        market=_infer_market_from_symbol(code),
        list_date=_parse_optional_date(record.get("ipoDate")),
        status=record.get("status"),
        delist_date=_parse_optional_date(record.get("outDate")),
        security_type=_normalize_baostock_security_type(record.get("type")),
    )


def _normalize_baostock_security_type(value: Any) -> str | None:
    """将 BaoStock `type` 原始编码映射为统一 `security_type` 符号值。"""

    if value in (None, ""):
        return None

    normalized = str(value).strip().lower()
    if not normalized:
        return None
    return _BAOSTOCK_SECURITY_TYPE_MAP.get(normalized, "unknown")


def _normalize_baostock_financial_record(
    record: dict[str, Any],
    *,
    symbol_hint: str,
    report_type: str,
    report_year: int | None = None,
    report_quarter: int | None = None,
) -> FinancialReportRecord:
    """将 baostock 返回的单条财务/业绩记录转换为 `FinancialReportRecord`。

    会提取发布日期、统计日期，并将其余指标放到 `metrics` 字段中。
    """

    published_at = _parse_optional_date(record.get("pubDate") or record.get("performanceExpPubDate"))
    report_date = _parse_optional_date(record.get("statDate") or record.get("performanceExpStatDate"))
    metrics = {
        key: value
        for key, value in record.items()
        if key not in {
            "code",
            "pubDate",
            "statDate",
            "performanceExpPubDate",
            "performanceExpStatDate",
        }
    }
    return FinancialReportRecord(
        symbol=_to_canonical_symbol(str(record.get("code", symbol_hint))),
        report_type=report_type,
        report_date=report_date,
        published_at=published_at,
        report_year=report_year,
        report_quarter=report_quarter,
        metrics=metrics,
    )


def _coerce_record_values(record: dict[str, Any]) -> dict[str, Any]:
    """对从 baostock 得到的字符串值进行类型强转。

    - 对于包含小数点或科学计数法的字符串，尝试转换为 `float`。
    - 否则尝试转换为 `int`。
    - 对于空字符串或特定跳过字段，保留原值或置为 `None`。
    返回转换后的字典副本。
    """

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


def _parse_optional_date(value: Any) -> datetime | None:
    """解析可选日期字符串为 `datetime.date` 风格的 `datetime` 对象。

    如果输入为空或不可解析，返回 `None`。
    支持格式为 `%Y-%m-%d`。
    """

    if value in (None, ""):
        return None

    text = str(value).strip()
    if not text:
        return None
    return datetime.strptime(text, "%Y-%m-%d")


def _infer_market_from_symbol(symbol: str) -> str | None:
    """从符号推断市场前缀（'sh' / 'sz'），无法识别时返回 None。"""

    text = symbol.strip().lower()
    if text.startswith("sh."):
        return "sh"
    if text.startswith("sz."):
        return "sz"
    return None


def _to_float(value: Any) -> float | None:
    """将可能为字符串或数值的输入转换为 `float`，空值返回 `None`。"""

    if value in (None, ""):
        return None
    return float(value)


def _to_bool(value: Any) -> bool | None:
    """将常见的字符串/数字表示转换为布尔值。

    - 接受 `1/0`, `true/false`, `yes/no` 等形式（不区分大小写）。
    - 对于无法识别的输入返回 `None`。
    """

    if value in (None, ""):
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    text = str(value).strip().lower()
    if text in {"1", "true", "yes", "y"}:
        return True
    if text in {"0", "false", "no", "n"}:
        return False
    return None


def _resolve_report_types(extra: dict[str, Any]) -> tuple[str, ...]:
    """从 `extra` 字段解析用户请求的财报类型列表，返回合法的类型元组。

    若未指定则返回默认全部可用类型；若包含未知类型则抛出 `ValueError`。
    """

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
    """在给定的开始/结束时间区间内生成 (year, quarter) 的序列。

    若任一端为 None，则以另一端或当前时间作为参考点。
    返回值为按时间顺序增大的 (year, quarter) 元组列表。
    """

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
    """计算 datetime 所在的季度（1-4）。"""

    return (value.month - 1) // 3 + 1


def _format_date(value: datetime | None) -> str | None:
    """将可选的 datetime 格式化为 `YYYY-MM-DD` 字符串，空值返回 None。"""

    if value is None:
        return None
    return value.strftime("%Y-%m-%d")
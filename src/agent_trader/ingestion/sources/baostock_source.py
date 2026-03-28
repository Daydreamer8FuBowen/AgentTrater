from __future__ import annotations

import asyncio
import logging
import threading
import time
from collections.abc import Callable
from datetime import datetime
from typing import Any, TypeVar

import baostock as bs

from agent_trader.core.time import ensure_utc, market_time_to_utc, to_market_time
from agent_trader.domain.models import BarInterval, ExchangeKind
from agent_trader.ingestion.models import (
    BasicInfoFetchResult,
    BasicInfoRecord,
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
    to_baostock_symbol,
)

# 模块级日志器：统一承接 BaoStock source 的错误、告警与调试信息。
logger = logging.getLogger(__name__)

# 泛型类型变量：用于 _run_with_session 在不同 operation 返回类型下保持类型一致。
_T = TypeVar("_T")
# BaoStock 会话串行锁：限制登录/查询/登出流程串行执行，避免并发会话互相污染。
_BS_SESSION_LOCK = threading.Lock()
# BaoStock 接口限流阈值（每秒请求数）。
_BS_QPS_LIMIT = 10
# 统一周期到 BaoStock frequency 的映射表。
_INTERVAL_TO_FREQ: dict[BarInterval, str] = {
    # BarInterval.M5: "5",
    BarInterval.D1: "d",
}
# 该 source 对外声明的可用 K 线周期集合。
_SUPPORTED_KLINE_INTERVALS = tuple(_INTERVAL_TO_FREQ.keys())
# 该 source 当前支持的市场范围（A 股沪深）。
_A_SHARE_MARKETS = (ExchangeKind.SSE, ExchangeKind.SZSE)
# BaoStock 中按“日期粒度”返回数据的 frequency 集合。
_DAYLIKE_FREQS = {"d"}
# 日线查询字段集合：覆盖统一 KlineRecord 所需核心字段与可选衍生字段。
_DAYLIKE_FIELDS = (
    "date,code,open,high,low,close,preclose,volume,amount,adjustflag,turn,"
    "tradestatus,pctChg,peTTM,pbMRQ,psTTM,pcfNcfTTM,isST"
)
# 分钟线查询字段集合：与 BaoStock 分钟接口字段约束保持一致。
_MINUTE_FIELDS = "date,time,code,open,high,low,close,volume,amount,adjustflag"
# 类型转换时需跳过的字段，避免代码/时间字符串被误转数值。
_VALUE_SKIP_FIELDS = {"code", "symbol", "date", "time"}
# BaoStock 原生 security type 到统一语义值的映射表。
_BAOSTOCK_SECURITY_TYPE_MAP: dict[str, str] = {
    "1": "stock",
    "2": "index",
    "4": "bond",
    "5": "fund",
}


class _RateLimiter:
    """线程安全令牌桶限流器。

    架构说明：
    - 该类位于 source 适配层内部，不对外暴露。
    - 在“单体多模块 + 多源路由”架构中，BaoStock 属于外部公共接口，需在 provider 内主动控频。
    - 通过 Condition + monotonic clock 实现跨线程共享限流，保证 to_thread 并发下仍满足 QPS 约束。
    """

    def __init__(self, rate_per_sec: float) -> None:
        self._rate = float(rate_per_sec)
        self._capacity = float(rate_per_sec)
        self._tokens = float(rate_per_sec)
        self._last = time.monotonic()
        self._cond = threading.Condition()

    def acquire(self) -> None:
        with self._cond:
            while True:
                now = time.monotonic()
                elapsed = now - self._last
                self._last = now
                self._tokens = min(self._capacity, self._tokens + elapsed * self._rate)
                if self._tokens >= 1.0:
                    self._tokens -= 1.0
                    return
                need = (1.0 - self._tokens) / self._rate
                wait_for = min(max(need, 0.001), 1.0)
                self._cond.wait(wait_for)


# BaoStock 全局限流器实例：所有 API 调用共享同一限流窗口。
_BS_RATE_LIMITER = _RateLimiter(_BS_QPS_LIMIT)


def _call_baostock(func: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
    _BS_RATE_LIMITER.acquire()
    return func(*args, **kwargs)


class BaoStockSource:
    """BaoStock 统一数据源适配器。

    架构说明：
    - 本类是 sources 层的具体 provider，实现 K 线与基础信息统一输出契约。
    - 上层网关只依赖协议（capabilities/fetch_*），通过路由键驱动多源选择与故障降级。
    - 本类内部负责三类适配：
      1) symbol 规范化（统一代码 <-> BaoStock 代码）
      2) 时间语义规范化（市场时间 -> UTC，A 股 D1 对齐到 09:30）
      3) 字段语义规范化（provider 原生字段 -> 统一 record 模型）
    - 会话与控频策略内聚在本类，避免路由层感知 provider 细节。
    """

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
        config = settings.baostock
        return cls(
            user_id=config.user_id,
            password=config.password,
            options=config.options,
        )

    def capabilities(self) -> list[SourceCapabilitySpec]:
        return [
            SourceCapabilitySpec(
                source=self.name,
                capability=DataCapability.KLINE,
                markets=_A_SHARE_MARKETS,
                intervals=_SUPPORTED_KLINE_INTERVALS,
            ),
        ]

    async def fetch_klines_unified(self, query: KlineQuery) -> KlineFetchResult:
        """获取 K 线并保证 payload 按 bar_time 递增（从旧到新）排序。"""
        freq = _INTERVAL_TO_FREQ.get(query.interval)
        if freq is None:
            raise ValueError(f"BaoStock 不支持 BarInterval={query.interval.value}")
        start_utc = normalize_utc_minute(query.start_time, field_name="start_time")
        end_utc = normalize_utc_minute(query.end_time, field_name="end_time")
        if end_utc < start_utc:
            raise ValueError("end_time 不能早于 start_time")

        code = to_baostock_symbol(query.symbol, query.market)
        route_key = DataRouteKey(
            capability=DataCapability.KLINE,
            market=query.market,
            interval=query.interval,
        )
        start_date = to_market_time(start_utc, query.market).strftime("%Y-%m-%d")
        end_date = to_market_time(end_utc, query.market).strftime("%Y-%m-%d")
        fields = _DAYLIKE_FIELDS if freq in _DAYLIKE_FREQS else _MINUTE_FIELDS
        payload = await asyncio.to_thread(
            self._query_kline_payload,
            code,
            fields,
            start_date,
            end_date,
            freq,
            "2" if query.adjusted else "3",
            query.interval,
            query.adjusted,
        )
        payload = [item for item in payload if start_utc <= ensure_utc(item.bar_time) <= end_utc]
        payload = sorted(payload, key=lambda item: ensure_utc(item.bar_time))
        return KlineFetchResult(
            source=self.name,
            route_key=route_key,
            payload=payload,
            metadata={
                "symbol": normalize_a_share_symbol(query.symbol, query.market),
                "freq": freq,
                "count": len(payload),
            },
        )

    async def fetch_basic_info(self, market: ExchangeKind | None = None) -> BasicInfoFetchResult:
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

        if market in {ExchangeKind.SSE, ExchangeKind.SZSE}:
            suffix = "SH" if market == ExchangeKind.SSE else "SZ"
            payload = [item for item in payload if item.symbol.endswith(f".{suffix}")]
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
        return self._run_with_session(
            self._query_kline_payload_in_session,
            code,
            fields,
            start_date,
            end_date,
            frequency,
            adjustflag,
            interval,
            adjusted,
        )

    def _query_kline_payload_in_session(
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
        result = _call_baostock(
            bs.query_history_k_data_plus,
            code,
            fields,
            start_date=start_date,
            end_date=end_date,
            frequency=frequency,
            adjustflag=adjustflag,
        )
        rows = self._rows_from_result(result)
        return [
            _normalize_baostock_kline_record(record, interval, adjusted, code) for record in rows
        ]

    def _query_stock_basic_payload(self) -> list[BasicInfoRecord]:
        return self._run_with_session(self._query_stock_basic_payload_in_session)

    def _query_stock_basic_payload_in_session(self) -> list[BasicInfoRecord]:
        result = _call_baostock(bs.query_stock_basic)
        rows = self._rows_from_result(result)
        return [_normalize_baostock_basic_info_record(record) for record in rows]

    def _run_with_session(self, operation: Callable[..., _T], *args: Any, **kwargs: Any) -> _T:
        with _BS_SESSION_LOCK:
            login_result = bs.login(self.user_id, self.password, self.options)
            if getattr(login_result, "error_code", "0") != "0":
                raise RuntimeError(f"BaoStock login failed: {login_result.error_msg}")
            try:
                return operation(*args, **kwargs)
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


def _parse_bar_time(record: dict[str, Any], interval: BarInterval, symbol_hint: str) -> datetime:
    market = infer_market_from_symbol(str(record.get("code", symbol_hint)))
    time_value = record.get("time")
    if isinstance(time_value, str) and time_value.strip():
        digits = "".join(ch for ch in time_value if ch.isdigit())
        if len(digits) >= 14:
            return market_time_to_utc(datetime.strptime(digits[:14], "%Y%m%d%H%M%S"), market)

    date_value = str(record.get("date", "")).strip()
    if not date_value:
        raise ValueError("BaoStock K 线记录缺少 date/time 字段")
    parsed = datetime.strptime(date_value, "%Y-%m-%d")
    if interval == BarInterval.D1:
        return to_a_share_daily_bar_start_utc(parsed, market)
    return market_time_to_utc(parsed, market)


def _normalize_baostock_kline_record(
    record: dict[str, Any],
    interval: BarInterval,
    adjusted: bool,
    symbol_hint: str,
) -> KlineRecord:
    raw_symbol = str(record.get("code", symbol_hint))
    return KlineRecord(
        symbol=normalize_a_share_symbol(raw_symbol),
        bar_time=_parse_bar_time(record, interval, symbol_hint),
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
    code = str(record.get("code", "")).strip()
    symbol = normalize_a_share_symbol(code) if code else ""
    market = infer_market_from_symbol(symbol)
    status_raw = str(record.get("status", "")).strip()
    status_normalized = "1" if status_raw == "1" else "0"

    return BasicInfoRecord(
        symbol=symbol,
        name=record.get("code_name", record.get("name")),
        industry=None,
        area=None,
        market=market,
        list_date=_parse_optional_date(record.get("ipoDate"), market),
        status=status_normalized,
        delist_date=_parse_optional_date(record.get("outDate"), market),
        security_type=_normalize_baostock_security_type(record.get("type")),
    )


def _normalize_baostock_security_type(value: Any) -> str | None:
    if value in (None, ""):
        return None
    normalized = str(value).strip().lower()
    if not normalized:
        return None
    return _BAOSTOCK_SECURITY_TYPE_MAP.get(normalized, "unknown")


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
            coerced[key] = float(text) if any(ch in text for ch in (".", "e", "E")) else int(text)
        except ValueError:
            coerced[key] = value
    return coerced


def _parse_optional_date(value: Any, market: ExchangeKind | None) -> datetime | None:
    if value in (None, ""):
        return None
    text = str(value).strip()
    if not text:
        return None
    return market_time_to_utc(datetime.strptime(text, "%Y-%m-%d"), market)


def _to_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    return float(value)


def _to_bool(value: Any) -> bool | None:
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

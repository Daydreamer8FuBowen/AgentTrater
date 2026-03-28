from __future__ import annotations

from datetime import datetime, time

from agent_trader.core.time import market_time_to_utc
from agent_trader.domain.models import ExchangeKind

# A 股日线开盘时间（北京时间），用于将仅含日期的 D1 记录对齐到 bar 开始时刻。
A_SHARE_D1_OPEN_TIME = time(9, 30)


def normalize_a_share_symbol(symbol: str, market: ExchangeKind | None = None) -> str:
    text = symbol.strip()
    if not text:
        raise ValueError("symbol 不能为空")

    lower = text.lower()
    if lower.startswith(("sh.", "sz.")):
        prefix, code = lower.split(".", maxsplit=1)
        suffix = "SH" if prefix == "sh" else "SZ"
        if not code.isdigit():
            raise ValueError(f"symbol={symbol} 非法")
        return f"{code.zfill(6)}.{suffix}"

    if "." in text:
        code, suffix = text.split(".", maxsplit=1)
        up = suffix.upper()
        if up not in {"SH", "SZ"}:
            raise ValueError(f"symbol={symbol} 非法")
        if not code.isdigit():
            raise ValueError(f"symbol={symbol} 非法")
        return f"{code.zfill(6)}.{up}"

    if not text.isdigit():
        raise ValueError(f"symbol={symbol} 非法")

    if market == ExchangeKind.SSE or text.startswith(("6", "9")):
        return f"{text.zfill(6)}.SH"
    if market == ExchangeKind.SZSE or text.startswith(("0", "2", "3")):
        return f"{text.zfill(6)}.SZ"
    raise ValueError(f"无法推断 symbol={symbol} 所属市场")


def to_baostock_symbol(symbol: str, market: ExchangeKind | None = None) -> str:
    canonical = normalize_a_share_symbol(symbol, market)
    code, suffix = canonical.split(".", maxsplit=1)
    return f"{suffix.lower()}.{code}"


def infer_market_from_symbol(symbol: str) -> ExchangeKind | None:
    try:
        canonical = normalize_a_share_symbol(symbol)
    except ValueError:
        return None
    if canonical.endswith(".SH"):
        return ExchangeKind.SSE
    if canonical.endswith(".SZ"):
        return ExchangeKind.SZSE
    return None


def to_a_share_daily_bar_start_utc(trading_day: datetime, market: ExchangeKind | None) -> datetime:
    if market in {ExchangeKind.SSE, ExchangeKind.SZSE}:
        return market_time_to_utc(
            datetime.combine(trading_day.date(), A_SHARE_D1_OPEN_TIME),
            market,
        )
    return market_time_to_utc(datetime.combine(trading_day.date(), time(0, 0)), market)


def normalize_utc_minute(value: datetime, *, field_name: str) -> datetime:
    normalized = market_time_to_utc(value, None)
    if normalized.second != 0 or normalized.microsecond != 0:
        raise ValueError(f"{field_name} 必须精确到分钟（seconds/microseconds 必须为 0）")
    return normalized

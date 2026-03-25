"""K 线查询辅助工具：估算 K 线条数（含交易时段感知）。"""
from __future__ import annotations

from datetime import date, datetime, time, timedelta

from agent_trader.domain.models import BarInterval, ExchangeKind

MAX_KLINE_BARS = 1000

_A_SHARE_MARKETS = {ExchangeKind.SSE, ExchangeKind.SZSE}
_INTERVAL_SECONDS: dict[BarInterval, int] = {
    BarInterval.M1: 60,
    BarInterval.M3: 3 * 60,
    BarInterval.M5: 5 * 60,
    BarInterval.M15: 15 * 60,
    BarInterval.M30: 30 * 60,
    BarInterval.H1: 60 * 60,
    BarInterval.H4: 4 * 60 * 60,
    BarInterval.D1: 24 * 60 * 60,
    BarInterval.W1: 7 * 24 * 60 * 60,
    BarInterval.MN1: 30 * 24 * 60 * 60,
}
_A_SHARE_SESSIONS = (
    (time(9, 30), time(11, 30)),
    (time(13, 0), time(15, 0)),
)
_INTRADAY_INTERVALS = {
    BarInterval.M1,
    BarInterval.M3,
    BarInterval.M5,
    BarInterval.M15,
    BarInterval.M30,
    BarInterval.H1,
    BarInterval.H4,
}


def estimate_kline_count(
    start_time: datetime,
    end_time: datetime,
    interval: BarInterval,
    market: ExchangeKind | None,
) -> int:
    """根据时间范围、周期和市场估算 K 线数量（含起止端点，跳过非交易时段）。

    对 A 股（SSE/SZSE）：
    - 分钟/小时周期仅统计两段交易时间（09:30-11:30、13:00-15:00），跳过周末。
    - D1 按工作日计数，W1/MN1 分别按交易周/交易月计数。

    其他市场按总时长简单估算。

    Raises:
        ValueError: end_time < start_time 或不支持的周期。
    """
    if end_time < start_time:
        raise ValueError("K线查询 end_time 不能早于 start_time")

    if market in _A_SHARE_MARKETS:
        if interval in _INTRADAY_INTERVALS:
            return _estimate_a_share_intraday_bars(start_time, end_time, interval)
        if interval == BarInterval.D1:
            return _count_business_days(start_time.date(), end_time.date())
        if interval == BarInterval.W1:
            return _count_business_weeks(start_time.date(), end_time.date())
        if interval == BarInterval.MN1:
            return _count_business_months(start_time.date(), end_time.date())

    step_seconds = _INTERVAL_SECONDS.get(interval)
    if step_seconds is None:
        raise ValueError(f"不支持的 K线周期: {interval.value}")

    return int((end_time - start_time).total_seconds() // step_seconds) + 1


def _estimate_a_share_intraday_bars(
    start_time: datetime,
    end_time: datetime,
    interval: BarInterval,
) -> int:
    step_seconds = _INTERVAL_SECONDS[interval]
    bar_count = 0
    day = start_time.date()
    while day <= end_time.date():
        if day.weekday() < 5:
            for session_start, session_end in _A_SHARE_SESSIONS:
                bar_count += _count_session_bars(
                    day=day,
                    query_start=start_time,
                    query_end=end_time,
                    session_start=session_start,
                    session_end=session_end,
                    step_seconds=step_seconds,
                )
        day += timedelta(days=1)
    return bar_count


def _count_session_bars(
    *,
    day: date,
    query_start: datetime,
    query_end: datetime,
    session_start: time,
    session_end: time,
    step_seconds: int,
) -> int:
    session_open = datetime.combine(day, session_start)
    session_close = datetime.combine(day, session_end)
    effective_start = max(session_open, query_start)
    effective_end = min(session_close, query_end)
    if effective_start > effective_end:
        return 0

    bars = 0
    cursor = session_open
    while cursor <= session_close:
        if effective_start <= cursor <= effective_end:
            bars += 1
        cursor += timedelta(seconds=step_seconds)
    return bars


def _count_business_days(start_day: date, end_day: date) -> int:
    count = 0
    day = start_day
    while day <= end_day:
        if day.weekday() < 5:
            count += 1
        day += timedelta(days=1)
    return count


def _count_business_weeks(start_day: date, end_day: date) -> int:
    weeks: set[tuple[int, int]] = set()
    day = start_day
    while day <= end_day:
        if day.weekday() < 5:
            iso_year, iso_week, _ = day.isocalendar()
            weeks.add((iso_year, iso_week))
        day += timedelta(days=1)
    return len(weeks)


def _count_business_months(start_day: date, end_day: date) -> int:
    months: set[tuple[int, int]] = set()
    day = start_day
    while day <= end_day:
        if day.weekday() < 5:
            months.add((day.year, day.month))
        day += timedelta(days=1)
    return len(months)

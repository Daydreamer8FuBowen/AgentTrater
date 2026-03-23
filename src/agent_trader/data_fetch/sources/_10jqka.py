"""10jqka (同花顺) 新闻数据源实现。

此模块复用了 `agent_trader.ingestion.sources.tushare_source` 中的核心思路，
通过 TuShare `news` 接口获取 10jqka 新闻并执行关键词/标的过滤与去重，
供 `NewsFetcher` 注册调用。
"""

from __future__ import annotations

import logging
import os
import re
from collections.abc import Iterable
from datetime import datetime
from typing import Any

import tushare as ts

logger = logging.getLogger(__name__)

_TS_TIME_FMT = "%Y%m%d %H:%M:%S"
_KEYWORD_SPLIT_RE = re.compile(r"[,，;；\s]+")
_NEWS_SOURCE = "10jqka"


def fetch_news(
    query: str = "",
    limit: int = 50,
    *,
    keywords: list[str] | None = None,
    symbol: str | None = None,
    start_time: datetime | None = None,
    end_time: datetime | None = None,
    token: str | None = None,
    http_url: str | None = None,
) -> list[dict[str, Any]]:
    """拉取 10jqka 新闻并返回原始 payload 列表。

    Args:
        query: 关键词字符串（空格/逗号分隔）。若 `keywords` 未提供，将据此拆分。
        limit: 返回的最大新闻条数。<=0 时直接返回空列表。
        keywords: 关键词列表（OR 过滤）。
        symbol: 股票代码过滤（模糊匹配 TuShare `channels` 字段）。
        start_time: 起始时间（TuShare 需要精确到秒）。
        end_time: 结束时间。
        token: 可选 TuShare token。缺省时读取 `TUSHARE_TOKEN` 环境变量。
        http_url: TuShare HTTP 代理地址；若省略则使用默认。

    Returns:
        按 ingest 链路所需格式的原始新闻字典列表。
    """

    if limit <= 0:
        return []

    resolved_token = _resolve_token(token)
    resolved_http_url = http_url or os.getenv("TUSHARE_HTTP_URL")
    client = _build_client(resolved_token, resolved_http_url)

    params: dict[str, Any] = {"src": _NEWS_SOURCE}
    if start_time is not None:
        params["start_date"] = start_time.strftime(_TS_TIME_FMT)
    if end_time is not None:
        params["end_date"] = end_time.strftime(_TS_TIME_FMT)

    logger.debug("fetch_news params=%s", params)

    df = client.news(**params)
    if df is None or getattr(df, "empty", True):
        return []

    raw_records = [row.to_dict() for _, row in df.iterrows()]
    words = _normalize_keywords(query=query, keywords=keywords)
    filtered = _filter_by_keywords(raw_records, words)
    filtered = _filter_by_symbol(filtered, symbol)
    deduped = _dedupe_records(filtered)
    return deduped[:limit]


def _resolve_token(token: str | None) -> str:
    resolved = token or os.getenv("TUSHARE_TOKEN")
    if not resolved:
        raise ValueError("TuShare token 未配置。请传入 token 或设置 TUSHARE_TOKEN 环境变量。")
    return resolved


def _build_client(token: str, http_url: str | None) -> Any:
    client = ts.pro_api(token)
    # TuShare 的 DataApi 需要显式设置 token/http_url，确保和 ingestion 链路一致。
    client._DataApi__token = token  # type: ignore[attr-defined]
    if http_url:
        client._DataApi__http_url = http_url  # type: ignore[attr-defined]
    return client


def _normalize_keywords(query: str, keywords: list[str] | None) -> list[str]:
    if keywords:
        return [kw.strip() for kw in keywords if kw and kw.strip()]
    if not query:
        return []
    return [part.strip() for part in _KEYWORD_SPLIT_RE.split(query) if part.strip()]


def _filter_by_keywords(
    records: Iterable[dict[str, Any]],
    keywords: list[str],
) -> list[dict[str, Any]]:
    if not keywords:
        return list(records)
    lowered = [kw.lower() for kw in keywords]
    filtered: list[dict[str, Any]] = []
    for record in records:
        haystack = f"{record.get('title', '')} {record.get('content', '')}".lower()
        if any(keyword in haystack for keyword in lowered):
            filtered.append(record)
    return filtered


def _filter_by_symbol(records: list[dict[str, Any]], symbol: str | None) -> list[dict[str, Any]]:
    if not symbol:
        return records
    return [record for record in records if symbol in str(record.get("channels", ""))]


def _dedupe_records(records: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[str, str]] = set()
    deduped: list[dict[str, Any]] = []
    for record in records:
        key = (str(record.get("datetime", "")), str(record.get("title", "")))
        if key in seen:
            continue
        seen.add(key)
        deduped.append(record)
    return deduped


__all__ = ["fetch_news"]

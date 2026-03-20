from __future__ import annotations

from datetime import datetime
from hashlib import sha256
import re
from typing import Any

from agent_trader.data_fetch.models import CleanedNewsItem

_STOCK_CODE_PATTERN = re.compile(r"\b(?:\d{6}\.(?:SZ|SH)|\d{5}\.HK|[A-Z]{2,5})\b")
_CODE_FIELDS = ("symbol", "symbols", "stock_code", "stock_codes", "ts_code", "ticker")
_TITLE_FIELDS = ("title", "headline", "name")
_CONTENT_FIELDS = ("content", "body", "text", "summary", "abstract", "desc", "description")
_URL_FIELDS = ("url", "link", "source_url", "article_url")
_TIME_FIELDS = ("published_at", "publish_time", "pub_time", "datetime", "time")

_INDUSTRY_KEYWORDS: dict[str, tuple[str, ...]] = {
    "bank": ("银行", "bank"),
    "brokerage": ("券商", "证券"),
    "insurance": ("保险",),
    "semiconductor": ("半导体", "芯片"),
    "ai": ("ai", "人工智能", "大模型"),
    "new_energy": ("新能源", "储能", "锂电"),
    "pharmaceutical": ("医药", "创新药", "biotech"),
}

_CONCEPT_KEYWORDS: dict[str, tuple[str, ...]] = {
    "robotics": ("机器人",),
    "aigc": ("aigc",),
    "chip": ("芯片", "算力", "半导体"),
    "ev": ("新能源车", "电动车", "ev"),
    "solar": ("光伏", "solar"),
    "gold": ("黄金", "gold"),
}

_SOURCE_CREDIBILITY: dict[str, float] = {
    "tushare": 0.9,
    "eastmoney": 0.8,
    "cls": 0.85,
    "wind": 0.9,
    "sina": 0.7,
}


def build_news_dedupe_key(*, source: str, title: str, url: str | None, published_at: datetime | None) -> str:
    if url:
        base = f"{source}|{url.strip()}"
    else:
        timestamp = published_at.isoformat() if published_at is not None else ""
        base = f"{source}|{title.strip()}|{timestamp}"
    return sha256(base.encode("utf-8")).hexdigest()


def parse_published_at(value: Any) -> datetime | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value
    text = str(value).strip()
    if not text:
        return None

    candidates = (
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%Y/%m/%d %H:%M:%S",
        "%Y/%m/%d %H:%M",
        "%Y-%m-%d",
        "%Y/%m/%d",
        "%Y%m%d%H%M%S",
        "%Y%m%d",
    )
    for pattern in candidates:
        try:
            return datetime.strptime(text, pattern)
        except ValueError:
            continue

    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None


def build_minimal_cleaned_news(*, source: str, payload: dict[str, Any]) -> CleanedNewsItem:
    title = _pick_first_text(payload, _TITLE_FIELDS) or f"{source} news"
    content = _pick_first_text(payload, _CONTENT_FIELDS)
    summary = content[:120] if content else title[:120]
    url = _pick_first_text(payload, _URL_FIELDS) or None
    published_at = _pick_datetime(payload)
    stock_tags = _extract_stock_tags(payload=payload, title=title, content=content)
    industry_tags = _extract_keyword_tags(title=title, content=content, keyword_map=_INDUSTRY_KEYWORDS)
    concept_tags = _extract_keyword_tags(title=title, content=content, keyword_map=_CONCEPT_KEYWORDS)
    market = _infer_market(payload=payload, title=title, content=content, source=source, stock_tags=stock_tags)
    credibility = _infer_credibility(source=source, url=url, content=content)
    tags = _merge_tags(industry_tags, concept_tags, stock_tags, [source, market])

    return CleanedNewsItem(
        title=title,
        content=content,
        summary=summary,
        source=source,
        published_at=published_at,
        url=url,
        market=market,
        industry_tags=industry_tags,
        concept_tags=concept_tags,
        stock_tags=stock_tags,
        tags=tags,
        credibility=credibility,
        raw_payload=dict(payload),
        dedupe_key=build_news_dedupe_key(source=source, title=title, url=url, published_at=published_at),
    )


def merge_cleaned_news(base: CleanedNewsItem, patch: dict[str, Any]) -> CleanedNewsItem:
    title = _non_empty_string(patch.get("title")) or base.title
    content = _non_empty_string(patch.get("content")) or base.content
    summary = _non_empty_string(patch.get("summary")) or base.summary
    url = _non_empty_string(patch.get("url")) or base.url
    published_at = parse_published_at(patch.get("published_at")) or base.published_at
    market = _non_empty_string(patch.get("market")) or base.market
    industry_tags = _normalize_tags(patch.get("industry_tags")) or base.industry_tags
    concept_tags = _normalize_tags(patch.get("concept_tags")) or base.concept_tags
    stock_tags = _normalize_tags(patch.get("stock_tags")) or base.stock_tags
    credibility = _coerce_credibility(patch.get("credibility"), base.credibility)
    tags = _merge_tags(industry_tags, concept_tags, stock_tags, _normalize_tags(patch.get("tags")) or base.tags)

    return CleanedNewsItem(
        title=title,
        content=content,
        summary=summary,
        source=base.source,
        published_at=published_at,
        url=url,
        market=market,
        industry_tags=industry_tags,
        concept_tags=concept_tags,
        stock_tags=stock_tags,
        tags=tags,
        credibility=credibility,
        raw_payload=base.raw_payload,
        dedupe_key=build_news_dedupe_key(source=base.source, title=title, url=url, published_at=published_at),
    )


def _pick_first_text(payload: dict[str, Any], fields: tuple[str, ...]) -> str:
    for field in fields:
        value = payload.get(field)
        if value is None:
            continue
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _pick_datetime(payload: dict[str, Any]) -> datetime | None:
    for field in _TIME_FIELDS:
        published_at = parse_published_at(payload.get(field))
        if published_at is not None:
            return published_at
    return None


def _extract_stock_tags(*, payload: dict[str, Any], title: str, content: str) -> list[str]:
    stock_tags: list[str] = []
    for field in _CODE_FIELDS:
        value = payload.get(field)
        stock_tags.extend(_normalize_tags(value))

    text = f"{title} {content}"
    stock_tags.extend(_STOCK_CODE_PATTERN.findall(text))
    return _normalize_tags(stock_tags)


def _extract_keyword_tags(*, title: str, content: str, keyword_map: dict[str, tuple[str, ...]]) -> list[str]:
    text = f"{title} {content}".lower()
    tags = [tag for tag, keywords in keyword_map.items() if any(keyword.lower() in text for keyword in keywords)]
    return _normalize_tags(tags)


def _infer_market(*, payload: dict[str, Any], title: str, content: str, source: str, stock_tags: list[str]) -> str:
    explicit_market = _non_empty_string(payload.get("market")) or _non_empty_string(payload.get("exchange"))
    if explicit_market:
        return explicit_market.lower()

    for stock_tag in stock_tags:
        normalized = stock_tag.upper()
        if normalized.endswith(".SZ") or normalized.endswith(".SH"):
            return "cn_a"
        if normalized.endswith(".HK"):
            return "hk"

    text = f"{title} {content} {source}".lower()
    if any(token in text for token in ("纳斯达克", "nasdaq", "nyse", "美股")):
        return "us"
    if any(token in text for token in ("港股", "hkex", ".hk")):
        return "hk"
    if any(token in text for token in ("比特币", "btc", "以太坊", "crypto")):
        return "crypto"
    return "cn_a"


def _infer_credibility(*, source: str, url: str | None, content: str) -> float:
    credibility = _SOURCE_CREDIBILITY.get(source.lower(), 0.6)
    if not url:
        credibility -= 0.05
    if len(content) < 20:
        credibility -= 0.1
    return round(min(1.0, max(0.0, credibility)), 2)


def _normalize_tags(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        values = re.split(r"[,，;；\s]+", value)
    elif isinstance(value, (list, tuple, set)):
        values = [str(item) for item in value if str(item).strip()]
    else:
        values = [str(value)]

    deduped: list[str] = []
    seen: set[str] = set()
    for item in values:
        normalized = item.strip()
        if not normalized:
            continue
        key = normalized.lower()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(normalized)
    return deduped


def _merge_tags(*groups: list[str]) -> list[str]:
    merged: list[str] = []
    for group in groups:
        merged.extend(group)
    return _normalize_tags(merged)


def _coerce_credibility(value: Any, default: float) -> float:
    if value is None:
        return default
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return default
    return round(min(1.0, max(0.0, numeric)), 2)


def _non_empty_string(value: Any) -> str:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return ""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4


@dataclass(slots=True)
class CleanedNewsItem:
    """清洗后的新闻数据模型。

    包含用于入库或进一步处理的标准化新闻字段（标题、正文、摘要、来源、发布时间、标签等）。
    """
    title: str
    content: str
    summary: str
    source: str
    published_at: datetime | None
    url: str | None
    market: str
    industry_tags: list[str] = field(default_factory=list)
    concept_tags: list[str] = field(default_factory=list)
    stock_tags: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    credibility: float = 0.5
    raw_payload: dict[str, Any] = field(default_factory=dict)
    dedupe_key: str = ""
    id: UUID = field(default_factory=uuid4)


@dataclass(slots=True)
class NewsIngestionResult:
    """新闻抓取/入库结果统计。

    包含清洗后的条目列表及各类统计计数（总抓取、插入、重复、失败）。
    """
    items: list[CleanedNewsItem]
    total_fetched: int
    inserted_count: int
    duplicate_count: int
    failed_count: int = 0

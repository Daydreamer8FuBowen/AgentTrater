from __future__ import annotations

from agent_trader.data_fetch import NewsFetcher
from agent_trader.data_fetch.models import CleanedNewsItem, NewsIngestionResult
from agent_trader.storage.base import UnitOfWork
from agent_trader.storage.mongo.documents import NewsDocument


class NewsIngestionService:
    """编排新闻抓取、清洗去重与显式落库。"""

    def __init__(self, news_fetcher: NewsFetcher, unit_of_work: UnitOfWork) -> None:
        self._news_fetcher = news_fetcher
        self._unit_of_work = unit_of_work

    async def ingest(self, *args, **kwargs) -> NewsIngestionResult:
        cleaned_items = self._news_fetcher.fetch_all(*args, **kwargs)
        inserted_count = 0
        duplicate_count = 0

        async with self._unit_of_work as uow:
            for item in cleaned_items:
                if await uow.news.exists_by_dedupe_key(item.dedupe_key):
                    duplicate_count += 1
                    continue
                await uow.news.add(self._to_document(item))
                inserted_count += 1

        return NewsIngestionResult(
            items=cleaned_items,
            total_fetched=len(cleaned_items),
            inserted_count=inserted_count,
            duplicate_count=duplicate_count,
        )

    @staticmethod
    def _to_document(item: CleanedNewsItem) -> NewsDocument:
        return NewsDocument(
            title=item.title,
            content=item.content,
            summary=item.summary,
            source=item.source,
            source_url=item.url,
            published_at=item.published_at,
            market=item.market,
            industry_tags=item.industry_tags,
            concept_tags=item.concept_tags,
            stock_tags=item.stock_tags,
            tags=item.tags,
            credibility=item.credibility,
            dedupe_key=item.dedupe_key,
            raw_payload=item.raw_payload,
        )

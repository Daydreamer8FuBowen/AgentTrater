"""Service entrypoints."""

from agent_trader.agents.news_preprocess_agent import NewsPreprocessAgent
from agent_trader.application.services.data_source_gateway import (
    DataAccessGateway,
    DataSourceRegistry,
    SourceSelectionAdapter,
)
from agent_trader.application.services.news_ingestion_service import NewsIngestionService

__all__ = [
    "DataAccessGateway",
    "DataSourceRegistry",
    "NewsIngestionService",
    "NewsPreprocessAgent",
    "SourceSelectionAdapter",
]
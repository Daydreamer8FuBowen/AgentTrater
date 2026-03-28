"""Source adapters."""

from agent_trader.ingestion.sources.baostock_source import BaoStockSource
from agent_trader.ingestion.sources.tushare_source import TuShareSource

__all__ = ["BaoStockSource", "TuShareSource"]

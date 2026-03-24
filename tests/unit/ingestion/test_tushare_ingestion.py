"""Tests for TuShare unified ingestion capabilities."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from agent_trader.domain.models import BarInterval
from agent_trader.ingestion.models import (
    BasicInfoFetchResult,
    DataCapability,
    FinancialReportFetchResult,
    FinancialReportQuery,
    KlineFetchResult,
    KlineQuery,
    NewsFetchResult,
    NewsQuery,
)
from agent_trader.ingestion.sources.tushare_source import TuShareSource


class TestTuShareSource:
    """TuShare data source adapter tests."""

    def test_init_with_token(self) -> None:
        with patch("tushare.pro_api") as mock_api:
            source = TuShareSource(token="test_token")
            assert source.token == "test_token"
            assert source.name == "tushare"
            mock_api.assert_called_once_with("test_token")

    def test_capabilities_include_three_domains(self) -> None:
        with patch("tushare.pro_api"):
            source = TuShareSource(token="test_token")
            declared = {spec.capability for spec in source.capabilities()}
            assert DataCapability.KLINE in declared
            assert DataCapability.NEWS in declared
            assert DataCapability.FINANCIAL_REPORT in declared

    @pytest.mark.asyncio
    async def test_fetch_klines_unified(self) -> None:
        with patch("tushare.pro_api"), patch("tushare.pro_bar") as mock_pro_bar:
            mock_row = MagicMock()
            mock_row.to_dict.return_value = {
                "ts_code": "000001.SZ",
                "trade_date": "20240115",
                "open": 100.0,
                "high": 105.0,
                "low": 98.0,
                "close": 103.0,
                "vol": 1000000,
                "amount": 103000000,
                "pct_chg": 3.2,
            }
            mock_df = MagicMock()
            mock_df.empty = False
            mock_df.iterrows.return_value = [(0, mock_row)]
            mock_pro_bar.return_value = mock_df

            source = TuShareSource(token="test_token")
            query = KlineQuery(
                symbol="000001.SZ",
                start_time=datetime(2024, 1, 1),
                end_time=datetime(2024, 1, 31),
                interval=BarInterval.D1,
            )
            result = await source.fetch_klines_unified(query)

            assert isinstance(result, KlineFetchResult)
            assert result.source == "tushare"
            assert result.data_kind == "kline"
            assert result.route_key.capability == DataCapability.KLINE
            assert len(result.payload) == 1
            assert result.payload[0].symbol == "000001.SZ"
            assert result.payload[0].interval == BarInterval.D1.value

    @pytest.mark.asyncio
    async def test_fetch_news_unified(self) -> None:
        with patch("tushare.pro_api") as mock_api:
            mock_row = MagicMock()
            mock_row.to_dict.return_value = {
                "datetime": "2024-01-15 10:00:00",
                "title": "Test News",
                "content": "Market moved higher.",
                "src": "sina",
                "channels": "000001.SZ",
                "url": "https://example.com/news/1",
            }
            mock_df = MagicMock()
            mock_df.empty = False
            mock_df.iterrows.return_value = [(0, mock_row)]

            api = MagicMock()
            api.news.return_value = mock_df
            mock_api.return_value = api

            source = TuShareSource(token="test_token")
            result = await source.fetch_news_unified(
                NewsQuery(
                    symbol="000001.SZ",
                    start_time=datetime(2024, 1, 1),
                    end_time=datetime(2024, 1, 31),
                    keywords=["market"],
                )
            )

            assert isinstance(result, NewsFetchResult)
            assert result.source == "tushare"
            assert result.data_kind == "news"
            assert result.route_key.capability == DataCapability.NEWS
            assert len(result.payload) == 1
            assert result.payload[0].title == "Test News"
            assert result.payload[0].symbols == ["000001.SZ"]

    @pytest.mark.asyncio
    async def test_fetch_basic_info(self) -> None:
        with patch("tushare.pro_api") as mock_api:
            mock_row = MagicMock()
            mock_row.to_dict.return_value = {
                "ts_code": "000001.SZ",
                "name": "平安银行",
                "industry": "银行",
                "area": "深圳",
                "market": "main",
                "list_date": "19910403",
                "list_status": "L",
            }
            mock_df = MagicMock()
            mock_df.empty = False
            mock_df.iterrows.return_value = [(0, mock_row)]

            api = MagicMock()
            api.stock_basic.return_value = mock_df
            mock_api.return_value = api

            source = TuShareSource(token="test_token")
            result = await source.fetch_basic_info()

            assert isinstance(result, BasicInfoFetchResult)
            assert result.source == "tushare"
            assert result.data_kind == "basic_info"
            assert result.route_key.capability == DataCapability.KLINE
            assert len(result.payload) == 1
            assert result.payload[0].symbol == "000001.SZ"

    @pytest.mark.asyncio
    async def test_fetch_financial_reports_unified(self) -> None:
        with patch("tushare.pro_api") as mock_api:
            mock_row = MagicMock()
            mock_row.to_dict.return_value = {
                "ts_code": "000001.SZ",
                "end_type": "fina_indicator",
                "end_date": "20231231",
                "ann_date": "20240330",
                "eps": "1.23",
                "dt_eps": "1.12",
                "total_revenue_ps": "5.67",
                "netprofit_margin": "12.0",
                "roe": "9.2",
                "roa": "1.1",
                "debt_to_assets": "65.0",
            }
            mock_df = MagicMock()
            mock_df.empty = False
            mock_df.iterrows.return_value = [(0, mock_row)]

            api = MagicMock()
            api.fina_indicator.return_value = mock_df
            mock_api.return_value = api

            source = TuShareSource(token="test_token")
            result = await source.fetch_financial_reports_unified(
                FinancialReportQuery(
                    symbol="000001.SZ",
                    start_time=datetime(2023, 1, 1),
                    end_time=datetime(2024, 1, 1),
                )
            )

            assert isinstance(result, FinancialReportFetchResult)
            assert result.source == "tushare"
            assert result.data_kind == "financial_report"
            assert result.route_key.capability == DataCapability.FINANCIAL_REPORT
            assert len(result.payload) == 1
            assert result.payload[0].symbol == "000001.SZ"
            assert result.payload[0].report_type == "fina_indicator"

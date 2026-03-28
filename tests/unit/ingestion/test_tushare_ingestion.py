"""Tests for TuShare unified ingestion capabilities."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from agent_trader.domain.models import BarInterval
from agent_trader.ingestion.models import (
    CompanyFinancialIndicatorFetchResult,
    CompanyIncomeStatementFetchResult,
    CompanyValuationFetchResult,
    DataCapability,
    KlineFetchResult,
    KlineQuery,
)
from agent_trader.ingestion.sources.tushare_source import TuShareSource


class TestTuShareSource:
    """TuShare data source adapter tests."""

    def test_init_with_token(self) -> None:
        with patch("tushare.set_token") as mock_set_token, patch("tushare.pro_api") as mock_api:
            source = TuShareSource(token="test_token")
            assert source.token == "test_token"
            assert source.name == "tushare"
            mock_set_token.assert_called_once_with("test_token")
            mock_api.assert_called_once_with()

    def test_init_with_api_url(self) -> None:
        with patch("tushare.set_token") as mock_set_token, patch("tushare.pro_api") as mock_api:
            mock_pro = MagicMock()
            mock_api.return_value = mock_pro
            source = TuShareSource(token="test_token", http_url="https://example.com")
            assert source.token == "test_token"
            assert source.http_url == "https://example.com"
            mock_set_token.assert_not_called()
            mock_api.assert_called_once_with("test_token")
            assert mock_pro._DataApi__token == "test_token"
            assert mock_pro._DataApi__http_url == "https://example.com"

    def test_capabilities_include_kline_domain(self) -> None:
        with patch("tushare.pro_api"):
            source = TuShareSource(token="test_token")
            declared = {spec.capability for spec in source.capabilities()}
            assert declared == {DataCapability.KLINE, DataCapability.COMPANY_DETAIL}

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
            assert result.payload[0].bar_time == datetime(2024, 1, 15, 1, 30, tzinfo=timezone.utc)

    @pytest.mark.asyncio
    async def test_fetch_company_detail_apis_unified(self) -> None:
        with patch("tushare.pro_api"):
            source = TuShareSource(token="test_token")
            source.pro.daily_basic = MagicMock()
            source.pro.fina_indicator = MagicMock()
            source.pro.income = MagicMock()

            daily_basic_row = MagicMock()
            daily_basic_row.to_dict.return_value = {
                "ts_code": "000001.SZ",
                "trade_date": "20250310",
                "pe": 12.3,
                "pe_ttm": 11.8,
                "pb": 1.4,
            }
            daily_basic_df = MagicMock()
            daily_basic_df.empty = False
            daily_basic_df.iterrows.return_value = [(0, daily_basic_row)]
            source.pro.daily_basic.return_value = daily_basic_df

            indicator_row_old = MagicMock()
            indicator_row_old.to_dict.return_value = {
                "end_date": "20231231",
                "grossprofit_margin": 20.1,
                "netprofit_margin": 9.8,
                "roe": 12.2,
                "debt_to_assets": 45.0,
            }
            indicator_row_new = MagicMock()
            indicator_row_new.to_dict.return_value = {
                "end_date": "20241231",
                "grossprofit_margin": 21.3,
                "netprofit_margin": 10.2,
                "roe": 13.1,
                "debt_to_assets": 44.2,
            }
            indicator_df = MagicMock()
            indicator_df.empty = False
            indicator_df.iterrows.return_value = [(0, indicator_row_new), (1, indicator_row_old)]
            source.pro.fina_indicator.return_value = indicator_df

            income_row_old = MagicMock()
            income_row_old.to_dict.return_value = {
                "end_date": "20231231",
                "report_type": "1",
                "total_revenue": 1000.0,
                "n_income": 200.0,
            }
            income_row_new = MagicMock()
            income_row_new.to_dict.return_value = {
                "end_date": "20241231",
                "report_type": "1",
                "total_revenue": 1200.0,
                "n_income": 260.0,
            }
            income_df = MagicMock()
            income_df.empty = False
            income_df.iterrows.return_value = [(0, income_row_new), (1, income_row_old)]
            source.pro.income.return_value = income_df

            valuation_result = await source.fetch_company_valuation_unified(symbol="000001.SZ")
            indicator_result = await source.fetch_company_financial_indicators_unified(
                symbol="000001.SZ"
            )
            income_result = await source.fetch_company_income_statements_unified(symbol="000001.SZ")

            assert isinstance(valuation_result, CompanyValuationFetchResult)
            assert valuation_result.source == "tushare"
            assert valuation_result.route_key.capability == DataCapability.COMPANY_DETAIL
            assert valuation_result.metadata["count"] == 1
            assert len(valuation_result.payload) == 1
            assert valuation_result.payload[0].pe_ttm == 11.8

            assert isinstance(indicator_result, CompanyFinancialIndicatorFetchResult)
            assert indicator_result.route_key.capability == DataCapability.COMPANY_DETAIL
            assert [item.report_date for item in indicator_result.payload] == sorted(
                [item.report_date for item in indicator_result.payload]
            )

            assert isinstance(income_result, CompanyIncomeStatementFetchResult)
            assert income_result.route_key.capability == DataCapability.COMPANY_DETAIL
            assert [item.report_date for item in income_result.payload] == sorted(
                [item.report_date for item in income_result.payload]
            )

            fina_kwargs = source.pro.fina_indicator.call_args.kwargs
            income_kwargs = source.pro.income.call_args.kwargs
            assert isinstance(fina_kwargs["start_date"], str)
            assert isinstance(fina_kwargs["end_date"], str)
            assert fina_kwargs["start_date"] <= fina_kwargs["end_date"]
            assert income_kwargs["start_date"] == fina_kwargs["start_date"]
            assert income_kwargs["end_date"] == fina_kwargs["end_date"]

    @pytest.mark.live
    @pytest.mark.asyncio
    async def test_fetch_company_detail_apis_live(self) -> None:
        token = os.getenv("TUSHARE_TOKEN", "").strip()
        if not token:
            pytest.skip("未配置 TUSHARE_TOKEN，跳过实时测试")

        source = TuShareSource(token=token)
        symbol = "000001.SZ"

        valuation_result = await source.fetch_company_valuation_unified(symbol=symbol)
        indicator_result = await source.fetch_company_financial_indicators_unified(symbol=symbol)
        income_result = await source.fetch_company_income_statements_unified(symbol=symbol)

        assert valuation_result.source == "tushare"
        assert indicator_result.source == "tushare"
        assert income_result.source == "tushare"
        assert valuation_result.route_key.capability == DataCapability.COMPANY_DETAIL
        assert indicator_result.route_key.capability == DataCapability.COMPANY_DETAIL
        assert income_result.route_key.capability == DataCapability.COMPANY_DETAIL
        assert valuation_result.metadata["symbol"] == symbol
        assert indicator_result.metadata["symbol"] == symbol
        assert income_result.metadata["symbol"] == symbol
        assert valuation_result.metadata["count"] == len(valuation_result.payload)
        assert indicator_result.metadata["count"] == len(indicator_result.payload)
        assert income_result.metadata["count"] == len(income_result.payload)
        assert indicator_result.metadata["start_date"] <= indicator_result.metadata["end_date"]
        assert income_result.metadata["start_date"] <= income_result.metadata["end_date"]
        assert [item.report_date for item in indicator_result.payload] == sorted(
            [item.report_date for item in indicator_result.payload]
        )
        assert [item.report_date for item in income_result.payload] == sorted(
            [item.report_date for item in income_result.payload]
        )

    @pytest.mark.live
    @pytest.mark.asyncio
    async def test_fetch_company_detail_apis_live_with_http_url(self) -> None:
        token = os.getenv("TUSHARE_TOKEN", "").strip()
        http_url = os.getenv("TUSHARE_API_URL", "").strip()
        if not token:
            pytest.skip("未配置 TUSHARE_TOKEN，跳过实时测试")
        if not http_url:
            pytest.skip("未配置 TUSHARE_API_URL，跳过 HTTP 实时测试")

        source = TuShareSource(token=token, http_url=http_url)
        symbol = "000001.SZ"

        valuation_result = await source.fetch_company_valuation_unified(symbol=symbol)
        indicator_result = await source.fetch_company_financial_indicators_unified(symbol=symbol)
        income_result = await source.fetch_company_income_statements_unified(symbol=symbol)

        assert source.http_url == http_url
        assert source.pro._DataApi__http_url == http_url
        assert valuation_result.route_key.capability == DataCapability.COMPANY_DETAIL
        assert indicator_result.route_key.capability == DataCapability.COMPANY_DETAIL
        assert income_result.route_key.capability == DataCapability.COMPANY_DETAIL
        assert valuation_result.metadata["symbol"] == symbol
        assert indicator_result.metadata["symbol"] == symbol
        assert income_result.metadata["symbol"] == symbol
        assert valuation_result.metadata["count"] == len(valuation_result.payload)
        assert indicator_result.metadata["count"] == len(indicator_result.payload)
        assert income_result.metadata["count"] == len(income_result.payload)

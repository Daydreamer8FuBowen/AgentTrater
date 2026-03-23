"""Tests for BaoStock ingestion components."""
from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from agent_trader.domain.models import BarInterval
from agent_trader.ingestion.models import FinancialReportQuery, KlineQuery, SourceFetchResult
from agent_trader.ingestion.sources.baostock_source import BaoStockSource


class _FakeResultSet:
    def __init__(self, fields: list[str], rows: list[list[str]], *, error_code: str = "0", error_msg: str = "ok") -> None:
        self.fields = fields
        self._rows = rows
        self._index = -1
        self.error_code = error_code
        self.error_msg = error_msg

    def next(self) -> bool:
        self._index += 1
        return self._index < len(self._rows)

    def get_row_data(self) -> list[str]:
        return self._rows[self._index]


class TestBaoStockSource:
    def test_init_with_defaults(self) -> None:
        source = BaoStockSource()
        assert source.user_id == "anonymous"
        assert source.password == "123456"
        assert source.options == 0
        assert source.name == "baostock"

    @pytest.mark.asyncio
    async def test_fetch_klines_unified(self) -> None:
        login_result = SimpleNamespace(error_code="0", error_msg="success")
        result = _FakeResultSet(
            fields=["date", "code", "open", "high", "low", "close", "volume", "amount", "adjustflag"],
            rows=[["2024-01-15", "sz.000001", "10.1", "10.8", "9.9", "10.5", "1000000", "10500000", "2"]],
        )

        with patch("baostock.login", return_value=login_result), patch(
            "baostock.query_history_k_data_plus",
            return_value=result,
        ) as mock_query, patch("baostock.logout") as mock_logout:
            source = BaoStockSource()
            query = KlineQuery(
                symbol="000001.SZ",
                start_time=datetime(2024, 1, 1),
                end_time=datetime(2024, 1, 31),
                interval=BarInterval.D1,
            )

            fetch_result = await source.fetch_klines_unified(query)

        assert isinstance(fetch_result, SourceFetchResult)
        assert fetch_result.source == "baostock"
        assert len(fetch_result.payload) == 1
        assert fetch_result.payload[0]["symbol"] == "000001.SZ"
        assert fetch_result.payload[0]["close"] == 10.5
        mock_query.assert_called_once()
        mock_logout.assert_called_once_with("anonymous")

    @pytest.mark.asyncio
    async def test_fetch_klines_unified_rejects_unsupported_interval(self) -> None:
        source = BaoStockSource()
        query = KlineQuery(
            symbol="000001.SZ",
            start_time=datetime(2024, 1, 1),
            end_time=datetime(2024, 1, 31),
            interval=BarInterval.M1,
        )

        with pytest.raises(ValueError, match="BaoStock 不支持"):
            await source.fetch_klines_unified(query)

    @pytest.mark.asyncio
    async def test_fetch_basic_info(self) -> None:
        login_result = SimpleNamespace(error_code="0", error_msg="success")
        result = _FakeResultSet(
            fields=["code", "code_name", "ipoDate", "outDate", "type", "status"],
            rows=[["sh.600000", "浦发银行", "1999-11-10", "", "1", "1"]],
        )

        with patch("baostock.login", return_value=login_result), patch(
            "baostock.query_stock_basic",
            return_value=result,
        ), patch("baostock.logout"):
            source = BaoStockSource()
            events = await source.fetch_basic_info()

        assert len(events) == 1
        assert events[0].source == "baostock:stock_basic"
        assert events[0].payload["symbol"] == "600000.SH"

    @pytest.mark.asyncio
    async def test_fetch_financial_reports_unified(self) -> None:
        login_result = SimpleNamespace(error_code="0", error_msg="success")
        def build_quarterly_result() -> _FakeResultSet:
            return _FakeResultSet(
                fields=["code", "pubDate", "statDate", "roeAvg"],
                rows=[["sz.000001", "2024-04-30", "2024-03-31", "12.5"]],
            )

        date_range_result = _FakeResultSet(
            fields=["code", "performanceExpStatDate", "performanceExpPubDate", "netProfit"],
            rows=[["sz.000001", "2024-03-31", "2024-04-15", "1000000000"]],
        )

        with patch("baostock.login", return_value=login_result), patch(
            "baostock.query_profit_data",
            side_effect=[build_quarterly_result(), build_quarterly_result()],
        ) as mock_profit, patch(
            "baostock.query_forecast_report",
            return_value=date_range_result,
        ) as mock_forecast, patch("baostock.logout"):
            source = BaoStockSource()
            query = FinancialReportQuery(
                symbol="000001.SZ",
                start_time=datetime(2024, 1, 1),
                end_time=datetime(2024, 6, 30),
                extra={"report_types": ["profit", "forecast"]},
            )

            fetch_result = await source.fetch_financial_reports_unified(query)

        assert isinstance(fetch_result, SourceFetchResult)
        assert fetch_result.source == "baostock"
        assert len(fetch_result.payload) == 3
        assert {item["_report_type"] for item in fetch_result.payload} == {"profit", "forecast"}
        assert mock_profit.call_count == 2
        mock_forecast.assert_called_once()

    @pytest.mark.asyncio
    async def test_fetch_financial_reports_unified_rejects_invalid_report_type(self) -> None:
        source = BaoStockSource()
        query = FinancialReportQuery(
            symbol="000001.SZ",
            start_time=datetime(2024, 1, 1),
            end_time=datetime(2024, 3, 31),
            extra={"report_types": ["unknown"]},
        )

        with pytest.raises(ValueError, match="BaoStock 不支持的财报类型"):
            await source.fetch_financial_reports_unified(query)
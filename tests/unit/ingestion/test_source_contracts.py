from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from agent_trader.domain.models import BarInterval, ExchangeKind
from agent_trader.ingestion.models import (
    BasicInfoFetchResult,
    DataCapability,
    KlineFetchResult,
    KlineQuery,
)
from agent_trader.ingestion.sources.baostock_source import BaoStockSource
from agent_trader.ingestion.sources.tushare_source import TuShareSource


class _FakeResultSet:
    def __init__(
        self,
        fields: list[str],
        rows: list[list[str]],
        *,
        error_code: str = "0",
        error_msg: str = "ok",
    ) -> None:
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


_KLINE_REQUIRED_KEYS = {
    "symbol",
    "bar_time",
    "interval",
    "open",
    "high",
    "low",
    "close",
    "volume",
    "amount",
    "change_pct",
    "turnover_rate",
    "adjusted",
}
_KLINE_ALLOWED_KEYS = _KLINE_REQUIRED_KEYS | {"is_trading"}

_BASIC_INFO_REQUIRED_KEYS = {
    "symbol",
    "name",
    "industry",
    "area",
    "market",
    "list_date",
    "status",
}
_BASIC_INFO_ALLOWED_KEYS = _BASIC_INFO_REQUIRED_KEYS | {
    "delist_date",
    "security_type",
    "act_ent_type",
    "pe_ttm",
    "pe",
    "pb",
    "grossprofit_margin",
    "netprofit_margin",
    "roe",
    "debt_to_assets",
    "revenue",
    "net_profit",
}


def _assert_kline_contract(result: KlineFetchResult) -> None:
    assert result.data_kind == "kline"
    assert result.schema_version == "v1"
    assert result.route_key.capability == DataCapability.KLINE
    assert result.metadata["count"] == len(result.payload)
    assert result.payload

    record = result.payload[0]
    record_dict = asdict(record)
    assert _KLINE_REQUIRED_KEYS.issubset(record_dict)
    assert set(record_dict).issubset(_KLINE_ALLOWED_KEYS)
    assert isinstance(record.symbol, str)
    assert isinstance(record.bar_time, datetime)
    assert isinstance(record.interval, str)
    assert isinstance(record.adjusted, bool)


def _assert_basic_info_contract(result: BasicInfoFetchResult) -> None:
    assert result.data_kind == "basic_info"
    assert result.schema_version == "v1"
    assert result.route_key.capability == DataCapability.KLINE
    assert result.metadata["count"] == len(result.payload)
    assert result.payload

    record = result.payload[0]
    record_dict = asdict(record)
    assert _BASIC_INFO_REQUIRED_KEYS.issubset(record_dict)
    assert set(record_dict).issubset(_BASIC_INFO_ALLOWED_KEYS)
    assert isinstance(record.symbol, str)
    assert record.list_date is None or isinstance(record.list_date, datetime)


@pytest.mark.asyncio
async def test_kline_contract_matches_between_tushare_and_baostock() -> None:
    with patch("tushare.pro_api") as mock_api, patch("tushare.pro_bar") as mock_pro_bar:
        tushare_row = MagicMock()
        tushare_row.to_dict.return_value = {
            "ts_code": "000001.SZ",
            "trade_date": "20240115",
            "open": 100.0,
            "high": 105.0,
            "low": 98.0,
            "close": 103.0,
            "vol": 1000000,
            "amount": 103000000,
            "pct_chg": 3.2,
            "turnover_rate": 1.8,
        }
        tushare_df = MagicMock()
        tushare_df.empty = False
        tushare_df.iterrows.return_value = [(0, tushare_row)]
        mock_pro_bar.return_value = tushare_df
        mock_api.return_value = MagicMock()

        tushare_source = TuShareSource(token="test_token")
        tushare_result = await tushare_source.fetch_klines_unified(
            KlineQuery(
                symbol="000001.SZ",
                start_time=datetime(2024, 1, 1),
                end_time=datetime(2024, 1, 31),
                interval=BarInterval.D1,
                market=ExchangeKind.SZSE,
                adjusted=True,
            )
        )

    login_result = SimpleNamespace(error_code="0", error_msg="success")
    baostock_result = _FakeResultSet(
        fields=[
            "date",
            "code",
            "open",
            "high",
            "low",
            "close",
            "volume",
            "amount",
            "adjustflag",
            "pctChg",
            "turn",
            "tradestatus",
        ],
        rows=[
            [
                "2024-01-15",
                "sz.000001",
                "100",
                "105",
                "98",
                "103",
                "1000000",
                "103000000",
                "2",
                "3.2",
                "1.8",
                "1",
            ]
        ],
    )
    with (
        patch("baostock.login", return_value=login_result),
        patch(
            "baostock.query_history_k_data_plus",
            return_value=baostock_result,
        ),
        patch("baostock.logout"),
    ):
        baostock_source = BaoStockSource()
        baostock_fetch_result = await baostock_source.fetch_klines_unified(
            KlineQuery(
                symbol="000001.SZ",
                start_time=datetime(2024, 1, 1),
                end_time=datetime(2024, 1, 31),
                interval=BarInterval.D1,
                market=ExchangeKind.SZSE,
                adjusted=True,
            )
        )

    _assert_kline_contract(tushare_result)
    _assert_kline_contract(baostock_fetch_result)
    assert set(asdict(tushare_result.payload[0])) == _KLINE_ALLOWED_KEYS
    assert _KLINE_REQUIRED_KEYS.issubset(set(asdict(baostock_fetch_result.payload[0])))


@pytest.mark.asyncio
async def test_kline_payload_is_sorted_by_bar_time_ascending() -> None:
    with patch("tushare.pro_api") as mock_api, patch("tushare.pro_bar") as mock_pro_bar:
        tushare_row_latest = MagicMock()
        tushare_row_latest.to_dict.return_value = {
            "ts_code": "000001.SZ",
            "trade_date": "20240115",
            "open": 100.0,
            "high": 105.0,
            "low": 98.0,
            "close": 103.0,
            "vol": 1000000,
            "amount": 103000000,
            "pct_chg": 3.2,
            "turnover_rate": 1.8,
        }
        tushare_row_earlier = MagicMock()
        tushare_row_earlier.to_dict.return_value = {
            "ts_code": "000001.SZ",
            "trade_date": "20240114",
            "open": 99.0,
            "high": 104.0,
            "low": 97.0,
            "close": 102.0,
            "vol": 900000,
            "amount": 102000000,
            "pct_chg": 2.1,
            "turnover_rate": 1.6,
        }
        tushare_df = MagicMock()
        tushare_df.empty = False
        tushare_df.iterrows.return_value = [(0, tushare_row_latest), (1, tushare_row_earlier)]
        mock_pro_bar.return_value = tushare_df
        mock_api.return_value = MagicMock()

        tushare_source = TuShareSource(token="test_token")
        tushare_result = await tushare_source.fetch_klines_unified(
            KlineQuery(
                symbol="000001.SZ",
                start_time=datetime(2024, 1, 1),
                end_time=datetime(2024, 1, 31),
                interval=BarInterval.D1,
                market=ExchangeKind.SZSE,
                adjusted=True,
            )
        )

    login_result = SimpleNamespace(error_code="0", error_msg="success")
    baostock_result = _FakeResultSet(
        fields=[
            "date",
            "code",
            "open",
            "high",
            "low",
            "close",
            "volume",
            "amount",
            "adjustflag",
            "pctChg",
            "turn",
            "tradestatus",
        ],
        rows=[
            [
                "2024-01-15",
                "sz.000001",
                "100",
                "105",
                "98",
                "103",
                "1000000",
                "103000000",
                "2",
                "3.2",
                "1.8",
                "1",
            ],
            [
                "2024-01-14",
                "sz.000001",
                "99",
                "104",
                "97",
                "102",
                "900000",
                "102000000",
                "2",
                "2.1",
                "1.6",
                "1",
            ],
        ],
    )
    with (
        patch("baostock.login", return_value=login_result),
        patch("baostock.query_history_k_data_plus", return_value=baostock_result),
        patch("baostock.logout"),
    ):
        baostock_source = BaoStockSource()
        baostock_fetch_result = await baostock_source.fetch_klines_unified(
            KlineQuery(
                symbol="000001.SZ",
                start_time=datetime(2024, 1, 1),
                end_time=datetime(2024, 1, 31),
                interval=BarInterval.D1,
                market=ExchangeKind.SZSE,
                adjusted=True,
            )
        )

    assert [item.bar_time for item in tushare_result.payload] == sorted(
        [item.bar_time for item in tushare_result.payload]
    )
    assert [item.bar_time for item in baostock_fetch_result.payload] == sorted(
        [item.bar_time for item in baostock_fetch_result.payload]
    )


@pytest.mark.asyncio
async def test_basic_info_contract_matches_between_tushare_and_baostock() -> None:
    with patch("tushare.pro_api") as mock_api:
        tushare_row = MagicMock()
        tushare_row.to_dict.return_value = {
            "ts_code": "000001.SZ",
            "name": "平安银行",
            "industry": "银行",
            "area": "深圳",
            "market": "main",
            "list_date": "19910403",
            "list_status": "L",
        }
        tushare_df = MagicMock()
        tushare_df.empty = False
        tushare_df.iterrows.return_value = [(0, tushare_row)]

        tushare_api = MagicMock()
        tushare_api.stock_basic.return_value = tushare_df
        mock_api.return_value = tushare_api

        tushare_source = TuShareSource(token="test_token")
        tushare_result = await tushare_source.fetch_basic_info(market=ExchangeKind.SZSE)

    login_result = SimpleNamespace(error_code="0", error_msg="success")
    baostock_result = _FakeResultSet(
        fields=["code", "code_name", "ipoDate", "outDate", "type", "status"],
        rows=[["sz.000001", "平安银行", "1991-04-03", "", "1", "1"]],
    )
    with (
        patch("baostock.login", return_value=login_result),
        patch(
            "baostock.query_stock_basic",
            return_value=baostock_result,
        ),
        patch("baostock.logout"),
    ):
        baostock_source = BaoStockSource()
        baostock_fetch_result = await baostock_source.fetch_basic_info(market=ExchangeKind.SZSE)

    _assert_basic_info_contract(tushare_result)
    _assert_basic_info_contract(baostock_fetch_result)
    assert set(asdict(tushare_result.payload[0])).issubset(
        set(asdict(baostock_fetch_result.payload[0]))
    )
    assert set(asdict(tushare_result.payload[0])) == _BASIC_INFO_ALLOWED_KEYS
    assert _BASIC_INFO_REQUIRED_KEYS.issubset(set(asdict(baostock_fetch_result.payload[0])))


def test_kline_sources_must_bind_basic_info_capability() -> None:
    """协议约束：提供 K 线统一接口的 source 必须同时提供 fetch_basic_info。"""
    for source in (BaoStockSource(), TuShareSource(token="test_token")):
        assert callable(getattr(source, "fetch_klines_unified", None))
        assert callable(getattr(source, "fetch_basic_info", None))


def test_kline_sources_do_not_declare_separate_basic_info_capability() -> None:
    """能力声明约束：basic_info 绑定在 KLINE 内，不单独声明独立 capability。"""
    for source in (BaoStockSource(), TuShareSource(token="test_token")):
        declared = {spec.capability for spec in source.capabilities()}
        assert DataCapability.KLINE in declared

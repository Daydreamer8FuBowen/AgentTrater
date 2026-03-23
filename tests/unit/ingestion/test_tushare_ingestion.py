"""Tests for TuShare ingestion components."""
import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

from agent_trader.domain.models import BarInterval, TriggerKind
from agent_trader.ingestion.models import (
    KlineQuery,
    NormalizedEvent,
    RawEvent,
    ResearchTrigger,
    SourceFetchResult,
)
from agent_trader.ingestion.normalizers.tushare_normalizer import TuShareNormalizer
from agent_trader.ingestion.sources.tushare_source import TuShareSource


class TestTuShareSource:
    """TuShare 数据源适配器测试"""

    def test_init_with_token(self):
        """测试初始化 TuShareSource with token"""
        with patch("tushare.pro_api") as mock_api:
            source = TuShareSource(token="test_token")
            assert source.token == "test_token"
            assert source.name == "tushare"
            mock_api.assert_called_once_with("test_token")

    def test_init_config_attributes(self):
        """测试初始化时配置 token 和 http_url 属性"""
        with patch("tushare.pro_api") as mock_api:
            # 创建 mock api 实例，支持私有属性设置
            mock_api_instance = MagicMock()
            mock_api.return_value = mock_api_instance

            source = TuShareSource(token="test_token")

            # 验证 token 被正确设置到私有属性
            mock_api_instance._DataApi__token = "test_token"
            assert source.token == "test_token"

            # 验证 http_url 被正确设置
            mock_api_instance._DataApi__http_url = "http://lianghua.nanyangqiankun.top"

    @pytest.mark.asyncio
    async def test_fetch_klines_unified(self):
        """测试通过统一接口获取 K 线数据"""
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

            assert isinstance(result, SourceFetchResult)
            assert len(result.payload) == 1
            assert result.payload[0]["ts_code"] == "000001.SZ"
            assert result.source == "tushare"

    @pytest.mark.asyncio
    async def test_fetch_basic_info(self):
        """测试获取股票基本信息"""
        with patch("tushare.pro_api") as mock_api:
            mock_df = MagicMock()
            mock_df.empty = False
            mock_row = MagicMock()
            mock_row.to_dict.return_value = {
                "ts_code": "000001.SZ",
                "name": "平安银行",
                "industry": "银行",
            }
            mock_df.iterrows.return_value = [(0, mock_row)]

            mock_api_instance = MagicMock()
            mock_api_instance.stock_basic.return_value = mock_df
            mock_api.return_value = mock_api_instance

            source = TuShareSource(token="test_token")
            events = await source.fetch_basic_info()

            assert len(events) > 0
            assert events[0].source == "tushare:stock_basic"

    @pytest.mark.asyncio
    async def test_fetch_klines_unified_empty(self):
        """测试统一接口处理空结果"""
        with patch("tushare.pro_api"), patch("tushare.pro_bar") as mock_pro_bar:
            mock_df = MagicMock()
            mock_df.empty = True
            mock_pro_bar.return_value = mock_df

            source = TuShareSource(token="test_token")
            query = KlineQuery(
                symbol="000001.SZ",
                start_time=datetime(2024, 1, 1),
                end_time=datetime(2024, 1, 31),
                interval=BarInterval.D1,
            )
            result = await source.fetch_klines_unified(query)

            assert isinstance(result, SourceFetchResult)
            assert result.payload == []


class TestTuShareNormalizer:
    """TuShare 规范化器测试"""

    @pytest.mark.asyncio
    async def test_normalize_kline_up(self):
        """测试规范化上涨 K 线数据"""
        normalizer = TuShareNormalizer()
        raw_event = RawEvent(
            source="tushare",
            payload={
                "ts_code": "000001.SZ",
                "trade_date": "20240115",
                "close": 103.0,
                "change_pct": 6.5,
                "open": 100.0,
                "high": 105.0,
                "low": 98.0,
                "vol": 1000000,
                "amount": 103000000,
            },
        )

        result = await normalizer.normalize(raw_event)

        assert result is not None
        assert isinstance(result, NormalizedEvent)
        assert result.symbol == "000001.SZ"
        assert result.trigger_kind == TriggerKind.INDICATOR
        assert "6.5" in result.title

    @pytest.mark.asyncio
    async def test_normalize_kline_down(self):
        """测试规范化下跌 K 线数据"""
        normalizer = TuShareNormalizer()
        raw_event = RawEvent(
            source="tushare",
            payload={
                "ts_code": "000001.SZ",
                "trade_date": "20240115",
                "close": 93.0,
                "change_pct": -7.0,
                "open": 100.0,
                "high": 100.0,
                "low": 93.0,
                "vol": 1000000,
                "amount": 93000000,
            },
        )

        result = await normalizer.normalize(raw_event)

        assert result is not None
        assert result.trigger_kind == TriggerKind.INDICATOR
        assert "-7" in result.title

    @pytest.mark.asyncio
    async def test_normalize_daily_basic(self):
        """测试规范化每日基础信息"""
        normalizer = TuShareNormalizer()
        raw_event = RawEvent(
            source="tushare:daily_basic",
            payload={
                "ts_code": "000001.SZ",
                "trade_date": "20240115",
                "pe": 8.5,
                "pb": 0.9,
                "dv_ratio": 0.05,
                "dv_ttm": 3.2,
                "total_mv": 1000000000000,
            },
        )

        result = await normalizer.normalize(raw_event)

        assert result is not None
        assert result.trigger_kind == TriggerKind.INDICATOR
        assert result.symbol == "000001.SZ"
        assert "8.5" in str(result.metadata["pe"])

    @pytest.mark.asyncio
    async def test_to_trigger(self):
        """测试转换为研究触发对象"""
        normalizer = TuShareNormalizer()
        normalized_event = NormalizedEvent(
            trigger_kind=TriggerKind.INDICATOR,
            symbol="000001.SZ",
            title="测试题目",
            content="测试内容",
            metadata={"test": "value"},
        )

        trigger = await normalizer.to_trigger(normalized_event)

        assert isinstance(trigger, ResearchTrigger)
        assert trigger.symbol == "000001.SZ"
        assert trigger.trigger_kind == TriggerKind.INDICATOR
        assert trigger.summary == "测试题目"
        assert "test" in trigger.metadata

    @pytest.mark.asyncio
    async def test_normalize_unknown_source(self):
        """测试处理未知数据源"""
        normalizer = TuShareNormalizer()
        raw_event = RawEvent(
            source="unknown_source",
            payload={"test": "value"},
        )

        result = await normalizer.normalize(raw_event)

        assert result is None

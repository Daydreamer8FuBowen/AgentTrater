"""
TuShare 实时集成测试

这个文件包含使用真实 TuShare token 的集成测试。
这些测试会实际连接到 TuShare API，因此：
1. 需要有效的 token
2. 可能受 API 调用限制
3. 默认被跳过，需要设置环境变量 TUSHARE_INTEGRATION_TEST=1 启用

使用方式：
    TUSHARE_INTEGRATION_TEST=1 TUSHARE_TOKEN=<token> uv run pytest tests/test_tushare_integration_live.py -v
"""
import asyncio
import os
import pytest

from agent_trader.ingestion.normalizers.tushare_normalizer import TuShareNormalizer
from agent_trader.ingestion.sources.tushare_source import TuShareSource


# 只有当环境变量设置时才运行这些测试
INTEGRATION_ENABLED = os.getenv("TUSHARE_INTEGRATION_TEST", "").lower() == "1"
TUSHARE_TOKEN = os.getenv("TUSHARE_TOKEN", "")

pytestmark = pytest.mark.skipif(
    not INTEGRATION_ENABLED or not TUSHARE_TOKEN,
    reason="需要设置 TUSHARE_INTEGRATION_TEST=1 和 TUSHARE_TOKEN 环境变量"
)


class TestTuShareLiveIntegration:
    """使用真实 token 的实时测试"""

    async def test_real_fetch_klines(self):
        """测试使用真实 token 获取 K 线数据"""
        source = TuShareSource(token=TUSHARE_TOKEN)
        normalizer = TuShareNormalizer()

        # 获取平安银行最近一周的日线数据
        from datetime import datetime, timedelta

        end_date = datetime.now()
        start_date = end_date - timedelta(days=7)

        events = await source.fetch_klines(
            symbol="000001.SZ",
            start_date=start_date.strftime("%Y%m%d"),
            end_date=end_date.strftime("%Y%m%d"),
            freq="D",
        )

        # 验证返回结果
        assert isinstance(events, list)
        print(f"✓ 成功获取 {len(events)} 条 K 线数据")

        # 规范化数据
        if events:
            normalized = await normalizer.normalize(events[0])
            assert normalized is not None
            trigger = await normalizer.to_trigger(normalized)
            print(f"✓ 规范化成功: {trigger.symbol} - {trigger.trigger_kind}")

    async def test_real_fetch_basic_info(self):
        """测试使用真实 token 获取股票基本信息"""
        source = TuShareSource(token=TUSHARE_TOKEN)
        normalizer = TuShareNormalizer()

        events = await source.fetch_basic_info()

        assert isinstance(events, list)
        print(f"✓ 成功获取 {len(events)} 条股票基本信息")

        if events:
            normalized = await normalizer.normalize(events[0])
            assert normalized is not None
            trigger = await normalizer.to_trigger(normalized)
            print(f"✓ 规范化成功: {trigger.symbol}")

    async def test_real_fetch_daily_basic(self):
        """测试使用真实 token 获取每日基础信息"""
        source = TuShareSource(token=TUSHARE_TOKEN)
        normalizer = TuShareNormalizer()

        events = await source.fetch_daily_basic()

        assert isinstance(events, list)
        print(f"✓ 成功获取 {len(events)} 条每日基础信息")

        if events:
            normalized = await normalizer.normalize(events[0])
            assert normalized is not None
            trigger = await normalizer.to_trigger(normalized)
            print(f"✓ 规范化成功: {trigger.symbol} - PE: {trigger.metadata.get('pe', 'N/A')}")

    async def test_real_complete_flow(self):
        """测试完整的数据流：获取 → 规范化 → 转换"""
        source = TuShareSource(token=TUSHARE_TOKEN)
        normalizer = TuShareNormalizer()

        # 并发获取多种数据
        from datetime import datetime, timedelta

        end_date = datetime.now()
        start_date = end_date - timedelta(days=1)

        klines, basic, daily = await asyncio.gather(
            source.fetch_klines(
                "000001.SZ",
                start_date.strftime("%Y%m%d"),
                end_date.strftime("%Y%m%d")
            ),
            source.fetch_basic_info(),
            source.fetch_daily_basic(),
        )

        print(f"\n✓ 完整流程:")
        print(f"  - K线: {len(klines)} 条")
        print(f"  - 基本信息: {len(basic)} 条")
        print(f"  - 每日基础面: {len(daily)} 条")

        # 规范化示例
        all_events = klines + basic + daily
        normalized_count = 0
        for event in all_events[:5]:
            normalized = await normalizer.normalize(event)
            if normalized:
                normalized_count += 1

        print(f"  - 成功规范化: {normalized_count} 条")
        assert normalized_count > 0


# 使用 pytest-asyncio 运行异步测试
@pytest.mark.asyncio
async def test_tushare_live_klines():
    """独立的异步测试函数"""
    test_instance = TestTuShareLiveIntegration()
    await test_instance.test_real_fetch_klines()


@pytest.mark.asyncio
async def test_tushare_live_complete():
    """完整流程测试"""
    test_instance = TestTuShareLiveIntegration()
    await test_instance.test_real_complete_flow()

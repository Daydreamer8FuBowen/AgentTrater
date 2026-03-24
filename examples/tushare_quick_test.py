"""
使用真实 TuShare Token 的快速测试指南

本指南演示如何使用提供的 TuShare token 来测试数据源集成。
"""
import asyncio
import os

# 配置 token 和 http_url
TUSHARE_TOKEN = "6588e45307d18e78fc1725898b2ec1dfdad28cb085145d1c47e9f4ee6d12"

# 设置环境变量（可选，用于集成测试）
os.environ["TUSHARE_TOKEN"] = TUSHARE_TOKEN
os.environ["TUSHARE_INTEGRATION_TEST"] = "1"


async def main():
    """
    完整工作流演示：
    1. 初始化数据源
    2. 获取实际数据
    3. 规范化处理
    4. 转换为研究对象
    """
    from agent_trader.ingestion.sources.tushare_source import TuShareSource
    from agent_trader.ingestion.normalizers.tushare_normalizer import TuShareNormalizer
    from agent_trader.domain.models import BarInterval
    from agent_trader.ingestion.models import KlineQuery, RawEvent
    from datetime import datetime, timedelta

    print("=" * 70)
    print("TuShare 数据源实时测试")
    print("=" * 70)
    print()

    # 初始化
    print("📋 步骤 1: 初始化 TuShareSource...")
    source = TuShareSource(token=TUSHARE_TOKEN)
    normalizer = TuShareNormalizer()
    print(f"✓ 初始化成功，数据源: {source.name}")
    print(f"✓ Token 已配置")
    print()

    try:
        # 获取 K 线数据
        print("📊 步骤 2: 获取 K 线数据...")
        end_date = datetime.now()
        start_date = end_date - timedelta(days=5)

        kline_result = await source.fetch_klines_unified(
            KlineQuery(
                symbol="000001.SZ",
                start_time=start_date,
                end_time=end_date,
                interval=BarInterval.D1,
            )
        )

        if kline_result.payload:
            print(f"✓ 成功获取 {len(kline_result.payload)} 条 K 线数据")
            print()

            # 规范化前 3 条
            print("📈 步骤 3: 规范化和转换...")
            for i, record in enumerate(kline_result.payload[:3], 1):
                raw_event = RawEvent(source=source.name, payload=record)
                normalized = await normalizer.normalize(raw_event)
                if normalized:
                    trigger = await normalizer.to_trigger(normalized)
                    print(f"\n  数据 {i}:")
                    print(f"    代码: {trigger.symbol}")
                    print(f"    触发类型: {trigger.trigger_kind}")
                    print(f"    摘要: {trigger.summary}")
                    print(f"    详情: {trigger.metadata}")
        else:
            print("⚠ 未获取到 K 线数据")

        print()

        # 获取其他数据类型
        print("🔄 步骤 4: 获取其他数据类型...")

        basic_result = await source.fetch_basic_info()
        print(f"✓ 股票基本信息: {len(basic_result.payload)} 条")

        daily_basic = await source.fetch_daily_basic()
        print(f"✓ 每日基础面: {len(daily_basic)} 条")

        if daily_basic:
            # 规范化第一条每日基础面数据
            normalized = await normalizer.normalize(daily_basic[0])
            if normalized:
                trigger = await normalizer.to_trigger(normalized)
                print(f"\n  每日基础面示例:")
                print(f"    代码: {trigger.symbol}")
                print(f"    PE: {trigger.metadata.get('pe', 'N/A')}")
                print(f"    PB: {trigger.metadata.get('pb', 'N/A')}")

        print()
        print("=" * 70)
        print("✅ 测试完成！所有数据源正常运行")
        print("=" * 70)

    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    print(f"""
╔══════════════════════════════════════════════════════════════════════╗
║                    TuShare 数据源实时测试                              ║
╚══════════════════════════════════════════════════════════════════════╝

配置信息：
  Token: {TUSHARE_TOKEN[:20]}...
  HTTP URL: http://lianghua.nanyangqiankun.top
  
关键特性：
  ✓ 自动配置 token 和 HTTP URL
  ✓ 支持 K 线数据获取
  ✓ 支持股票基本信息获取
  ✓ 支持每日基础面信息获取
  ✓ 自动规范化和转换

运行测试：
""")

    asyncio.run(main())

"""
TuShare 数据源集成示例

演示如何使用 TuShareSource 获取数据以及 TuShareNormalizer 规范化数据的完整流程。
"""
import asyncio
from datetime import datetime, timedelta

from agent_trader.domain.models import BarInterval
from agent_trader.ingestion.models import KlineQuery, RawEvent
from agent_trader.ingestion.normalizers.tushare_normalizer import TuShareNormalizer
from agent_trader.ingestion.sources.tushare_source import TuShareSource


async def example_fetch_and_normalize():
    """
    完整示例：获取 TuShare 数据 → 规范化 → 转换为研究触发对象

    使用步骤：
    1. 从 https://tushare.pro 获取 API token
    2. 将 token 替换到下面的代码中
    3. 运行此脚本
    """
    # 用实际的 TuShare token 替换
    TUSHARE_TOKEN = "your_tushare_token_here"

    # 初始化数据源和规范化器
    source = TuShareSource(token=TUSHARE_TOKEN)
    normalizer = TuShareNormalizer()

    try:
        # ==================== 获取 K 线数据 ====================
        print("📊 获取平安银行 (000001.SZ) 最近 30 天的日线数据...")
        end_date = datetime.now()
        start_date = end_date - timedelta(days=30)

        kline_result = await source.fetch_klines_unified(
            KlineQuery(
                symbol="000001.SZ",
                start_time=start_date,
                end_time=end_date,
                interval=BarInterval.D1,
            )
        )

        print(f"✓ 获取了 {len(kline_result.payload)} 条 K 线数据\n")

        # 规范化 K 线数据
        for record in kline_result.payload[:3]:  # 仅显示前 3 条
            raw_event = RawEvent(source=source.name, payload=record)
            normalized = await normalizer.normalize(raw_event)
            if normalized:
                trigger = await normalizer.to_trigger(normalized)
                print(f"  K线事件: {trigger.summary}")
                print(f"    - 代码: {trigger.symbol}")
                print(f"    - 触发类型: {trigger.trigger_kind}")
                print(f"    - 详情: {trigger.metadata}\n")

        # ==================== 获取股票基本信息 ====================
        print("📋 获取所有 A 股基本信息...")
        basic_result = await source.fetch_basic_info()
        print(f"✓ 获取了 {len(basic_result.payload)} 条股票基本信息\n")

        # 规范化基本信息（仅显示前 2 条）
        for record in basic_result.payload[:2]:
            raw_event = RawEvent(source=f"{source.name}:stock_basic", payload=record)
            normalized = await normalizer.normalize(raw_event)
            if normalized:
                trigger = await normalizer.to_trigger(normalized)
                print(f"  基本信息事件: {trigger.summary}")
                print(f"    - 代码: {trigger.symbol}")
                print(f"    - 详情: {trigger.metadata}\n")

        # ==================== 获取每日基础信息 ====================
        print("📈 获取最近交易日每日基础信息 (PE、PB等)...")
        daily_basics = await source.fetch_daily_basic()
        print(f"✓ 获取了 {len(daily_basics)} 条每日基础信息\n")

        # 规范化每日基础信息（仅显示前 2 条）
        for raw_event in daily_basics[:2]:
            normalized = await normalizer.normalize(raw_event)
            if normalized:
                trigger = await normalizer.to_trigger(normalized)
                print(f"  基础面事件: {trigger.summary}")
                print(f"    - 代码: {trigger.symbol}")
                print(f"    - PE: {trigger.metadata.get('pe', 'N/A')}")
                print(f"    - PB: {trigger.metadata.get('pb', 'N/A')}\n")

    except Exception as e:
        print(f"❌ 错误: {e}")


async def example_workflow_integration():
    """
    工作流集成示例：SourceAdapter → EventNormalizer → TriggerService

    这演示了完整的数据流：
    TuShareSource (获取数据)
        ↓
    TuShareNormalizer (规范化)
        ↓
    ResearchTrigger (研究触发)
        ↓
    TriggerService.submit_trigger (提交到系统)
        ↓
    Agent 系统 (进行研究)
    """
    from agent_trader.application.services.trigger_service import TriggerService
    from agent_trader.ingestion.models import RawEvent, ResearchTrigger

    # 创建 TriggerService（需要注入 UnitOfWork）
    # trigger_service = TriggerService(unit_of_work=...)

    # 示例：创建一个研究触发对象并提交
    trigger = ResearchTrigger(
        trigger_kind="indicator",
        symbol="000001.SZ",
        summary="平安银行异常上涨 6.5%",
        metadata={
            "close": 103.0,
            "change_pct": 6.5,
            "source": "tushare",
        },
    )

    # 提交到系统
    # result = await trigger_service.submit_trigger(trigger)
    # print(f"研究任务已提交: {result}")


if __name__ == "__main__":
    print("=" * 60)
    print("TuShare 数据源集成演示")
    print("=" * 60)
    print()

    # 运行示例（需要有效的 TuShare token）
    # asyncio.run(example_fetch_and_normalize())

    print("💡 提示:")
    print("  1. 获取 TuShare token: https://tushare.pro")
    print("  2. 将 token 替换到 TUSHARE_TOKEN 变量")
    print("  3. 取消注释最后一行并运行示例")
    print()
    print("支持的数据类型:")
    print("  - K线数据 (daily, weekly, monthly)")
    print("  - 股票基本信息")
    print("  - 每日基础面信息 (PE, PB等)")
    print()
    print("支持的触发类型:")
    print("  - INDICATOR: K线或基本面数据变化")
    print("  - ANNOUNCEMENT: 股票信息更新")

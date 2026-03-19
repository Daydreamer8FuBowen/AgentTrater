# 快速开始 - 事件驱动系统演示

这个脚本演示如何在你的项目中使用事件系统。

## 运行方式

```bash
# 单独运行这个脚本查看事件处理流程
uv run python -m scripts.demo_events
```

---

## 1. 事件类型定义演示

```python
# 查看您项目中的事件定义
# 位置: src/agent_trader/domain/models.py

from enum import Enum

class TriggerKind(str, Enum):
    """系统支持的事件类型"""
    NEWS = "news"                  # 新闻事件
    ANNOUNCEMENT = "announcement"  # 公告事件
    DISCUSSION = "discussion"      # 讨论事件
    INDICATOR = "indicator"        # 技术指标事件
```

## 2. 事件数据模型演示

```python
from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID, uuid4
from typing import Any

# 层级 1: 原始事件
@dataclass(slots=True)
class RawEvent:
    """从外部 API 接收的原始事件"""
    source: str                    # 事件来源 (如 "tushare", "news_api")
    payload: dict[str, Any]        # 原始数据，始终是字典格式
    received_at: datetime          # 接收时间戳
    id: UUID = field(default_factory=uuid4)

# 层级 2: 规范化事件  
@dataclass(slots=True)
class NormalizedEvent:
    """系统内部统一的事件格式"""
    trigger_kind: TriggerKind      # 事件类型
    symbol: str                    # 股票代码
    title: str                     # 标题摘要
    content: str                   # 详细内容
    metadata: dict[str, Any]       # 其他元数据

# 层级 3: 研究触发对象
@dataclass(slots=True)
class ResearchTrigger:
    """提交给 Agent 系统处理的对象"""
    trigger_kind: TriggerKind
    symbol: str
    summary: str                   # 摘要
    metadata: dict[str, Any]       # 元数据
    id: UUID = field(default_factory=uuid4)
```

## 3. 事件转换流程演示（从 TuShare 数据源）

```python
# 实际的数据流转

# 数据源获取原始数据
from agent_trader.ingestion.sources.tushare_source import TuShareSource
from agent_trader.ingestion.normalizers.tushare_normalizer import TuShareNormalizer
from agent_trader.core.config import get_settings

async def demo_event_flow():
    settings = get_settings()
    source = TuShareSource.from_settings(settings)
    normalizer = TuShareNormalizer()
    
    # 步骤 1: 获取原始事件
    raw_events = await source.fetch_klines(
        symbol="000001.SZ",
        start_date="20240115",
        end_date="20240115",
    )
    # 输出: [RawEvent(source="tushare", payload={...}), ...]
    
    # 步骤 2: 规范化事件
    for raw_event in raw_events:
        normalized = await normalizer.normalize(raw_event)
        # 输出: NormalizedEvent(trigger_kind=INDICATOR, symbol="000001.SZ", ...)
        
        # 步骤 3: 生成研究触发
        trigger = await normalizer.to_trigger(normalized)
        # 输出: ResearchTrigger(trigger_kind=INDICATOR, symbol="000001.SZ", ...)
        
        # 步骤 4: 提交给 Agent 系统 (伪代码)
        # await agent_system.process(trigger)
```

## 4. 定时任务示例

```python
# 查看您项目中的定时任务实现
# 位置: src/agent_trader/worker/

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from datetime import datetime

# 任务 1: 摄入 K 线数据
async def ingest_kline_data():
    print(f"[{datetime.now()}] 开始摄入 K 线数据...")
    # 实际逻辑：调用 TuShareSource.fetch_klines()

# 任务 2: 刷新候选池
async def refresh_candidate_pool():
    print(f"[{datetime.now()}] 开始刷新候选池...")
    # 实际逻辑：评分和刷新候选项

# 任务 3: 运行回测
async def run_backtest():
    print(f"[{datetime.now()}] 开始运行回测...")
    # 实际逻辑：对入选候选项进行回测

# 创建和配置调度器
scheduler = AsyncIOScheduler(timezone="UTC")

# 注册任务
scheduler.add_job(
    ingest_kline_data,
    trigger="interval",
    seconds=300,  # 每 5 分钟执行一次
    id="ingest_kline_data",
    name="摄入 K 线数据",
)

scheduler.add_job(
    refresh_candidate_pool,
    trigger="interval",
    seconds=900,  # 每 15 分钟执行一次
    id="refresh_candidate_pool",
    name="刷新候选池",
)

scheduler.add_job(
    run_backtest,
    trigger="interval",
    seconds=3600,  # 每 1 小时执行一次
    id="run_backtest",
    name="运行回测",
)

# 启动调度器
scheduler.start()
```

## 5. 添加新数据源步骤总结

### 第 1 步：创建数据源类

```python
# src/agent_trader/ingestion/sources/my_source.py

from agent_trader.ingestion.models import RawEvent

class MyDataSource:
    """我的数据源"""
    
    async def fetch_data(self) -> list[RawEvent]:
        # 调用外部 API 获取数据
        # 返回 RawEvent 列表
        events = []
        for item in api_response:
            event = RawEvent(
                source="my_data_source",
                payload=item,  # 字典格式
            )
            events.append(event)
        return events
```

### 第 2 步：创建规范化器

```python
# src/agent_trader/ingestion/normalizers/my_normalizer.py

from agent_trader.ingestion.models import NormalizedEvent, ResearchTrigger, RawEvent
from agent_trader.domain.models import TriggerKind

class MyDataNormalizer:
    """规范化我的数据源"""
    
    async def normalize(self, raw_event: RawEvent) -> NormalizedEvent | None:
        # 转换为统一格式
        return NormalizedEvent(
            trigger_kind=TriggerKind.INDICATOR,
            symbol=raw_event.payload.get("symbol"),
            title=raw_event.payload.get("title"),
            content=raw_event.payload.get("content"),
            metadata=raw_event.payload,
        )
    
    async def to_trigger(self, normalized: NormalizedEvent) -> ResearchTrigger:
        # 转换为研究触发对象
        return ResearchTrigger(
            trigger_kind=normalized.trigger_kind,
            symbol=normalized.symbol,
            summary=normalized.title,
            metadata=normalized.metadata,
        )
```

### 第 3 步：在定时任务中使用

```python
# src/agent_trader/worker/tasks.py

async def ingest_my_data():
    """定时任务：摄入我的数据源"""
    source = MyDataSource()
    normalizer = MyDataNormalizer()
    
    raw_events = await source.fetch_data()
    for raw_event in raw_events:
        normalized = await normalizer.normalize(raw_event)
        if normalized:
            trigger = await normalizer.to_trigger(normalized)
            # 提交给 Agent 系统
            # await trigger_service.submit(trigger)
```

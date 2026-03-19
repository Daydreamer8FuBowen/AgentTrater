# AgentTrader 项目开发完全指南

*为从 Java 转向 Python 的开发者编写*

目录：
1. [事件驱动系统设计](#1-事件驱动系统设计)
2. [定时任务配置与执行](#2-定时任务配置与执行)
3. [Ingestion 数据摄入层](#3-ingestion-数据摄入层)
4. [与 Java 开发的对比](#4-与-java-开发的对比)

---

## 1. 事件驱动系统设计

### 1.1 核心概念对比

**Java 开发者视角**：
```java
// Java 中枚举事件类型
public enum EventType {
    PRICE_ALERT,      // 价格告警
    NEWS_ANNOUNCEMENT,  // 新闻公告
    INDICATOR_CHANGE   // 指标变化
}

// 事件类
public abstract class Event {
    public abstract EventType getType();
}

public class PriceAlertEvent extends Event {
    private String symbol;
    private double price;
    
    @Override
    public EventType getType() {
        return EventType.PRICE_ALERT;
    }
}

// 事件监听器
public interface EventListener {
    void onEvent(Event event);
}

// 事件调度器
public class EventDispatcher {
    public void dispatch(Event event) {
        // 分发事件给各个监听器
    }
}
```

**Python/AgentTrader 中的实现**：

```python
# Python 中使用 Enum + Dataclass
from enum import Enum
from dataclasses import dataclass
from datetime import datetime

# 第一步：定义事件类型
class TriggerKind(str, Enum):
    """系统的统一触发入口类型"""
    NEWS = "news"                # 新闻类事件
    ANNOUNCEMENT = "announcement"  # 公告类事件
    DISCUSSION = "discussion"      # 讨论类事件
    INDICATOR = "indicator"        # 指标类事件
```

**关键差异**：
- Java: 使用继承 `extends Event` 创建不同事件类
- Python: 使用 `Enum` 和 `Dataclass` 组合，更简洁灵活

### 1.2 事件数据流

#### 事件定义层（Domain Models）

**文件**: [src/agent_trader/domain/models.py](../src/agent_trader/domain/models.py)

```python
# 1. 事件类型定义
class TriggerKind(str, Enum):
    """定义系统支持的事件类型"""
    NEWS = "news"
    ANNOUNCEMENT = "announcement"
    DISCUSSION = "discussion"
    INDICATOR = "indicator"

# 2. 事件数据模型
@dataclass(slots=True)
class Opportunity:
    """代表一个商业机会事件"""
    symbol: str              # 标的代码
    kind: TriggerKind        # 事件类型
    title: str               # 事件标题
    confidence: float        # 信心度 (0-1)
    source: str              # 数据源
    created_at: datetime = field(default_factory=datetime.utcnow)

# 3. 状态转移类型
class CandidateStatus(str, Enum):
    """候选项在系统中的状态转移"""
    DRAFT = "draft"              # 初始状态
    WATCHING = "watching"        # 监控中
    RESEARCHING = "researching"  # 研究中
    SHORTLISTED = "shortlisted"  # 入选
    APPROVED = "approved"        # 批准
    REJECTED = "rejected"        # 拒绝
    ARCHIVED = "archived"        # 存档
```

#### 事件转换层（Ingestion）

**文件**: [src/agent_trader/ingestion/models.py](../src/agent_trader/ingestion/models.py)

事件在系统中经过三层转换：

```python
# 层次 1: 原始事件（外部数据源）
@dataclass(slots=True)
class RawEvent:
    """外部数据源的原始事件"""
    source: str                    # 数据源名称（如 "tushare", "news_api"）
    payload: dict[str, Any]        # 原始数据（JSON 格式）
    received_at: datetime          # 接收时间
    id: UUID = field(default_factory=uuid4)

# 层次 2: 规范化事件（内部统一格式）
@dataclass(slots=True)
class NormalizedEvent:
    """系统内部统一的事件格式"""
    trigger_kind: TriggerKind      # 事件类型
    symbol: str                    # 标的代码
    title: str                     # 事件标题
    content: str                   # 事件内容
    metadata: dict[str, Any]       # 元数据

# 层次 3: 研究触发对象（系统可处理的形式）
@dataclass(slots=True)
class ResearchTrigger:
    """提交给 Agent 系统进行研究的对象"""
    trigger_kind: TriggerKind
    symbol: str
    summary: str                   # 摘要
    metadata: dict[str, Any]       # 元数据
    id: UUID = field(default_factory=uuid4)
```

### 1.3 事件处理流程（完整示例）

```
外部数据源 (TuShare API)
    ↓
[1] RawEvent 原始事件
    source = "tushare"
    payload = {
        "ts_code": "000001.SZ",
        "trade_date": "20240115",
        "close": 103.0,
        "change_pct": 6.5,
        ...
    }
    
    ↓ [SourceAdapter 适配器]
    
[2] NormalizedEvent 规范化事件
    trigger_kind = TriggerKind.INDICATOR
    symbol = "000001.SZ"
    title = "平安银行异常上涨 6.5%"
    content = "日线收盘价: 103.0, 涨跌幅: 6.5%"
    metadata = {
        "open": 100.0,
        "high": 105.0,
        "low": 98.0,
        "volume": 1000000,
        ...
    }
    
    ↓ [EventNormalizer 规范化器]
    
[3] ResearchTrigger 研究触发对象
    trigger_kind = TriggerKind.INDICATOR
    symbol = "000001.SZ"
    summary = "平安银行异常上涨 6.5%"
    metadata = { ...完整信息... }
    
    ↓ [POST /api/v1/triggers]
    
[4] Agent 系统处理
    ├─ TriggerRouterGraph: 路由分发
    ├─ ResearchGraph: 进行研究
    ├─ CandidatePoolGraph: 管理候选池
    └─ BacktestRepairGraph: 运行回测
```

### 1.4 事件定义的最佳实践

**对 Java 开发者的建议**：

```python
# ❌ 不推荐：定义过多子类
class Event:
    pass

class PriceEvent(Event):
    pass

class NewsEvent(Event):
    pass

# ✅ 推荐：使用 Enum + Dataclass 组合
class TriggerKind(str, Enum):
    PRICE_ALERT = "price_alert"
    NEWS = "news"

@dataclass
class Trigger:
    kind: TriggerKind
    symbol: str
    metadata: dict

# 原因：
# 1. Python 没有强类型，子类继承意义不大
# 2. Dataclass 自动生成 __init__, __repr__ 等方法
# 3. Enum 提供类型安全的枚举值
```

### 1.5 添加新事件类型的步骤

**示例**：添加"技术面突破"事件

1️⃣ **在 Domain 中定义事件类型**
```python
# src/agent_trader/domain/models.py
class TriggerKind(str, Enum):
    NEWS = "news"
    ANNOUNCEMENT = "announcement"
    DISCUSSION = "discussion"
    INDICATOR = "indicator"
    TECHNICAL_BREAKOUT = "technical_breakout"  # 新类型
```

2️⃣ **创建数据源适配器处理新事件**
```python
# src/agent_trader/ingestion/sources/technical_analyzer.py
class TechnicalAnalyzerSource:
    async def fetch_breakouts(self) -> list[RawEvent]:
        """检测技术面突破点"""
        events = []
        # 你的技术分析逻辑
        for symbol, breakout_info in detected_breakouts:
            event = RawEvent(
                source="technical_analyzer",
                payload={
                    "symbol": symbol,
                    "breakout_type": "resistance",
                    "level": 15.5,
                    ...
                }
            )
            events.append(event)
        return events
```

3️⃣ **创建规范化器处理新事件**
```python
# src/agent_trader/ingestion/normalizers/technical_normalizer.py
class TechnicalNormalizer:
    async def normalize(self, raw_event: RawEvent) -> NormalizedEvent:
        payload = raw_event.payload
        return NormalizedEvent(
            trigger_kind=TriggerKind.TECHNICAL_BREAKOUT,
            symbol=payload["symbol"],
            title=f"{payload['symbol']} 突破 {payload['level']}",
            content=f"检测到 {payload['breakout_type']} 突破",
            metadata=payload
        )
```

4️⃣ **提交触发给 Agent 系统**
```python
# 自动流程：在 API 检查到新事件类型时
if normalized.trigger_kind == TriggerKind.TECHNICAL_BREAKOUT:
    # Agent 系统自动处理新类型
    await trigger_service.submit_trigger(trigger)
```

---

## 2. 定时任务配置与执行

### 2.1 技术栈对比

**Java 方案**：
```java
// Spring Boot 原生支持
@Configuration
public class SchedulingConfig {
    @Bean
    public TaskScheduler taskScheduler() {
        return new ThreadPoolTaskScheduler();
    }
}

@Component
public class ScheduledTasks {
    @Scheduled(fixedRate = 5 * 60 * 1000)  // 5分钟
    public void ingestData() {
        // 任务逻辑
    }
}
```

**Python 方案**：
```python
# APScheduler 是 Python 最流行的任务调度库
from apscheduler.schedulers.asyncio import AsyncIOScheduler

scheduler = AsyncIOScheduler()
scheduler.add_job(
    ingest_data,
    trigger="interval",
    seconds=300,  # 5分钟
)
```

### 2.2 完整实现（从 0 到 1）

**步骤 1: 创建任务定义**

```python
# src/agent_trader/worker/tasks.py
import logging
from datetime import datetime
from agent_trader.core.config import get_settings
from agent_trader.ingestion.sources.tushare_source import TuShareSource
from agent_trader.ingestion.normalizers.tushare_normalizer import TuShareNormalizer

logger = logging.getLogger(__name__)


async def ingest_kline_data():
    """
    定时任务 1: 摄入 K 线数据
    
    流程:
    1. 初始化 TuShare 数据源
    2. 获取最新 K 线数据
    3. 规范化为 NormalizedEvent
    4. 转换为 ResearchTrigger
    5. 存储到数据库
    """
    logger.info(f"[{datetime.now()}] 开始摄入 K 线数据...")
    
    try:
        settings = get_settings()
        source = TuShareSource.from_settings(settings)
        normalizer = TuShareNormalizer()
        
        # 获取数据
        raw_events = await source.fetch_klines(
            symbol="000001.SZ",
            start_date="20240115",
            end_date="20240115",
        )
        
        # 规范化
        normalized_count = 0
        for raw_event in raw_events:
            normalized = await normalizer.normalize(raw_event)
            if normalized:
                trigger = await normalizer.to_trigger(normalized)
                # 提交给 Agent 系统
                # await trigger_service.submit_trigger(trigger)
                normalized_count += 1
        
        logger.info(f"✓ 成功摄入 {normalized_count} 条数据")
        
    except Exception as e:
        logger.error(f"✗ 摄入失败: {e}", exc_info=True)


async def refresh_candidate_pool():
    """
    定时任务 2: 刷新候选池
    
    职责:
    - 评分所有候选项
    - 更新状态转移
    - 剔除低分项
    """
    logger.info(f"[{datetime.now()}] 开始刷新候选池...")
    
    try:
        # TODO: 实现候选池刷新逻辑
        logger.info("✓ 候选池已刷新")
    except Exception as e:
        logger.error(f"✗ 刷新失败: {e}", exc_info=True)


async def run_backtest():
    """
    定时任务 3: 运行回测
    
    职责:
    - 对入选候选项进行历史回测
    - 计算 Sharpe、最大回撤等指标
    - 生成回测报告
    """
    logger.info(f"[{datetime.now()}] 开始运行回测...")
    
    try:
        # TODO: 实现回测逻辑
        logger.info("✓ 回测完成")
    except Exception as e:
        logger.error(f"✗ 回测失败: {e}", exc_info=True)
```

**步骤 2: 创建调度器配置**

```python
# src/agent_trader/worker/scheduler.py
import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from agent_trader.core.config import get_settings
from agent_trader.worker.tasks import (
    ingest_kline_data,
    refresh_candidate_pool,
    run_backtest,
)

logger = logging.getLogger(__name__)


def setup_scheduler() -> AsyncIOScheduler:
    """
    设置任务调度器
    
    配置说明:
    - trigger="interval": 使用时间间隔触发
    - seconds: 间隔秒数
    - id: 任务唯一标识符（用于管理）
    - name: 人类可读的任务名称
    - misfire_grace_time: 错过触发时间的容忍度（秒）
    """
    settings = get_settings()
    
    # 创建调度器，设置时区
    scheduler = AsyncIOScheduler(timezone=settings.worker.timezone)
    
    # 任务 1: 摄入 K 线数据
    scheduler.add_job(
        ingest_kline_data,
        trigger="interval",
        seconds=settings.worker.ingestion_interval_seconds,
        id="ingest_kline_data",
        name="📊 摄入 K 线数据",
        misfire_grace_time=60,
        coalesce=True,  # 如果落后多个周期，只执行一次
    )
    
    # 任务 2: 刷新候选池
    scheduler.add_job(
        refresh_candidate_pool,
        trigger="interval",
        seconds=settings.worker.candidate_refresh_seconds,
        id="refresh_candidate_pool",
        name="🎯 刷新候选池",
        misfire_grace_time=60,
    )
    
    # 任务 3: 运行回测
    scheduler.add_job(
        run_backtest,
        trigger="interval",
        seconds=settings.worker.backtest_interval_seconds,
        id="run_backtest",
        name="📈 运行回测",
        misfire_grace_time=60,
    )
    
    # 打印已注册的任务
    logger.info("=" * 60)
    logger.info("✓ 定时任务调度器已配置")
    logger.info("-" * 60)
    for job in scheduler.get_jobs():
        logger.info(f"  [{job.id}] {job.name} - 每 {job.trigger} 执行")
    logger.info("=" * 60)
    
    return scheduler
```

**步骤 3: 集成到 FastAPI 生命周期**

```python
# src/agent_trader/api/main.py
from contextlib import asynccontextmanager
from fastapi import FastAPI
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from agent_trader.worker.scheduler import setup_scheduler
from agent_trader.core.config import get_settings
from agent_trader.core.logging import configure_logging


# 全局调度器引用
_scheduler: AsyncIOScheduler | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    FastAPI 应用生命周期管理
    
    async with 模式:
    - yield 前的代码在应用启动时执行
    - yield 后的代码在应用关闭时执行
    """
    global _scheduler
    
    # ==================== 应用启动 ====================
    print("\n" + "=" * 60)
    print("🚀 AgentTrader 应用启动中...")
    print("=" * 60)
    
    # 1. 配置日志
    settings = get_settings()
    configure_logging(settings.log_level)
    print(f"✓ 日志已配置 (级别: {settings.log_level})")
    
    # 2. 启动定时任务调度器
    _scheduler = setup_scheduler()
    _scheduler.start()
    print("✓ 定时任务调度器已启动")
    
    print("=" * 60)
    print("🎉 应用已就绪，监听 http://127.0.0.1:8000\n")
    
    yield  # 应用运行时的分割点
    
    # ==================== 应用关闭 ====================
    print("\n" + "=" * 60)
    print("💤 AgentTrader 应用关闭中...")
    print("=" * 60)
    
    # 1. 停止定时任务调度器
    if _scheduler and _scheduler.running:
        _scheduler.shutdown()
        print("✓ 定时任务调度器已停止")
    
    print("=" * 60)
    print("👋 应用已安全关闭\n")


def create_app() -> FastAPI:
    """创建 FastAPI 应用"""
    app = FastAPI(
        title="AgentTrader",
        description="Agent-centric quantitative research backend",
        lifespan=lifespan,
    )
    
    # 挂载路由
    from agent_trader.api.routes.health import router as health_router
    from agent_trader.api.routes.triggers import router as trigger_router
    
    app.include_router(health_router)
    app.include_router(trigger_router, prefix="/api/v1")
    
    return app


app = create_app()
```

### 2.3 启动应用查看效果

```bash
uv run uvicorn agent_trader.api.main:app --reload
```

**预期输出**：
```
============================================================
🚀 AgentTrader 应用启动中...
============================================================
✓ 日志已配置 (级别: INFO)
============================================================
📊 摄入 K 线数据
🎯 刷新候选池
📈 运行回测
============================================================
✓ 定时任务调度器已配置
-----------
  [ingest_kline_data] 📊 摄入 K 线数据 - 每 interval seconds=300 执行
  [refresh_candidate_pool] 🎯 刷新候选池 - 每 interval seconds=900 执行
  [run_backtest] 📈 运行回测 - 每 interval seconds=3600 执行
============================================================
✓ 定时任务调度器已启动
============================================================
🎉 应用已就绪，监听 http://127.0.0.1:8000
```

### 2.4 监听器模式（可选高级用法）

如果需要在任务执行前后做些事情（类似 Java 的拦截器）：

```python
# src/agent_trader/worker/listeners.py
from apscheduler.events import EVENT_JOB_EXECUTED, EVENT_JOB_ERROR

def job_listener(event):
    """任务执行监听器"""
    if event.exception:
        logger.error(f"❌ 任务执行失败 [{event.job_id}]: {event.exception}")
    else:
        logger.info(f"✓ 任务执行成功 [{event.job_id}]")

# 在调度器中注册
scheduler.add_listener(job_listener, EVENT_JOB_EXECUTED | EVENT_JOB_ERROR)
```

---

## 3. Ingestion 数据摄入层

### 3.1 架构设计理念

Ingestion 层的三层转换模式设计是为了**解耦合**：

```
┌─────────────────────────────────────────────────────┐
│ Layer 1: SourceAdapter (数据源适配器)               │
│ 职责: 从各种外部 API 获取原始数据                    │
│ 输入: 外部 API (TuShare, 新闻 API, etc)            │
│ 输出: RawEvent (payload 是字典)                     │
└─────────────────────────────────────────────────────┘
              ↓
┌─────────────────────────────────────────────────────┐
│ Layer 2: EventNormalizer (事件规范化器)             │
│ 职责: 转换为系统内部统一格式                         │
│ 输入: RawEvent                                       │
│ 输出: NormalizedEvent + ResearchTrigger             │
└─────────────────────────────────────────────────────┘
              ↓
┌─────────────────────────────────────────────────────┐
│ Layer 3: Agent System (智能体处理)                  │
│ 职责: 分析, 决策, 执行                               │
│ 输入: ResearchTrigger                               │
│ 输出: 研究结果, 信号信号, 交易决策                  │
└─────────────────────────────────────────────────────┘
```

### 3.2 现有数据源分析

#### TuShare 数据源（已实现）

**文件结构**：
```
src/agent_trader/ingestion/
├── sources/
│   ├── base.py                  # SourceAdapter 协议定义
│   └── tushare_source.py        # TuShare 具体实现
├── normalizers/
│   ├── base.py                  # EventNormalizer 协议定义
│   └── tushare_normalizer.py    # TuShare 数据规范化
└── models.py                    # RawEvent, NormalizedEvent 定义
```

**流程示例**（获取 K 线数据）：

```python
# 1. SourceAdapter 层 - 获取原始数据
source = TuShareSource(token="...")
raw_events = await source.fetch_klines(
    symbol="000001.SZ",
    start_date="20240101",
    end_date="20240131",
)
# 输出: [RawEvent(source="tushare", payload={数据库}), ...]

# 2. Normalizer 层 - 转换为标准格式
normalizer = TuShareNormalizer()
for raw_event in raw_events:
    normalized = await normalizer.normalize(raw_event)
    # normalized.trigger_kind = TriggerKind.INDICATOR
    # normalized.symbol = "000001.SZ"
    # normalized.title = "平安银行异常上涨 6.5%"
    
    # 进一步转换为研究触发对象
    trigger = await normalizer.to_trigger(normalized)
    # trigger 可以提交给 Agent 系统
```

### 3.3 添加新数据源的完整指南

**示例**：添加"东方财富财报数据"源

#### 第 1 步：创建数据源适配器

```python
# src/agent_trader/ingestion/sources/eastmoney_source.py
"""
东方财富数据源适配器

提供获取上市公司财报数据的接口。
API 文档: http://quote.eastmoney.com/
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any

import httpx

from agent_trader.ingestion.models import RawEvent

logger = logging.getLogger(__name__)


class EastMoneySource:
    """东方财富数据源适配器"""

    def __init__(self, token: str | None = None):
        """
        初始化数据源
        
        Args:
            token: API token（如果需要认证）
        """
        self.token = token
        self.base_url = "http://api.eastmoney.com"
        self.name = "eastmoney"

    async def fetch_financial_report(
        self,
        symbol: str,
        year: int,
        quarter: int,
    ) -> list[RawEvent]:
        """
        获取财报数据
        
        Args:
            symbol: 股票代码(如 '000001')
            year: 年份(如 2024)
            quarter: 季度(1-4)
        
        Returns:
            RawEvent 列表
        """
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/financial/report",
                    params={
                        "code": symbol,
                        "year": year,
                        "quarter": quarter,
                    },
                )
            
            if response.status_code != 200:
                logger.warning(f"Failed to fetch financial report for {symbol}")
                return []
            
            data = response.json()
            
            # 将每份财报转换为 RawEvent
            events = []
            if "result" in data:
                for item in data["result"]:
                    event = RawEvent(
                        source=f"{self.name}:financial_report",
                        payload=item,  # item 已经是字典
                    )
                    events.append(event)
            
            logger.info(f"Fetched {len(events)} financial reports for {symbol}")
            return events

        except Exception as e:
            logger.error(f"Error fetching financial report: {e}")
            return []

    async def fetch_industry_ranking(self, industry: str) -> list[RawEvent]:
        """获取行业排名数据"""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/industry/ranking",
                    params={"industry": industry},
                )
            
            if response.status_code != 200:
                return []
            
            data = response.json()
            events = []
            
            for item in data.get("result", []):
                event = RawEvent(
                    source=f"{self.name}:industry_ranking",
                    payload=item,
                )
                events.append(event)
            
            logger.info(f"Fetched {len(events)} industry ranking records")
            return events

        except Exception as e:
            logger.error(f"Error fetching industry ranking: {e}")
            return []
```

**关键点**：
- ✅ 类名为 `EastMoneySource`（跟随命名约定）
- ✅ 实现异步方法 `async def fetch_*`
- ✅ 返回 `list[RawEvent]`
- ✅ 错误处理和日志记录
- ✅ `payload` 始终是字典

#### 第 2 步：创建规范化器

```python
# src/agent_trader/ingestion/normalizers/eastmoney_normalizer.py
"""
东方财富数据规范化器

将东方财富的原始数据转换为系统内部格式。
"""
from __future__ import annotations

import logging
from typing import Any

from agent_trader.domain.models import TriggerKind
from agent_trader.ingestion.models import NormalizedEvent, RawEvent, ResearchTrigger

logger = logging.getLogger(__name__)


class EastMoneyNormalizer:
    """东方财富数据规范化器"""

    async def normalize(self, raw_event: RawEvent) -> NormalizedEvent | None:
        """
        规范化原始事件
        
        Args:
            raw_event: 原始事件
        
        Returns:
            规范化后的事件，若无法转换则返回 None
        """
        source = raw_event.source
        payload = raw_event.payload

        if "financial_report" in source:
            return self._normalize_financial_report(payload)
        elif "industry_ranking" in source:
            return self._normalize_industry_ranking(payload)
        
        logger.warning(f"Unknown EastMoney source type: {source}")
        return None

    async def to_trigger(self, normalized_event: NormalizedEvent) -> ResearchTrigger:
        """
        将规范化事件转换为研究触发对象
        """
        return ResearchTrigger(
            trigger_kind=normalized_event.trigger_kind,
            symbol=normalized_event.symbol,
            summary=normalized_event.title,
            metadata={
                "content": normalized_event.content,
                **normalized_event.metadata,
            },
        )

    def _normalize_financial_report(self, payload: dict[str, Any]) -> NormalizedEvent:
        """规范化财报数据"""
        symbol = payload.get("code", "unknown")
        net_profit = payload.get("net_profit", 0)
        roe = payload.get("roe", 0)
        
        # 根据财报指标判断触发类型
        if net_profit > 1_000_000_000:  # 10亿以上
            title = f"{symbol} 净利润超 10 亿"
        else:
            title = f"{symbol} 财报更新 - 净利润: {net_profit}"
        
        return NormalizedEvent(
            trigger_kind=TriggerKind.INDICATOR,
            symbol=symbol,
            title=title,
            content=f"ROE: {roe}%, 净利润: {net_profit}",
            metadata={
                "net_profit": net_profit,
                "roe": roe,
                "period": payload.get("period", ""),
                "report_type": "financial_report",
            },
        )

    def _normalize_industry_ranking(self, payload: dict[str, Any]) -> NormalizedEvent:
        """规范化行业排名数据"""
        symbol = payload.get("code", "unknown")
        industry = payload.get("industry", "")
        rank = payload.get("rank", 0)
        
        return NormalizedEvent(
            trigger_kind=TriggerKind.ANNOUNCEMENT,
            symbol=symbol,
            title=f"{symbol} 在 {industry} 中排名 #{rank}",
            content=f"行业排名更新",
            metadata={
                "industry": industry,
                "rank": rank,
                "score": payload.get("score", 0),
                "report_type": "industry_ranking",
            },
        )
```

#### 第 3 步：导出到模块接口

```python
# src/agent_trader/ingestion/sources/__init__.py
"""数据源适配器模块"""
from agent_trader.ingestion.sources.tushare_source import TuShareSource
from agent_trader.ingestion.sources.eastmoney_source import EastMoneySource

__all__ = ["TuShareSource", "EastMoneySource"]


# src/agent_trader/ingestion/normalizers/__init__.py
"""规范化器模块"""
from agent_trader.ingestion.normalizers.tushare_normalizer import TuShareNormalizer
from agent_trader.ingestion.normalizers.eastmoney_normalizer import EastMoneyNormalizer

__all__ = ["TuShareNormalizer", "EastMoneyNormalizer"]
```

#### 第 4 步：添加到定时任务

```python
# src/agent_trader/worker/tasks.py
async def ingest_eastmoney_data():
    """定时任务: 摄入东方财富财报数据"""
    logger.info(f"[{datetime.now()}] 开始摄入财报数据...")
    
    try:
        settings = get_settings()
        source = EastMoneySource()  # 可选: token = settings.eastmoney.token
        normalizer = EastMoneyNormalizer()
        
        # 获取最新财报
        raw_events = await source.fetch_financial_report(
            symbol="000001",
            year=2024,
            quarter=4,
        )
        
        # 规范化
        for raw_event in raw_events:
            normalized = await normalizer.normalize(raw_event)
            if normalized:
                trigger = await normalizer.to_trigger(normalized)
                logger.info(f"✓ 财报触发: {trigger.summary}")
        
    except Exception as e:
        logger.error(f"✗ 财报摄入失败: {e}")


# 在 scheduler.py 中注册
scheduler.add_job(
    ingest_eastmoney_data,
    trigger="interval",
    seconds=3600,  # 每小时
    id="ingest_eastmoney",
    name="📊 摄入财报数据",
)
```

#### 第 5 步：集成测试

```python
# tests/test_eastmoney_ingestion.py
@pytest.mark.asyncio
async def test_eastmoney_fetch_financial_report():
    """测试财报数据获取"""
    with patch("httpx.AsyncClient.get") as mock_get:
        # 模拟响应
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "result": [
                {
                    "code": "000001",
                    "net_profit": 1_500_000_000,
                    "roe": 12.5,
                }
            ]
        }
        mock_get.return_value = mock_response
        
        source = EastMoneySource()
        events = await source.fetch_financial_report("000001", 2024, 4)
        
        assert len(events) > 0
        assert events[0].source == "eastmoney:financial_report"


@pytest.mark.asyncio
async def test_eastmoney_normalize():
    """测试财报数据规范化"""
    normalizer = EastMoneyNormalizer()
    raw_event = RawEvent(
        source="eastmoney:financial_report",
        payload={
            "code": "000001",
            "net_profit": 1_500_000_000,
            "roe": 12.5,
        },
    )
    
    normalized = await normalizer.normalize(raw_event)
    
    assert normalized is not None
    assert normalized.symbol == "000001"
    assert "净利润" in normalized.title
```

### 3.4 Ingestion 最佳实践清单

| 检查项 | 说明 | 示例 |
|--------|------|------|
| ✅ SourceAdapter 实现 | 实现 `async def fetch_*()` 返回 `list[RawEvent]` | `fetch_financial_report()` |
| ✅ 错误处理 | 使用 try-except，返回空列表而非抛出异常 | `except Exception as e: return []` |
| ✅ 日志记录 | 记录关键操作和错误 | `logger.info(...)` |
| ✅ EventNormalizer 实现 | 实现 `normalize()` 和 `to_trigger()` 两个方法 | `TuShareNormalizer` |
| ✅ 异步编程 | 全部使用 `async/await` 避免阻塞 | `await asyncio.to_thread(...)` |
| ✅ 类型注解 | 使用类型提示便于 IDE 自动补全和类型检查 | `list[RawEvent]` |
| ✅ 单元测试 | 为新数据源编写测试 | `test_eastmoney_ingestion.py` |
| ✅ 文档字符串 | 使用 docstring 说明职责和用法 | """获取财报数据""" |

---

## 4. 与 Java 开发的对比

### 4.1 设计模式对比

| 模式 | Java 实现 | Python 实现 | 优势 |
|------|---------|-----------|------|
| **工厂模式** | `Factory` 接口 + 多个实现类 | `@classmethod` 或工厂函数 | Python 更轻量 |
| **适配器模式** | `Adapter` 类继承 | Protocol + 实现类 | Python 使用鸭子类型 |
| **观察者模式** | `Observer` 接口 + `Subject` | `async` 回调 + 事件系统 | Python 更自然 |
| **生命周期管理** | Spring `@PostConstruct` / `@PreDestroy` | `async with lifespan` | Python 使用上下文管理器 |
| **依赖注入** | Spring `@Autowired` / `@Bean` | FastAPI `Depends()` | 都很易用 |

### 4.2 概念映射表

| Java 概念 | Python 相当物 | 说明 |
|----------|-------------|------|
| `interface` | `Protocol` / ABC | Python 使用结构化子类型 |
| `@Component` | 注册到 `Depends()` | Python 通过函数签名自动注入 |
| `@Scheduled` | APScheduler | Python 需要额外库支持定时 |
| `@Value` | `pydantic.BaseSettings` | Python 使用数据验证库 |
| `@Transactional` | `async with session` | Python 手动管理事务 |
| `Stream API` | `async for` 或 列表推导式 | Python 天然支持异步迭代 |
| `Thread Pool` | `asyncio` / `concurrent.futures` | Python 推荐异步而非多线程 |

### 4.3 常见陷阱和最佳实践

**陷阱 1: 忘记 `await`**
```python
# ❌ 错误
result = get_data()  # 返回 Coroutine 而非数据

# ✅ 正确
result = await get_data()
```

**陷阱 2: 在 `async` 函数中调用同步代码**
```python
# ❌ 错误 - 阻塞事件循环
import time
time.sleep(5)

# ✅ 正确 - 使用线程池
await asyncio.to_thread(time.sleep, 5)
```

**陷阱 3: 环境变量没有设置**
```python
# ❌ 直接访问可能报错
token = settings.tushare.token

# ✅ 先检查
if settings.tushare.token:
    source = TuShareSource.from_settings(settings)
else:
    logger.warning("TuShare token not configured")
```

### 4.4 Python 特有优势

1. **Duck Typing（动态类型）**
   ```python
   # 不需要显式实现接口，只要有相同方法即可
   class DataSource:
       async def fetch(self): ...
   
   class TuShareSource:
       async def fetch(self): ...  # 没有显式继承，但可以互换
   ```

2. **Dataclass 自动生成代码**
   ```python
   @dataclass  # 自动生成 __init__, __repr__, __eq__ 等
   class Opportunity:
       symbol: str
       kind: TriggerKind
   ```

3. **异步上下文管理器**
   ```python
   async with mysql_manager.session() as session:
       # 自动处理获取和释放
       await session.execute(...)
   ```

4. **装饰器简化代码**
   ```python
   @lru_cache(maxsize=1)  # 自动单例化
   def get_settings() -> Settings:
       return Settings()
   ```

---

## 总结

AgentTrader 的架构特点：

1. **事件驱动**: 通过 `TriggerKind` Enum + 三层事件转换 (RawEvent → NormalizedEvent → ResearchTrigger)

2. **定时任务**: 使用 APScheduler 在 FastAPI 的生命周期中管理，简洁高效

3. **可扩展摄入**: 通过 SourceAdapter + EventNormalizer 两层设计，添加新数据源只需：
   - 创建新 source class
   - 创建新 normalizer class
   - 导出到 __init__.py
   - 添加到定时任务

4. **Python 特色**: 充分利用异步编程、dataclass、Protocol 等 Python 特性

---

**继续学习资源**：
- APScheduler 文档: https://apscheduler.readthedocs.io/
- FastAPI 生命周期: https://fastapi.tiangolo.com/advanced/events/
- Pydantic Settings: https://docs.pydantic.dev/latest/concepts/pydantic_settings/

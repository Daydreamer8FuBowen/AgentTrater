# Ingestion 层扩展性设计深度解析

> 深入理解 AgentTrader 的数据摄入架构与扩展机制

---

## 1. 为什么需要三层转换？

### 问题：为什么不直接存储外部数据？

```
❌ 不好的做法：
外部数据 API → 直接存储到数据库
后果：
- 数据格式混乱（每个数据源格式不同）
- 很难统一查询
- 添加新数据源时，整个系统都要改动
```

### 解决方案：三层转换模式

```
✅ 好的做法：
外部数据 API
    ↓ [Layer 1: SourceAdapter]
RawEvent（原始事件，payload 是字典）
    ↓ [Layer 2: EventNormalizer]
NormalizedEvent（统一格式）
    ↓ [Layer 3: to_trigger]
ResearchTrigger（Agent 可处理的形式）
```

**优点**：
1. **解耦合**：每个数据源的适配器互不影响
2. **统一接口**：所有数据最终都成为 ResearchTrigger
3. **易扩展**：添加新数据源只需实现两个类
4. **可测试**：每一层都可以独立测试

---

## 2. 架构图解

```
┌─────────────────────────────────────────────────────────────┐
│ 外部数据源（多个）                                          │
├─────────────────────────────────────────────────────────────┤
│  TuShare API  │  Yahoo Finance  │  News API  │  Custom API  │
└────────┬──────┴────────┬────────┴─────┬──────┴────────┬──────┘
         │               │              │              │
         v               v              v              v
┌────────────────────────────────────────────────────────────┐
│ Layer 1: SourceAdapter (数据源适配器)                     │
├────────────────────────────────────────────────────────────┤
│ TuShareSource   │ YahooSource   │ NewsSource   │ CustomSource│
│ - fetch_*()    │ - fetch_*()  │ - fetch_*() │ - fetch_*() │
│ 返回: RawEvent  │ 返回: RawEvent│ 返回: Raw... │ 返回: Raw... │
└────────┬───────┴────────┬──────┴─────┬──────┴────────┬──────┘
         │                │            │              │
         └────────────────┴────────────┴──────────────┤
                         ↓
┌────────────────────────────────────────────────────────────┐
│ Layer 2: EventNormalizer (规范化器)                        │
├────────────────────────────────────────────────────────────┤
│ TuShareNormalizer  │ YahooNormalizer  │ NewsNormalizer │
│ - normalize()      │ - normalize()    │ - normalize()  │
│ - to_trigger()     │ - to_trigger()   │ - to_trigger() │
│ 返回: NormalizedEvent + ResearchTrigger                    │
└────────────────────────────────────────────────────────────┘
                         ↓
┌────────────────────────────────────────────────────────────┐
│ Layer 3: Agent System (智能体系统处                         │
├────────────────────────────────────────────────────────────┤
│ - TriggerRouter      (路由分发)                            │
│ - ResearchGraph      (基本面研究)                          │
│ - CandidatePool      (候选池管理)                          │
│ - BacktestGraph      (回测评估)                            │
└────────────────────────────────────────────────────────────┘
```

---

## 3. 层级详解

### Layer 1: SourceAdapter (适配器层)

**职责**：从各种外部 API 获取数据，转换为统一的 `RawEvent` 格式

**特点**：
- 接收不同 API 的响应格式
- 处理网络错误、超时等异常
- 最小化数据处理（基本关键字段提取）

**示例类结构**：
```python
class SourceAdapter(Protocol):
    """数据源适配器协议"""
    
    async def fetch_*(
        self,
        symbol: str,
        **kwargs
    ) -> list[RawEvent]:
        """
        获取数据
        返回: RawEvent 列表
        - source: 数据源名称
        - payload: 原始数据字典（保持原样，不处理）
        """
        ...
```

**为什么 payload 是字典？**
- ✅ 不同数据源的数据结构完全不同
- ✅ 字典可以包含任何 JSON 序列化的数据
- ✅ 规范化器后面会处理

### Layer 2: EventNormalizer (规范化层)

**职责**：
1. 检查 RawEvent 是否满足触发条件
2. 如满足，转换为统一的 NormalizedEvent
3. 进一步转换为 ResearchTrigger

**特点**：
- 包含业务逻辑（什么情况算触发）
- 决定事件的类型（TriggerKind）
- 提取关键信息

**示例类结构**：
```python
class EventNormalizer(Protocol):
    """事件规范化协议"""
    
    async def normalize(
        self,
        raw_event: RawEvent
    ) -> NormalizedEvent | None:
        """
        规范化原始事件
        返回: 
        - 满足条件: NormalizedEvent
        - 不满足条件: None
        """
        ...
    
    async def to_trigger(
        self,
        normalized_event: NormalizedEvent
    ) -> ResearchTrigger:
        """转换为研究触发对象"""
        ...
```

### Layer 3: Agent System (处理层)

**职责**：
- 接收 ResearchTrigger
- 根据 TriggerKind 路由到相应的 Agent
- 执行分析、决策、行动

**工作流**：
```
ResearchTrigger (kind=INDICATOR)
    ↓
TriggerRouter.route()
    ↓
ResearchGraph (基本面研究)
    ├─ 获取财报数据
    ├─ 计算估值指标
    └─ 生成研究意见
    ↓
CandidatePool (候选池管理)
    ├─ 评分
    ├─ 排序
    └─ 入池
    ↓
BacktestGraph (回测评估)
    ├─ 历史回测
    ├─ 计算收益
    └─ 生成报告
```

---

## 4. 添加新数据源的完整工作流

### 场景：添加"新浪财经"数据源

#### 步骤 1: 分析新数据源

```markdown
数据源名称: SinaFinance
数据类型: 财務新聞、股票评论
API 端点: http://finance.sina.com.cn/realstock/
认证方式: 无需认证
速率限制: 无限制
数据示例:
{
    "symbol": "000001",
    "title": "平安银行发布重磅公告",
    "content": "...",
    "source": "新浪网",
    "published_at": "2024-01-15 10:00:00",
}
```

#### 步骤 2: 实现 SourceAdapter

```python
# src/agent_trader/ingestion/sources/sina_source.py
import asyncio
import logging
from typing import Any

import httpx

from agent_trader.ingestion.models import RawEvent

logger = logging.getLogger(__name__)

class SinaFinanceSource:
    """新浪财经数据源适配器"""
    
    def __init__(self):
        self.name = "sina_finance"
        self.base_url = "http://finance.sina.com.cn"
        self.timeout = 10
    
    async def fetch_news(self, symbol: str) -> list[RawEvent]:
        """
        获取相关新闻
        
        Args:
            symbol: 股票代码 (如 "000001")
        
        Returns:
            RawEvent 列表
        """
        logger.info(f"[SinaFinance] 获取 {symbol} 的新闻...")
        
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                # 调用新浪 API
                response = await client.get(
                    f"{self.base_url}/realstock/api_tickersearch.php",
                    params={
                        "symbol": f"cn_{symbol}",
                        "type": "news",
                        "limit": 10,
                    }
                )
            
            if response.status_code != 200:
                logger.warning(
                    f"新浪 API 返回状态码 {response.status_code}"
                )
                return []
            
            data = response.json()
            
            # 将每条新闻转为 RawEvent
            events = []
            for item in data.get("result", []):
                # 关键：payload 必须是字典
                event = RawEvent(
                    source="sina_finance:news",
                    payload={
                        "symbol": symbol,
                        "title": item.get("title"),
                        "content": item.get("content"),
                        "source": "新浪财经",
                        "published_at": item.get("published_at"),
                        "url": item.get("url"),
                    },
                )
                events.append(event)
            
            logger.info(f"成功获取 {len(events)} 条新闻")
            return events
        
        except httpx.TimeoutException:
            logger.error(f"新浪 API 超时")
            return []
        except Exception as e:
            logger.error(f"获取新浪数据失败: {e}")
            return []
```

**关键要点**：
- ✅ 方法名：`async def fetch_*`
- ✅ 返回值：`list[RawEvent]`
- ✅ payload 是字典
- ✅ 错误处理：返回空列表而非抛异常
- ✅ 日志记录

#### 步骤 3: 实现 EventNormalizer

```python
# src/agent_trader/ingestion/normalizers/sina_normalizer.py
import logging
from typing import Any

from agent_trader.domain.models import TriggerKind
from agent_trader.ingestion.models import (
    NormalizedEvent,
    RawEvent,
    ResearchTrigger,
)

logger = logging.getLogger(__name__)

class SinaFinanceNormalizer:
    """新浪财经数据规范化器"""
    
    # 关键词触发列表
    TRIGGER_KEYWORDS = [
        "公告",
        "重大",
        "收购",
        "资产重组",
        "股权转让",
        "业绩预增",
        "扭亏",
        "破产",
    ]
    
    async def normalize(
        self,
        raw_event: RawEvent
    ) -> NormalizedEvent | None:
        """
        规范化原始新闻事件
        
        规则：
        1. 检查标题是否包含触发关键词
        2. 如是，转为 NormalizedEvent
        3. 如否，返回 None（过滤）
        """
        payload = raw_event.payload
        title = payload.get("title", "")
        
        # 检查是否有触发关键词
        has_trigger = any(kw in title for kw in self.TRIGGER_KEYWORDS)
        
        if not has_trigger:
            logger.debug(f"[新浪规范化] 新闻未触发: {title[:50]}")
            return None
        
        logger.info(f"[新浪规范化] 检测到触发新闻: {title}")
        
        # 创建规范化事件
        return NormalizedEvent(
            trigger_kind=TriggerKind.ANNOUNCEMENT,  # 公告类
            symbol=payload.get("symbol", ""),
            title=title,
            content=payload.get("content", ""),
            metadata={
                "source": payload.get("source"),
                "published_at": payload.get("published_at"),
                "url": payload.get("url"),
            },
        )
    
    async def to_trigger(
        self,
        normalized: NormalizedEvent
    ) -> ResearchTrigger:
        """转换为研究触发对象"""
        return ResearchTrigger(
            trigger_kind=normalized.trigger_kind,
            symbol=normalized.symbol,
            summary=normalized.title,
            metadata={
                "content": normalized.content,
                **normalized.metadata,
            },
        )
```

**业务规则**：
- 检查标题中的关键词
- 只对重要事项触发
- 完整保存原始内容供后续分析

#### 步骤 4: 集成到系统

```python
# src/agent_trader/ingestion/sources/__init__.py
from agent_trader.ingestion.sources.sina_source import SinaFinanceSource

__all__ = ["TuShareSource", "SinaFinanceSource"]


# src/agent_trader/ingestion/normalizers/__init__.py
from agent_trader.ingestion.normalizers.sina_normalizer import SinaFinanceNormalizer

__all__ = ["TuShareNormalizer", "SinaFinanceNormalizer"]
```

#### 步骤 5: 添加定时任务

```python
# src/agent_trader/worker/tasks.py
from agent_trader.ingestion.sources.sina_source import SinaFinanceSource
from agent_trader.ingestion.normalizers.sina_normalizer import SinaFinanceNormalizer

async def ingest_sina_news():
    """定时任务：摄入新浪财经新闻"""
    logger.info("[定时任务] 开始摄入新浪新闻...")
    
    try:
        source = SinaFinanceSource()
        normalizer = SinaFinanceNormalizer()
        
        # 监控的股票列表（应该来自配置或数据库）
        symbols = ["000001", "000002", "600000", "600036"]
        
        for symbol in symbols:
            # 1. 获取原始事件
            raw_events = await source.fetch_news(symbol)
            
            # 2. 规范化
            for raw_event in raw_events:
                normalized = await normalizer.normalize(raw_event)
                
                # 3. 满足条件则转为触发
                if normalized:
                    trigger = await normalizer.to_trigger(normalized)
                    logger.info(f"✓ 新浪新闻触发: {trigger.summary}")
                    
                    # 4. 提交给 Agent 系统
                    # await trigger_service.submit_trigger(trigger)
    
    except Exception as e:
        logger.error(f"✗ 新浪新闻摄入失败: {e}")
```

在调度器中注册：

```python
# src/agent_trader/worker/scheduler.py
scheduler.add_job(
    ingest_sina_news,
    trigger="interval",
    seconds=settings.worker.news_ingestion_seconds,  # 例如 600（10分钟）
    id="ingest_sina_news",
    name="📰 摄入新浪新闻",
)
```

#### 步骤 6: 编写单元测试

```python
# tests/ingestion/sources/test_sina_source.py
@pytest.mark.asyncio
async def test_sina_fetch_news():
    """测试新浪新闻获取"""
    with patch("httpx.AsyncClient.get") as mock_get:
        # 模拟 API 响应
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "result": [
                {
                    "title": "平安银行发布重大公告",
                    "content": "...",
                    "published_at": "2024-01-15",
                    "url": "http://...",
                }
            ]
        }
        mock_get.return_value = mock_response
        
        source = SinaFinanceSource()
        events = await source.fetch_news("000001")
        
        assert len(events) == 1
        assert events[0].source == "sina_finance:news"
        assert events[0].payload["title"] == "平安银行发布重大公告"


@pytest.mark.asyncio
async def test_sina_normalizer():
    """测试新浪数据规范化"""
    normalizer = SinaFinanceNormalizer()
    
    # 包含触发关键词
    raw_event = RawEvent(
        source="sina_finance:news",
        payload={
            "symbol": "000001",
            "title": "平安银行发布重大公告",
            "content": "金额超过 10 亿",
        },
    )
    
    normalized = await normalizer.normalize(raw_event)
    
    assert normalized is not None
    assert normalized.trigger_kind == TriggerKind.ANNOUNCEMENT
    assert "重大" in normalized.title
    
    # 不包含触发关键词
    raw_event2 = RawEvent(
        source="sina_finance:news",
        payload={
            "symbol": "000001",
            "title": "平安银行股价上升 1%",
            "content": "今日涨幅 1%",
        },
    )
    
    normalized2 = await normalizer.normalize(raw_event2)
    
    assert normalized2 is None  # 应该被过滤
```

---

## 5. 扩展性检查清单

添加新数据源时，使用本检查表确保代码质量：

| 项目 | 检查内容 | 示例 |
|------|--------|------|
| **API 集成** | ✅ 使用 httpx 异步客户端 | `async with httpx.AsyncClient()` |
| | ✅ 处理超时异常 | `except httpx.TimeoutException` |
| | ✅ 处理网络错误 | `try-except` 包装 |
| **数据格式** | ✅ RawEvent payload 是字典 | `payload: dict[str, Any]` |
| | ✅ 日志记录关键操作 | `logger.info(...)` |
| | ✅ 返回结果统一为列表 | `list[RawEvent]` |
| **规范化** | ✅ normalize() 返回可选类型 | `NormalizedEvent \| None` |
| | ✅ 定义清晰的触发规则 | 注释说明什么时候触发 |
| | ✅ to_trigger() 始终返回对象 | `ResearchTrigger` |
| **集成** | ✅ 添加到 `__init__.py` | 导出类 |
| | ✅ 在 tasks.py 中创建定时任务 | `async def ingest_*` |
| | ✅ 在 scheduler.py 中注册 | `scheduler.add_job()` |
| **测试** | ✅ Mock 外部 API | 使用 `patch` |
| | ✅ 测试成功路径 | 测试正常数据处理 |
| | ✅ 测试失败路径 | 测试网络错误、空响应等 |
| | ✅ 测试过滤逻辑 | 测试 `normalize()` 返回 None 的情况 |

---

## 6. 性能优化建议

### 并发获取多个数据源

```python
async def ingest_all_sources():
    """并发获取所有数据源"""
    
    # 串行执行（慢）
    await ingest_tushare_data()
    await ingest_sina_news()
    await ingest_yahoo_finance()
    
    # 并行执行（快）
    await asyncio.gather(
        ingest_tushare_data(),
        ingest_sina_news(),
        ingest_yahoo_finance(),
    )
```

### 批量处理数据

```python
# 处理数据时分批规范化
BATCH_SIZE = 100

async def normalize_batch(raw_events: list[RawEvent]):
    """分批规范化"""
    for i in range(0, len(raw_events), BATCH_SIZE):
        batch = raw_events[i:i + BATCH_SIZE]
        
        normalized_events = []
        for raw in batch:
            normalized = await normalizer.normalize(raw)
            if normalized:
                normalized_events.append(normalized)
```

### 缓存规范化结果

```python
from functools import lru_cache

class CachingNormalizer:
    @lru_cache(maxsize=1000)
    def _get_trigger_keywords(self) -> frozenset[str]:
        """缓存关键词列表"""
        return frozenset(self.TRIGGER_KEYWORDS)
```

---

## 总结

Ingestion 层的核心设计理念：

1. **三层转换**：解耦合不同的关注点
   - Layer 1: 获取原始数据
   - Layer 2: 规范化和决策
   - Layer 3: Agent 处理

2. **高度可扩展**：添加新数据源只需实现两个类
   - SourceAdapter: 获取数据
   - EventNormalizer: 规范化数据

3. **异步优先**：充分利用 Python 的异步编程
   - 所有网络操作都是异步的
   - 可以并发处理多个数据源

4. **错误恢复**：任何单个数据源的失败都不会影响其他源
   - 返回空列表而不抛异常
   - 日志记录便于调试

这个设计模式类似于 Java 中的 Pipeline 模式或 Spring Cloud Stream，但用 Python 的异步特性实现得更加优雅。

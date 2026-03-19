# TuShare 数据源集成

## 概述

TuShare 是一个提供 A 股、港股、期货等多市场数据的数据库。本集成提供了从 TuShare 获取数据并将其规范化为系统事件的完整接口。

## 快速开始

### 1. 获取 API Token

访问 [TuShare Pro](https://tushare.pro) 注册账户并获取 API token。

### 2. 安装依赖

TuShare 依赖已通过 `pyproject.toml` 安装：

```bash
uv sync
```

### 3. 配置 Token 和 HTTP URL

**重要**: 为了正确使用 TuShare API（特别是通过国内代理），需要确保以下配置：

```python
from agent_trader.ingestion.sources import TuShareSource

# token 会自动配置以下两个关键属性：
# 1. pro._DataApi__token = token         # 设置认证 token
# 2. pro._DataApi__http_url = 'http://lianghua.nanyangqiankun.top'  # 设置数据源 URL
source = TuShareSource(token="your_token")
```

这两行配置在 TuShareSource 初始化时自动执行，保证能够正常获取数据。

### 4. 使用 SourceAdapter

```python
from agent_trader.ingestion.sources import TuShareSource

# 初始化数据源
source = TuShareSource(token="your_token")

# 获取 K 线数据
events = await source.fetch_klines(
    symbol="000001.SZ",  # 平安银行
    start_date="20240101",
    end_date="20240131",
)

# 获取股票基本信息
basic_info = await source.fetch_basic_info()

# 获取每日基础面信息
daily_basic = await source.fetch_daily_basic()
```

### 5. 使用 EventNormalizer

```python
from agent_trader.ingestion.normalizers import TuShareNormalizer

normalizer = TuShareNormalizer()

# 规范化原始事件
for raw_event in events:
    normalized = await normalizer.normalize(raw_event)
    
    # 转换为研究触发对象
    trigger = await normalizer.to_trigger(normalized)
    print(f"触发类型: {trigger.trigger_kind}")
    print(f"标的: {trigger.symbol}")
    print(f"摘要: {trigger.summary}")
```

## 数据流向

```
┌─────────────────────┐
│  External Data      │
│   (TuShare API)     │
└──────────┬──────────┘
           │ SourceAdapter
           ↓
┌─────────────────────┐
│   RawEvent          │
│ - source            │
│ - payload (dict)    │
│ - received_at       │
└──────────┬──────────┘
           │ EventNormalizer.normalize()
           ↓
┌─────────────────────┐
│ NormalizedEvent     │
│ - trigger_kind      │
│ - symbol            │
│ - title             │
│ - content           │
│ - metadata          │
└──────────┬──────────┘
           │ EventNormalizer.to_trigger()
           ↓
┌─────────────────────┐
│ ResearchTrigger     │
│ - trigger_kind      │
│ - symbol            │
│ - summary           │
│ - metadata          │
└──────────┬──────────┘
           │ TriggerService.submit_trigger()
           ↓
    ┌──────────────┐
    │ Agent System │
    │  (Research   │
    │   & Analyze) │
    └──────────────┘
```

## 支持的数据类型

### 1. K 线数据 (Daily Klines)

**源:** `tushare`
**字段:** ts_code, trade_date, open, high, low, close, vol, amount

**示例:**
```python
events = await source.fetch_klines("000001.SZ", "20240101", "20240131")
```

**规范化输出:**
- `TriggerKind.INDICATOR`
- 涨跌幅 > 5% 时: "异常上涨"
- 涨跌幅 < -5% 时: "异常下跌"
- 其他: "价格变化"

### 2. 每日基础面信息 (Daily Basic)

**源:** `tushare:daily_basic`
**字段:** ts_code, trade_date, pe, pb, dv_ratio, dv_ttm, total_mv

**示例:**
```python
events = await source.fetch_daily_basic()
```

**规范化输出:**
- `TriggerKind.INDICATOR`
- 包含 PE、PB 等基本面数据

### 3. 股票基本信息 (Stock Basic)

**源:** `tushare:stock_basic`
**字段:** ts_code, name, industry, area, market, list_date

**示例:**
```python
events = await source.fetch_basic_info()
```

**规范化输出:**
- `TriggerKind.ANNOUNCEMENT`
- 用于新股纳入监控

## 触发类型映射

| 数据类型 | TriggerKind | 使用场景 |
|---------|------------|--------|
| K 线数据 | INDICATOR | 价格/成交量异常 |
| 基础面信息 | INDICATOR | PE/PB 变化 |
| 股票信息 | ANNOUNCEMENT | 新股上市、纳入监控 |

## 异常处理

所有操作都包含错误处理，异常会被记录但不会崩溃：

```python
try:
    events = await source.fetch_klines(...)
except Exception as e:
    logger.error(f"获取数据失败: {e}")
    return []
```

## 性能考虑

- **并发请求:** `fetch()` 方法使用 `asyncio.gather()` 并发获取多个数据源
- **线程池:** 所有 TuShare 同步调用在线程池中执行，避免阻塞事件循环
- **缓存:** 建议在应用层实现缓存以减少 API 调用

## 测试

### 单元测试（无需真实 Token）

运行模拟测试（使用 mock 数据，无需真实的 TuShare 账户）：

```bash
uv run pytest tests/test_tushare_ingestion.py -v
```

测试覆盖：
- ✅ 源适配器初始化和数据获取
- ✅ 规范化逻辑和事件转换
- ✅ 错误处理和边界情况
- ✅ Token 和 HTTP URL 配置验证

### 实时集成测试（需要真实 Token）

如果有有效的 TuShare token，可以运行真实的集成测试来验证与 API 的实际连接：

```bash
# 设置环境变量并运行测试
TUSHARE_INTEGRATION_TEST=1 TUSHARE_TOKEN="your_token" uv run pytest tests/test_tushare_integration_live.py -v
```

**注意:**
- 这些测试会实际连接到 TuShare API，可能受 API 调用限制
- 默认被跳过（需要显式启用环保变量）
- 测试内容包括：
  - ✅ 真实 K 线数据获取
  - ✅ 真实股票基本信息获取
  - ✅ 真实每日基础面数据获取
  - ✅ 完整的数据流测试（获取 → 规范化 → 转换）

## 配置

TuShare token 可以通过以下方式提供：

1. **直接传参:**
   ```python
   source = TuShareSource(token="your_token")
   ```

2. **环境变量** (未来扩展):
   ```python
   import os
   token = os.getenv("TUSHARE_TOKEN")
   source = TuShareSource(token=token)
   ```

## 示例脚本

查看 [examples/tushare_integration_example.py](../examples/tushare_integration_example.py) 获取完整的使用示例。

## 常见问题

**Q: 如何处理 TuShare API 限流?**
A: TuShare 有调用频率限制。建议：
- 增加请求间隔
- 使用本地缓存
- 考虑付费计划以获得更高限额

**Q: 支持其他数据源吗?**
A: 是的！按照 `SourceAdapter` 和 `EventNormalizer` 协议实现其他数据源。

**Q: 如何扩展到其他数据指标?**
A: 在 `TuShareSource` 中添加新的 `fetch_*` 方法，并在 `TuShareNormalizer` 中添加对应的 `_normalize_*` 处理方法。

## 相关文档

- [SourceAdapter 协议](../src/agent_trader/ingestion/sources/base.py)
- [EventNormalizer 协议](../src/agent_trader/ingestion/normalizers/base.py)
- [Ingestion 数据模型](../src/agent_trader/ingestion/models.py)
- [系统架构文档](../README.md)

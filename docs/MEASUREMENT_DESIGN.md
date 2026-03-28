# InfluxDB Measurement 设计文档

## 1. 概述

本文档定义 AgentTrader 项目在 InfluxDB 中用于存储 K 线数据的 measurement `candles` 的结构、字段、索引策略及使用规范。

---

## 2. Measurement: `candles`

### 2.1 基本信息

| 属性 | 值 |
|-----|----|
| **Measurement 名** | `candles` |
| **所属 Bucket** | `market-data`（default，可配置） |
| **时精度** | 秒级（`WritePrecision.S`） |
| **主时间戳** | `open_time`（K 线开始时间，UTC aware） |
| **行键（Row Key）** | `symbol`、`interval`、`open_time` 的组合 |

---

### 2.2 Tags（标签/索引字段）

**用途**：用于快速过滤和分组、支持较高维度的聚合查询。

| Tag 名 | 数据类型 | 来源 | 示例 | 说明 |
|--------|--------|------|------|------|
| `symbol` | string | `Candle.symbol` | `"000001.SZ"` | 股票代码，必须包含市场代码后缀 |
| `interval` | string | `Candle.interval.value` | `"5m"` / `"1d"` | K 线周期 |
| `asset_class` | string | `Candle.asset_class.value` | `"stock"` | 资产类别（股票、期货等） |
| `exchange` | string | `Candle.exchange.value` | `"sse"` / `"szse"` | 交易所代码 |
| `adjusted` | string | `str(Candle.adjusted).lower()` | `"true"` / `"false"` | 是否复权 |
| `source` | string | `Candle.source` | `"baostock"` / `"tushare"` | 数据源 |

**查询建议**：
- 经常联合 `symbol` + `interval` 查询，建议建立复合索引
- `source` 用于数据源对账和故障排查

---

### 2.3 Fields（数值字段）

#### 必填 Fields

| Field 名 | 数据类型 | 来源 | 说明 |
|---------|--------|------|------|
| `open` | float | `Candle.open_price` | 开盘价 |
| `high` | float | `Candle.high_price` | 最高价 |
| `low` | float | `Candle.low_price` | 最低价 |
| `close` | float | `Candle.close_price` | 收盘价 |
| `volume` | float | `Candle.volume` | 成交量 |

#### 可选 Fields

| Field 名 | 数据类型 | 条件 | 说明 |
|---------|--------|------|------|
| `turnover` | float | `Candle.turnover is not None` | 成交额（当源数据有时才写） |
| `trade_count` | int | `Candle.trade_count is not None` | 成交笔数（当源数据有时才写） |

---

### 2.4 时间戳设计

#### 存储策略

- **主时间戳**：使用 `Candle.open_time`（K 线开始时间）
- **格式**：UTC aware `datetime`，精度秒级
- **Flux 中时间列名**：`_time`

#### 关键约束

1. **`open_time` 是唯一的时间源**
   - 所有时间逻辑都基于 K 线开始时间
   - K 线结束时间（`close_time`）**不存储在 InfluxDB 中**

2. **`close_time` 计算方法**
   ```python
   from agent_trader.application.data_access.kline_utils import get_bar_close_time
   
   close_time = get_bar_close_time(open_time, interval)
   ```
   
   例如：
   - `interval=BarInterval.M5`，`open_time=2026-03-26 01:00:00Z`
   - 则 `close_time=2026-03-26 01:05:00Z`
   - 对应 A 股市场时间：开盘 `09:00:00 CST` 到 `09:05:00 CST`

3. **为何不存储 `close_time`**
   - `close_time` 可由 `open_time + interval_duration` 完全确定性计算
   - 避免冗余字段占用存储空间
   - 简化写入逻辑，减少数据不一致风险

---

## 3. 行键唯一性

每条 InfluxDB 行的唯一标识由以下组合确定：

```
(timestamp=open_time, symbol, interval, asset_class, exchange, adjusted, source)
```

实际上，最小唯一性由以下保证：
```
(timestamp=open_time, symbol, interval)
```

这意味着：
- 同一个 `symbol`、同一个 `interval`、同一个 `open_time` **最多只有一条记录**
- 同一时刻、同一标的、同一周期，来自不同源（`source`）的数据会覆盖（不区分）
  - **为避免覆盖**，建议在应用层确保统一使用一个源或明确的源优先级

---

## 4. 查询示例

### 4.1 查询最近 N 条 K 线

```python
from agent_trader.storage.influx import InfluxCandleRepository

repo = InfluxCandleRepository(connection_manager)

# 查询 000001.SZ 5分钟线的过去 7 天数据
from agent_trader.core.time import utc_now
from datetime import timedelta

end_time = utc_now()
start_time = end_time - timedelta(days=7)

rows = await repo.query_history(
    symbol="000001.SZ",
    interval="5m",
    start_time=start_time,
    end_time=end_time,
    limit=10000,
)

# 返回格式：list[dict[str, Any]]
# [
#   {
#     "symbol": "000001.SZ",
#     "interval": "5m",
#     "bar_time": datetime(...),  # open_time
#     "open": 17.5,
#     "high": 17.8,
#     "low": 17.45,
#     "close": 17.65,
#     "volume": 12345678.0,
#   },
#   ...
# ]

# 如需 close_time，应用层计算：
from agent_trader.application.data_access.kline_utils import get_bar_close_time
from agent_trader.domain.models import BarInterval

for row in rows:
    open_time = row["bar_time"]
    close_time = get_bar_close_time(open_time, BarInterval.M5)
    print(f"开始: {open_time}, 结束: {close_time}")
```

### 4.2 Flux 查询语言（原生）

```flux
from(bucket: "market-data")
  |> range(start: 2026-03-19T00:00:00Z, stop: 2026-03-26T23:59:59Z)
  |> filter(fn: (r) => 
      r._measurement == "candles" 
      and r.symbol == "000001.SZ"
      and r.interval == "5m"
    )
  |> pivot(rowKey: ["_time"], columnKey: ["_field"], valueColumn: "_value")
  |> sort(columns: ["_time"], desc: false)
  |> limit(n: 100)
```

---

## 5. 写入流程

### 5.1 流程图

```
KlineSyncService.sync_realtime_m5_positions()
    ↓ (通过 DataAccessGateway)
BaoStockSource/TuShareSource.fetch_klines_unified()
    ↓ (返回 KlineFetchResult 其中 payload 是 KlineRecord list)
KlineSyncService._sync_single_symbol()
    ↓ (转换为 Candle domain object)
InfluxCandleRepository.write_batch(candles)
    ↓
candle_repository._to_point(candle)
    → Point(measurement="candles")
      .tag("symbol", candle.symbol)
      .tag("interval", candle.interval.value)
      .tag("asset_class", candle.asset_class.value)
      .tag("exchange", candle.exchange.value)
      .tag("adjusted", str(candle.adjusted).lower())
      .tag("source", candle.source)
      .field("open", candle.open_price)
      .field("high", candle.high_price)
      .field("low", candle.low_price)
      .field("close", candle.close_price)
      .field("volume", candle.volume)
      [.field("turnover", ...) if candle.turnover is not None]
      [.field("trade_count", ...) if candle.trade_count is not None]
      .time(ensure_utc(candle.open_time), WritePrecision.S)
    ↓
InfluxDB write_api.write()
    ↓
InfluxDB cluster
```

### 5.2 关键点

1. **时间归一化**：所有 `open_time` 在写入前必须通过 `ensure_utc()` 转为 UTC aware
2. **批量写入**：使用 `write_batch()` 而非逐条 `write()`，提升性能
3. **错误处理**：批量写入失败会在 KlineSyncService 的异常分支记录，确保 failed 计数和堆栈日志完整

---

## 6. 数据源对账

由于 `source` tag 记录了数据最初来自哪个源，可以快速对账不同源的数据差异。

### 6.1 对账查询

```flux
from(bucket: "market-data")
  |> range(start: 2026-03-25T00:00:00Z, stop: 2026-03-26T23:59:59Z)
  |> filter(fn: (r) => 
      r._measurement == "candles" 
      and r.symbol == "000001.SZ"
      and r.interval == "1d"
    )
  |> pivot(rowKey: ["_time"], columnKey: ["_field"], valueColumn: "_value")
  |> group(columns: ["source"])
  |> sort(columns: ["_time"], desc: false)
```

结果会按 `source` 分组，直观对比 BaoStock 和 TuShare 的数据差异。

---

## 7. 性能优化建议

### 7.1 索引优化

```sql
-- 推荐的复合索引策略（在 InfluxDB 配置或初始化时指定）
symbol + interval + _time
```

### 7.2 数据保留策略

在 bucket 级别配置数据保留期限（Retention Policy），例如：
- 分钟线：保留 3 个月
- 日线及以上：保留 5 年

### 7.3 查询最佳实践

1. **总是指定时间范围**：avoid full scan
2. **优先使用 symbol + interval 条件**：leverage tag filters
3. **使用 pivot 前进行 filter**：减少行数
4. **limit 合理设置**：10000+ 查询可能需要分页

---

## 8. 变更历史

| 日期 | 变更内容 |
|------|---------|
| 2026-03-26 | 初版：移除 `close_ts` 冗余字段，仅保留 `open_time` 作为主时间索引。`close_time` 由应用层通过 `get_bar_close_time()` 计算。 |

---

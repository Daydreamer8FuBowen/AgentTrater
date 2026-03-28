# 5分钟K线实时更新设计文档

## 概述

5分钟（M5）K线的实时更新采用**覆盖更新机制**，确保每次同步获取当日全部数据，通过InfluxDB的自动覆盖来保证数据一致性，避免冗余的删除操作。

## 关键设计原则

### 1. 时间窗口范围

- **起点**：当日开盘时间（09:30 UTC+8，转换为UTC）
- **终点**：当前时间对齐到最近的5分钟边界（向下取整）
- **更新频率**：由 `KlineSyncConfig.realtime_m5_interval_seconds` 决定（通常为300秒=5分钟）

实现函数：`_realtime_m5_window(now, market)` → `tuple[datetime, datetime]`

```python
def _realtime_m5_window(now: datetime, market: str | ExchangeKind) -> tuple[datetime, datetime]:
    """获取当日全部 K 线数据的时间窗口"""
    end_time = _align_time(now, BarInterval.M5, market)  # 向下对齐到5m边界
    current_day = market_date(now, market)
    session_start = _A_SHARE_SESSIONS[0][0]  # 09:30
    start_time = market_time_to_utc(
        datetime.combine(current_day, session_start), 
        market
    )
    return start_time, end_time
```

### 2. 数据获取流程

```
每次实时同步任务触发
    ↓
获取当日全部K线数据（09:30到现在）
    ├─ 首次09:35：fetch(09:30-09:35) → 1条bar
    ├─ 再次09:40：fetch(09:30-09:40) → 2条bar
    ├─ 中午13:45：fetch(09:30-15:00) → 46条bar（整个交易日）
    └─ 下午15:05：fetch(09:30-15:00) → 48条bar（午盘以后可能继续）
    ↓
转换为Candle对象 + 零填充（如果无数据）
    ↓
覆盖写入InfluxDB（write_batch）
    └─ 相同时间戳+tags的数据自动覆盖，无需删除
```

### 3. 覆盖写入机制

#### InfluxDB自动覆盖

写入时，InfluxDB根据以下标识来判断是否覆盖：

- **时间戳**（timestamp）：使用 `candle.open_time` 作为唯一的时间索引
- **Tags**（索引标签）：6个维度
  - `symbol`：股票代码（如 `000001.SZ`）
  - `interval`：K线周期（如 `5m`）
  - `asset_class`：资产类别（如 `stock`）
  - `exchange`：交易所（如 `sse` 或 `szse`）
  - `adjusted`：是否复权（`true` 或 `false`）
  - `source`：数据源（如 `tushare` 或 `baostock`）

**覆盖规则**：当新写入的数据拥有**完全相同**的 timestamp + tags 组合时，所有字段值会被新数据覆盖。

#### 写入代码示例

```python
# src/agent_trader/storage/influx/candle_repository.py

async def write_batch(self, candles: Sequence[Candle]) -> None:
    """批量写入 K 线数据，采用自动覆盖机制。
    
    相同 timestamp + tags 的数据会自动被新值覆盖，
    无需先删除history再写入新数据。
    """
    points = [self._to_point(candle) for candle in candles]
    if not points:
        return
    self._write_points(points)  # 直接写入，InfluxDB自动覆盖

def _to_point(self, candle: Candle) -> Point:
    """将Candle转换为InfluxDB Point对象"""
    point = (
        Point(self.measurement)
        # 6个tag标签，组成唯一键
        .tag("symbol", candle.symbol)
        .tag("interval", candle.interval.value)
        .tag("asset_class", candle.asset_class.value)
        .tag("exchange", candle.exchange.value)
        .tag("adjusted", str(candle.adjusted).lower())
        .tag("source", candle.source)
        # 字段值
        .field("open", candle.open_price)
        .field("high", candle.high_price)
        .field("low", candle.low_price)
        .field("close", candle.close_price)
        .field("volume", candle.volume)
        # 时间戳：使用K线开始时间作为唯一索引
        .time(ensure_utc(candle.open_time), WritePrecision.S)
    )
    # 可选字段
    if candle.turnover is not None:
        point = point.field("turnover", candle.turnover)
    if candle.trade_count is not None:
        point = point.field("trade_count", candle.trade_count)
    return point
```

### 4. 实际使用流程示例

#### 场景：工作日上午9:30-15:00的实时更新

| 时间 | 触发事件 | 数据获取窗口 | 获取数据 | 写入行为 |
|------|--------|----------|---------|--------|
| 09:35 | 首次任务 | 09:30-09:35 | 1条bar (09:30) | 新增写入 |
| 09:40 | 第二次任务 | 09:30-09:40 | 2条bar | 第一条覆盖，第二条新增 |
| 09:45 | 第三次任务 | 09:30-09:45 | 3条bar | 前两条覆盖，第三条新增 |
| ... | ... | ... | ... | ... |
| 13:00 | 下午开盘 | 09:30-13:00 | 24条bar | 前面的覆盖，新增下午数据 |
| 15:00 | 交易日结束 | 09:30-15:00 | 48条bar | 全部完整数据一次性覆盖 |

**关键点**：
- ✅ 不删除任何旧数据
- ✅ 每次都覆盖写入全量窗口数据
- ✅ InfluxDB自动处理覆盖逻辑
- ✅ 确保最终状态总是与最新获取数据一致

## 跟踪覆盖行为的日志

在应用日志中，可以看到以下消息来确认覆盖写入：

```
INFO  K线同步开始 market=sse interval=5m symbols=100 range=[2026-03-26T01:30:00+00:00,2026-03-26T07:00:00+00:00]

INFO  获取K线 symbol=000001.SZ interval=5m bars=48 source=tushare range=[2026-03-26T01:30:00+00:00,2026-03-26T07:00:00+00:00]

DEBUG 准备覆盖写入Influx symbol=000001.SZ bars=48 (采用自动覆盖机制，相同timestamp+tags会自动覆盖)

DEBUG 覆盖写入Influx完成 symbol=000001.SZ bars=48

INFO  K线同步完成 {'market': 'sse', 'interval': '5m', 'synced': 100, 'skipped': 0, 'failed': 0, 'completion_ratio': 1.0}
```

## 优势分析

### vs. 先删除后覆盖的方案

| 指标 | 当前覆盖方案 | 先删除后覆盖 |
|------|-----------|----------|
| 数据一致性 | ✅ 高（原子性覆盖） | ⚠️ 低（删除-写入间可能失败） |
| 性能 | ✅ 高（一次写入） | ⚠️ 低（删除+写入两次操作） |
| 网络开销 | ✅ 低 | ⚠️ 高（需要额外删除请求） |
| 数据丢失风险 | ✅ 无 | ⚠️ 有（删除后写入前失败） |
| 代码复杂度 | ✅ 低 | ⚠️ 高（需要事务控制） |

## 告诫和注意事项

### ⚠️ 注意事项

1. **时间精度**：InfluxDB中使用秒级精度存储（`WritePrecision.S`），确保应用层的时间戳也是秒级对齐。

2. **Tags的唯一性**：Tag组合必须能唯一标识一个candle，否则可能发生意外的覆盖。当前设计中，相同symbol+interval+asset_class+exchange+adjusted+source的数据才会相互覆盖。

3. **数据源变更**：如果同一个symbol从不同数据源获取（例如从TuShare切换到BaoStock），由于`source` tag不同，系统会将其视为两条不同的数据记录，不会发生覆盖。这是安全的行为。

4. **零填充数据**：当市场休盘（周末、节假日）时，系统会生成零值K线（所有价格=0，体积=0）并标记为 `synthetic_zero_fill`。这些数据也会参与覆盖写入。

5. **时区转换**：确保所有时间戳都经过 `ensure_utc()` 转换，否则会导致时间匹配失败。

### ✅ 最佳实践

1. **监控覆盖比率**：在实时更新日志中，观察每次更新前后的bar数量变化，确认覆盖是否发生。

2. **验证数据完整性**：定期查询最新K线并与源API对比，确认没有数据丢失。

3. **处理异常情况**：
   - 网络中断：重试机制会自动处理
   - 数据源延迟：覆盖机制会自动补齐新数据
   - InfluxDB故障：写入异常会被记录，下次同步时会重新尝试

## 配置参数

在 `src/agent_trader/core/config.py` 中：

```python
@dataclass
class KlineSyncConfig:
    """K线同步配置"""
    enabled_markets: list[str] = field(
        default_factory=lambda: ["sse", "szse"]
    )
    realtime_m5_interval_seconds: int = 300  # 5分钟同步一次
    m5_window_days: int = 1  # 回补窗口（天数）
    m5_backfill_chunk_days: int = 5  # 分块粒度（天数）
    d1_window_days: int = 30  # D1回补窗口（天数）
    d1_sync_hour: int = 16  # D1同步时间（16:00=下午4点）
```

## 关联代码

- **时间窗口定义**：`src/agent_trader/application/jobs/kline_sync.py` -> `_realtime_m5_window()`
- **数据获取**：`src/agent_trader/application/jobs/kline_sync.py` -> `_sync_single_symbol()`
- **覆盖写入**：`src/agent_trader/storage/influx/candle_repository.py` -> `write_batch()`
- **任务调度**：`src/agent_trader/worker/jobs.py` -> `register_kline_sync_jobs()`
- **时间处理**：`src/agent_trader/core/time.py` -> `ensure_utc()`, `market_time_to_utc()`, `to_market_time()`

